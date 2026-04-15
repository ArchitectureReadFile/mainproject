"""
domains/rag/group_document_chunk_builder.py

GroupDocument(document_id, group_id, file_name, body_text, table_blocks)를
body chunk / table chunk 리스트로 변환한다.

chunk payload 계약:
    chunk_id      str    "gdoc:{document_id}:chunk:{order_index}"
    document_id   int    그룹핑 기준
    group_id      int    권한/검색 범위 필터 기준
    file_name     str    citation / 카드 표시용
    source_type   str    "pdf"
    chunk_type    str    "body" | "table"
    section_title str | None
    order_index   int
    text          str    실제 임베딩/BM25 대상
"""

import re
from dataclasses import dataclass
from typing import TypedDict

BODY_CHUNK_MAX = 1000
BODY_CHUNK_OVERLAP = 120
TABLE_CHUNK_MAX = 1200

_BLANK_LINE_RE = re.compile(r"\n{2,}")


@dataclass
class GroupDocument:
    document_id: int
    group_id: int
    file_name: str
    body_text: str
    table_blocks: list[str]
    source_type: str = "pdf"


class GroupDocumentChunk(TypedDict):
    chunk_id: str
    document_id: int
    group_id: int
    file_name: str
    source_type: str
    chunk_type: str
    section_title: str | None
    order_index: int
    text: str


def _split_body(text: str) -> list[tuple[str, str | None]]:
    """
    body_text를 문단 경계 우선, 초과 시 길이 기반으로 분할한다.
    반환: [(chunk_text, section_title), ...]
    """
    paragraphs = [p.strip() for p in _BLANK_LINE_RE.split(text) if p.strip()]

    segments: list[tuple[str, str | None]] = []
    buffer = ""

    for para in paragraphs:
        candidate = (buffer + "\n\n" + para).strip() if buffer else para
        if len(candidate) <= BODY_CHUNK_MAX:
            buffer = candidate
        else:
            if buffer:
                segments.append((buffer, None))
            # 단일 문단이 MAX 초과 → 길이 기반 분할
            if len(para) > BODY_CHUNK_MAX:
                segments.extend(_split_by_length(para))
                buffer = ""
            else:
                buffer = para

    if buffer:
        segments.append((buffer, None))

    return segments


def _split_by_length(text: str) -> list[tuple[str, str | None]]:
    """MAX 초과 텍스트를 overlap 포함해 분할한다."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + BODY_CHUNK_MAX
        chunks.append((text[start:end], None))
        start = end - BODY_CHUNK_OVERLAP
    return chunks


def _split_table(table_text: str) -> list[tuple[str, str | None]]:
    """
    표 1개 = 기본 1 chunk. TABLE_CHUNK_MAX 초과 시 길이 기반 추가 분할.
    """
    if len(table_text) <= TABLE_CHUNK_MAX:
        return [(table_text, "table")]
    chunks = []
    start = 0
    while start < len(table_text):
        chunks.append((table_text[start : start + TABLE_CHUNK_MAX], "table"))
        start += TABLE_CHUNK_MAX
    return chunks


def build_chunks_from_group_document(doc: GroupDocument) -> list[GroupDocumentChunk]:
    """
    GroupDocument → GroupDocumentChunk 리스트.

    처리 순서:
    1. body_text → body chunk 분할
    2. table_blocks → table chunk 분할
    3. order_index 부여
    """
    raw_segments: list[
        tuple[str, str | None, str]
    ] = []  # (text, section_title, chunk_type)

    for text, title in _split_body(doc.body_text):
        raw_segments.append((text, title, "body"))

    for table_text in doc.table_blocks:
        for text, title in _split_table(table_text):
            raw_segments.append((text, title, "table"))

    result: list[GroupDocumentChunk] = []
    for order_index, (text, section_title, chunk_type) in enumerate(raw_segments):
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
                order_index=order_index,
                text=text,
            )
        )

    return result
