"""
services/platform/mappers/admin_rule_mapper.py

국가법령정보 행정규칙 API 응답 → PlatformDocumentSchema 정규화.

━━━ 현재 상태: 구조 검증 전 fail-closed ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
실제 API 응답 필드명이 확정되지 않은 placeholder 상수 기반이다.
빈 body_text로 조용히 성공하는 경로를 막기 위해 required-field validation을 적용한다.

실제 API 응답 수신 후:
    1. _FIELD_* 상수 블록을 실제 필드명으로 교체
    2. validate_payload() 검증 기준 갱신
    3. settings/platform.py의 ENABLE_INGESTION_ADMIN_RULE=true로 전환
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

공식 API 필드 기준 (행정규칙 본문/목록):
    행정규칙ID, 행정규칙명, 소관기관명
    발령일자, 시행일자, 행정규칙번호
    조문번호, 조문내용, 부칙내용, 별표내용
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from schemas.platform_knowledge_schema import (
    PlatformChunkSchema,
    PlatformDocumentSchema,
)

logger = logging.getLogger(__name__)

_MAX_CHUNK_CHARS = 1500
_OVERLAP_CHARS = 150

# ── API 필드명 상수 (실제 응답 수신 후 이 블록만 교체) ───────────────────────────
# WARNING: 이 필드명은 placeholder다. 실제 API 응답과 다를 수 있다.
_FIELD_ID = "행정규칙ID"
_FIELD_NAME = "행정규칙명"
_FIELD_AGENCY = "소관기관명"
_FIELD_PROMULGATION_DATE = "발령일자"
_FIELD_EFFECTIVE_DATE = "시행일자"
_FIELD_RULE_NO = "행정규칙번호"
_FIELD_ARTICLES = "조문"
_FIELD_ARTICLE_NO = "조문번호"
_FIELD_ARTICLE_CONTENT = "조문내용"
_FIELD_ADDENDUM = "부칙내용"
_FIELD_ANNEX = "별표내용"
# ─────────────────────────────────────────────────────────────────────────────

# body를 구성하는 필드 목록 (조문 외 보조 텍스트)
_BODY_TEXT_FIELDS = (_FIELD_ADDENDUM, _FIELD_ANNEX)


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


def _build_article_text(article: dict) -> str:
    no = str(article.get(_FIELD_ARTICLE_NO) or "").strip()
    content = (article.get(_FIELD_ARTICLE_CONTENT) or "").strip()
    if no:
        return f"제{no}조\n{content}".strip()
    return content


def validate_payload(raw_payload: dict) -> None:
    """
    admin_rule payload required-field validation.

    실패 조건 (placeholder mapper이므로 더 엄격히 검증):
        - 행정규칙ID 없음 → external_id 없음
        - 행정규칙명 없음 → title 없음
        - 조문 목록 / 부칙내용 / 별표내용 모두 없음 → body_text가 비게 됨

    Raises:
        ValueError: validation 실패 시. 메시지에 "placeholder mapper" 컨텍스트 포함.
    """
    errors: list[str] = []

    external_id = str(raw_payload.get(_FIELD_ID) or "").strip()
    if not external_id:
        errors.append(f"{_FIELD_ID}(external_id) 누락")

    title = (raw_payload.get(_FIELD_NAME) or "").strip()
    if not title:
        errors.append(f"{_FIELD_NAME}(title) 누락")

    articles: list[dict] = raw_payload.get(_FIELD_ARTICLES) or []
    has_article_text = any(_build_article_text(a) for a in articles)
    has_body_field = any((raw_payload.get(f) or "").strip() for f in _BODY_TEXT_FIELDS)

    if not has_article_text and not has_body_field:
        errors.append(
            f"조문({_FIELD_ARTICLES}) / 본문 필드({'/'.join(_BODY_TEXT_FIELDS)}) 모두 없음 — "
            "실제 상세 필드 확인 전 placeholder mapper. "
            "API 응답 구조 확인 후 _FIELD_* 상수를 교체하고 ENABLE_INGESTION_ADMIN_RULE=true로 전환하세요."
        )

    if errors:
        msg = (
            "[admin_rule mapper] validate_payload 실패 (placeholder mapper 미검증 상태): "
            + "; ".join(errors)
        )
        logger.error(msg)
        raise ValueError(msg)


def normalize(raw_payload: dict) -> PlatformDocumentSchema:
    """
    국가법령정보 행정규칙 API 응답 dict → PlatformDocumentSchema.

    validate_payload()를 먼저 실행한다.
    검증 실패 시 ValueError를 발생시켜 indexing으로 진행하지 않는다.
    """
    validate_payload(raw_payload)

    external_id = str(raw_payload.get(_FIELD_ID) or "")
    rule_name = raw_payload.get(_FIELD_NAME) or ""
    agency = raw_payload.get(_FIELD_AGENCY) or None
    rule_no = raw_payload.get(_FIELD_RULE_NO) or None

    title = rule_name or None
    display_title = title

    issued_at = _parse_date(raw_payload.get(_FIELD_PROMULGATION_DATE)) or _parse_date(
        raw_payload.get(_FIELD_EFFECTIVE_DATE)
    )
    effective_date_str = raw_payload.get(_FIELD_EFFECTIVE_DATE)

    articles: list[dict] = raw_payload.get(_FIELD_ARTICLES) or []
    article_texts = [_build_article_text(a) for a in articles if _build_article_text(a)]
    body_parts = article_texts + [
        raw_payload.get(_FIELD_ADDENDUM) or "",
        raw_payload.get(_FIELD_ANNEX) or "",
    ]
    body_text = "\n\n".join(p.strip() for p in body_parts if p.strip())

    metadata: dict[str, Any] = {
        "rule_no": rule_no,
        "effective_date": effective_date_str,
        "promulgation_date": raw_payload.get(_FIELD_PROMULGATION_DATE),
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
    """조문 단위 chunk 생성. 조문 목록 없으면 body_text 전체를 단일 chunk로."""
    chunks: list[PlatformChunkSchema] = []
    order = 0

    base_meta: dict[str, Any] = {
        "source_url": doc.source_url,
        "issued_at": doc.issued_at.isoformat() if doc.issued_at else None,
        "agency": doc.agency,
        "rule_no": doc.metadata.get("rule_no"),
        "effective_date": doc.metadata.get("effective_date"),
    }

    articles: list[dict] = raw_payload.get(_FIELD_ARTICLES) or []

    if articles:
        for article in articles:
            text = _build_article_text(article)
            if not text:
                continue
            article_no = str(article.get(_FIELD_ARTICLE_NO) or "").strip()
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
        for part in _split_by_length(
            doc.body_text, max_chars=_MAX_CHUNK_CHARS, overlap=_OVERLAP_CHARS
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

    return chunks
