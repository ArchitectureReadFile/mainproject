"""
domains/rag/group_document_chunk_builder.py

GroupDocument → body chunk / table chunk 리스트 변환.

chunking 전략 선택 계층:
    override(env) > auto

    auto 우선순위:
        1. section  — sections 있을 때
        2. page     — sections 없고 실제 page 정보가 있을 때 (estimated=False)
        3. text     — 위 조건 모두 불충족 시 fallback

    전략별 동작:
        section  ODL 구조(heading/paragraph/table) 기반 섹션 단위 청킹
        page     DocumentPage 단위 분할 (page_start/page_end 채움)
        text     body_text 문단 경계 우선, 초과 시 길이 기반 분할

    page 전략 downgrade 규칙:
        - pages가 비어 있거나
        - 모든 page에 estimated=True 가 설정되어 있으면
          실질적 page 정보 없음으로 판단 → text fallback으로 downgrade
        "page 전략이 있는 척"하지 않는다.

env 설정:
    DOCUMENT_CHUNK_STRATEGY   auto | section | page | text  (기본 auto)
    DOCUMENT_CHUNK_TARGET_CHARS   소프트 목표 글자 수         (기본 1000)
    DOCUMENT_CHUNK_MAX_CHARS      절대 상한 글자 수           (기본 1500)

chunk payload 계약:
    chunk_id      str    "gdoc:{document_id}:chunk:{order_index}"
    document_id   int    그룹핑 기준
    group_id      int    권한/검색 범위 필터 기준
    file_name     str    citation / 카드 표시용
    source_type   str    "pdf"
    chunk_type    str    "body" | "table"
    section_title str | None
    page_start    int | None
    page_end      int | None
    order_index   int
    text          str    실제 임베딩/BM25 대상
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Literal, TypedDict

from domains.document.document_schema import DocumentPage, DocumentSection

# ── 설정 (env override 허용) ──────────────────────────────────────────────────

ChunkStrategy = Literal["auto", "section", "page", "text"]

_ENV_STRATEGY = os.getenv("DOCUMENT_CHUNK_STRATEGY", "auto").lower()
CHUNK_STRATEGY: ChunkStrategy = (
    _ENV_STRATEGY if _ENV_STRATEGY in ("auto", "section", "page", "text") else "auto"
)

BODY_CHUNK_TARGET: int = int(os.getenv("DOCUMENT_CHUNK_TARGET_CHARS", "1000"))
BODY_CHUNK_MAX: int = int(os.getenv("DOCUMENT_CHUNK_MAX_CHARS", "1500"))
BODY_CHUNK_OVERLAP = 120
TABLE_CHUNK_MAX = 1200

_BLANK_LINE_RE = re.compile(r"\n{2,}")

# ── 타입 정의 ─────────────────────────────────────────────────────────────────

# 내부 segment 타입: (text, section_title, chunk_type, page_start, page_end)
_Segment = tuple[str, str | None, str, int | None, int | None]


@dataclass
class GroupDocument:
    document_id: int
    group_id: int
    file_name: str
    body_text: str
    table_blocks: list[str]
    source_type: str = "pdf"
    sections: list[DocumentSection] = field(default_factory=list)
    pages: list[DocumentPage] = field(default_factory=list)


class GroupDocumentChunk(TypedDict):
    chunk_id: str
    document_id: int
    group_id: int
    file_name: str
    source_type: str
    chunk_type: str
    section_title: str | None
    page_start: int | None
    page_end: int | None
    order_index: int
    text: str


# ── 전략 선택 ─────────────────────────────────────────────────────────────────


def _resolve_strategy(
    doc: GroupDocument, override: ChunkStrategy | None
) -> ChunkStrategy:
    """
    실제로 사용할 전략을 결정한다.

    우선순위: 호출측 override > env override > auto
    auto 내부 우선순위: section > page > text
    """
    requested = override or CHUNK_STRATEGY

    if requested == "section":
        return "section" if doc.sections else "text"

    if requested == "page":
        return "page" if _has_real_pages(doc.pages) else "text"

    if requested == "text":
        return "text"

    # auto
    if doc.sections:
        return "section"
    if _has_real_pages(doc.pages):
        return "page"
    return "text"


def _has_real_pages(pages: list[DocumentPage]) -> bool:
    """
    실질적 page 정보가 있는지 판단한다.

    pages가 비어 있거나 모든 page의 metadata에 estimated=True이면
    page 1 단순화 상태로 간주해 False를 반환한다.
    page 전략이 있는 척하지 않기 위한 downgrade 판단 기준이다.
    """
    if not pages:
        return False
    return any(not page.metadata.get("estimated", False) for page in pages)


# ── section-aware chunking ────────────────────────────────────────────────────


def _chunks_from_sections(
    sections: list[DocumentSection],
    table_blocks_text: list[str],
) -> list[_Segment]:
    """
    섹션 구조 기반 chunking.

    table chunk의 section_title:
        _split_table()은 text만 반환한다 (title 반환 제거).
        section_title은 항상 현재 섹션의 heading(title)을 직접 사용한다.
        "table" literal이 section_title로 들어가는 버그를 이 구조로 차단한다.
    """
    table_id_to_text: dict[str, str] = {
        f"table:{i}": text for i, text in enumerate(table_blocks_text)
    }

    result: list[_Segment] = []

    for section in sections:
        title = section.heading
        p_start = section.page_start
        p_end = section.page_end

        # ── 본문 병합 ─────────────────────────────────────────────────────────
        buffer = ""
        for para in section.paragraphs:
            candidate = (buffer + "\n\n" + para).strip() if buffer else para
            if len(candidate) <= BODY_CHUNK_TARGET:
                buffer = candidate
            else:
                if buffer:
                    result.append((buffer, title, "body", p_start, p_end))
                if len(para) > BODY_CHUNK_MAX:
                    for seg in _split_by_length(para):
                        result.append((seg, title, "body", p_start, p_end))
                    buffer = ""
                else:
                    buffer = para
        if buffer:
            result.append((buffer, title, "body", p_start, p_end))

        # ── 표 chunk: section_title은 항상 현재 섹션 heading ─────────────────
        for tid in section.table_ids:
            table_text = table_id_to_text.get(tid)
            if not table_text:
                continue
            for seg in _split_table(table_text):
                result.append((seg, title, "table", p_start, p_end))

    return result


# ── page-aware chunking ───────────────────────────────────────────────────────


def _chunks_from_pages(
    pages: list[DocumentPage],
    table_blocks_text: list[str],
) -> list[_Segment]:
    """
    DocumentPage 단위 chunking.

    각 페이지 텍스트를 BODY_CHUNK_TARGET 기준으로 분할한다.
    page의 table_ids에 해당하는 표는 별도 chunk로 생성한다.
    page_start / page_end 에 해당 페이지 번호를 채운다.

    이 함수는 _has_real_pages()가 True일 때만 호출된다.
    """
    table_id_to_text: dict[str, str] = {
        f"table:{i}": text for i, text in enumerate(table_blocks_text)
    }

    result: list[_Segment] = []

    for page in pages:
        pn = page.page_number

        # 페이지 본문 분할
        if page.text.strip():
            for para in [
                p.strip() for p in _BLANK_LINE_RE.split(page.text) if p.strip()
            ]:
                if len(para) > BODY_CHUNK_MAX:
                    for seg in _split_by_length(para):
                        result.append((seg, None, "body", pn, pn))
                else:
                    result.append((para, None, "body", pn, pn))

        # 페이지 소속 표
        for tid in page.table_ids:
            table_text = table_id_to_text.get(tid)
            if not table_text:
                continue
            for seg in _split_table(table_text):
                result.append((seg, None, "table", pn, pn))

    return result


# ── text fallback chunking ────────────────────────────────────────────────────


def _chunks_from_text(
    body_text: str,
    table_blocks_text: list[str],
) -> list[_Segment]:
    """문단 경계 우선, 초과 시 길이 기반 분할. table은 별도 chunk."""
    result: list[_Segment] = []

    paragraphs = [p.strip() for p in _BLANK_LINE_RE.split(body_text) if p.strip()]
    buffer = ""
    for para in paragraphs:
        candidate = (buffer + "\n\n" + para).strip() if buffer else para
        if len(candidate) <= BODY_CHUNK_TARGET:
            buffer = candidate
        else:
            if buffer:
                result.append((buffer, None, "body", None, None))
            if len(para) > BODY_CHUNK_MAX:
                for seg in _split_by_length(para):
                    result.append((seg, None, "body", None, None))
                buffer = ""
            else:
                buffer = para
    if buffer:
        result.append((buffer, None, "body", None, None))

    for table_text in table_blocks_text:
        for seg in _split_table(table_text):
            result.append((seg, None, "table", None, None))

    return result


# ── 공통 분할 헬퍼 ────────────────────────────────────────────────────────────


def _split_by_length(text: str) -> list[str]:
    """MAX 초과 텍스트를 overlap 포함해 분할한다. text만 반환."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + BODY_CHUNK_MAX])
        start += BODY_CHUNK_MAX - BODY_CHUNK_OVERLAP
    return chunks


def _split_table(table_text: str) -> list[str]:
    """
    표 text만 반환한다 (title 반환 없음).

    section_title은 호출측(_chunks_from_sections)에서 직접 섹션 heading을 사용한다.
    이 함수가 "table" literal을 두 번째 값으로 반환하던 구조를 제거해
    section_title에 "table"이 들어가는 버그를 차단한다.

    TABLE_CHUNK_MAX 이하: 1개 그대로 반환.
    초과: 행 단위 분할 시도 → 불가능하면 길이 기반 분할.
    """
    if len(table_text) <= TABLE_CHUNK_MAX:
        return [table_text]

    lines = table_text.split("\n")
    header = lines[0] if lines else ""
    rows = lines[1:]

    if not rows:
        return [
            table_text[i : i + TABLE_CHUNK_MAX]
            for i in range(0, len(table_text), TABLE_CHUNK_MAX)
        ]

    chunks: list[str] = []
    buffer_rows: list[str] = []

    for row in rows:
        candidate = "\n".join(([header] if header else []) + buffer_rows + [row])
        if len(candidate) <= TABLE_CHUNK_MAX:
            buffer_rows.append(row)
        else:
            if buffer_rows:
                chunks.append("\n".join(([header] if header else []) + buffer_rows))
            buffer_rows = [row]

    if buffer_rows:
        chunks.append("\n".join(([header] if header else []) + buffer_rows))

    return chunks or [table_text]


# ── 메인 빌더 ─────────────────────────────────────────────────────────────────


def build_chunks_from_group_document(
    doc: GroupDocument,
    *,
    strategy_override: ChunkStrategy | None = None,
) -> list[GroupDocumentChunk]:
    """
    GroupDocument → GroupDocumentChunk 리스트.

    strategy_override: 테스트/재인덱싱 스크립트에서 전략을 강제할 때 사용.
                       None이면 env 설정(DOCUMENT_CHUNK_STRATEGY)을 따른다.
    """
    strategy = _resolve_strategy(doc, strategy_override)

    if strategy == "section":
        raw_segments = _chunks_from_sections(doc.sections, doc.table_blocks)
    elif strategy == "page":
        raw_segments = _chunks_from_pages(doc.pages, doc.table_blocks)
    else:  # text
        raw_segments = _chunks_from_text(doc.body_text, doc.table_blocks)

    result: list[GroupDocumentChunk] = []
    for order_index, (
        text,
        section_title,
        chunk_type,
        page_start,
        page_end,
    ) in enumerate(raw_segments):
        if not text.strip():
            continue
        result.append(
            GroupDocumentChunk(
                chunk_id=f"gdoc:{doc.document_id}:chunk:{order_index}",
                document_id=doc.document_id,
                group_id=doc.group_id,
                file_name=doc.file_name,
                source_type=doc.source_type,
                chunk_type=chunk_type,
                section_title=section_title,
                page_start=page_start,
                page_end=page_end,
                order_index=order_index,
                text=text,
            )
        )

    return result
