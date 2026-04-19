"""
platform, workspace, session retriever를 묶는 orchestration layer.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from domains.knowledge.platform_knowledge_retriever import PlatformKnowledgeRetriever
from domains.knowledge.schemas import KnowledgeRetrievalRequest, RetrievedKnowledgeItem
from domains.knowledge.session_document_retriever import SessionDocumentRetriever
from domains.knowledge.workspace_knowledge_retriever import WorkspaceKnowledgeRetriever
from domains.rag.schemas import SearchMode
from errors import ErrorCode, FailureStage, build_failure_payload
from settings.knowledge import KNOWLEDGE_DEDUPE_TEXT_PREFIX_LEN

logger = logging.getLogger(__name__)


class KnowledgeRetrievalService:
    """각 retriever를 호출하고 score 정렬/중복 제거를 수행한다."""

    def __init__(self) -> None:
        self._platform = PlatformKnowledgeRetriever()
        self._workspace = WorkspaceKnowledgeRetriever()
        self._session = SessionDocumentRetriever()

    def retrieve(
        self,
        request: KnowledgeRetrievalRequest,
        *,
        session_reference_text: str | None = None,
        session_reference_chunks: list[object] | None = None,
        session_title: str | None = None,
        search_mode: SearchMode = SearchMode.dense,
        failure_metadata: list[dict[str, object]] | None = None,
    ) -> list[RetrievedKnowledgeItem]:
        items: list[RetrievedKnowledgeItem] = []

        try:
            items += self._platform.retrieve(request, search_mode=search_mode)
        except Exception as exc:
            logger.exception("[KnowledgeRetrievalService] platform retrieval 실패")
            _record_failure(failure_metadata, retriever="platform", exc=exc)

        try:
            items += self._workspace.retrieve(
                _with_workspace_query(request), search_mode=search_mode
            )
        except Exception as exc:
            logger.exception("[KnowledgeRetrievalService] workspace retrieval 실패")
            _record_failure(failure_metadata, retriever="workspace", exc=exc)

        try:
            items += self._session.retrieve(
                _with_session_query(request),
                stored_chunks=session_reference_chunks,
                session_reference_text=session_reference_text or "",
                session_title=session_title,
            )
        except Exception as exc:
            logger.exception("[KnowledgeRetrievalService] session retrieval 실패")
            _record_failure(failure_metadata, retriever="session", exc=exc)

        items = _sort_by_score(items)
        items = _dedupe(items)
        return items


def _record_failure(
    failure_metadata: list[dict[str, object]] | None,
    *,
    retriever: str,
    exc: Exception,
) -> None:
    """source별 retrieval 실패를 상위 계층이 추적할 수 있게 기록한다."""
    if failure_metadata is None:
        return
    payload = build_failure_payload(
        stage=FailureStage.RETRIEVE,
        error_code=ErrorCode.CHAT_RETRIEVAL_FAILED,
        status="error",
        retryable=False,
        retriever=retriever,
        exception_type=type(exc).__name__,
    )
    failure_metadata.append(payload)


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


def _with_workspace_query(
    request: KnowledgeRetrievalRequest,
) -> KnowledgeRetrievalRequest:
    """workspace 검색용 query 문맥을 보강한다."""
    if not request.include_workspace:
        return request
    return replace(request, query=f"그룹 문서를 참고한 질문: {request.query.strip()}")


def _with_session_query(
    request: KnowledgeRetrievalRequest,
) -> KnowledgeRetrievalRequest:
    """session 첨부 검색용 query 문맥을 보강한다."""
    if not request.include_session:
        return request
    return replace(request, query=f"첨부 문서를 참고한 질문: {request.query.strip()}")
