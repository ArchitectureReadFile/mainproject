"""
domains/precedent/chunk_builder.py

PrecedentDocument를 meta / 주문 / 이유 중심 chunk 리스트로 변환한다.

━━━ Source of Truth ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  판례 본문 원문:   detail_text   (taxlaw 상세내용 HTML에서 추출)
  판례 사건부 원문: detail_table  (같은 HTML의 사건정보 테이블에서 추출)
  precedent.text:   backward compatibility / fallback 전용
                    (gist + detail_text 합본. 재인덱싱 경로에서만 사용)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PrecedentDocument 구조:
    {
        "precedent_id": int,
        "source_url":   str,
        "title":        str | None,
        "gist":         str | None,
        "detail_table": dict | None,   # 사건·원고·피고·원심판결·판결선고
        "sections":     [{"title": str, "text": str}, ...],
    }

chunk payload 계약:
    chunk_id         str
    precedent_id     int
    title            str | None
    source_url       str
    case_number      str | None   # 사건번호만 (예: "2025두34754")
    case_name        str | None   # 사건명만 (예: "종합소득세부과처분취소")
    court_name       str | None   # metadata_parser 보강값 (detail_table에 없음)
    judgment_date    str | None
    plaintiff        str | None
    defendant        str | None
    lower_court_case str | None
    section_title    str | None   # "meta" / "주문" / "이유" / 섹션명
    element_type     str          # "meta" / "section" / "paragraph"
    order_index      int
    text             str
"""

import re
from typing import TypedDict

MAX_CHUNK_CHARS = 1200
OVERLAP_CHARS = 150

# detail_text 섹션 분리 패턴 — 【주문】 형태와 plain "주 문" 형태 모두 지원
_SECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("주문", re.compile(r"(?:^【주\s*문】|^주\s*문\s*$)", re.MULTILINE)),
    ("이유", re.compile(r"(?:^【이\s*유】|^이\s*유\s*$)", re.MULTILINE)),
    (
        "청구취지",
        re.compile(r"(?:^【청\s*구\s*취\s*지】|^청\s*구\s*취\s*지\s*$)", re.MULTILINE),
    ),
    (
        "판결요지",
        re.compile(r"(?:^【판\s*결\s*요\s*지】|^판\s*결\s*요\s*지\s*$)", re.MULTILINE),
    ),
    (
        "참조조문",
        re.compile(r"(?:^【참\s*조\s*조\s*문】|^참\s*조\s*조\s*문\s*$)", re.MULTILINE),
    ),
    (
        "참조판례",
        re.compile(r"(?:^【참\s*조\s*판\s*례】|^참\s*조\s*판\s*례\s*$)", re.MULTILINE),
    ),
]

# 사건번호 패턴: "2025두34754" 또는 "2025-두-34754" 형태
# 사건번호 뒤에 오는 나머지 텍스트는 사건명
_CASE_NUMBER_RE = re.compile(
    r"^((?:20\d{2})\s*[-–]?\s*[가-힣]{1,4}\s*[-–]?\s*\d{1,7})\s*(.*)?$"
)


class PrecedentChunk(TypedDict):
    chunk_id: str
    precedent_id: int
    title: str | None
    source_url: str
    case_number: str | None
    case_name: str | None
    court_name: str | None
    judgment_date: str | None
    plaintiff: str | None
    defendant: str | None
    lower_court_case: str | None
    section_title: str | None
    element_type: str
    order_index: int
    text: str


def _parse_case_field(raw: str | None) -> tuple[str | None, str | None]:
    """
    detail_table["사건"] 값에서 (case_number, case_name)을 분리한다.

    예:
        "2025두34754 종합소득세부과처분취소"  → ("2025두34754", "종합소득세부과처분취소")
        "2025두34754"                        → ("2025두34754", None)
        None                                 → (None, None)
    """
    if not raw:
        return None, None
    raw = raw.strip()
    m = _CASE_NUMBER_RE.match(raw)
    if not m:
        return None, raw or None
    case_number = re.sub(r"\s+", "", m.group(1))  # 공백 제거 정규화
    case_name = m.group(2).strip() if m.group(2) else None
    return case_number or None, case_name or None


def _split_by_length(
    text: str, section_title: str | None
) -> list[tuple[str, str | None]]:
    """MAX_CHUNK_CHARS 초과 시 overlap 포함 2차 분할."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [(text, section_title)]

    chunks = []
    start = 0
    while start < len(text):
        end = start + MAX_CHUNK_CHARS
        chunks.append((text[start:end], section_title))
        start = end - OVERLAP_CHARS
    return chunks


def _split_sections(text: str) -> list[tuple[str, str | None]]:
    """
    detail_text를 섹션 패턴 기준으로 분리한다.

    반환: [(section_text, section_title), ...]
    섹션 패턴 미탐지 시 전체를 ("본문", None) 하나로 반환.
    """
    boundaries: list[tuple[int, str]] = []
    for section_title, pattern in _SECTION_PATTERNS:
        for m in pattern.finditer(text):
            boundaries.append((m.start(), section_title))

    boundaries.sort(key=lambda x: x[0])

    if not boundaries:
        return [(text.strip(), "본문")]

    segments: list[tuple[str, str | None]] = []

    # 첫 섹션 이전 텍스트 → meta 취급
    pre = text[: boundaries[0][0]].strip()
    if pre:
        segments.append((pre, "meta"))

    for i, (start_pos, section_title) in enumerate(boundaries):
        end_pos = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        seg = text[start_pos:end_pos].strip()
        if seg:
            segments.append((seg, section_title))

    return segments


def _build_meta_text(
    title: str | None,
    gist: str | None,
    detail_table: dict | None,
    case_number: str | None,
    case_name: str | None,
) -> str:
    """
    meta chunk 텍스트를 조립한다.

    형식:
        [사건부]
        사건번호: 2025두34754
        사건명: 종합소득세부과처분취소
        원고: ...
        피고: ...
        원심판결: ...
        판결선고: ...
        제목: ...
        요지: ...
    """
    lines: list[str] = []

    if detail_table or case_number:
        lines.append("[사건부]")
        if case_number:
            lines.append(f"사건번호: {case_number}")
        if case_name:
            lines.append(f"사건명: {case_name}")
        if detail_table:
            for k, v in detail_table.items():
                # "사건" 필드는 이미 위에서 분리했으므로 skip
                if k == "사건" or not v:
                    continue
                lines.append(f"{k}: {v}")

    if title:
        lines.append(f"제목: {title}")
    if gist:
        lines.append(f"요지: {gist}")

    return "\n".join(lines).strip()


def _element_type(section_title: str | None) -> str:
    if section_title == "meta":
        return "meta"
    if section_title in (
        "주문",
        "이유",
        "청구취지",
        "판결요지",
        "참조조문",
        "참조판례",
        "본문",
    ):
        return "section"
    return "paragraph"


def build_chunks_from_precedent_document(doc: dict) -> list[PrecedentChunk]:
    """
    PrecedentDocument dict를 PrecedentChunk 리스트로 변환한다.

    처리 순서:
    1. detail_table["사건"]에서 case_number / case_name 분리
    2. meta chunk 생성 (사건부 + title + gist)
    3. sections 순회 → 각 section 길이 분할
    4. sections 없을 때 gist fallback
    """
    precedent_id: int = doc["precedent_id"]
    source_url: str = doc.get("source_url", "")
    title: str | None = doc.get("title")
    gist: str | None = doc.get("gist")
    detail_table: dict | None = doc.get("detail_table")
    sections: list[dict] = doc.get("sections") or []

    # 사건번호 / 사건명 분리
    raw_case = detail_table.get("사건") if detail_table else None
    case_number, case_name = _parse_case_field(raw_case)

    base_payload: dict = {
        "precedent_id": precedent_id,
        "title": title,
        "source_url": source_url,
        "case_number": case_number,
        "case_name": case_name,
        "court_name": None,  # index_precedent에서 metadata_parser로 보강
        "judgment_date": detail_table.get("판결선고") if detail_table else None,
        "plaintiff": detail_table.get("원고") if detail_table else None,
        "defendant": detail_table.get("피고") if detail_table else None,
        "lower_court_case": detail_table.get("원심판결") if detail_table else None,
    }

    raw_segments: list[tuple[str, str | None]] = []

    # 1. meta chunk
    meta_text = _build_meta_text(title, gist, detail_table, case_number, case_name)
    if meta_text:
        raw_segments.append((meta_text, "meta"))

    # 2. sections
    if sections:
        for section in sections:
            sec_title = section.get("title")
            sec_text = (section.get("text") or "").strip()
            if sec_text:
                raw_segments.append((sec_text, sec_title))
    else:
        # fallback: gist만 있을 때
        if gist:
            raw_segments.append((gist, "요지"))

    # 3. 2차 길이 분할
    all_segments: list[tuple[str, str | None]] = []
    for seg_text, sec_title in raw_segments:
        all_segments.extend(_split_by_length(seg_text, sec_title))

    result: list[PrecedentChunk] = []
    for order_index, (chunk_text, sec_title) in enumerate(all_segments):
        if not chunk_text.strip():
            continue
        result.append(
            PrecedentChunk(
                chunk_id=f"precedent:{precedent_id}:chunk:{order_index}",
                **base_payload,
                section_title=sec_title,
                element_type=_element_type(sec_title),
                order_index=order_index,
                text=chunk_text,
            )
        )

    return result


def build_precedent_document(
    precedent_id: int,
    source_url: str,
    title: str | None,
    gist: str | None,
    detail_table: dict | None,
    detail_text: str | None,
) -> dict:
    """
    extractor 반환값을 PrecedentDocument dict로 조립한다.

    detail_text (1순위 원문):
        taxlaw 상세내용 HTML에서 추출한 주문·이유 본문.
        있으면 섹션 분리 후 sections 생성.

    detail_text가 None인 경우:
        sections는 빈 리스트. build_chunks_from_precedent_document에서
        gist fallback 또는 빈 상태로 처리된다.
        이 경로는 재인덱싱(index_precedent)에서 precedent.text fallback이
        detail_text 자리에 들어올 때만 발생한다.
    """
    sections: list[dict] = []

    if detail_text:
        for seg_text, sec_title in _split_sections(detail_text):
            if seg_text:
                sections.append({"title": sec_title, "text": seg_text})

    return {
        "precedent_id": precedent_id,
        "source_url": source_url,
        "title": title,
        "gist": gist,
        "detail_table": detail_table,
        "sections": sections,
    }
