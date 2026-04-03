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
    workspace_selection.document_ids whitelist 범위만 검색.
    group_id + document_ids 이중 필터 (BM25/Qdrant 저장소 레벨 + Python 재검증).
    전체 group 검색으로 fallback 없음 (fail-closed).
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
        document_ids: list[int] | None = None

        if selection.mode == "documents":
            if not selection.document_ids:
                # 방어 코드: parser에서 이미 막히지만 도달 시 fail-closed
                logger.warning(
                    "[WorkspaceKnowledgeRetriever] mode='documents' + empty ids → 빈 결과"
                )
                return []
            document_ids = selection.document_ids

        grouped = retrieve_group_documents(
            query=request.query,
            group_id=request.group_id,
            top_k=request.top_k,
            search_mode=search_mode,
            document_ids=document_ids,
        )
        return [workspace_grouped_to_item(g) for g in grouped]
