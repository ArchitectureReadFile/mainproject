"""
services/platform/mappers/admin_rule_annex_formatter.py

행정규칙 별표(annex) 원문을 RAG 검색용 텍스트로 정규화한다.

책임:
    - annex 텍스트 유형 판별 (plain_text / table / flowchart / diagram_like)
    - 유형별 검색용 요약 텍스트 생성
    - annex chunk 수 제한 (원칙 1개, 최대 2개)

비책임:
    - 원문 저장 (→ PlatformRawSource.raw_payload)
    - chunk 생성 자체 (→ admin_rule_mapper.build_chunks)
    - 완벽한 표 파서 / OCR

원칙:
    - "시각 구조 완벽 복원"이 목표가 아니다.
    - retrieval에 쓸 만한 검색용 설명 텍스트를 만드는 것이 목표다.
    - 원문은 PlatformRawSource에 이미 보존되어 있다.
"""

from __future__ import annotations

import re
from typing import Literal

# ── 상수 ─────────────────────────────────────────────────────────────────────

AnnexType = Literal["plain_text", "table", "flowchart", "diagram_like"]

# box-drawing 문자 집합
_BOX_CHARS = set("│┌┐└┘─┼┃━┠┨┤├┬┴╋╔╗╚╝║═╠╣╦╩╬▶◀▲▼→←↑↓➡")

# annex chunk 수 제한
_MAX_ANNEX_CHUNKS = 2
_ANNEX_CHUNK_MAX_CHARS = 1200

# 유형 판별 임계값
_BOX_CHAR_RATIO_THRESHOLD = 0.03  # 전체 문자 중 3% 이상이 box 문자이면 table/diagram
_LONG_LINE_REPEAT_THRESHOLD = 3  # 구분선(---/===) 반복 횟수
_FLOWCHART_KEYWORDS = {
    "흐름도",
    "절차도",
    "단계",
    "처리",
    "접수",
    "검토",
    "승인",
    "결재",
}


# ══════════════════════════════════════════════════════════════════════════════
# 유형 판별
# ══════════════════════════════════════════════════════════════════════════════


def classify_annex_text(text: str) -> AnnexType:
    """
    annex 텍스트 유형을 heuristic으로 판별한다.

    판별 우선순위:
        1. box-drawing 문자 비율 → table 또는 diagram_like
        2. flowchart 키워드 → flowchart
        3. 구분선 반복 패턴 → table
        4. 나머지 → plain_text

    Returns:
        "plain_text" | "table" | "flowchart" | "diagram_like"
    """
    if not text or not text.strip():
        return "plain_text"

    # 1. box-drawing 문자 비율
    total_chars = len(text)
    box_count = sum(1 for c in text if c in _BOX_CHARS)
    box_ratio = box_count / total_chars if total_chars > 0 else 0.0

    if box_ratio >= _BOX_CHAR_RATIO_THRESHOLD:
        # flowchart 키워드가 같이 있으면 flowchart
        if any(kw in text for kw in _FLOWCHART_KEYWORDS):
            return "flowchart"
        # box 비율이 매우 높으면 diagram_like
        if box_ratio >= 0.08:
            return "diagram_like"
        return "table"

    # 2. flowchart 키워드 (box 문자가 없어도)
    if any(kw in text for kw in _FLOWCHART_KEYWORDS):
        # 실제 단계/절차 패턴인지 확인
        lines = text.splitlines()
        step_pattern = re.compile(r"^[\s①②③④⑤⑥⑦⑧⑨⑩\d]+[.\)。]?\s*.+")
        step_lines = sum(1 for line in lines if step_pattern.match(line))
        if step_lines >= 3:
            return "flowchart"

    # 3. 구분선 반복 패턴
    lines = text.splitlines()
    separator_lines = sum(
        1
        for line in lines
        if len(line.strip()) >= 5 and re.match(r"^[-=─━+|]+$", line.strip())
    )
    if separator_lines >= _LONG_LINE_REPEAT_THRESHOLD:
        return "table"

    return "plain_text"


# ══════════════════════════════════════════════════════════════════════════════
# 유형별 텍스트 정규화
# ══════════════════════════════════════════════════════════════════════════════


def _clean_box_chars(text: str) -> str:
    """box-drawing 문자와 연속 공백을 제거한다."""
    cleaned = "".join(" " if c in _BOX_CHARS else c for c in text)
    # 연속 공백 정리
    cleaned = re.sub(r" {3,}", "  ", cleaned)
    # box 문자만 있던 줄 제거
    lines = [line for line in cleaned.splitlines() if line.strip()]
    return "\n".join(lines)


def _normalize_plain_text(text: str) -> str:
    """plain_text annex: 불필요한 공백/연속 개행만 정리."""
    # 연속 빈 줄 2개 이상 → 1개
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 줄 단위 앞뒤 공백 정리
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def _normalize_table(text: str) -> str:
    """
    table 유형 annex: 표 테두리/박스문자를 제거하고
    셀 내용을 읽을 수 있는 텍스트로 변환한다.
    """
    cleaned = _clean_box_chars(text)
    lines = cleaned.splitlines()

    result_lines: list[str] = ["[별표 요약]"]
    seen: set[str] = set()

    for line in lines:
        stripped = line.strip()
        # 너무 짧거나 구분선만 남은 줄 skip
        if len(stripped) < 2:
            continue
        if re.match(r"^[-=─━ ]+$", stripped):
            continue
        # 중복 줄 skip
        if stripped in seen:
            continue
        seen.add(stripped)
        result_lines.append(stripped)

    # 헤더만 남은 경우(실질 내용 없음) → 빈 문자열 반환
    if len(result_lines) == 1:
        return ""

    return "\n".join(result_lines).strip()


def _normalize_flowchart(text: str) -> str:
    """
    flowchart 유형 annex: 화살표/박스 제거 후
    단계형 설명 텍스트로 변환한다.
    """
    # 화살표 문자 → 공백
    arrow_chars = set("→←↑↓↗↙▶◀▲▼➡⇒⇐⇑⇓")
    cleaned = "".join(" " if c in arrow_chars else c for c in text)
    cleaned = _clean_box_chars(cleaned)

    lines = cleaned.splitlines()
    result_lines: list[str] = ["[흐름도 요약]", "절차:"]
    step_no = 1
    seen: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if len(stripped) < 2:
            continue
        if re.match(r"^[-=─━ ]+$", stripped):
            continue
        if stripped in seen:
            continue
        seen.add(stripped)
        result_lines.append(f"{step_no}. {stripped}")
        step_no += 1

    # 헤더+절차: 만 남은 경우 → 빈 문자열 반환
    if len(result_lines) <= 2:
        return ""

    return "\n".join(result_lines).strip()


def _normalize_diagram_like(text: str) -> str:
    """
    diagram_like 유형 annex: box 문자 제거 후
    의미 있는 텍스트만 최대한 추출한다.
    """
    cleaned = _clean_box_chars(text)
    lines = cleaned.splitlines()

    result_lines: list[str] = ["[도표 요약]"]
    seen: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if len(stripped) < 3:
            continue
        if re.match(r"^[-=─━ ]+$", stripped):
            continue
        if stripped in seen:
            continue
        seen.add(stripped)
        result_lines.append(stripped)

    # 헤더만 남은 경우 → 빈 문자열 반환
    if len(result_lines) == 1:
        return ""

    return "\n".join(result_lines).strip()


# ══════════════════════════════════════════════════════════════════════════════
# 공개 인터페이스
# ══════════════════════════════════════════════════════════════════════════════


def normalize_annex_for_rag(text: str, annex_type: AnnexType) -> str:
    """
    annex 텍스트를 RAG 검색용 텍스트로 정규화한다.

    Args:
        text:       annex 원문 (_to_text() 처리 후 문자열)
        annex_type: classify_annex_text()가 반환한 유형

    Returns:
        검색용 정규화 텍스트. 원문보다 짧거나 같다.
        레이아웃 노이즈는 제거, 의미 있는 내용은 보존.
        빈 문자열이거나 공백만 있으면 "" 반환.
    """
    if not text or not text.strip():
        return ""
    if annex_type == "plain_text":
        return _normalize_plain_text(text)
    if annex_type == "table":
        return _normalize_table(text)
    if annex_type == "flowchart":
        return _normalize_flowchart(text)
    if annex_type == "diagram_like":
        return _normalize_diagram_like(text)
    return _normalize_plain_text(text)


def build_annex_chunks_text(
    annex_text: str,
) -> tuple[list[str], AnnexType]:
    """
    annex 원문을 RAG chunk 텍스트 리스트로 변환한다.

    정책:
        - 유형 판별 후 normalize_annex_for_rag() 적용
        - 결과가 _ANNEX_CHUNK_MAX_CHARS 이하이면 단일 chunk
        - 초과 시 최대 _MAX_ANNEX_CHUNKS개로 제한 분할

    Returns:
        (chunk 텍스트 리스트, annex_type)
    """
    annex_type = classify_annex_text(annex_text)
    normalized = normalize_annex_for_rag(annex_text, annex_type)

    if not normalized:
        return [], annex_type

    if len(normalized) <= _ANNEX_CHUNK_MAX_CHARS:
        return [normalized], annex_type

    # 최대 _MAX_ANNEX_CHUNKS개로 제한
    chunks: list[str] = []
    start = 0
    overlap = 100
    while start < len(normalized) and len(chunks) < _MAX_ANNEX_CHUNKS:
        chunks.append(normalized[start : start + _ANNEX_CHUNK_MAX_CHARS])
        start += _ANNEX_CHUNK_MAX_CHARS - overlap

    return chunks, annex_type
