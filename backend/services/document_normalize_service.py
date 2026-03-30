"""
services/document_normalize_service.py

ExtractedDocument → DocumentSchema 정규화 계층.

책임:
    - extractor가 넘긴 source_type 사용 (odl | ocr)
    - raw_* 필드 세팅
    - body_text 생성 (ODL: markdown 우선 → json fallback / OCR: raw_text)
    - table_blocks 생성 (ODL json에서만 추출, OCR는 빈 리스트)
    - pages 생성 (v1: 전체 문서를 page 1 하나로 단순화)
    - metadata 기본값 생성

비책임 (각 소비처 서비스가 담당):
    - [본문]/[표] prompt 문자열 조립 (→ DocumentSummaryPayloadService / SessionDocumentPayloadService)
    - truncate / 길이 정책
    - chunk 분할 (→ DocumentChunkService)
    - document_type 분류 확정
"""

from __future__ import annotations

from schemas.document_schema import DocumentPage, DocumentSchema, DocumentTableBlock
from services.document_extract_service import ExtractedDocument

_NORMALIZATION_VERSION = "v1"


class DocumentNormalizeService:
    def normalize(self, extracted: ExtractedDocument) -> DocumentSchema:
        source_type = extracted.source_type

        raw_markdown, raw_json, raw_text = self._build_raw_fields(
            extracted, source_type
        )
        body_text = self._build_body_text(extracted, source_type)
        table_blocks = self._build_table_blocks(extracted, source_type)
        pages = self._build_pages(body_text, table_blocks)
        metadata = self._build_metadata(source_type, body_text, table_blocks, pages)

        return DocumentSchema(
            source_type=source_type,
            raw_markdown=raw_markdown,
            raw_json=raw_json,
            raw_text=raw_text,
            body_text=body_text,
            table_blocks=table_blocks,
            pages=pages,
            metadata=metadata,
        )

    # ── raw 필드 ──────────────────────────────────────────────────────────────

    def _build_raw_fields(
        self, extracted: ExtractedDocument, source_type: str
    ) -> tuple[str | None, dict | list | None, str | None]:
        if source_type == "odl":
            return extracted.markdown or None, extracted.json_data, None
        # ocr: OCR 원문은 raw_text로 보존 (raw_markdown에 섞지 않음)
        return None, None, extracted.markdown or None

    # ── body_text ─────────────────────────────────────────────────────────────

    def _build_body_text(self, extracted: ExtractedDocument, source_type: str) -> str:
        if source_type == "ocr":
            return (extracted.markdown or "").strip()
        # ODL: markdown 우선, 비면 json fallback
        body = (extracted.markdown or "").strip()
        if not body:
            body = _extract_body_from_json(extracted.json_data)
        return body

    # ── table_blocks ──────────────────────────────────────────────────────────

    def _build_table_blocks(
        self, extracted: ExtractedDocument, source_type: str
    ) -> list[DocumentTableBlock]:
        if source_type == "ocr" or not extracted.json_data:
            return []
        return _extract_table_blocks(extracted.json_data)

    # ── pages ─────────────────────────────────────────────────────────────────

    def _build_pages(
        self, body_text: str, table_blocks: list[DocumentTableBlock]
    ) -> list[DocumentPage]:
        """v1: 전체 문서를 page 1 하나로 단순화. page 단위 분리는 추후 과제."""
        if not body_text and not table_blocks:
            return []

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
    ) -> dict:
        return {
            "extraction_source": source_type,
            "has_tables": len(table_blocks) > 0,
            "page_count": len(pages),
            "body_char_count": len(body_text),
            "table_count": len(table_blocks),
            "normalization_version": _NORMALIZATION_VERSION,
        }


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────
# ODL JSON에서 body/table을 파싱하는 구현체.
# DocumentExtractService의 OCR fallback 판단용 헬퍼와 형태가 유사하지만
# 역할이 다르다: 여기서는 "정규화된 DocumentSchema 생성"이 목적이다.


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
