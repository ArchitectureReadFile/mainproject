"""
domains/knowledge/platform_knowledge_retriever.py

Platform 지식원 retriever.
"""

from __future__ import annotations

import logging

from qdrant_client.http import models as qmodels

from domains.knowledge.mappers.platform_item_mapper import (
    platform_hit_to_item,
    precedent_grouped_to_item,
)
from domains.knowledge.schemas import KnowledgeRetrievalRequest, RetrievedKnowledgeItem
from domains.rag import bm25_store, vector_store
from domains.rag.embedding_service import embed_query
from domains.rag.retrieval_service import retrieve_precedents
from domains.rag.schemas import SearchMode
from settings.platform import (
    get_platform_corpus_source_types,
    use_legacy_precedent_corpus,
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

        if use_legacy_precedent_corpus():
            try:
                items += self._retrieve_precedents(request, search_mode=search_mode)
            except Exception:
                logger.exception("[PlatformRetriever] precedent corpus 검색 실패")

        try:
            items += self._retrieve_platform_chunks(request, search_mode=search_mode)
        except Exception:
            logger.exception("[PlatformRetriever] platform corpus 검색 실패")

        return items

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

    def _retrieve_platform_chunks(
        self,
        request: KnowledgeRetrievalRequest,
        *,
        search_mode: SearchMode,
    ) -> list[RetrievedKnowledgeItem]:
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
            if not bm25_store.platform_corpus_exists():
                logger.info(
                    "[PlatformRetriever] BM25 corpus 없음 → dense fallback: query=%s",
                    request.query,
                )
                hits = vector_store.search(
                    query_embedding=query_vector,
                    top_k=fetch_k,
                    query_filter=platform_filter,
                )
                return [platform_hit_to_item(hit) for hit in hits[: request.top_k]]

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
