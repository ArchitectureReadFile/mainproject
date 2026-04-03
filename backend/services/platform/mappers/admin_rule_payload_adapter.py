"""
services/platform/mappers/admin_rule_payload_adapter.py

행정규칙(AdmRulService) 응답을 mapper가 읽기 쉬운 canonical payload로 정리한다.

책임:
    - nested / flat payload 차이를 흡수
    - 조문 입력 형식을 표준 리스트로 정규화
    - 부칙/별표 텍스트를 flat dict로 승격

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


def normalize_article_list(raw_articles: Any) -> list[dict | str]:
    """
    조문 항목을 downstream이 안전하게 처리할 수 있는 표준 리스트로 변환한다.

    입력 형태:
        1. dict 리스트  — [{"조문번호": "1", "조문내용": "..."}]
        2. str 리스트   — ["제1조 ...", "제2조 ..."]
        3. 단일 str     — "제1조 ... 제2조 ..."
        4. 단일 dict    — {"조문번호": "1", "조문내용": "..."}

    반환: list[dict | str]
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
        return result

    return []


def canonicalize_admin_rule_payload(raw: dict) -> dict:
    """
    실제 API 중첩 응답 구조를 mapper가 기대하는 flat dict로 변환한다.

    지원하는 입력 형태:
        1. 이미 flat한 dict (행정규칙ID가 top-level) → 그대로 반환
        2. 중첩 dict (행정규칙기본정보.행정규칙ID 등) → flatten 후 반환
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

    # 4) 부칙: canonical key가 있으면 우선, 없으면 nested 부칙에서 추출
    addendum_text = flat.get(FIELD_ADDENDUM)
    if not addendum_text:
        addendum_section = raw.get("부칙")
        if isinstance(addendum_section, dict):
            addendum_text = addendum_section.get(FIELD_ADDENDUM) or ""
        elif isinstance(addendum_section, str):
            addendum_text = addendum_section.strip()
    if addendum_text:
        flat[FIELD_ADDENDUM] = addendum_text

    # 5) 별표: canonical key가 있으면 우선, 없으면 nested 별표단위 합본
    annex_text = flat.get(FIELD_ANNEX)
    if not annex_text:
        annex_section = raw.get("별표")
        if isinstance(annex_section, dict):
            annex_units = annex_section.get("별표단위") or []
            if isinstance(annex_units, dict):
                annex_units = [annex_units]
            if isinstance(annex_units, list):
                annex_parts = []
                for unit in annex_units:
                    if isinstance(unit, dict):
                        content = (unit.get(FIELD_ANNEX) or "").strip()
                        if content:
                            annex_parts.append(content)
                if annex_parts:
                    annex_text = "\n\n".join(annex_parts)
    if annex_text:
        flat[FIELD_ANNEX] = annex_text

    return flat
