"""
services/document_input_builder.py

ExtractedDocument를 소비처별 입력 형태로 변환한다.

소비처:
    summary  → 단일 문자열 (LLM 요약 입력)
    chat     → 단일 문자열 (채팅 컨텍스트 입력)
    rag      → 구조 dict  (chunk builder 입력)

OpenDataLoader JSON 구조:
    최상위: {"kids": [...]}
    table:  {"type": "table", "rows": [{"type": "table row", "cells": [...]}]}
    cell:   {"type": "table cell", "kids": [{"type": "paragraph", "content": "..."}]}
    텍스트는 항상 leaf paragraph의 "content" 필드에 있다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.document_extract_service import ExtractedDocument


def extract_body_from_markdown(markdown: str) -> str:
    """markdown 원문을 그대로 반환한다. 후처리 없음."""
    return markdown.strip()


def extract_body_from_json(json_data: dict | list | None) -> str:
    """
    OpenDataLoader JSON에서 paragraph/content 기반 본문 텍스트를 수집해 반환한다.

    markdown 산출물이 비어 있을 때 fallback으로 사용한다.
    """
    if not json_data:
        return ""

    lines: list[str] = []
    _collect_body_lines(json_data, lines)
    return "\n".join(line for line in lines if line.strip()).strip()


def extract_tables_from_json(json_data: dict | None) -> list[str]:
    """
    json_data에서 type == "table"인 요소를 찾아
    사람이 읽기 좋은 형태로 직렬화한 문자열 리스트를 반환한다.

    직렬화 형태 예시:
        [표 1]
        문서번호 | 2024구합10997
        결정유형 | 국승
    """
    if not json_data:
        return []

    tables: list[str] = []
    table_idx = 1

    for element in _collect_table_elements(json_data):
        rows = element.get("rows") or []
        serialized_rows = []

        for row in rows:
            if not isinstance(row, dict):
                continue
            cells = row.get("cells") or []
            cell_texts = [_extract_cell_text(cell) for cell in cells]
            if any(cell_texts):
                serialized_rows.append(" | ".join(cell_texts))

        if serialized_rows:
            tables.append(f"[표 {table_idx}]\n" + "\n".join(serialized_rows))
            table_idx += 1

    return tables


def build_summary_input(extracted: ExtractedDocument) -> str:
    """
    업로드 요약용 단일 텍스트를 구성한다.

    포맷:
        [본문]
        ...

        [표]
        [표 1]
        ...
    표가 없으면 [표] 섹션은 생략한다.
    """
    body = extract_body_from_markdown(extracted.markdown)
    if not body:
        body = extract_body_from_json(extracted.json_data)
    tables = extract_tables_from_json(extracted.json_data)

    parts = [f"[본문]\n{body}"]
    if tables:
        parts.append("[표]\n" + "\n\n".join(tables))

    return "\n\n".join(parts)


def build_chat_input(extracted: ExtractedDocument) -> str:
    """
    채팅 첨부용 단일 텍스트를 구성한다.
    본문 6000자, 표 2000자 상한.
    """
    body = extract_body_from_markdown(extracted.markdown)
    if not body:
        body = extract_body_from_json(extracted.json_data)
    tables = extract_tables_from_json(extracted.json_data)

    body = body[:6000]
    parts = [f"[본문]\n{body}"]

    if tables:
        table_block = "\n\n".join(tables)[:2000]
        parts.append(f"[표]\n{table_block}")

    return "\n\n".join(parts)


def build_rag_source(extracted: ExtractedDocument) -> dict:
    """
    RAG 인덱싱용 구조 dict를 반환한다.

    반환 형태:
        {
            "body_text": "...",
            "table_blocks": ["[표 1] ...", "[표 2] ..."],
        }
    """
    body = extract_body_from_markdown(extracted.markdown)
    if not body:
        body = extract_body_from_json(extracted.json_data)
    tables = extract_tables_from_json(extracted.json_data)
    return {
        "body_text": body,
        "table_blocks": tables,
    }


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────


def _collect_table_elements(json_data: dict | list) -> list[dict]:
    """json_data를 재귀 탐색해 type == "table"인 요소만 모아 반환한다."""
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
    """cell.kids[].content (paragraph leaf)에서 텍스트를 추출한다."""
    if not isinstance(cell, dict):
        return ""

    parts = []
    for kid in cell.get("kids", []):
        content = kid.get("content", "")
        if content:
            parts.append(str(content).strip())

    return " ".join(parts)


def _collect_body_lines(node: dict | list, lines: list[str]) -> None:
    """
    paragraph/content 중심으로 JSON 트리를 순회하며 본문 줄을 수집한다.
    """
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
