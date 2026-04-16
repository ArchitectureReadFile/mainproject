"""
domains/platform_sync/platform_document_normalize_service.py

공공 API raw payload → PlatformDocumentSchema + PlatformChunkSchema 정규화.

책임:
    - source_type 기반 mapper 분기
    - PlatformDocumentSchema 반환
    - PlatformChunkSchema 리스트 반환

비책임:
    - DB 저장 (→ PlatformKnowledgeIndexingService)
    - API 호출 (→ PlatformKnowledgeIngestionService)
    - 임베딩 / BM25 적재 (→ PlatformKnowledgeIndexingService)
"""

from __future__ import annotations

import json
import logging

from domains.platform_sync.mappers import (
    admin_rule_mapper,
    interpretation_mapper,
    law_mapper,
    precedent_mapper,
)
from domains.platform_sync.schemas import PlatformChunkSchema, PlatformDocumentSchema

logger = logging.getLogger(__name__)

_MAPPER_MAP = {
    "law": law_mapper,
    "precedent": precedent_mapper,
    "interpretation": interpretation_mapper,
    "admin_rule": admin_rule_mapper,
}


class PlatformDocumentNormalizeService:
    """
    source_type → mapper 분기 후 PlatformDocumentSchema 반환.

    normalize():
        raw_payload dict 또는 JSON 문자열을 받아 정규화 결과를 반환.
        raw_source_id가 있으면 schema.raw_payload_ref에 주입.

    normalize_and_chunk():
        normalize() + mapper.build_chunks() 까지 한 번에 처리.
        indexing service에서 주로 이 메서드를 사용한다.
    """

    def normalize(
        self,
        source_type: str,
        raw_payload: dict | str,
        *,
        raw_source_id: int | None = None,
    ) -> PlatformDocumentSchema:
        mapper = _MAPPER_MAP.get(source_type)
        if mapper is None:
            raise ValueError(
                f"[NormalizeService] 지원하지 않는 source_type: {source_type!r}"
            )

        if isinstance(raw_payload, str):
            raw_payload = json.loads(raw_payload)

        doc = mapper.normalize(raw_payload)
        doc.raw_payload_ref = raw_source_id
        return doc

    def build_chunks(
        self,
        doc: PlatformDocumentSchema,
        raw_payload: dict | str,
    ) -> list[PlatformChunkSchema]:
        mapper = _MAPPER_MAP.get(doc.source_type)
        if mapper is None:
            raise ValueError(
                f"[NormalizeService] 지원하지 않는 source_type: {doc.source_type!r}"
            )

        if isinstance(raw_payload, str):
            raw_payload = json.loads(raw_payload)

        return mapper.build_chunks(doc, raw_payload)

    def normalize_and_chunk(
        self,
        source_type: str,
        raw_payload: dict | str,
        *,
        raw_source_id: int | None = None,
    ) -> tuple[PlatformDocumentSchema, list[PlatformChunkSchema]]:
        """
        정규화 + chunk 생성을 한 번에 처리.

        반환:
            (PlatformDocumentSchema, list[PlatformChunkSchema])
        """
        if isinstance(raw_payload, str):
            raw_payload = json.loads(raw_payload)

        doc = self.normalize(source_type, raw_payload, raw_source_id=raw_source_id)
        chunks = self.build_chunks(doc, raw_payload)

        logger.debug(
            "[NormalizeService] source_type=%s external_id=%s chunks=%d",
            source_type,
            doc.external_id,
            len(chunks),
        )
        return doc, chunks
