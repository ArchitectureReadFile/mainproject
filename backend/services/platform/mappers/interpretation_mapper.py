"""
services/platform/mappers/interpretation_mapper.py

국가법령정보 법령해석례 API 응답 → PlatformDocumentSchema 정규화.

━━━ 현재 상태: 구조 검증 전 fail-closed ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
상세 API 필드명이 확정되지 않은 placeholder 상수(_FIELD_QUESTION 등) 기반이다.
실제 응답 구조가 다를 경우 body_text가 비는 "가짜 성공"이 발생할 수 있으므로,
아래 required-field validation을 통해 명시적 실패로 막는다.

실제 상세 API 응답을 수신한 후:
    1. _FIELD_QUESTION / _FIELD_ANSWER / _FIELD_REASON 상수를 실제 필드명으로 교체
    2. validate_payload()의 검증 기준도 함께 갱신
    3. settings/platform.py의 ENABLE_INGESTION_INTERPRETATION=true로 전환
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

공식 목록 API 필드:
    법령해석례일련번호, 안건명, 안건번호, 질의기관명, 회신기관명, 회신일자
    법령해석례상세링크

상세 API 필드 (미확정 — 아래 상수를 실제 필드명으로 교체):
    _FIELD_QUESTION → chunk_type="question"
    _FIELD_ANSWER   → chunk_type="answer"
    _FIELD_REASON   → chunk_type="reason"
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

# ── 상세 API 필드명 상수 (실제 응답 수신 후 이 블록만 교체) ─────────────────────
# WARNING: 이 필드명은 placeholder다. 실제 API 응답과 다를 수 있다.
_FIELD_QUESTION = "질의내용"
_FIELD_ANSWER = "회신내용"
_FIELD_REASON = "이유내용"
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


def validate_payload(raw_payload: dict) -> None:
    """
    interpretation payload required-field validation.

    실패 조건 (placeholder mapper이므로 더 엄격히 검증):
        - 법령해석례일련번호 없음 → external_id 없음
        - 안건명 없음 → title 없음
        - 질의내용 / 회신내용 / 이유내용 모두 없음 → body_text가 비게 됨

    주의:
        이 필드명은 placeholder 상수 기반이다.
        실제 응답 수신 후 _FIELD_* 상수와 함께 이 검증 기준도 갱신해야 한다.

    Raises:
        ValueError: validation 실패 시. 메시지에 "placeholder mapper" 컨텍스트 포함.
    """
    errors: list[str] = []

    external_id = str(raw_payload.get("법령해석례일련번호") or "").strip()
    if not external_id:
        errors.append("법령해석례일련번호(external_id) 누락")

    title = (raw_payload.get("안건명") or "").strip()
    if not title:
        errors.append("안건명(title) 누락")

    has_body = any(
        (raw_payload.get(f) or "").strip()
        for f in (_FIELD_QUESTION, _FIELD_ANSWER, _FIELD_REASON)
    )
    if not has_body:
        errors.append(
            f"body 필드({_FIELD_QUESTION}/{_FIELD_ANSWER}/{_FIELD_REASON}) 모두 없음 — "
            "실제 상세 필드 확인 전 placeholder mapper. "
            "API 응답 구조 확인 후 _FIELD_* 상수를 교체하고 ENABLE_INGESTION_INTERPRETATION=true로 전환하세요."
        )

    if errors:
        msg = (
            "[interpretation mapper] validate_payload 실패 (placeholder mapper 미검증 상태): "
            + "; ".join(errors)
        )
        logger.error(msg)
        raise ValueError(msg)


def normalize(raw_payload: dict) -> PlatformDocumentSchema:
    """
    국가법령정보 법령해석례 API 응답 dict → PlatformDocumentSchema.

    validate_payload()를 먼저 실행한다.
    검증 실패 시 ValueError를 발생시켜 indexing으로 진행하지 않는다.
    """
    validate_payload(raw_payload)

    external_id = str(raw_payload.get("법령해석례일련번호") or "")
    agenda_name = raw_payload.get("안건명") or ""
    agenda_no = raw_payload.get("안건번호") or ""

    title = agenda_name or None
    display_title = (
        f"{agenda_name} {agenda_no}".strip() if agenda_no else agenda_name or None
    )

    issued_at = _parse_date(raw_payload.get("회신일자"))
    agency = raw_payload.get("회신기관명") or None
    source_url = raw_payload.get("법령해석례상세링크") or None

    question = (raw_payload.get(_FIELD_QUESTION) or "").strip()
    answer = (raw_payload.get(_FIELD_ANSWER) or "").strip()
    reason = (raw_payload.get(_FIELD_REASON) or "").strip()
    body_text = "\n\n".join(p for p in (question, answer, reason) if p)

    metadata: dict[str, Any] = {
        "agenda_no": agenda_no or None,
        "query_org": raw_payload.get("질의기관명") or None,
        "source_url": source_url,
    }

    return PlatformDocumentSchema(
        source_type="interpretation",
        external_id=external_id,
        title=title,
        display_title=display_title,
        body_text=body_text,
        source_url=source_url,
        issued_at=issued_at,
        agency=agency,
        metadata=metadata,
    )


def build_chunks(
    doc: PlatformDocumentSchema, raw_payload: dict
) -> list[PlatformChunkSchema]:
    """질의내용 / 회신내용 / 이유내용 3-way chunk 생성."""
    chunks: list[PlatformChunkSchema] = []
    order = 0

    base_meta: dict[str, Any] = {
        "source_url": doc.source_url,
        "issued_at": doc.issued_at.isoformat() if doc.issued_at else None,
        "agency": doc.agency,
        "agenda_no": doc.metadata.get("agenda_no"),
        "query_org": doc.metadata.get("query_org"),
    }

    spec: list[tuple[str, str, str]] = [
        (_FIELD_QUESTION, "question", "질의내용"),
        (_FIELD_ANSWER, "answer", "회신내용"),
        (_FIELD_REASON, "reason", "이유내용"),
    ]

    for field_key, chunk_type, section_title in spec:
        text = (raw_payload.get(field_key) or "").strip()
        if not text:
            continue
        for part in _split_by_length(
            text, max_chars=_MAX_CHUNK_CHARS, overlap=_OVERLAP_CHARS
        ):
            chunks.append(
                PlatformChunkSchema(
                    source_type="interpretation",
                    external_id=doc.external_id,
                    chunk_type=chunk_type,
                    chunk_order=order,
                    chunk_text=part,
                    section_title=section_title,
                    metadata=base_meta,
                )
            )
            order += 1

    return chunks
