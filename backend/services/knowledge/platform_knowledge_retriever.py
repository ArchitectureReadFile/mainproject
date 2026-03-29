"""
services/knowledge/platform_knowledge_retriever.py

Platform 지식원 retriever.

━━━ Migration 단계 정책 (settings/platform.py 참조) ━━━━━━━━━━━━━━━━━━━━━━━━
ENABLE_PLATFORM_PRECEDENT_CORPUS=false (기본):
    A. 기존 precedent corpus  → 판례 검색
    B. platform corpus        → source_type="precedent" 제외 ["law", "interpretation", "admin_rule"]

ENABLE_PLATFORM_PRECEDENT_CORPUS=true (migration 완료 후):
    A. 기존 precedent corpus  → 비활성화
    B. platform corpus        → 모든 source_type 포함 ["law", "precedent", "interpretation", "admin_rule"]

"둘 다 검색 후 dedupe" 방식은 사용하지 않는다.
source_id 체계가 달라 dedupe 키가 충돌 없이 통과해 중복 반환 위험이 있다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import logging

from schemas.knowledge import KnowledgeRetrievalRequest, RetrievedKnowledgeItem
from schemas.search import SearchMode
from services.rag import bm25_store, vector_store
from services.rag.embedding_service import embed_query
from services.rag.retrieval_service import retrieve_precedents
from settings.platform import (
    ENABLE_PLATFORM_PRECEDENT_CORPUS,
    get_platform_corpus_source_types,
)

logger = logging.getLogger(__name__)

_PRECEDENT_META_FIELDS = (
    "source_url",
    "case_number",
    "case_name",
    "court_name",
    "judgment_date",
    "plaintiff",
    "defendant",
    "lower_court_case",
)

# platform corpus BM25 키
_PL_DOCS_KEY = "bm25:pl:docs"
_PL_IDS_KEY = "bm25:pl:ids"
_PL_REV_KEY = "bm25:pl:rev"


class PlatformKnowledgeRetriever:
    def retrieve(
        self,
        request: KnowledgeRetrievalRequest,
        *,
        search_mode: SearchMode = SearchMode.dense,
    ) -> list[RetrievedKnowledgeItem]:
        if not request.include_platform:
            return []

        items: list[RetrievedKnowledgeItem] = []

        # A. 기존 precedent corpus
        # migration 완료(ENABLE_PLATFORM_PRECEDENT_CORPUS=true)이면 비활성화
        if not ENABLE_PLATFORM_PRECEDENT_CORPUS:
            try:
                items += self._retrieve_precedents(request, search_mode=search_mode)
            except Exception:
                logger.exception("[PlatformRetriever] precedent corpus 검색 실패")

        # B. platform corpus
        # source_type 목록은 migration flag 기반으로 구성
        # (false이면 "precedent" 제외, true이면 "precedent" 포함)
        try:
            items += self._retrieve_platform_chunks(request, search_mode=search_mode)
        except Exception:
            logger.exception("[PlatformRetriever] platform corpus 검색 실패")

        return items

    # ── A. 기존 precedent corpus ──────────────────────────────────────────────

    def _retrieve_precedents(
        self,
        request: KnowledgeRetrievalRequest,
        *,
        search_mode: SearchMode,
    ) -> list[RetrievedKnowledgeItem]:
        grouped = retrieve_precedents(
            query=request.query,
            top_k=request.top_k,
            search_mode=search_mode,
        )
        return [self._precedent_to_item(g) for g in grouped]

    def _precedent_to_item(self, grouped: dict) -> RetrievedKnowledgeItem:
        chunks = grouped.get("chunks") or []
        chunk_text = "\n".join(c.get("text", "") for c in chunks).strip()
        chunk_id = chunks[0].get("chunk_id") if chunks else None

        return RetrievedKnowledgeItem(
            knowledge_type="platform",
            source_type="precedent",
            source_id=grouped.get("precedent_id", ""),
            title=grouped.get("title") or "제목 없음",
            chunk_text=chunk_text,
            score=grouped.get("score", 0.0),
            chunk_id=chunk_id,
            metadata={
                field: grouped.get(field)
                for field in _PRECEDENT_META_FIELDS
                if grouped.get(field) is not None
            },
        )

    # ── B. platform corpus ────────────────────────────────────────────────────

    def _retrieve_platform_chunks(
        self,
        request: KnowledgeRetrievalRequest,
        *,
        search_mode: SearchMode,
    ) -> list[RetrievedKnowledgeItem]:
        """
        platform corpus(bm25:pl:* / Qdrant platform_document_id 기반)를 검색한다.

        source_type 필터는 get_platform_corpus_source_types()로 결정된다.
        migration flag false이면 "precedent"가 제외되어 기존 corpus와 중복이 발생하지 않는다.
        """
        source_types = get_platform_corpus_source_types()

        # platform corpus BM25 비어 있는지 확인
        try:
            r = bm25_store._get_redis()
            if not r.exists(_PL_IDS_KEY):
                return []
        except Exception:
            return []

        query_vector = embed_query(request.query)
        fetch_k = request.top_k * 4

        from qdrant_client.http import models as qmodels

        platform_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="source_type",
                    match=qmodels.MatchAny(any=source_types),
                )
            ]
        )

        if search_mode == SearchMode.dense:
            hits = vector_store.search(
                query_embedding=query_vector,
                top_k=fetch_k,
                query_filter=platform_filter,
            )
        else:
            bm25_hits = self._search_platform_bm25(
                request.query, top_k=fetch_k * 2, source_types=source_types
            )
            hits = vector_store.hybrid_search(
                query_embedding=query_vector,
                bm25_results=bm25_hits,
                top_k=fetch_k,
                query_filter=platform_filter,
            )

        return [self._platform_hit_to_item(hit) for hit in hits[: request.top_k]]

    def _search_platform_bm25(
        self, query: str, top_k: int, source_types: list[str]
    ) -> list[dict]:
        """
        bm25:pl:* corpus BM25 검색.

        source_types 필터는 Qdrant hybrid_search의 query_filter가 담당하므로
        여기서는 전체 corpus를 대상으로 검색 후 Qdrant 단계에서 필터링된다.
        """
        try:
            from rank_bm25 import BM25Okapi
            from soynlp.tokenizer import LTokenizer
            from soynlp.word import WordExtractor

            r = bm25_store._get_redis()
            chunk_ids = r.lrange(_PL_IDS_KEY, 0, -1)
            if not chunk_ids:
                return []

            texts = [r.hget(_PL_DOCS_KEY, cid) or "" for cid in chunk_ids]
            extractor = WordExtractor(
                min_frequency=1,
                min_cohesion_forward=0.0,
                min_right_branching_entropy=0.0,
            )
            extractor.train(texts)
            words = extractor.extract()
            scores = {
                w: max(s.cohesion_forward, 0.0) for w, s in words.items() if len(w) >= 2
            }
            tokenizer = LTokenizer(scores=scores)
            tokenized = [
                [t for t in tokenizer.tokenize(tx) if len(t) >= 2] for tx in texts
            ]
            bm25 = BM25Okapi(tokenized)
            query_tokens = [t for t in tokenizer.tokenize(query) if len(t) >= 2]
            doc_scores = bm25.get_scores(query_tokens)

            indexed = sorted(enumerate(doc_scores), key=lambda x: x[1], reverse=True)[
                :top_k
            ]
            return [
                {"chunk_id": chunk_ids[i], "score": float(score)}
                for i, score in indexed
                if score > 0
            ]
        except Exception:
            logger.exception("[PlatformRetriever] platform BM25 검색 실패")
            return []

    def _platform_hit_to_item(self, hit: dict) -> RetrievedKnowledgeItem:
        source_type = hit.get("source_type") or "platform"
        platform_document_id = hit.get("platform_document_id") or ""
        chunk_id = hit.get("chunk_id")

        metadata = {
            k: hit.get(k)
            for k in (
                "source_url",
                "issued_at",
                "agency",
                "chunk_type",
                "section_title",
                "related_law_refs",
                "related_case_refs",
            )
            if hit.get(k) is not None
        }

        return RetrievedKnowledgeItem(
            knowledge_type="platform",
            source_type=source_type,
            source_id=platform_document_id,
            title=hit.get("title") or source_type,
            chunk_text=hit.get("text") or "",
            score=hit.get("score", 0.0),
            chunk_id=chunk_id,
            metadata=metadata,
        )
