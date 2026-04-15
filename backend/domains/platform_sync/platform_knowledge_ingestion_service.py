"""
domains/platform_sync/platform_knowledge_ingestion_service.py

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

external_id 계약:
    ingest_from_payload()에 전달된 external_id가 최종 canonical key이다.
    mapper가 raw payload에서 다른 ID(예: 법령ID)를 읽더라도
    최종 doc.external_id는 이 인자로 강제된다.
    mapper가 추출한 ID는 metadata(예: law_id)에 보존될 수 있다.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from domains.platform_sync.mappers.precedent_summary_fallback_mapper import (
    build_chunks_from_list_item,
    normalize_from_list_item,
)
from domains.platform_sync.platform_document_normalize_service import (
    PlatformDocumentNormalizeService,
)
from domains.platform_sync.platform_knowledge_indexing_service import (
    PlatformKnowledgeIndexingService,
)
from domains.platform_sync.platform_raw_source_service import PlatformRawSourceService
from domains.platform_sync.schemas import PlatformChunkSchema, PlatformDocumentSchema
from models.platform_knowledge import PlatformDocument
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

        external_id 계약:
            전달된 external_id가 최종 canonical key이다.
            normalize 후 doc.external_id를 이 값으로 강제한다.

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
            external_id:   공공 API 원본 고유 식별자 (canonical key)
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
            msg = (
                f"[Ingestion] normalize 실패 (raw는 보관됨): "
                f"source_type={source_type} external_id={external_id} — {exc}"
            )
            logger.error(msg)
            raise PlatformNormalizeError(msg) from exc

        # 2-1. external_id canonical 강제
        #      mapper가 raw payload 내 다른 ID(예: 법령ID)를 읽더라도
        #      최종 저장 키는 ingestion 인자(법령일련번호 등)로 통일한다.
        if doc.external_id != external_id:
            logger.debug(
                "[Ingestion] external_id 보정: mapper=%r → canonical=%r "
                "(source_type=%s)",
                doc.external_id,
                external_id,
                source_type,
            )
            # mapper가 추출한 ID는 metadata에 보존
            if doc.external_id:
                meta_key = f"{source_type}_id"
                doc.metadata[meta_key] = doc.external_id
            doc.external_id = external_id
            # chunk들도 동일하게 갱신
            for chunk in chunks:
                chunk.external_id = external_id

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

    def ingest_list_only(
        self,
        db: Session,
        *,
        source_type: str,
        external_id: str,
        list_item: dict,
        detail_fetch_error: str | None = None,
        data_source_name: str | None = None,
    ) -> tuple[PlatformDocument, int]:
        """
        목록 item만으로 list_only 문서를 생성/갱신한다.

        현재는 precedent source 전용 fallback 경로다.
        raw 저장소 추가 없이 normalized/chunk/index 레이어에만 적재한다.
        """
        if source_type != "precedent":
            raise PlatformNormalizeError(
                f"[Ingestion] ingest_list_only는 precedent 전용입니다: {source_type}"
            )

        if not is_ingestion_enabled(source_type):
            msg = (
                f"[Ingestion] source_type={source_type!r} 비활성 — "
                "ingestion이 활성화되지 않은 source_type입니다. "
                f"settings/platform.py의 ENABLE_INGESTION_{source_type.upper()}=true로 전환하세요."
            )
            logger.warning(msg)
            raise PlatformIngestionDisabledError(msg)

        try:
            doc: PlatformDocumentSchema = normalize_from_list_item(
                list_item,
                external_id=external_id,
                detail_fetch_error=detail_fetch_error,
                data_source_name=data_source_name,
            )
            chunks: list[PlatformChunkSchema] = build_chunks_from_list_item(
                doc, list_item
            )
        except ValueError as exc:
            msg = (
                f"[Ingestion] list_only normalize 실패: "
                f"source_type={source_type} external_id={external_id} — {exc}"
            )
            logger.error(msg)
            raise PlatformNormalizeError(msg) from exc

        if doc.external_id != external_id:
            if doc.external_id:
                doc.metadata[f"{source_type}_id"] = doc.external_id
            doc.external_id = external_id
            for chunk in chunks:
                chunk.external_id = external_id

        if not chunks:
            msg = (
                f"[Ingestion] list_only chunk 0개 — 성공으로 취급하지 않음: "
                f"source_type={source_type} external_id={external_id}"
            )
            logger.error(msg)
            raise PlatformNormalizeError(msg)

        pd, n_chunks = self._indexing_service.index(db, doc, chunks)
        logger.info(
            "[Ingestion] list_only 완료: source_type=%s external_id=%s chunks=%d",
            source_type,
            external_id,
            n_chunks,
        )
        return pd, n_chunks
