"""
domains/platform_sync/mappers/interpretation_mapper.py

국가법령정보 법령해석례 API 응답 → PlatformDocumentSchema 정규화.

공식 API 필드 (목록):
    법령해석례일련번호, 안건명, 안건번호, 질의기관명, 회신기관명, 회신일자
    법령해석례상세링크

공식 API 필드 (상세):
    질의요지, 회답, 이유

body_text 조립 순서:
    질의요지 → 회답 → 이유

chunk 전략:
    chunk_type = "question" : 질의요지
    chunk_type = "answer"   : 회답
    chunk_type = "reason"   : 이유

title 예시:
    법제처 21-0913 근로기준법 제74조제5항 관련
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from domains.platform_sync.schemas import PlatformChunkSchema, PlatformDocumentSchema

logger = logging.getLogger(__name__)

_MAX_CHUNK_CHARS = 1500
_OVERLAP_CHARS = 150

# ── 상세 API 필드명 상수 (확인 완료) ─────────────────────────────────────────
_FIELD_QUESTION = "질의요지"
_FIELD_ANSWER = "회답"
_FIELD_REASON = "이유"
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

    실패 조건:
        - 법령해석례일련번호 없음 → external_id 없음
        - 안건명 없음 → title 없음
        - 질의요지 / 회답 / 이유 모두 없음 → body_text가 비게 됨

    Raises:
        ValueError: validation 실패 시.
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
            f"body 필드({_FIELD_QUESTION}/{_FIELD_ANSWER}/{_FIELD_REASON}) 모두 없음"
        )

    if errors:
        msg = "[interpretation mapper] validate_payload 실패: " + "; ".join(errors)
        logger.error(msg)
        raise ValueError(msg)


def normalize(raw_payload: dict) -> PlatformDocumentSchema:
    """
    국가법령정보 법령해석례 API 응답 dict → PlatformDocumentSchema.

    raw_payload 최상위 구조:
        {
            "법령해석례일련번호": "...",
            "안건명": "...",
            "안건번호": "...",
            "질의기관명": "...",
            "회신기관명": "...",
            "회신일자": "20240101",
            "법령해석례상세링크": "...",
            "질의요지": "...",
            "회답": "...",
            "이유": "...",
        }
    """
    validate_payload(raw_payload)

    external_id = str(raw_payload.get("법령해석례일련번호") or "")
    agenda_name = raw_payload.get("안건명") or ""
    agenda_no = raw_payload.get("안건번호") or ""

    title = agenda_name or None
    # title 예시: "법제처 21-0913 근로기준법 제74조제5항 관련"
    responder = raw_payload.get("회신기관명") or ""
    if responder and agenda_no:
        display_title = f"{responder} {agenda_no} {agenda_name}".strip()
    elif agenda_no:
        display_title = f"{agenda_name} {agenda_no}".strip()
    else:
        display_title = agenda_name or None

    issued_at = _parse_date(raw_payload.get("회신일자"))
    agency = responder or None
    source_url = raw_payload.get("법령해석례상세링크") or None

    question = (raw_payload.get(_FIELD_QUESTION) or "").strip()
    answer = (raw_payload.get(_FIELD_ANSWER) or "").strip()
    reason = (raw_payload.get(_FIELD_REASON) or "").strip()
    body_text = "\n\n".join(p for p in (question, answer, reason) if p)

    metadata: dict[str, Any] = {
        "agenda_no": agenda_no or None,
        "query_org": raw_payload.get("질의기관명") or None,
        "responder_name": responder or None,
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
    """질의요지 / 회답 / 이유 3-way chunk 생성."""
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
        (_FIELD_QUESTION, "question", "질의요지"),
        (_FIELD_ANSWER, "answer", "회답"),
        (_FIELD_REASON, "reason", "이유"),
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
