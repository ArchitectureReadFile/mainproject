"""
domains/platform_sync/mappers/admin_rule_payload_adapter.py

행정규칙(AdmRulService) 응답을 mapper가 읽기 쉬운 canonical payload로 정리한다.

책임:
    - nested / flat payload 차이를 흡수
    - 조문 입력 형식을 표준 리스트로 정규화
    - 부칙/별표 텍스트를 flat dict로 승격
    - str / list / dict 혼합 텍스트 필드를 안전하게 문자열로 변환

비책임:
    - PlatformDocumentSchema 생성
    - chunk 생성
"""

from __future__ import annotations

from typing import Any

FIELD_ID = "행정규칙ID"
FIELD_ARTICLES = "조문"
FIELD_ADDENDUM = "부칙내용"
FIELD_ANNEX = "별표내용"


def _to_text(value: Any) -> str:
    """
    임의 값을 안전하게 문자열로 변환한다.

    None  → ""
    str   → stripped
    list  → 각 요소를 재귀 변환 후 non-empty join
    dict  → values를 재귀 변환 후 non-empty join
    기타  → str() 변환
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(t for item in value if (t := _to_text(item)))
    if isinstance(value, dict):
        return "\n".join(t for v in value.values() if (t := _to_text(v)))
    return str(value).strip()


def normalize_article_list(raw_articles: Any) -> list[dict | str]:
    """
    조문 항목을 downstream이 안전하게 처리할 수 있는 표준 리스트로 변환한다.

    입력 형태:
        1. dict 리스트  — [{"조문번호": "1", "조문내용": "..."}]
        2. str 리스트   — ["제1조 ...", "제2조 ..."]
        3. 단일 str     — "제1조 ... 제2조 ..."
        4. 단일 dict    — {"조문번호": "1", "조문내용": "..."}

    반환: list[dict | str]

    dict 항목 내 조문내용이 list여도 downstream의 _to_text()가 처리한다.
    여기서는 list/str/dict 최상위 구조만 정규화한다.
    """
    if not raw_articles:
        return []

    if isinstance(raw_articles, dict):
        return [raw_articles]

    if isinstance(raw_articles, str):
        text = raw_articles.strip()
        return [text] if text else []

    if isinstance(raw_articles, list):
        result: list[dict | str] = []
        for item in raw_articles:
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    result.append(stripped)
            elif isinstance(item, list):
                # 중첩 list → 텍스트로 합쳐서 단일 str 항목으로
                text = _to_text(item)
                if text:
                    result.append(text)
        return result

    return []


def _extract_addendum_text(raw: dict, flat: dict) -> str:
    """
    부칙내용을 다양한 입력 형태에서 안전하게 추출한다.

    우선순위:
        1. flat에 이미 있는 canonical 값
        2. raw["부칙"]["부칙내용"]  (nested dict)
        3. raw["부칙"]  (직접 문자열)
    """
    existing = flat.get(FIELD_ADDENDUM)
    if existing:
        return _to_text(existing)

    addendum_section = raw.get("부칙")
    if isinstance(addendum_section, dict):
        return _to_text(addendum_section.get(FIELD_ADDENDUM))
    if addendum_section is not None:
        return _to_text(addendum_section)
    return ""


def _extract_annex_text(raw: dict, flat: dict) -> str:
    """
    별표내용을 다양한 입력 형태에서 안전하게 추출한다.

    우선순위:
        1. flat에 이미 있는 canonical 값
        2. raw["별표"]["별표단위"] 항목들의 별표내용 합본
        3. raw["별표"]  (직접 문자열)
    """
    existing = flat.get(FIELD_ANNEX)
    if existing:
        return _to_text(existing)

    annex_section = raw.get("별표")
    if isinstance(annex_section, dict):
        annex_units = annex_section.get("별표단위") or []
        if isinstance(annex_units, dict):
            annex_units = [annex_units]
        if isinstance(annex_units, list):
            parts = []
            for unit in annex_units:
                if isinstance(unit, dict):
                    content = _to_text(unit.get(FIELD_ANNEX))
                    if content:
                        parts.append(content)
                elif isinstance(unit, str) and unit.strip():
                    parts.append(unit.strip())
            return "\n\n".join(parts)
    if annex_section is not None:
        return _to_text(annex_section)
    return ""


def canonicalize_admin_rule_payload(raw: dict) -> dict:
    """
    실제 API 중첩 응답 구조를 mapper가 기대하는 flat dict로 변환한다.

    지원하는 입력 형태:
        1. 이미 flat한 dict (행정규칙ID가 top-level) → 그대로 반환
        2. 중첩 dict (행정규칙기본정보.행정규칙ID 등) → flatten 후 반환

    텍스트 필드(조문내용, 부칙내용, 별표내용)는 str/list/dict 어떤 형태여도
    _to_text()로 안전하게 변환된 문자열로 반환된다.
    """
    flat: dict[str, Any] = {}

    # 1) nested 기본정보를 먼저 펼친다.
    basic_info = raw.get("행정규칙기본정보") or {}
    if isinstance(basic_info, dict):
        flat.update(basic_info)

    # 2) top-level canonical/non-structural 키를 덮어써서 flat-ish payload도 수용한다.
    for key, value in raw.items():
        if key in {"행정규칙기본정보", "조문내용", "부칙", "별표"}:
            continue
        flat[key] = value

    # 3) 조문: canonical key(조문)가 있으면 우선, 없으면 raw key(조문내용) 사용
    articles_raw = raw.get(FIELD_ARTICLES)
    if articles_raw is None:
        articles_raw = raw.get("조문내용")
    flat[FIELD_ARTICLES] = normalize_article_list(articles_raw)

    # 4) 부칙내용 — str/list/dict 모두 안전하게 text 변환
    addendum = _extract_addendum_text(raw, flat)
    if addendum:
        flat[FIELD_ADDENDUM] = addendum
    elif FIELD_ADDENDUM in flat:
        flat[FIELD_ADDENDUM] = _to_text(flat[FIELD_ADDENDUM])

    # 5) 별표내용 — str/list/dict 모두 안전하게 text 변환
    annex = _extract_annex_text(raw, flat)
    if annex:
        flat[FIELD_ANNEX] = annex
    elif FIELD_ANNEX in flat:
        flat[FIELD_ANNEX] = _to_text(flat[FIELD_ANNEX])

    return flat
