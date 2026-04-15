"""
domains/knowledge/workspace_knowledge_retriever.py

Workspace 지식원 retriever.

검색 계약:
    include_workspace=False 또는 group_id 없음 → 빈 결과
    mode="all"       → group 전체 검색 (document_ids=None)
    mode="documents" → selection.document_ids whitelist 검색
"""

from __future__ import annotations

import logging

from domains.knowledge.mappers.workspace_item_mapper import workspace_grouped_to_item
from domains.knowledge.schemas import KnowledgeRetrievalRequest, RetrievedKnowledgeItem
from domains.rag.group_document_retrieval_service import retrieve_group_documents
from domains.rag.schemas import SearchMode

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

        if selection is None or selection.mode == "all":
            document_ids = None
        else:
            # mode="documents"
            document_ids = selection.document_ids

        grouped = retrieve_group_documents(
            query=request.query,
            group_id=request.group_id,
            top_k=request.top_k,
            search_mode=search_mode,
            document_ids=document_ids,
        )
        return [workspace_grouped_to_item(g) for g in grouped]
