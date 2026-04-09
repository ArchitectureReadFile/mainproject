"""
services/knowledge/workspace_knowledge_retriever.py

Workspace 지식원 retriever.

책임:
    - workspace layer 검색 정책 결정 (include_workspace / group_id 조건)
    - selection mode에 따라 group 전체 or document whitelist 범위 결정
    - retrieve_group_documents() 호출
    - 결과를 mapper에 위임해 RetrievedKnowledgeItem으로 변환

비책임:
    - 직접 검색 구현 (→ group_document_retrieval_service)
    - RetrievedKnowledgeItem 매핑 로직 (→ mappers/workspace_item_mapper)

mode="all":
    group_id 전체 범위 검색.

mode="documents":
    미구현 (11단계 예정). fail-closed 정책 — 빈 결과 반환.
    전체 group 검색으로 fallback 없음.
    retrieve_group_documents() 호출하지 않음.
"""

from __future__ import annotations

import logging

from schemas.knowledge import KnowledgeRetrievalRequest, RetrievedKnowledgeItem
from schemas.search import SearchMode
from services.knowledge.mappers.workspace_item_mapper import workspace_grouped_to_item
from services.rag.group_document_retrieval_service import retrieve_group_documents

logger = logging.getLogger(__name__)


class WorkspaceKnowledgeRetriever:
    def retrieve(
        self,
        request: KnowledgeRetrievalRequest,
        *,
        search_mode: SearchMode = SearchMode.dense,
    ) -> list[RetrievedKnowledgeItem]:
        if not request.include_workspace or request.group_id is None:
            return []

        selection = request.workspace_selection

        if selection is None or selection.mode == "documents":
            # mode="documents" 는 Qdrant/BM25 document_ids 필터 미구현 (11단계 예정).
            # 전체 group 검색으로 fallback하지 않는다 (fail-closed).
            if selection is not None and selection.mode == "documents":
                logger.warning(
                    "[WorkspaceKnowledgeRetriever] mode='documents' → fail-closed, 빈 결과"
                )
            return []

        # mode="all"
        grouped = retrieve_group_documents(
            query=request.query,
            group_id=request.group_id,
            top_k=request.top_k,
            search_mode=search_mode,
            document_ids=None,
        )
        return [workspace_grouped_to_item(g) for g in grouped]
