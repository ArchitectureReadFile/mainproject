"""
domains/platform_sync/platform_knowledge_indexing_service.py

Platform Knowledge normalized document → DB 저장 + BM25/Qdrant 적재.

책임:
    - PlatformDocument DB upsert
    - PlatformDocumentChunk DB upsert
    - embed + Qdrant upsert
    - BM25 upsert

비책임:
    - API 호출 (→ PlatformKnowledgeIngestionService)
    - raw 저장 (→ PlatformRawSourceService)
    - normalize / chunk 생성 (→ PlatformDocumentNormalizeService)

BM25 / Qdrant 네임스페이스:
    platform knowledge chunk_id 형식:
        "platform:{source_type}:pd:{platform_document_id}:chunk:{chunk_order}"

    Qdrant payload 필드:
        chunk_id, platform_document_id, source_type, chunk_type,
        section_title, chunk_order, text,
        source_url, issued_at, agency (metadata에서 promote)

    BM25:
        platform corpus(bm25:pl:*)에만 적재한다.
        source_type 무관하게 platform_document_id 역인덱스만 관리한다.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from domains.platform_sync.schemas import PlatformChunkSchema, PlatformDocumentSchema
from domains.rag import bm25_store, vector_store
from domains.rag.embedding_service import embed_passages
from models.platform_knowledge import PlatformDocument, PlatformDocumentChunk

logger = logging.getLogger(__name__)

# platform chunk용 BM25 Redis 키 (기존 판례 네임스페이스와 분리)
_PL_DOCS_KEY = "bm25:pl:docs"
_PL_IDS_KEY = "bm25:pl:ids"
_PL_REV_KEY = "bm25:pl:rev"
_PL_PD_PREFIX = "bm25:pl:pd:"  # platform_document_id 역인덱스


class PlatformKnowledgeIndexingService:
    """
    normalized document + chunk → DB + BM25 + Qdrant 저장.

    index():
        PlatformDocumentSchema + list[PlatformChunkSchema]를 받아
        전체 저장 파이프라인을 실행한다.

    deindex():
        platform_document_id 기준으로 DB chunk + 벡터 + BM25를 모두 삭제한다.
    """

    def index(
        self,
        db: Session,
        doc: PlatformDocumentSchema,
        chunks: list[PlatformChunkSchema],
    ) -> tuple[PlatformDocument, int]:
        """
        저장 파이프라인 전체 실행.

        Returns:
            (PlatformDocument, 저장된 chunk 수)
        """
        # 1. PlatformDocument upsert
        pd = self._upsert_document(db, doc)

        if not chunks:
            logger.warning(
                "[PlatformIndexing] chunk 없음: source_type=%s external_id=%s",
                doc.source_type,
                doc.external_id,
            )
            return pd, 0

        # 2. 배치 임베딩을 먼저 완료한다.
        texts = [c.chunk_text for c in chunks]
        embeddings = embed_passages(texts)

        # 3. 새 인덱스 준비가 끝난 뒤 기존 인덱스 교체
        self._deindex_chunks(db, pd.id)

        # 4. chunk_id_str 생성 및 DB 저장
        db_chunks = self._upsert_chunks(db, pd, chunks)
        db.flush()

        # 5. Qdrant + BM25 적재
        for db_chunk, chunk, embedding in zip(db_chunks, chunks, embeddings):
            chunk_id = db_chunk.chunk_id_str
            payload = self._build_qdrant_payload(db_chunk, chunk)

            vector_store.upsert(
                chunk_id=chunk_id,
                embedding=embedding,
                payload=payload,
            )
            self._bm25_upsert(chunk_id, pd.id, chunk.chunk_text)

        logger.info(
            "[PlatformIndexing] 완료: source_type=%s external_id=%s pd_id=%s chunks=%d",
            doc.source_type,
            doc.external_id,
            pd.id,
            len(db_chunks),
        )
        return pd, len(db_chunks)

    def deindex(self, db: Session, platform_document_id: int) -> None:
        """platform_document_id 기준 DB chunk + 벡터 + BM25 전체 삭제."""
        self._deindex_chunks(db, platform_document_id)
        logger.info("[PlatformIndexing] deindex 완료: pd_id=%s", platform_document_id)

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _upsert_document(
        self, db: Session, doc: PlatformDocumentSchema
    ) -> PlatformDocument:
        existing: PlatformDocument | None = (
            db.query(PlatformDocument)
            .filter_by(source_type=doc.source_type, external_id=doc.external_id)
            .first()
        )

        issued_at_naive = None
        if doc.issued_at is not None:
            issued_at_naive = doc.issued_at.replace(tzinfo=None)

        meta_json = (
            json.dumps(doc.metadata, ensure_ascii=False) if doc.metadata else None
        )

        if existing is None:
            row = PlatformDocument(
                source_type=doc.source_type,
                external_id=doc.external_id,
                raw_source_id=doc.raw_payload_ref,
                title=doc.title,
                display_title=doc.display_title,
                body_text=doc.body_text,
                source_url=doc.source_url,
                issued_at=issued_at_naive,
                agency=doc.agency,
                status="active",
                metadata_json=meta_json,
            )
            db.add(row)
            db.flush()
            return row

        # 갱신
        existing.title = doc.title
        existing.display_title = doc.display_title
        existing.body_text = doc.body_text
        existing.source_url = doc.source_url
        existing.issued_at = issued_at_naive
        existing.agency = doc.agency
        existing.metadata_json = meta_json
        if doc.raw_payload_ref is not None:
            existing.raw_source_id = doc.raw_payload_ref
        db.flush()
        return existing

    def _upsert_chunks(
        self,
        db: Session,
        pd: PlatformDocument,
        chunks: list[PlatformChunkSchema],
    ) -> list[PlatformDocumentChunk]:
        rows: list[PlatformDocumentChunk] = []
        for chunk in chunks:
            chunk_id_str = (
                f"platform:{chunk.source_type}:pd:{pd.id}:chunk:{chunk.chunk_order}"
            )
            meta_json = (
                json.dumps(chunk.metadata, ensure_ascii=False)
                if chunk.metadata
                else None
            )
            row = PlatformDocumentChunk(
                platform_document_id=pd.id,
                source_type=chunk.source_type,
                chunk_type=chunk.chunk_type,
                chunk_order=chunk.chunk_order,
                section_title=chunk.section_title,
                chunk_text=chunk.chunk_text,
                chunk_id_str=chunk_id_str,
                metadata_json=meta_json,
            )
            db.add(row)
            rows.append(row)
        return rows

    def _deindex_chunks(self, db: Session, platform_document_id: int) -> None:
        """기존 DB chunk를 삭제하고 벡터·BM25 인덱스도 정리한다."""
        existing_chunks = (
            db.query(PlatformDocumentChunk)
            .filter_by(platform_document_id=platform_document_id)
            .all()
        )

        for chunk in existing_chunks:
            if chunk.chunk_id_str:
                # Qdrant: chunk_id_str 기반 삭제
                try:
                    from qdrant_client.http import models as qmodels

                    client = vector_store._get_client()
                    import hashlib

                    point_id = int(
                        hashlib.md5(chunk.chunk_id_str.encode()).hexdigest(), 16
                    ) % (2**63)
                    client.delete(
                        collection_name=vector_store.QDRANT_COLLECTION,
                        points_selector=qmodels.PointIdsList(points=[point_id]),
                    )
                except Exception:
                    logger.warning(
                        "[PlatformIndexing] Qdrant 삭제 실패: chunk_id=%s",
                        chunk.chunk_id_str,
                    )
                # BM25
                self._bm25_delete_chunk(chunk.chunk_id_str, platform_document_id)

            db.delete(chunk)

        if existing_chunks:
            db.flush()
            logger.debug(
                "[PlatformIndexing] 기존 chunk %d개 삭제: pd_id=%s",
                len(existing_chunks),
                platform_document_id,
            )

    def _build_qdrant_payload(
        self, db_chunk: PlatformDocumentChunk, chunk: PlatformChunkSchema
    ) -> dict:
        payload: dict = {
            "platform_document_id": db_chunk.platform_document_id,
            "source_type": chunk.source_type,
            "chunk_type": chunk.chunk_type,
            "section_title": chunk.section_title,
            "chunk_order": chunk.chunk_order,
            "text": chunk.chunk_text,
            # metadata에서 retrieval에 필요한 필드 promote
            "source_url": chunk.metadata.get("source_url"),
            "issued_at": chunk.metadata.get("issued_at"),
            "agency": chunk.metadata.get("agency"),
            "related_law_refs": chunk.metadata.get("related_law_refs"),
            "related_case_refs": chunk.metadata.get("related_case_refs"),
        }
        return {k: v for k, v in payload.items() if v is not None}

    # ── BM25 platform corpus 직접 조작 ────────────────────────────────────────

    def _bm25_upsert(self, chunk_id: str, platform_document_id: int, text: str) -> None:
        try:
            r = bm25_store._get_redis()
            if not r.hexists(_PL_DOCS_KEY, chunk_id):
                r.rpush(_PL_IDS_KEY, chunk_id)
            r.hset(_PL_DOCS_KEY, chunk_id, text)
            r.sadd(f"{_PL_PD_PREFIX}{platform_document_id}", chunk_id)
            r.incr(_PL_REV_KEY)
        except Exception:
            logger.exception(
                "[PlatformIndexing] BM25 upsert 실패: chunk_id=%s", chunk_id
            )

    def _bm25_delete_chunk(self, chunk_id: str, platform_document_id: int) -> None:
        try:
            r = bm25_store._get_redis()
            r.hdel(_PL_DOCS_KEY, chunk_id)
            r.lrem(_PL_IDS_KEY, 1, chunk_id)
            r.srem(f"{_PL_PD_PREFIX}{platform_document_id}", chunk_id)
            r.incr(_PL_REV_KEY)
        except Exception:
            logger.warning("[PlatformIndexing] BM25 삭제 실패: chunk_id=%s", chunk_id)
