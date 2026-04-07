"""
services/platform/mappers/precedent_summary_fallback_mapper.py

판례(precedent) 목록 item 기반 기본 문서(list_only) 적재.

적용 대상:
    - 상세 API 응답이 "unsupported detail" 형태인 경우
      예: {"Law": "일치하는 판례가 없습니다. 판례명을 확인하여 주십시오."}
    - 데이터출처명 = 국세법령정보시스템 계열에서 많이 발생

원칙:
    - 목록 item 메타 기반으로 검색 가능한 summary 문서를 생성한다.
    - canonical external_id는 full 문서와 동일하게 목록의 판례일련번호를 사용한다.
    - chunk는 1~3개로 제한해 과도한 분할을 방지한다.
    - metadata.detail_mode = "list_only" 로 표시한다.

chunk 전략:
    chunk_type = "holding"  : 판시사항 (있는 경우)
    chunk_type = "summary"  : 판결요지 + 기본 메타 요약
    없으면 단일 "meta" chunk로 fallback
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from schemas.platform_knowledge_schema import (
    PlatformChunkSchema,
    PlatformDocumentSchema,
)


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip().replace("-", "").replace(".", "").replace(" ", "")
    try:
        return datetime.strptime(raw[:8], "%Y%m%d")
    except (ValueError, IndexError):
        return None


def normalize_from_list_item(
    list_item: dict[str, Any],
    *,
    external_id: str,
    detail_fetch_error: str | None = None,
    data_source_name: str | None = None,
) -> PlatformDocumentSchema:
    """
    목록 item 메타 기반으로 list_only PlatformDocumentSchema를 생성한다.

    Args:
        list_item:           목록 API 응답 item dict
        external_id:         canonical external_id (판례일련번호)
        detail_fetch_error:  상세 조회 실패 메시지 (운영 추적용)
        data_source_name:    데이터출처명 (있는 경우)

    Returns:
        PlatformDocumentSchema (detail_mode="list_only")
    """
    case_name: str = str(list_item.get("사건명") or "").strip()
    case_no: str = str(list_item.get("사건번호") or "").strip()
    court_name: str = str(list_item.get("법원명") or "").strip()
    case_type: str = str(list_item.get("사건종류명") or "").strip()
    judgment_type: str = str(list_item.get("판결유형") or "").strip()
    decision_date: str = str(list_item.get("선고일자") or "").strip()

    # 목록에서 직접 제공되는 요약 필드 (API에 따라 있을 수도 없을 수도 있음)
    holding: str = str(list_item.get("판시사항") or "").strip()
    summary: str = str(list_item.get("판결요지") or "").strip()
    ref_law: str = str(list_item.get("참조조문") or "").strip()
    ref_case: str = str(list_item.get("참조판례") or "").strip()

    title = case_name or None
    display_title = (
        f"{court_name} {case_no} {case_name}".strip()
        if court_name or case_no
        else case_name or None
    )

    issued_at = _parse_date(decision_date)
    agency = court_name or None

    # body_text: 검색 가능한 요약 텍스트 조립
    body_lines: list[str] = []
    if case_name:
        body_lines.append(f"사건명: {case_name}")
    if case_no:
        body_lines.append(f"사건번호: {case_no}")
    if court_name:
        body_lines.append(f"법원명: {court_name}")
    if decision_date:
        body_lines.append(f"선고일자: {decision_date}")
    if case_type:
        body_lines.append(f"사건종류: {case_type}")
    if judgment_type:
        body_lines.append(f"판결유형: {judgment_type}")
    if holding:
        body_lines.append(f"\n판시사항:\n{holding}")
    if summary:
        body_lines.append(f"\n판결요지:\n{summary}")
    if ref_law:
        body_lines.append(f"\n참조조문: {ref_law}")
    if ref_case:
        body_lines.append(f"\n참조판례: {ref_case}")

    body_text = "\n".join(body_lines).strip()

    related_law_refs = (
        [r.strip() for r in ref_law.split(",") if r.strip()] if ref_law else []
    )
    related_case_refs = (
        [r.strip() for r in ref_case.split(",") if r.strip()] if ref_case else []
    )

    metadata: dict[str, Any] = {
        "detail_mode": "list_only",
        "detail_fetch_supported": False,
        "detail_fetch_error_message": detail_fetch_error or None,
        "data_source_name": data_source_name or list_item.get("데이터출처명") or None,
        "case_no": case_no or None,
        "court_name": court_name or None,
        "decision_date": decision_date or None,
        "judgment_type": judgment_type or None,
        "case_type_name": case_type or None,
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


def build_chunks_from_list_item(
    doc: PlatformDocumentSchema,
    list_item: dict[str, Any],
) -> list[PlatformChunkSchema]:
    """
    list_only PlatformDocumentSchema로부터 chunk를 생성한다.

    chunk 전략 (최대 3개):
        1. "holding"  : 판시사항이 있는 경우
        2. "summary"  : 판결요지가 있는 경우
        3. "meta"     : 위 둘 모두 없으면 기본 메타 요약 단일 chunk
    """
    chunks: list[PlatformChunkSchema] = []
    order = 0

    base_meta: dict[str, Any] = {
        "source_url": doc.source_url,
        "issued_at": doc.issued_at.isoformat() if doc.issued_at else None,
        "agency": doc.agency,
        "detail_mode": "list_only",
        "related_law_refs": doc.metadata.get("related_law_refs"),
        "related_case_refs": doc.metadata.get("related_case_refs"),
    }

    holding = str(list_item.get("판시사항") or "").strip()
    summary = str(list_item.get("판결요지") or "").strip()

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

    # holding/summary 모두 없으면 body_text 전체를 meta chunk 1개로
    if not chunks and doc.body_text:
        chunks.append(
            PlatformChunkSchema(
                source_type="precedent",
                external_id=doc.external_id,
                chunk_type="meta",
                chunk_order=order,
                chunk_text=doc.body_text,
                section_title="판례 요약",
                metadata=base_meta,
            )
        )

    return chunks
