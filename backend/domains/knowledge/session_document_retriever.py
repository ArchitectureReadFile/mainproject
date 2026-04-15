"""
domains/knowledge/session_document_retriever.py

Session 지식원 retriever.
"""

from __future__ import annotations

from domains.knowledge.mappers.session_item_mapper import session_text_to_item
from domains.knowledge.schemas import KnowledgeRetrievalRequest, RetrievedKnowledgeItem


class SessionDocumentRetriever:
    def retrieve_from_text(
        self,
        request: KnowledgeRetrievalRequest,
        *,
        reference_document_text: str,
        session_title: str | None = None,
    ) -> list[RetrievedKnowledgeItem]:
        if not request.include_session or not reference_document_text.strip():
            return []

        return [
            session_text_to_item(
                session_id=request.session_id,
                reference_document_text=reference_document_text,
                session_title=session_title,
            )
        ]
