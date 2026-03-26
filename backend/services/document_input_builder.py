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

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.document_extract_service import ExtractedDocument

_TABLE_ROW_RE = re.compile(r"^\|.*\|$")
_TABLE_SEP_RE = re.compile(r"^\|[\s\-|:]+\|$")
_HEADING_RE = re.compile(r"^#{1,6}\s")
_LIST_RE = re.compile(r"^(\s*[-*]\s|\s*\d+\.\s|\s*[가나다라마바사아자차카타파하]\.\s)")
_SHORT_HEADING_RE = re.compile(r"^[가-힣A-Za-z0-9\s]{1,20}$")


def _is_list_like_line(line: str) -> bool:
    return bool(_LIST_RE.match(line))


def _is_heading_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _HEADING_RE.match(stripped):
        return True
    # 표·목록·일반 본문 제외
    if _TABLE_ROW_RE.match(stripped) or _TABLE_SEP_RE.match(stripped):
        return False
    if _is_list_like_line(stripped):
        return False
    # 공백 제거 후 12자 이하의 짧은 독립 줄 → heading-like 보호
    compact = stripped.replace(" ", "")
    if _SHORT_HEADING_RE.match(stripped) and 1 <= len(compact) <= 12:
        return True
    return False


def _is_blank_line(line: str) -> bool:
    return not line.strip()


def _is_plain_body_line(line: str) -> bool:
    """heading / list-like / 표 / 빈 줄이 아닌 일반 본문 줄 여부."""
    stripped = line.strip()
    if not stripped:
        return False
    if _is_heading_line(stripped):
        return False
    if _is_list_like_line(stripped):
        return False
    if _TABLE_ROW_RE.match(stripped) or _TABLE_SEP_RE.match(stripped):
        return False
    return True


def _reflow_body_lines(lines: list[str]) -> list[str]:
    """
    같은 문단 내부 soft line break를 공백 1개로 이어붙인다.

    규칙:
    - 빈 줄 → 문단 경계: 현재 누적 버퍼를 flush하고 빈 줄 출력
    - heading / list-like 줄 → standalone block: 버퍼 flush 후 그 줄만 단독 출력
    - 일반 본문 줄 → 버퍼에 누적
    """
    output: list[str] = []
    buffer: list[str] = []

    def flush():
        if buffer:
            output.append(" ".join(buffer))
            buffer.clear()

    for line in lines:
        stripped = line.rstrip()

        if stripped == "":
            flush()
            output.append("")
        elif _is_heading_line(stripped) or _is_list_like_line(stripped):
            flush()
            output.append(stripped)
        else:
            buffer.append(stripped)

    flush()
    return output


def _merge_weak_paragraph_breaks(lines: list[str]) -> list[str]:
    """
    _reflow_body_lines() 이후, 빈 줄 1개를 사이에 둔 두 일반 본문 블록을 병합한다.

    알고리즘: blank 위치(i)에서 앞(result[-1])과 뒤(lines[i+1])를 동시에 확인한다.
    - 앞: result[-1]이 plain body
    - 뒤: lines[i+1]이 plain body
    → 조건 충족 시 blank + next를 소비하고 result[-1]에 " "로 이어붙인다.
    → 이 방식으로 A/blank/B/blank/C 연쇄 병합이 자연스럽게 처리된다.

    병합하지 않는 경우:
    - 앞이나 뒤가 heading / list / 표
    - 빈 줄이 2개 이상 연속 (blank 다음도 blank이면 조건 불충족)
    """
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if (
            _is_blank_line(line)
            and result
            and _is_plain_body_line(result[-1])
            and i + 1 < len(lines)
            and _is_plain_body_line(lines[i + 1])
        ):
            # blank + next 소비, result[-1]에 이어붙임
            prev = result.pop()
            result.append(prev.rstrip() + " " + lines[i + 1].lstrip())
            i += 2
            continue

        result.append(line)
        i += 1

    return result


def extract_body_from_markdown(markdown: str) -> str:
    """
    markdown에서 표 행을 제거하고 본문 텍스트를 reflow + weak paragraph merge 후 반환한다.

    처리 순서:
    1. splitlines + table lines 제거
    2. _reflow_body_lines (soft line break → 공백 이어붙임)
    3. _merge_weak_paragraph_breaks (빈 줄 1개 사이 일반 본문 블록 병합)
    4. \\n{3,} → \\n\\n 압축
    5. strip 후 반환
    """
    filtered_lines = []
    for line in markdown.splitlines():
        stripped = line.rstrip()
        if _TABLE_ROW_RE.match(stripped) or _TABLE_SEP_RE.match(stripped):
            continue
        filtered_lines.append(stripped)

    reflowed_lines = _reflow_body_lines(filtered_lines)
    merged_lines = _merge_weak_paragraph_breaks(reflowed_lines)

    body = re.sub(r"\n{3,}", "\n\n", "\n".join(merged_lines))
    return body.strip()


def extract_body_from_json(json_data: dict | list | None) -> str:
    """
    OpenDataLoader JSON에서 paragraph/content 기반 본문 텍스트를 재구성한다.

    markdown 산출물이 비어 있거나 지나치게 짧은 경우 fallback 본문으로 사용한다.
    """
    if not json_data:
        return ""

    lines: list[str] = []
    _collect_body_lines(json_data, lines)

    filtered_lines = [line.rstrip() for line in lines if line and line.strip()]
    reflowed_lines = _reflow_body_lines(filtered_lines)
    merged_lines = _merge_weak_paragraph_breaks(reflowed_lines)
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(merged_lines))
    return body.strip()


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
