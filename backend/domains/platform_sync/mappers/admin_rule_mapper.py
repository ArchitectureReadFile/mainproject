"""
domains/platform_sync/mappers/admin_rule_mapper.py

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
            {"조문번호": "1", "조문내용": "..."},   # 조문내용이 str 또는 list
            ...
        ],
        "부칙": {
            "부칙내용": "..."   # str 또는 list
        },
        "별표": {
            "별표단위": [
                {"별표내용": "..."},   # str 또는 list
                ...
            ]
        }
    }

    normalize 전에 adapter를 거쳐 top-level 구조로 변환한 뒤
    이후 로직은 flat dict 기반으로 동작한다.

텍스트 안전화:
    adapter와 mapper는 모두 _to_text()를 통해 str/list/dict 혼합 필드를
    안전하게 문자열로 변환한다. .strip() 직접 호출은 금지한다.

chunk 전략:
    chunk_type = "rule"        : 조문 단위 (기존 유지)
    chunk_type = "addendum"    : 부칙내용 (기존 유지)
    chunk_type = "annex"       : 별표 — annex_formatter를 통해 유형별 요약 텍스트로 적재
                                  원칙 1개, 최대 2개 chunk로 제한
                                  원문은 PlatformRawSource.raw_payload에 보존됨

annex body_text 정책:
    - PlatformDocument.body_text에는 조문 + 부칙 중심으로 유지
    - annex는 normalize_annex_for_rag() 요약 텍스트만 body_text에 포함
    - 표/흐름도형 원문이 body_text에 그대로 섞이지 않게 한다
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from domains.platform_sync.mappers.admin_rule_annex_formatter import (
    build_annex_chunks_text,
    classify_annex_text,
    normalize_annex_for_rag,
)
from domains.platform_sync.mappers.admin_rule_payload_adapter import (
    _to_text,
    canonicalize_admin_rule_payload,
)
from domains.platform_sync.schemas import PlatformChunkSchema, PlatformDocumentSchema

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

_ARTICLE_PREFIX_RE = re.compile(r"^제\s*\d+\s*조(?:\s*\(|\b)")
_HEADING_PREFIX_RE = re.compile(r"^제\s*\d+\s*[장절관]\b")


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = _to_text(raw).replace("-", "").replace(".", "").replace(" ", "")
    try:
        return datetime.strptime(text[:8], "%Y%m%d")
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

    - dict: 조문번호 + 조문내용 조합. 조문내용은 _to_text()로 안전하게 처리.
    - str: 텍스트 그대로 반환
    """
    if isinstance(article, str):
        return _to_text(article)

    if isinstance(article, dict):
        no = _to_text(article.get(_FIELD_ARTICLE_NO))
        content = _to_text(article.get(_FIELD_ARTICLE_CONTENT))
        if no:
            return f"제{no}조\n{content}".strip() if content else f"제{no}조"
        return content

    return ""


def _get_article_no(article: dict | str) -> str:
    """dict 조문에서 조문번호를 추출한다. str이면 빈 문자열 반환."""
    if isinstance(article, dict):
        return _to_text(article.get(_FIELD_ARTICLE_NO))
    return ""


def _classify_article_entry(article: dict | str) -> str:
    """
    canonicalized 조문 항목을 article / heading / unknown으로 분류한다.

    - dict 조문은 article로 간주한다.
    - str 조문은 접두 패턴으로 장/절/관 제목과 실제 조문을 구분한다.
    """
    if isinstance(article, dict):
        return "article"

    text = _to_text(article)
    if not text:
        return "unknown"
    if _ARTICLE_PREFIX_RE.match(text):
        return "article"
    if _HEADING_PREFIX_RE.match(text):
        return "heading"
    return "unknown"


def _join_heading_context(headings: list[str], article_no: str) -> str | None:
    """
    누적된 heading context를 조문 section_title로 합친다.

    예:
        ["제2장 정원관리", "제1절 채용"] + "5"
        -> "제2장 정원관리 / 제1절 채용 / 제5조"
    """
    parts = [heading for heading in headings if heading]
    if article_no:
        parts.append(f"제{article_no}조")
    return " / ".join(parts) if parts else None


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

    external_id = _to_text(flat.get(_FIELD_ID))
    if not external_id:
        errors.append(f"{_FIELD_ID}(external_id) 누락")

    title = _to_text(flat.get(_FIELD_NAME))
    if not title:
        errors.append(f"{_FIELD_NAME}(title) 누락")

    articles: list[dict | str] = flat.get(_FIELD_ARTICLES) or []
    has_article_text = any(_build_article_text(a) for a in articles)
    has_addendum = _to_text(flat.get(_FIELD_ADDENDUM))
    has_annex = _to_text(flat.get(_FIELD_ANNEX))

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
    모든 텍스트 필드는 _to_text()를 통해 안전하게 문자열로 변환한다.

    body_text annex 정책:
        annex 원문 대신 normalize_annex_for_rag() 요약 텍스트만 포함한다.
        표/흐름도형 레이아웃 원문이 body_text에 섞이지 않게 한다.
    """
    flat = canonicalize_admin_rule_payload(raw_payload)
    validate_payload(flat)

    external_id = _to_text(flat.get(_FIELD_ID))
    rule_name = _to_text(flat.get(_FIELD_NAME))
    agency = _to_text(flat.get(_FIELD_AGENCY)) or None
    rule_no = _to_text(flat.get(_FIELD_RULE_NO)) or None

    title = rule_name or None
    display_title = title

    issued_at = _parse_date(flat.get(_FIELD_PROMULGATION_DATE)) or _parse_date(
        flat.get(_FIELD_EFFECTIVE_DATE)
    )
    effective_date_str = flat.get(_FIELD_EFFECTIVE_DATE)

    articles: list[dict | str] = flat.get(_FIELD_ARTICLES) or []
    article_texts: list[str] = []
    pending_headings: list[str] = []
    for article in articles:
        kind = _classify_article_entry(article)
        if kind == "heading":
            heading = _to_text(article)
            if heading:
                pending_headings.append(heading)
            continue

        text = _build_article_text(article)
        if not text:
            continue

        if pending_headings:
            article_texts.append("\n".join([*pending_headings, text]))
            pending_headings = []
        else:
            article_texts.append(text)
    addendum_text = _to_text(flat.get(_FIELD_ADDENDUM))

    # annex: 원문 대신 요약 텍스트만 body_text에 포함
    annex_raw = _to_text(flat.get(_FIELD_ANNEX))
    annex_type = classify_annex_text(annex_raw) if annex_raw else "plain_text"
    annex_summary = normalize_annex_for_rag(annex_raw, annex_type) if annex_raw else ""

    body_parts = article_texts + [addendum_text, annex_summary]
    body_text = "\n\n".join(p for p in body_parts if p)

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
        "rule"     — 조문 단위 (기존 유지)
        "addendum" — 부칙내용 (기존 유지)
        "annex"    — 별표: annex_formatter 통해 유형별 요약 텍스트, 최대 2개

    annex chunk metadata 추가 필드:
        annex_type:       "plain_text" | "table" | "flowchart" | "diagram_like"
        normalized_from:  "raw_annex"
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

    # ── 조문 chunk ────────────────────────────────────────────────────────────
    if articles:
        pending_headings: list[str] = []
        for article in articles:
            kind = _classify_article_entry(article)
            if kind == "heading":
                heading = _to_text(article)
                if heading:
                    pending_headings.append(heading)
                continue

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
                        section_title=_join_heading_context(
                            pending_headings, article_no
                        ),
                        metadata={
                            **base_meta,
                            "article_no": article_no or None,
                            "heading_context": pending_headings or None,
                        },
                    )
                )
                order += 1
            pending_headings = []
    else:
        # 조문 없을 때 — body_text에서 부칙/별표 요약 제외 부분을 단일 chunk
        addendum_text = _to_text(flat.get(_FIELD_ADDENDUM))
        annex_raw = _to_text(flat.get(_FIELD_ANNEX))
        annex_type = classify_annex_text(annex_raw) if annex_raw else "plain_text"
        annex_summary = (
            normalize_annex_for_rag(annex_raw, annex_type) if annex_raw else ""
        )

        remaining = doc.body_text
        if addendum_text:
            remaining = remaining.replace(addendum_text, "").strip()
        if annex_summary:
            remaining = remaining.replace(annex_summary, "").strip()

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

    # ── 부칙 chunk ────────────────────────────────────────────────────────────
    addendum = _to_text(flat.get(_FIELD_ADDENDUM))
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

    # ── 별표 chunk — 유형별 요약 텍스트, 최대 2개 ────────────────────────────
    annex_raw = _to_text(flat.get(_FIELD_ANNEX))
    if annex_raw:
        annex_parts, annex_type = build_annex_chunks_text(annex_raw)
        annex_meta = {
            **base_meta,
            "annex_type": annex_type,
            "normalized_from": "raw_annex",
        }
        for part in annex_parts:
            chunks.append(
                PlatformChunkSchema(
                    source_type="admin_rule",
                    external_id=doc.external_id,
                    chunk_type="annex",
                    chunk_order=order,
                    chunk_text=part,
                    section_title="별표",
                    metadata=annex_meta,
                )
            )
            order += 1

        if annex_parts:
            logger.debug(
                "[admin_rule mapper] annex chunk 생성: external_id=%s "
                "annex_type=%s chunks=%d",
                doc.external_id,
                annex_type,
                len(annex_parts),
            )

    return chunks
