"""
domains/document/normalize_service.py

ExtractedDocument → DocumentSchema 정규화 계층.

책임:
    - extractor가 넘긴 source_type 사용 (현재 기본은 odl)
    - raw_* 필드 세팅
    - body_text 생성 (markdown 우선 → json fallback)
    - table_blocks 생성 (ODL json에서만 추출)
    - sections 생성 (ODL raw_json 기반 구조 파싱. 실패 시 빈 리스트)
    - pages 생성 (v1: 전체 문서를 page 1 하나로 단순화)
    - metadata 기본값 생성

비책임 (각 소비처 서비스가 담당):
    - [본문]/[표] prompt 문자열 조립 (→ DocumentSummaryPayloadService)
    - truncate / 길이 정책
    - chunk 분할 (→ DocumentChunkService)
    - 분류 (→ DocumentClassificationService)

ODL JSON 구조 관찰:
    ODL이 반환하는 JSON의 node type 예시:
        "page"      - 페이지 경계. page_no 속성 포함
        "heading"   - 제목/소제목. content 텍스트 포함
        "paragraph" - 일반 문단. content 텍스트 포함
        "table"     - 표. rows/cells 구조
        "list"      - 목록. kids에 list-item 포함
        "list-item" - 목록 항목
    kids 배열로 계층 구조를 가질 수 있다.
    page_no가 없는 경우도 있으므로 현재 페이지 추적은 순서 기반으로 fallback.
"""

from __future__ import annotations

import logging

from domains.document.document_schema import (
    DocumentPage,
    DocumentSchema,
    DocumentSection,
    DocumentTableBlock,
)
from domains.document.extract_service import ExtractedDocument

logger = logging.getLogger(__name__)

_NORMALIZATION_VERSION = "v2"

# ODL JSON에서 heading으로 취급하는 type 집합
_HEADING_TYPES = {"heading", "title", "subtitle", "section-header", "chapter"}
# body 텍스트로 취급하는 type 집합
_BODY_TYPES = {"paragraph", "text", "list", "list-item", "caption", "footnote"}
# 무시하는 type 집합
_SKIP_TYPES = {"image", "figure", "picture"}


class DocumentNormalizeService:
    @property
    def normalization_version(self) -> str:
        return _NORMALIZATION_VERSION

    def normalize(self, extracted: ExtractedDocument) -> DocumentSchema:
        source_type = extracted.source_type

        raw_markdown, raw_json = self._build_raw_fields(extracted)
        body_text = self._build_body_text(extracted)
        table_blocks = self._build_table_blocks(extracted)
        sections = self._build_sections(extracted, table_blocks)
        pages = self._build_pages(extracted, body_text, table_blocks)
        metadata = self._build_metadata(
            source_type, body_text, table_blocks, pages, sections
        )

        return DocumentSchema(
            source_type=source_type,
            raw_markdown=raw_markdown,
            raw_json=raw_json,
            body_text=body_text,
            table_blocks=table_blocks,
            pages=pages,
            sections=sections,
            metadata=metadata,
        )

    # ── raw 필드 ──────────────────────────────────────────────────────────────

    def _build_raw_fields(
        self, extracted: ExtractedDocument
    ) -> tuple[str | None, dict | list | None]:
        return extracted.markdown or None, extracted.json_data

    # ── body_text ─────────────────────────────────────────────────────────────

    def _build_body_text(self, extracted: ExtractedDocument) -> str:
        body = (extracted.markdown or "").strip()
        if not body:
            body = _extract_body_from_json(extracted.json_data)
        return body

    # ── table_blocks ──────────────────────────────────────────────────────────

    def _build_table_blocks(
        self, extracted: ExtractedDocument
    ) -> list[DocumentTableBlock]:
        if not extracted.json_data:
            return []
        return _extract_table_blocks(extracted.json_data)

    # ── sections ─────────────────────────────────────────────────────────────

    def _build_sections(
        self,
        extracted: ExtractedDocument,
        table_blocks: list[DocumentTableBlock],
    ) -> list[DocumentSection]:
        """
        ODL raw_json 기반으로 구조화된 섹션 목록을 생성한다.

        파싱 실패 또는 raw_json 없음 → 빈 리스트 반환.
        chunker가 sections=[] 이면 body_text fallback으로 내려간다.
        """
        if not extracted.json_data:
            return []
        try:
            return _extract_sections(extracted.json_data, table_blocks)
        except Exception as exc:
            logger.warning("[normalize] sections 파싱 실패, fallback: %s", exc)
            return []

    # ── pages ─────────────────────────────────────────────────────────────────

    def _build_pages(
        self,
        extracted: ExtractedDocument,
        body_text: str,
        table_blocks: list[DocumentTableBlock],
    ) -> list[DocumentPage]:
        """
        ODL raw_json에 실제 page 정보가 있으면 page-aware 복원을 수행한다.
        page 경계가 없거나 파싱이 불가능하면 기존 estimated page 1 fallback을 유지한다.
        """
        if not body_text and not table_blocks:
            return []

        if extracted.json_data:
            try:
                real_pages = _extract_pages(extracted.json_data, table_blocks)
                if real_pages:
                    return real_pages
            except Exception as exc:
                logger.warning("[normalize] pages 파싱 실패, fallback: %s", exc)

        all_table_ids = [tb.table_id for tb in table_blocks]
        return [
            DocumentPage(
                page_number=1,
                text=body_text,
                table_ids=all_table_ids,
                metadata={"estimated": True},
            )
        ]

    # ── metadata ──────────────────────────────────────────────────────────────

    def _build_metadata(
        self,
        source_type: str,
        body_text: str,
        table_blocks: list[DocumentTableBlock],
        pages: list[DocumentPage],
        sections: list[DocumentSection],
    ) -> dict:
        return {
            "schema_version": "v1",
            "extraction_source": source_type,
            "has_tables": len(table_blocks) > 0,
            "page_count": len(pages),
            "body_char_count": len(body_text),
            "table_count": len(table_blocks),
            "section_count": len(sections),
            "normalization_version": _NORMALIZATION_VERSION,
        }


# ── 섹션 파싱 ─────────────────────────────────────────────────────────────────


def _extract_sections(
    json_data: dict | list,
    table_blocks: list[DocumentTableBlock],
) -> list[DocumentSection]:
    """
    ODL JSON을 순회하며 heading 경계 기준으로 섹션을 구성한다.

    알고리즘:
    1. JSON 트리를 DFS로 순회하며 FlatNode 스트림 생성
       (type, content/rows, page_no)
    2. heading을 만날 때마다 새 섹션 시작
    3. table은 현재 섹션에 table_id 추가
    4. paragraph/text 등은 현재 섹션의 paragraphs에 추가
    5. 마지막 버퍼 flush

    table_blocks는 table_id 매핑을 위해 순서대로 전달된다.
    """
    # table_id 역방향 매핑을 위해 ODL JSON에서 table 등장 순서대로 table_blocks와 대응
    table_iter = iter(table_blocks)

    flat_nodes = _flatten_json(json_data)

    sections: list[DocumentSection] = []
    current_heading: str | None = None
    current_paragraphs: list[str] = []
    current_table_ids: list[str] = []
    current_page_start: int | None = None
    current_page_end: int | None = None
    current_page: int | None = None

    def flush():
        nonlocal current_heading, current_paragraphs, current_table_ids
        nonlocal current_page_start, current_page_end
        if not current_paragraphs and not current_table_ids:
            return
        sections.append(
            DocumentSection(
                heading=current_heading,
                paragraphs=list(current_paragraphs),
                table_ids=list(current_table_ids),
                page_start=current_page_start,
                page_end=current_page_end,
            )
        )
        current_heading = None
        current_paragraphs = []
        current_table_ids = []
        current_page_start = current_page
        current_page_end = current_page

    for node_type, content, page_no in flat_nodes:
        # 페이지 추적
        if page_no is not None:
            current_page = page_no
            if current_page_start is None:
                current_page_start = page_no
            current_page_end = page_no

        if node_type in _HEADING_TYPES:
            flush()
            current_heading = content
            current_page_start = current_page
            current_page_end = current_page

        elif node_type == "table":
            tb = next(table_iter, None)
            if tb is not None:
                current_table_ids.append(tb.table_id)
                if current_page is not None:
                    current_page_end = current_page

        elif node_type in _BODY_TYPES:
            if content and content.strip():
                current_paragraphs.append(content.strip())
                if current_page is not None:
                    current_page_end = current_page

        # _SKIP_TYPES 및 기타는 무시

    flush()
    return sections


def _flatten_json(
    node: dict | list,
    current_page: int | None = None,
) -> list[tuple[str, str | None, int | None]]:
    """
    JSON 트리를 DFS로 순회하여 (type, content, page_no) 플랫 리스트로 변환.

    page_no는 "page" 타입 노드를 만날 때 갱신된다.
    page_no가 없는 노드는 None으로 전달 (현재 페이지 추적은 호출측에서).
    """
    results: list[tuple[str, str | None, int | None]] = []

    if isinstance(node, list):
        for item in node:
            results.extend(_flatten_json(item, current_page))
        return results

    if not isinstance(node, dict):
        return results

    node_type = node.get("type", "")

    # 페이지 경계 노드
    if node_type == "page":
        page_no = node.get("page_no") or node.get("page_number")
        if page_no is not None:
            try:
                current_page = int(page_no)
            except (ValueError, TypeError):
                pass
        results.append(("page", None, current_page))
        for child in node.get("kids", []):
            results.extend(_flatten_json(child, current_page))
        return results

    # 표 노드: 내부 순회 없이 table 이벤트만 emit
    if node_type == "table":
        results.append(("table", None, current_page))
        return results

    # heading / paragraph 등: content 추출
    content = node.get("content")
    if isinstance(content, str):
        results.append((node_type, content, current_page))
    elif node_type in _HEADING_TYPES | _BODY_TYPES:
        # content가 없는 경우 kids에서 텍스트 수집
        collected = _collect_text_from_kids(node.get("kids", []))
        if collected:
            results.append((node_type, collected, current_page))

    # 자식 순회 (table 제외 — 위에서 이미 return)
    for child in node.get("kids", []):
        results.extend(_flatten_json(child, current_page))

    return results


def _collect_text_from_kids(kids: list) -> str:
    """kids 리스트에서 텍스트를 평탄하게 수집한다."""
    parts = []
    for kid in kids:
        if not isinstance(kid, dict):
            continue
        content = kid.get("content")
        if isinstance(content, str) and content.strip():
            parts.append(content.strip())
    return " ".join(parts)


def _extract_pages(
    json_data: dict | list,
    table_blocks: list[DocumentTableBlock],
) -> list[DocumentPage]:
    """
    ODL raw_json에서 실제 page 단위 텍스트/표 귀속을 복원한다.

    계약:
    - page 노드(page_no/page_number)가 실제로 존재할 때만 real page로 간주
    - body 텍스트는 page 번호가 명시된 노드만 해당 페이지에 적재
    - table은 등장 순서대로 table_blocks와 매핑해 해당 page에 귀속
    - 결과 page는 estimated=False 로 표시
    """
    flat_nodes = _flatten_json(json_data)
    table_iter = iter(table_blocks)

    page_buffers: dict[int, dict[str, list[str]]] = {}
    saw_real_page = False

    def ensure_page(page_no: int) -> dict[str, list[str]]:
        bucket = page_buffers.get(page_no)
        if bucket is None:
            bucket = {"texts": [], "table_ids": []}
            page_buffers[page_no] = bucket
        return bucket

    for node_type, content, page_no in flat_nodes:
        if node_type == "page" and page_no is not None:
            saw_real_page = True
            ensure_page(page_no)
            continue

        if page_no is None:
            continue

        bucket = ensure_page(page_no)

        if node_type == "table":
            tb = next(table_iter, None)
            if tb is not None:
                bucket["table_ids"].append(tb.table_id)
        elif node_type in _BODY_TYPES:
            if content and content.strip():
                bucket["texts"].append(content.strip())

    if not saw_real_page:
        return []

    pages: list[DocumentPage] = []
    for page_no in sorted(page_buffers):
        bucket = page_buffers[page_no]
        pages.append(
            DocumentPage(
                page_number=page_no,
                text="\n".join(bucket["texts"]).strip(),
                table_ids=list(bucket["table_ids"]),
                metadata={"estimated": False},
            )
        )
    return pages


# ── 기존 헬퍼 (body_text / table_blocks 생성용) ───────────────────────────────


def _extract_body_from_json(json_data: dict | list | None) -> str:
    if not json_data:
        return ""
    lines: list[str] = []
    _collect_body_lines(json_data, lines)
    return "\n".join(line for line in lines if line.strip()).strip()


def _extract_table_blocks(json_data: dict | list) -> list[DocumentTableBlock]:
    blocks: list[DocumentTableBlock] = []
    table_idx = 0

    for element in _collect_table_elements(json_data):
        rows = element.get("rows") or []
        serialized_rows: list[str] = []

        for row in rows:
            if not isinstance(row, dict):
                continue
            cells = row.get("cells") or []
            cell_texts = [_extract_cell_text(cell) for cell in cells]
            if any(cell_texts):
                serialized_rows.append(" | ".join(cell_texts))

        if serialized_rows:
            text = f"[표 {table_idx + 1}]\n" + "\n".join(serialized_rows)
            blocks.append(
                DocumentTableBlock(
                    table_id=f"table:{table_idx}",
                    text=text,
                    row_count=len(serialized_rows),
                )
            )
            table_idx += 1

    return blocks


def _collect_table_elements(json_data: dict | list) -> list[dict]:
    results: list[dict] = []
    if isinstance(json_data, list):
        for item in json_data:
            results.extend(_collect_table_elements(item))
    elif isinstance(json_data, dict):
        if json_data.get("type") == "table":
            results.append(json_data)
        else:
            for child in json_data.get("kids", []):
                results.extend(_collect_table_elements(child))
    return results


def _extract_cell_text(cell: dict) -> str:
    if not isinstance(cell, dict):
        return ""
    parts = []
    for kid in cell.get("kids", []):
        content = kid.get("content", "")
        if content:
            parts.append(str(content).strip())
    return " ".join(parts)


def _collect_body_lines(node: dict | list, lines: list[str]) -> None:
    if isinstance(node, list):
        for item in node:
            _collect_body_lines(item, lines)
        return
    if not isinstance(node, dict):
        return
    node_type = node.get("type")
    content = node.get("content")
    if isinstance(content, str) and content.strip():
        if node_type not in {"table cell", "table row", "table"}:
            lines.append(content.strip())
    for child in node.get("kids", []):
        _collect_body_lines(child, lines)
    for row in node.get("rows", []):
        _collect_body_lines(row, lines)
    for cell in node.get("cells", []):
        _collect_body_lines(cell, lines)
