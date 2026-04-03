"""
services/platform/mappers/admin_rule_mapper.py

국가법령정보 행정규칙 API 응답 → PlatformDocumentSchema 정규화.

실제 API 응답 구조 (AdmRulService):
    {
        "행정규칙기본정보": {
            "행정규칙ID": "...",
            "행정규칙명": "...",
            "소관부처명": "...",
            "발령일자": "...",
            "시행일자": "...",
            "발령번호": "...",
            ...
        },
        "조문내용": [
            {"조문번호": "1", "조문내용": "..."},
            ...
        ],
        "부칙": {
            "부칙내용": "..."
        },
        "별표": {
            "별표단위": [
                {"별표내용": "..."},
                ...
            ]
        }
    }

    normalize 전에 adapter를 거쳐 top-level 구조로 변환한 뒤
    이후 로직은 flat dict 기반으로 동작한다.

chunk 전략:
    chunk_type = "rule"        : 조문 단위 (기본)
    chunk_type = "addendum"    : 부칙내용 (별도 chunk, 본문과 분리)
    chunk_type = "annex"       : 별표내용 (별도 chunk, 본문과 분리)
    조문 없을 때 body_text 전체를 단일 rule chunk로.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from schemas.platform_knowledge_schema import (
    PlatformChunkSchema,
    PlatformDocumentSchema,
)
from services.platform.mappers.admin_rule_payload_adapter import (
    canonicalize_admin_rule_payload,
)

logger = logging.getLogger(__name__)

_MAX_CHUNK_CHARS = 1500
_OVERLAP_CHARS = 150

# ── flat dict 기준 필드명 (확인 완료) ────────────────────────────────────────
_FIELD_ID = "행정규칙ID"
_FIELD_NAME = "행정규칙명"
_FIELD_AGENCY = "소관부처명"
_FIELD_PROMULGATION_DATE = "발령일자"
_FIELD_EFFECTIVE_DATE = "시행일자"
_FIELD_RULE_NO = "발령번호"
_FIELD_ARTICLES = "조문"
_FIELD_ARTICLE_NO = "조문번호"
_FIELD_ARTICLE_CONTENT = "조문내용"
_FIELD_ADDENDUM = "부칙내용"
_FIELD_ANNEX = "별표내용"
# ─────────────────────────────────────────────────────────────────────────────


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip().replace("-", "").replace(".", "").replace(" ", "")
    try:
        return datetime.strptime(raw[:8], "%Y%m%d")
    except (ValueError, IndexError):
        return None


def _split_by_length(text: str, *, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + max_chars])
        start += max_chars - overlap
    return chunks


def _build_article_text(article: dict | str) -> str:
    """
    조문 항목에서 본문 텍스트를 추출한다.

    - dict: 조문번호 + 조문내용 조합
    - str: 텍스트 그대로 반환
    """
    if isinstance(article, str):
        return article.strip()

    if isinstance(article, dict):
        no = str(article.get(_FIELD_ARTICLE_NO) or "").strip()
        content = (article.get(_FIELD_ARTICLE_CONTENT) or "").strip()
        if no:
            return f"제{no}조\n{content}".strip()
        return content

    return ""


def _get_article_no(article: dict | str) -> str:
    """dict 조문에서 조문번호를 추출한다. str이면 빈 문자열 반환."""
    if isinstance(article, dict):
        return str(article.get(_FIELD_ARTICLE_NO) or "").strip()
    return ""


def validate_payload(flat: dict) -> None:
    """
    admin_rule payload required-field validation.
    adapter 결과(flat dict)를 대상으로 검증한다.

    실패 조건:
        - 행정규칙ID 없음 → external_id 없음
        - 행정규칙명 없음 → title 없음
        - 조문 목록 / 부칙내용 / 별표내용 모두 없음 → body_text가 비게 됨

    Raises:
        ValueError: validation 실패 시.
    """
    errors: list[str] = []

    external_id = str(flat.get(_FIELD_ID) or "").strip()
    if not external_id:
        errors.append(f"{_FIELD_ID}(external_id) 누락")

    title = (flat.get(_FIELD_NAME) or "").strip()
    if not title:
        errors.append(f"{_FIELD_NAME}(title) 누락")

    articles: list[dict | str] = flat.get(_FIELD_ARTICLES) or []
    has_article_text = any(_build_article_text(a) for a in articles)
    has_addendum = (flat.get(_FIELD_ADDENDUM) or "").strip()
    has_annex = (flat.get(_FIELD_ANNEX) or "").strip()

    if not has_article_text and not has_addendum and not has_annex:
        errors.append(
            f"조문({_FIELD_ARTICLES}) / {_FIELD_ADDENDUM} / {_FIELD_ANNEX} 모두 없음"
        )

    if errors:
        msg = "[admin_rule mapper] validate_payload 실패: " + "; ".join(errors)
        logger.error(msg)
        raise ValueError(msg)


def normalize(raw_payload: dict) -> PlatformDocumentSchema:
    """
    국가법령정보 행정규칙 API 응답 dict → PlatformDocumentSchema.

    중첩 구조와 flat 구조 모두 수용한다.
    adapter에서 canonical payload로 통일한 뒤 정규화를 진행한다.
    """
    flat = canonicalize_admin_rule_payload(raw_payload)
    validate_payload(flat)

    external_id = str(flat.get(_FIELD_ID) or "")
    rule_name = flat.get(_FIELD_NAME) or ""
    agency = flat.get(_FIELD_AGENCY) or None
    rule_no = flat.get(_FIELD_RULE_NO) or None

    title = rule_name or None
    display_title = title

    issued_at = _parse_date(flat.get(_FIELD_PROMULGATION_DATE)) or _parse_date(
        flat.get(_FIELD_EFFECTIVE_DATE)
    )
    effective_date_str = flat.get(_FIELD_EFFECTIVE_DATE)

    articles: list[dict | str] = flat.get(_FIELD_ARTICLES) or []
    article_texts = [_build_article_text(a) for a in articles if _build_article_text(a)]
    body_parts = article_texts + [
        flat.get(_FIELD_ADDENDUM) or "",
        flat.get(_FIELD_ANNEX) or "",
    ]
    body_text = "\n\n".join(p.strip() for p in body_parts if p.strip())

    metadata: dict[str, Any] = {
        "rule_no": rule_no,
        "effective_date": effective_date_str,
        "promulgation_date": flat.get(_FIELD_PROMULGATION_DATE),
    }

    return PlatformDocumentSchema(
        source_type="admin_rule",
        external_id=external_id,
        title=title,
        display_title=display_title,
        body_text=body_text,
        issued_at=issued_at,
        agency=agency,
        metadata=metadata,
    )


def build_chunks(
    doc: PlatformDocumentSchema, raw_payload: dict
) -> list[PlatformChunkSchema]:
    """
    조문 단위 chunk 생성 + 부칙/별표 별도 chunk 분리.

    chunk_type 분류:
        "rule"     — 조문 단위
        "addendum" — 부칙내용 (본문과 분리)
        "annex"    — 별표내용 (본문과 분리)
    """
    flat = canonicalize_admin_rule_payload(raw_payload)
    chunks: list[PlatformChunkSchema] = []
    order = 0

    base_meta: dict[str, Any] = {
        "source_url": doc.source_url,
        "issued_at": doc.issued_at.isoformat() if doc.issued_at else None,
        "agency": doc.agency,
        "rule_no": doc.metadata.get("rule_no"),
        "effective_date": doc.metadata.get("effective_date"),
    }

    articles: list[dict | str] = flat.get(_FIELD_ARTICLES) or []

    # 조문 chunk
    if articles:
        for article in articles:
            text = _build_article_text(article)
            if not text:
                continue
            article_no = _get_article_no(article)
            for part in _split_by_length(
                text, max_chars=_MAX_CHUNK_CHARS, overlap=_OVERLAP_CHARS
            ):
                chunks.append(
                    PlatformChunkSchema(
                        source_type="admin_rule",
                        external_id=doc.external_id,
                        chunk_type="rule",
                        chunk_order=order,
                        chunk_text=part,
                        section_title=f"제{article_no}조" if article_no else None,
                        metadata={**base_meta, "article_no": article_no or None},
                    )
                )
                order += 1
    else:
        # 조문 없을 때 — body_text에서 부칙/별표 제외 부분을 단일 chunk
        addendum_text = (flat.get(_FIELD_ADDENDUM) or "").strip()
        annex_text = (flat.get(_FIELD_ANNEX) or "").strip()
        remaining = doc.body_text
        if addendum_text:
            remaining = remaining.replace(addendum_text, "").strip()
        if annex_text:
            remaining = remaining.replace(annex_text, "").strip()

        if remaining:
            for part in _split_by_length(
                remaining, max_chars=_MAX_CHUNK_CHARS, overlap=_OVERLAP_CHARS
            ):
                chunks.append(
                    PlatformChunkSchema(
                        source_type="admin_rule",
                        external_id=doc.external_id,
                        chunk_type="rule",
                        chunk_order=order,
                        chunk_text=part,
                        metadata=base_meta,
                    )
                )
                order += 1

    # 부칙 chunk (본문과 분리)
    addendum = (flat.get(_FIELD_ADDENDUM) or "").strip()
    if addendum:
        for part in _split_by_length(
            addendum, max_chars=_MAX_CHUNK_CHARS, overlap=_OVERLAP_CHARS
        ):
            chunks.append(
                PlatformChunkSchema(
                    source_type="admin_rule",
                    external_id=doc.external_id,
                    chunk_type="addendum",
                    chunk_order=order,
                    chunk_text=part,
                    section_title="부칙",
                    metadata=base_meta,
                )
            )
            order += 1

    # 별표 chunk (본문과 분리)
    annex = (flat.get(_FIELD_ANNEX) or "").strip()
    if annex:
        for part in _split_by_length(
            annex, max_chars=_MAX_CHUNK_CHARS, overlap=_OVERLAP_CHARS
        ):
            chunks.append(
                PlatformChunkSchema(
                    source_type="admin_rule",
                    external_id=doc.external_id,
                    chunk_type="annex",
                    chunk_order=order,
                    chunk_text=part,
                    section_title="별표",
                    metadata=base_meta,
                )
            )
            order += 1

    return chunks
