"""
services/platform/mappers/precedent_mapper.py

국가법령정보 판례 API 응답 → PlatformDocumentSchema 정규화.

공식 API 필드 기준:
    판례정보일련번호, 사건명, 사건번호, 선고일자, 법원명
    사건종류명, 판결유형, 판시사항, 판결요지, 참조조문, 참조판례, 판례내용

body_text 조립 순서:
    판시사항 → 판결요지 → 판례내용

chunk 전략:
    chunk_type = "holding"  : 판시사항
    chunk_type = "summary"  : 판결요지
    chunk_type = "body"     : 판례내용 (길이 분할)

기존 Precedent 모델 / chunk_builder.py 와의 관계:
    - 기존 코드는 그대로 유지.
    - 이 mapper는 platform knowledge ingestion 경로 전용.
    - 신규 수집분은 PlatformDocument로 적재, 기존 Precedent는 deprecated 방향.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from schemas.platform_knowledge_schema import (
    PlatformChunkSchema,
    PlatformDocumentSchema,
)

_MAX_CHUNK_CHARS = 1200
_OVERLAP_CHARS = 150


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


def normalize(raw_payload: dict) -> PlatformDocumentSchema:
    """
    국가법령정보 판례 API 응답 dict → PlatformDocumentSchema.

    raw_payload 최상위 구조 가정:
        {
            "판례정보일련번호": "...",
            "사건명": "...",
            "사건번호": "...",
            "선고일자": "20240101",
            "법원명": "...",
            "사건종류명": "...",
            "판결유형": "...",
            "판시사항": "...",
            "판결요지": "...",
            "참조조문": "...",
            "참조판례": "...",
            "판례내용": "...",
        }
    """
    external_id = str(raw_payload.get("판례정보일련번호") or "")
    case_name = raw_payload.get("사건명") or ""
    case_no = raw_payload.get("사건번호") or ""

    title = case_name or None
    display_title = f"{case_name} {case_no}".strip() if case_no else case_name or None

    issued_at = _parse_date(raw_payload.get("선고일자"))
    agency = raw_payload.get("법원명") or None

    holding = (raw_payload.get("판시사항") or "").strip()
    summary = (raw_payload.get("판결요지") or "").strip()
    body = (raw_payload.get("판례내용") or "").strip()
    body_text = "\n\n".join(p for p in (holding, summary, body) if p)

    related_law_refs: list[str] = []
    if raw_payload.get("참조조문"):
        related_law_refs = [
            r.strip() for r in str(raw_payload["참조조문"]).split(",") if r.strip()
        ]

    related_case_refs: list[str] = []
    if raw_payload.get("참조판례"):
        related_case_refs = [
            r.strip() for r in str(raw_payload["참조판례"]).split(",") if r.strip()
        ]

    metadata: dict[str, Any] = {
        "case_no": case_no or None,
        "case_type": raw_payload.get("사건종류명") or None,
        "judgment_type": raw_payload.get("판결유형") or None,
        "related_law_refs": related_law_refs or None,
        "related_case_refs": related_case_refs or None,
    }

    return PlatformDocumentSchema(
        source_type="precedent",
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
    판시사항 / 판결요지 / 판례내용 3-way chunk 생성.
    """
    chunks: list[PlatformChunkSchema] = []
    order = 0

    base_meta: dict[str, Any] = {
        "source_url": doc.source_url,
        "issued_at": doc.issued_at.isoformat() if doc.issued_at else None,
        "agency": doc.agency,
        "related_law_refs": doc.metadata.get("related_law_refs"),
        "related_case_refs": doc.metadata.get("related_case_refs"),
    }

    # holding
    holding = (raw_payload.get("판시사항") or "").strip()
    if holding:
        chunks.append(
            PlatformChunkSchema(
                source_type="precedent",
                external_id=doc.external_id,
                chunk_type="holding",
                chunk_order=order,
                chunk_text=holding,
                section_title="판시사항",
                metadata=base_meta,
            )
        )
        order += 1

    # summary
    summary = (raw_payload.get("판결요지") or "").strip()
    if summary:
        chunks.append(
            PlatformChunkSchema(
                source_type="precedent",
                external_id=doc.external_id,
                chunk_type="summary",
                chunk_order=order,
                chunk_text=summary,
                section_title="판결요지",
                metadata=base_meta,
            )
        )
        order += 1

    # body (길이 분할)
    body = (raw_payload.get("판례내용") or "").strip()
    if body:
        for part in _split_by_length(
            body, max_chars=_MAX_CHUNK_CHARS, overlap=_OVERLAP_CHARS
        ):
            chunks.append(
                PlatformChunkSchema(
                    source_type="precedent",
                    external_id=doc.external_id,
                    chunk_type="body",
                    chunk_order=order,
                    chunk_text=part,
                    section_title="판례내용",
                    metadata=base_meta,
                )
            )
            order += 1

    return chunks
