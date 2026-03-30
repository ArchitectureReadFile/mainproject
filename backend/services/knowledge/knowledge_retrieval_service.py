"""
services/knowledge/knowledge_retrieval_service.py

platform / workspace / session retriever를 하나의 진입점으로 묶는 orchestrator.

책임:
    - request 조건에 따라 각 retriever를 조건부 호출
    - 결과 merge → score 내림차순 정렬 → dedupe 순으로 반환

비책임:
    - 직접 검색 구현
    - prompt/context 문자열 조립 (→ AnswerContextBuilder)
    - ChatProcessor 로직

merge 정책 (v1):
    - 각 retriever는 request.top_k 기준으로 독립 검색
    - merge 후 상한 없이 전부 반환
      (소스별 예산은 AnswerContextBuilder에서 결정)
    - 정렬 먼저 → dedupe: 같은 key 중 항상 최고 score 항목이 남는다
    - dedupe 키: (knowledge_type, source_type, source_id, chunk_id or chunk_text 앞 100자)
"""

from __future__ import annotations

import logging

from schemas.knowledge import KnowledgeRetrievalRequest, RetrievedKnowledgeItem
from schemas.search import SearchMode
from services.knowledge.platform_knowledge_retriever import PlatformKnowledgeRetriever
from services.knowledge.session_document_retriever import SessionDocumentRetriever
from services.knowledge.workspace_knowledge_retriever import WorkspaceKnowledgeRetriever
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
        """
        platform / workspace / session을 조건부 검색 후 merged 결과를 반환한다.

        Returns:
            list[RetrievedKnowledgeItem] — sort → dedupe 순. v1은 상한 없이 전부 반환.
        """
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

        # 정렬 먼저 → dedupe: 높은 score 항목이 항상 살아남는다
        items = _sort_by_score(items)
        items = _dedupe(items)
        return items


# ── 내부 유틸 ─────────────────────────────────────────────────────────────────


def _dedupe_key(item: RetrievedKnowledgeItem) -> tuple:
    text_key = (
        item.chunk_id
        if item.chunk_id
        else item.chunk_text[:KNOWLEDGE_DEDUPE_TEXT_PREFIX_LEN]
    )
    return (item.knowledge_type, item.source_type, item.source_id, text_key)


def _dedupe(items: list[RetrievedKnowledgeItem]) -> list[RetrievedKnowledgeItem]:
    """이미 score 내림차순 정렬된 리스트를 받아 첫 번째(최고 score) 항목만 남긴다."""
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
