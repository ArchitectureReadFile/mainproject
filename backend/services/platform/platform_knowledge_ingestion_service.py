"""
services/platform/platform_knowledge_ingestion_service.py

공공 API 호출 → raw 저장 → normalize → chunk → index orchestration.

실패 정책:
    - raw 저장은 항상 유지 (재처리 기준)
    - normalize 실패(ValueError) → document/chunk/index 중단, 예외 상위 전파
    - chunk 0개 → 성공으로 취급하지 않음, ValueError 발생
    - "빈 chunk 0개로 성공" 경로 없음

source_type 활성화 flag:
    settings/platform.py의 is_ingestion_enabled() 기반.
    비활성 source_type이 들어오면 raw 저장 없이 즉시 차단.

지원 범위:
    law:            활성
    precedent:      활성 (migration flag로 corpus 전환 관리)
    interpretation: 활성
    admin_rule:     활성
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from models.platform_knowledge import PlatformDocument
from services.platform.platform_document_normalize_service import (
    PlatformDocumentNormalizeService,
)
from services.platform.platform_knowledge_indexing_service import (
    PlatformKnowledgeIndexingService,
)
from services.platform.platform_raw_source_service import PlatformRawSourceService
from settings.platform import is_ingestion_enabled

logger = logging.getLogger(__name__)

_PROVIDER = "korea_law_open_api"

_API_TARGET_MAP: dict[str, str] = {
    "law": "eflaw",
    "precedent": "prec",
    "interpretation": "expc",
    "admin_rule": "admrul",
}


class PlatformIngestionDisabledError(Exception):
    """source_type ingestion이 비활성화된 경우."""


class PlatformNormalizeError(Exception):
    """normalize 또는 chunk validation 실패."""


class PlatformKnowledgeIngestionService:
    """
    단일 문서 ingestion orchestrator.

    ingest_from_payload():
        raw_payload를 받아 저장 파이프라인 전체를 실행한다.

        Raises:
            PlatformIngestionDisabledError: source_type이 비활성화된 경우
            PlatformNormalizeError:         normalize / chunk validation 실패
    """

    def __init__(self) -> None:
        self._raw_service = PlatformRawSourceService()
        self._normalize_service = PlatformDocumentNormalizeService()
        self._indexing_service = PlatformKnowledgeIndexingService()

    def ingest_from_payload(
        self,
        db: Session,
        *,
        source_type: str,
        external_id: str,
        raw_payload: dict | str,
        raw_format: str = "json",
        force_reindex: bool = False,
    ) -> tuple[PlatformDocument, int]:
        """
        raw_payload를 받아 저장 파이프라인 전체를 실행한다.

        Args:
            db:            SQLAlchemy session
            source_type:   "law" | "precedent" | "interpretation" | "admin_rule"
            external_id:   공공 API 원본 고유 식별자
            raw_payload:   API 응답 dict 또는 JSON 문자열
            raw_format:    "json" | "xml"
            force_reindex: True이면 checksum 동일해도 재인덱싱 실행

        Returns:
            (PlatformDocument, 저장된 chunk 수)

        Raises:
            PlatformIngestionDisabledError: 비활성 source_type
            PlatformNormalizeError:         normalize/chunk 실패
        """
        # 0. source_type 활성화 확인 (raw 저장 전에 차단)
        if not is_ingestion_enabled(source_type):
            msg = (
                f"[Ingestion] source_type={source_type!r} 비활성 — "
                "ingestion이 활성화되지 않은 source_type입니다. "
                f"settings/platform.py의 ENABLE_INGESTION_{source_type.upper()}=true로 전환하세요."
            )
            logger.warning(msg)
            raise PlatformIngestionDisabledError(msg)

        api_target = _API_TARGET_MAP.get(source_type, source_type)

        # 1. raw 보관 (항상 유지)
        raw_row, changed = self._raw_service.upsert(
            db,
            source_type=source_type,
            provider=_PROVIDER,
            api_target=api_target,
            external_id=external_id,
            raw_format=raw_format,
            raw_payload=raw_payload,
        )

        if not changed and not force_reindex:
            logger.debug(
                "[Ingestion] no-op (checksum 동일): source_type=%s external_id=%s",
                source_type,
                external_id,
            )
            existing = (
                db.query(PlatformDocument)
                .filter_by(source_type=source_type, external_id=external_id)
                .first()
            )
            if existing:
                return existing, 0
            logger.info(
                "[Ingestion] raw는 있으나 document 없음, 정규화 진행: %s %s",
                source_type,
                external_id,
            )

        # 2. normalize + chunk 생성
        try:
            doc, chunks = self._normalize_service.normalize_and_chunk(
                source_type,
                raw_payload,
                raw_source_id=raw_row.id,
            )
        except ValueError as exc:
            # raw는 이미 저장됨 — normalize 실패는 명시적으로 올린다
            msg = (
                f"[Ingestion] normalize 실패 (raw는 보관됨): "
                f"source_type={source_type} external_id={external_id} — {exc}"
            )
            logger.error(msg)
            raise PlatformNormalizeError(msg) from exc

        # 3. chunk 0개 → 성공으로 취급하지 않음
        if not chunks:
            msg = (
                f"[Ingestion] chunk 0개 — 성공으로 취급하지 않음: "
                f"source_type={source_type} external_id={external_id}. "
                "raw는 보관됨. normalize 결과는 있으나 chunk가 비어 있습니다."
            )
            logger.error(msg)
            raise PlatformNormalizeError(msg)

        # 4. DB + 벡터 저장
        pd, n_chunks = self._indexing_service.index(db, doc, chunks)

        logger.info(
            "[Ingestion] 완료: source_type=%s external_id=%s chunks=%d",
            source_type,
            external_id,
            n_chunks,
        )
        return pd, n_chunks

    def deindex(self, db: Session, *, source_type: str, external_id: str) -> None:
        """
        external_id 기준으로 platform_document + chunk + 벡터 인덱스를 삭제한다.
        raw source는 보존한다.
        """
        pd = (
            db.query(PlatformDocument)
            .filter_by(source_type=source_type, external_id=external_id)
            .first()
        )
        if pd is None:
            logger.warning(
                "[Ingestion] deindex: document 없음 source_type=%s external_id=%s",
                source_type,
                external_id,
            )
            return

        self._indexing_service.deindex(db, pd.id)
        db.delete(pd)
        db.flush()
        logger.info(
            "[Ingestion] deindex 완료: source_type=%s external_id=%s pd_id=%s",
            source_type,
            external_id,
            pd.id,
        )
