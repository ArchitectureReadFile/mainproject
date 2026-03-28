"""
tests/unit/test_knowledge_retrieval_service.py

KnowledgeRetrievalService orchestration 단위 테스트.
각 retriever는 mock으로 격리한다.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schemas.knowledge import (
    KnowledgeRetrievalRequest,
    RetrievedKnowledgeItem,
    WorkspaceSelection,
)


def _item(
    knowledge_type: str,
    source_id: str | int = "1",
    score: float = 0.9,
    chunk_id: str | None = None,
    chunk_text: str = "텍스트",
) -> RetrievedKnowledgeItem:
    return RetrievedKnowledgeItem(
        knowledge_type=knowledge_type,  # type: ignore[arg-type]
        source_type=f"{knowledge_type}_src",
        source_id=source_id,
        title="제목",
        chunk_text=chunk_text,
        score=score,
        chunk_id=chunk_id,
    )


@pytest.fixture
def svc():
    from services.knowledge.knowledge_retrieval_service import KnowledgeRetrievalService

    return KnowledgeRetrievalService()


def _mock_retrievers(svc, *, platform=None, workspace=None, session=None):
    svc._platform.retrieve = MagicMock(return_value=platform or [])
    svc._workspace.retrieve = MagicMock(return_value=workspace or [])
    svc._session.retrieve_from_text = MagicMock(return_value=session or [])


# ── 포함 조건 ─────────────────────────────────────────────────────────────────


class TestIncludeConditions:
    def test_platform_always_called(self, svc):
        _mock_retrievers(svc, platform=[_item("platform")])
        req = KnowledgeRetrievalRequest(query="질문", include_platform=True)
        result = svc.retrieve(req)
        svc._platform.retrieve.assert_called_once()
        assert any(i.knowledge_type == "platform" for i in result)

    def test_workspace_results_included_when_true(self, svc):
        _mock_retrievers(svc, workspace=[_item("workspace")])
        req = KnowledgeRetrievalRequest(
            query="질문", include_workspace=True, group_id=1
        )
        result = svc.retrieve(req)
        assert any(i.knowledge_type == "workspace" for i in result)

    def test_session_excluded_when_text_empty(self, svc):
        _mock_retrievers(svc)
        req = KnowledgeRetrievalRequest(query="질문", include_session=True)
        result = svc.retrieve(req, reference_document_text="")
        assert not any(i.knowledge_type == "session" for i in result)

    def test_session_included_when_text_present(self, svc):
        _mock_retrievers(svc, session=[_item("session", score=1.0)])
        req = KnowledgeRetrievalRequest(query="질문", include_session=True)
        result = svc.retrieve(req, reference_document_text="첨부 문서 내용")
        assert any(i.knowledge_type == "session" for i in result)


# ── workspace fail-closed ─────────────────────────────────────────────────────


class TestWorkspaceFailClosed:
    def test_documents_mode_returns_empty(self):
        from services.knowledge.workspace_knowledge_retriever import (
            WorkspaceKnowledgeRetriever,
        )

        retriever = WorkspaceKnowledgeRetriever()
        req = KnowledgeRetrievalRequest(
            query="질문",
            include_workspace=True,
            group_id=1,
            workspace_selection=WorkspaceSelection(
                mode="documents", document_ids=[1, 2]
            ),
        )

        with patch(
            "services.knowledge.workspace_knowledge_retriever.retrieve_group_documents"
        ) as mock_retrieve:
            result = retriever.retrieve(req)

        assert result == []
        mock_retrieve.assert_not_called()

    def test_all_mode_calls_retrieve(self):
        from services.knowledge.workspace_knowledge_retriever import (
            WorkspaceKnowledgeRetriever,
        )

        retriever = WorkspaceKnowledgeRetriever()
        req = KnowledgeRetrievalRequest(
            query="질문",
            include_workspace=True,
            group_id=1,
            workspace_selection=WorkspaceSelection(mode="all"),
        )

        with patch(
            "services.knowledge.workspace_knowledge_retriever.retrieve_group_documents",
            return_value=[],
        ) as mock_retrieve:
            retriever.retrieve(req)

        mock_retrieve.assert_called_once()


# ── dedupe (6단계 보정: sort → dedupe 순서 보장) ──────────────────────────────


class TestDedupe:
    def test_higher_score_survives_when_chunk_id_duplicated(self, svc):
        """같은 chunk_id 중 score 높은 항목이 남아야 한다."""
        low = _item("platform", chunk_id="chunk:1", score=0.5)
        high = _item("platform", chunk_id="chunk:1", score=0.9)
        # low가 먼저 들어와도 high가 살아남아야 한다
        _mock_retrievers(svc, platform=[low, high])
        req = KnowledgeRetrievalRequest(query="질문")
        result = svc.retrieve(req)
        survivors = [i for i in result if i.chunk_id == "chunk:1"]
        assert len(survivors) == 1
        assert survivors[0].score == 0.9

    def test_higher_score_survives_across_retrievers(self, svc):
        """다른 retriever에서 온 같은 key 중 높은 score가 남아야 한다."""
        # platform이 낮은 score로 먼저 호출됨
        low = _item("platform", source_id="42", chunk_id="chunk:X", score=0.3)
        # workspace가 같은 key로 높은 score
        high = _item("platform", source_id="42", chunk_id="chunk:X", score=0.8)
        _mock_retrievers(svc, platform=[low], workspace=[high])
        req = KnowledgeRetrievalRequest(
            query="질문", include_workspace=True, group_id=1
        )
        result = svc.retrieve(req)
        survivors = [i for i in result if i.chunk_id == "chunk:X"]
        assert len(survivors) == 1
        assert survivors[0].score == 0.8

    def test_duplicate_chunk_text_removed(self, svc):
        text = "동일한 텍스트"
        dup = _item("platform", chunk_text=text, score=0.9)
        dup2 = _item("platform", chunk_text=text, score=0.8)
        _mock_retrievers(svc, platform=[dup, dup2])
        req = KnowledgeRetrievalRequest(query="질문")
        result = svc.retrieve(req)
        assert len([i for i in result if i.chunk_text == text]) == 1

    def test_different_knowledge_types_not_deduped(self, svc):
        """knowledge_type이 다르면 같은 chunk_id여도 dedupe 대상이 아니다."""
        p = _item("platform", chunk_id="chunk:1")
        w = _item("workspace", chunk_id="chunk:1")
        _mock_retrievers(svc, platform=[p], workspace=[w])
        req = KnowledgeRetrievalRequest(query="질문")
        result = svc.retrieve(req)
        assert len(result) == 2


# ── sort ──────────────────────────────────────────────────────────────────────


class TestSort:
    def test_sorted_by_score_desc_after_dedupe(self, svc):
        a = _item("platform", score=0.9, chunk_id="a")
        b = _item("platform", score=0.7, chunk_id="b")
        c = _item("platform", score=0.5, chunk_id="c")
        _mock_retrievers(svc, platform=[c, a, b])
        req = KnowledgeRetrievalRequest(query="질문")
        result = svc.retrieve(req)
        scores = [i.score for i in result]
        assert scores == sorted(scores, reverse=True)

    def test_all_sources_merged_and_sorted(self, svc):
        p = _item("platform", score=0.7, chunk_id="p1")
        w = _item("workspace", score=0.5, chunk_id="w1")
        s = _item("session", score=1.0, chunk_id="s1")
        _mock_retrievers(svc, platform=[p], workspace=[w], session=[s])
        req = KnowledgeRetrievalRequest(query="질문")
        result = svc.retrieve(req)
        scores = [i.score for i in result]
        assert scores == sorted(scores, reverse=True)


# ── retriever 예외 격리 ───────────────────────────────────────────────────────


class TestRetrieverIsolation:
    def test_platform_exception_does_not_abort(self, svc):
        svc._platform.retrieve = MagicMock(side_effect=RuntimeError("검색 실패"))
        svc._workspace.retrieve = MagicMock(return_value=[_item("workspace")])
        svc._session.retrieve_from_text = MagicMock(return_value=[])
        req = KnowledgeRetrievalRequest(
            query="질문", include_workspace=True, group_id=1
        )
        result = svc.retrieve(req)
        assert any(i.knowledge_type == "workspace" for i in result)

    def test_workspace_exception_does_not_abort(self, svc):
        svc._platform.retrieve = MagicMock(return_value=[_item("platform")])
        svc._workspace.retrieve = MagicMock(side_effect=RuntimeError("검색 실패"))
        svc._session.retrieve_from_text = MagicMock(return_value=[])
        req = KnowledgeRetrievalRequest(query="질문")
        result = svc.retrieve(req)
        assert any(i.knowledge_type == "platform" for i in result)
