"""
domains/knowledge/knowledge_retrieval_service.py

platform / workspace / session retriever를 하나의 진입점으로 묶는 orchestrator.
"""

from __future__ import annotations

import logging

from domains.knowledge.platform_knowledge_retriever import PlatformKnowledgeRetriever
from domains.knowledge.schemas import KnowledgeRetrievalRequest, RetrievedKnowledgeItem
from domains.knowledge.session_document_retriever import SessionDocumentRetriever
from domains.knowledge.workspace_knowledge_retriever import WorkspaceKnowledgeRetriever
from domains.rag.schemas import SearchMode
from settings.knowledge import KNOWLEDGE_DEDUPE_TEXT_PREFIX_LEN

logger = logging.getLogger(__name__)


class KnowledgeRetrievalService:
    def __init__(self) -> None:
        self._platform = PlatformKnowledgeRetriever()
        self._workspace = WorkspaceKnowledgeRetriever()
        self._session = SessionDocumentRetriever()

    def retrieve(
        self,
        request: KnowledgeRetrievalRequest,
        *,
        reference_document_text: str | None = None,
        session_title: str | None = None,
        search_mode: SearchMode = SearchMode.dense,
    ) -> list[RetrievedKnowledgeItem]:
        items: list[RetrievedKnowledgeItem] = []

        try:
            items += self._platform.retrieve(request, search_mode=search_mode)
        except Exception:
            logger.exception("[KnowledgeRetrievalService] platform retrieval 실패")

        try:
            items += self._workspace.retrieve(request, search_mode=search_mode)
        except Exception:
            logger.exception("[KnowledgeRetrievalService] workspace retrieval 실패")

        try:
            items += self._session.retrieve_from_text(
                request,
                reference_document_text=reference_document_text or "",
                session_title=session_title,
            )
        except Exception:
            logger.exception("[KnowledgeRetrievalService] session retrieval 실패")

        items = _sort_by_score(items)
        items = _dedupe(items)
        return items


def _dedupe_key(item: RetrievedKnowledgeItem) -> tuple:
    text_key = (
        item.chunk_id
        if item.chunk_id
        else item.chunk_text[:KNOWLEDGE_DEDUPE_TEXT_PREFIX_LEN]
    )
    return (item.knowledge_type, item.source_type, item.source_id, text_key)


def _dedupe(items: list[RetrievedKnowledgeItem]) -> list[RetrievedKnowledgeItem]:
    seen: set[tuple] = set()
    result: list[RetrievedKnowledgeItem] = []
    for item in items:
        key = _dedupe_key(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _sort_by_score(items: list[RetrievedKnowledgeItem]) -> list[RetrievedKnowledgeItem]:
    return sorted(items, key=lambda x: x.score, reverse=True)
