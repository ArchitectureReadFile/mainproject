"""
services/knowledge/workspace_knowledge_retriever.py

Workspace 지식원 retriever.

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
            document_ids=document_ids,  # None → all, list → whitelist
        )
        return [self._to_item(g) for g in grouped]

    def _to_item(self, grouped: dict) -> RetrievedKnowledgeItem:
        chunks = grouped.get("chunks") or []
        chunk_text = "\n".join(c.get("text", "") for c in chunks).strip()
        chunk_id = chunks[0].get("chunk_id") if chunks else None
        top_chunk = chunks[0] if chunks else {}

        return RetrievedKnowledgeItem(
            knowledge_type="workspace",
            source_type="workspace_document",
            source_id=grouped.get("document_id", ""),
            title=grouped.get("file_name") or "문서",
            chunk_text=chunk_text,
            score=grouped.get("score", 0.0),
            chunk_id=chunk_id,
            metadata={
                "group_id": grouped.get("group_id"),
                "file_name": grouped.get("file_name"),
                "chunk_type": top_chunk.get("chunk_type"),
            },
        )
