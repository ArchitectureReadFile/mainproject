"""
services/knowledge/platform_knowledge_retriever.py

Platform 지식원 retriever.

책임:
    - platform layer 검색 정책 결정 (include_platform 여부)
    - migration flag에 따라 legacy precedent corpus / platform corpus 분기 호출
    - search service (retrieval_service / bm25_store / vector_store) 호출
    - 결과를 mapper에 위임해 RetrievedKnowledgeItem으로 변환

비책임 (이 클래스 안에 두지 않는다):
    - BM25 corpus 빌드 / 토크나이저 초기화 (→ bm25_store)
    - RetrievedKnowledgeItem 매핑 로직 (→ mappers/platform_item_mapper)

━━━ Migration 단계 정책 (settings/platform.py 참조) ━━━━━━━━━━━━━━━━━━━━━━━━
ENABLE_PLATFORM_PRECEDENT_CORPUS=false (기본):
    A. legacy precedent corpus  → 판례 검색
    B. platform corpus          → source_type="precedent" 제외 검색

ENABLE_PLATFORM_PRECEDENT_CORPUS=true (migration 완료 후):
    A. legacy precedent corpus  → 비활성화
    B. platform corpus          → 모든 source_type 포함 검색

"둘 다 검색 후 dedupe" 방식은 사용하지 않는다.
source_id 체계가 달라 dedupe 키가 충돌 없이 통과해 중복 반환 위험이 있다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import logging

from qdrant_client.http import models as qmodels

from schemas.knowledge import KnowledgeRetrievalRequest, RetrievedKnowledgeItem
from schemas.search import SearchMode
from services.knowledge.mappers.platform_item_mapper import (
    platform_hit_to_item,
    precedent_grouped_to_item,
)
from services.rag import bm25_store, vector_store
from services.rag.embedding_service import embed_query
from services.rag.retrieval_service import retrieve_precedents
from settings.platform import (
    ENABLE_PLATFORM_PRECEDENT_CORPUS,
    get_platform_corpus_source_types,
)

logger = logging.getLogger(__name__)


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

        # A. legacy precedent corpus
        # migration 완료(ENABLE_PLATFORM_PRECEDENT_CORPUS=true)이면 비활성화
        if not ENABLE_PLATFORM_PRECEDENT_CORPUS:
            try:
                items += self._retrieve_precedents(request, search_mode=search_mode)
            except Exception:
                logger.exception("[PlatformRetriever] precedent corpus 검색 실패")

        # B. platform corpus
        # source_type 목록은 migration flag 기반으로 구성
        try:
            items += self._retrieve_platform_chunks(request, search_mode=search_mode)
        except Exception:
            logger.exception("[PlatformRetriever] platform corpus 검색 실패")

        return items

    # ── A. legacy precedent corpus ────────────────────────────────────────────

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
        return [precedent_grouped_to_item(g) for g in grouped]

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
        migration flag false이면 "precedent"가 제외되어 legacy corpus와 중복이 발생하지 않는다.

        BM25 검색은 bm25_store.search_platform()에 위임한다.
        corpus 빌드/토크나이저 초기화는 bm25_store 내부에서 캐시 기반으로 처리된다.
        """
        # corpus 존재 확인 (빈 corpus면 조기 반환)
        if not bm25_store.platform_corpus_exists():
            return []

        source_types = get_platform_corpus_source_types()
        query_vector = embed_query(request.query)
        fetch_k = request.top_k * 4

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
            bm25_hits = bm25_store.search_platform(
                query=request.query,
                top_k=fetch_k * 2,
            )
            hits = vector_store.hybrid_search(
                query_embedding=query_vector,
                bm25_results=bm25_hits,
                top_k=fetch_k,
                query_filter=platform_filter,
            )

        return [platform_hit_to_item(hit) for hit in hits[: request.top_k]]
