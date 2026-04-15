"""
domains/knowledge/workspace_knowledge_retriever.py

Workspace 지식원 retriever.
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

        if selection is None or selection.mode == "documents":
            if selection is not None and selection.mode == "documents":
                logger.warning(
                    "[WorkspaceKnowledgeRetriever] mode='documents' → fail-closed, 빈 결과"
                )
            return []

        grouped = retrieve_group_documents(
            query=request.query,
            group_id=request.group_id,
            top_k=request.top_k,
            search_mode=search_mode,
            document_ids=None,
        )
        return [workspace_grouped_to_item(g) for g in grouped]
