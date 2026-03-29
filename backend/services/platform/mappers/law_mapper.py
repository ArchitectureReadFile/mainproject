"""
services/platform/mappers/law_mapper.py

국가법령정보 현행법령 API 응답 → PlatformDocumentSchema 정규화.

공식 API 필드 기준:
    법령ID, 법령명_한글, 법령명약칭, 소관부처명
    공포일자, 공포번호, 시행일자
    조문번호, 조문제목, 조문내용, 항내용, 호내용, 목내용
    부칙내용, 별표내용, 제개정이유내용

body_text 조립 순서:
    조문(조문번호 + 조문제목 + 조문내용 + 항/호/목 내용)
    → 부칙내용 → 별표내용 → 제개정이유내용

chunk 전략:
    chunk_type = "article"
    조문 단위 분리. 조문이 없을 때 전체 body_text를 단일 chunk로.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from schemas.platform_knowledge_schema import (
    PlatformChunkSchema,
    PlatformDocumentSchema,
)

_PROVIDER = "korea_law_open_api"
_API_TARGET = "eflaw"
_MAX_CHUNK_CHARS = 1500
_OVERLAP_CHARS = 150


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip().replace("-", "").replace(".", "")
    try:
        return datetime.strptime(raw[:8], "%Y%m%d")
    except (ValueError, IndexError):
        return None


def _join_nonempty(*parts: str | None, sep: str = "\n") -> str:
    return sep.join(p.strip() for p in parts if p and p.strip())


def _build_article_text(article: dict) -> str:
    """조문 하나를 텍스트로 직렬화."""
    lines: list[str] = []
    no = article.get("조문번호") or ""
    title = article.get("조문제목") or ""
    if no or title:
        lines.append(f"제{no}조 {title}".strip())
    if article.get("조문내용"):
        lines.append(article["조문내용"].strip())
    for key in ("항내용", "호내용", "목내용"):
        val = article.get(key)
        if val:
            lines.append(val.strip())
    return "\n".join(lines).strip()


def _split_by_length(text: str, *, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + max_chars])
        start += max_chars - overlap
    return chunks


def normalize(raw_payload: dict) -> PlatformDocumentSchema:
    """
    국가법령정보 현행법령 API 응답 dict → PlatformDocumentSchema.

    raw_payload 최상위 구조 가정:
        {
            "법령ID": "...",
            "법령명_한글": "...",
            "법령명약칭": "...",
            "소관부처명": "...",
            "공포일자": "20240101",
            "공포번호": "...",
            "시행일자": "20240101",
            "조문": [...],          # 조문 목록
            "부칙내용": "...",
            "별표내용": "...",
            "제개정이유내용": "...",
        }
    """
    external_id: str = str(raw_payload.get("법령ID") or "")
    title: str = raw_payload.get("법령명_한글") or ""
    short_name: str = raw_payload.get("법령명약칭") or ""
    agency: str = raw_payload.get("소관부처명") or ""

    display_title = f"{title}({short_name})" if short_name else title

    issued_at = _parse_date(raw_payload.get("시행일자")) or _parse_date(
        raw_payload.get("공포일자")
    )

    # body_text 조립
    articles: list[dict] = raw_payload.get("조문") or []
    article_texts = [_build_article_text(a) for a in articles if _build_article_text(a)]
    body_parts = article_texts + [
        raw_payload.get("부칙내용") or "",
        raw_payload.get("별표내용") or "",
        raw_payload.get("제개정이유내용") or "",
    ]
    body_text = "\n\n".join(p.strip() for p in body_parts if p.strip())

    metadata: dict[str, Any] = {
        "promulgation_date": raw_payload.get("공포일자"),
        "promulgation_no": raw_payload.get("공포번호"),
        "law_name_short": short_name or None,
    }

    return PlatformDocumentSchema(
        source_type="law",
        external_id=external_id,
        title=title or None,
        display_title=display_title or None,
        body_text=body_text,
        issued_at=issued_at,
        agency=agency or None,
        metadata=metadata,
    )


def build_chunks(
    doc: PlatformDocumentSchema, raw_payload: dict
) -> list[PlatformChunkSchema]:
    """
    조문 단위 chunk 생성.

    조문 목록이 없을 때는 body_text 전체를 단일 chunk로.
    """
    articles: list[dict] = raw_payload.get("조문") or []
    chunks: list[PlatformChunkSchema] = []
    order = 0

    if articles:
        for article in articles:
            text = _build_article_text(article)
            if not text:
                continue
            article_no = str(article.get("조문번호") or "")
            section_title = article.get("조문제목") or None

            for part in _split_by_length(
                text, max_chars=_MAX_CHUNK_CHARS, overlap=_OVERLAP_CHARS
            ):
                chunks.append(
                    PlatformChunkSchema(
                        source_type="law",
                        external_id=doc.external_id,
                        chunk_type="article",
                        chunk_order=order,
                        chunk_text=part,
                        section_title=section_title,
                        metadata={
                            "article_no": article_no or None,
                            "source_url": doc.source_url,
                            "issued_at": doc.issued_at.isoformat()
                            if doc.issued_at
                            else None,
                            "agency": doc.agency,
                        },
                    )
                )
                order += 1
    else:
        # 조문 없을 때 — body_text 전체를 단일 chunk
        for part in _split_by_length(
            doc.body_text, max_chars=_MAX_CHUNK_CHARS, overlap=_OVERLAP_CHARS
        ):
            chunks.append(
                PlatformChunkSchema(
                    source_type="law",
                    external_id=doc.external_id,
                    chunk_type="article",
                    chunk_order=order,
                    chunk_text=part,
                    metadata={
                        "source_url": doc.source_url,
                        "issued_at": doc.issued_at.isoformat()
                        if doc.issued_at
                        else None,
                        "agency": doc.agency,
                    },
                )
            )
            order += 1

    return chunks
