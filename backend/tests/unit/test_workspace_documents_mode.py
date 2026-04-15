"""
tests/unit/test_workspace_documents_mode.py

WorkspaceSelection(mode="documents") retrieval 계층별 테스트.

테스트 계층 분리:
    A. BM25 store 레벨: document_ids whitelist 필터 구현 검증
       → bm25_store.search_documents()가 document_ids를 올바르게 처리하는지

    B. group_document_retrieval_service 레벨: Python 재검증 + Qdrant 필터 검증
       → retrieve_group_documents()가 document_ids whitelist를 올바르게 처리하는지

    C. WorkspaceKnowledgeRetriever 레벨: 복구된 계약 검증
       → mode="all"       → document_ids=None 으로 retrieve 호출
       → mode="documents" → selection.document_ids 로 retrieve 호출
       → include_workspace=False / group_id 없음 → retrieve 호출 안 함
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from domains.knowledge.schemas import KnowledgeRetrievalRequest, WorkspaceSelection

# ── A. BM25 document_ids 필터 ────────────────────────────────────────────────


class TestBM25DocumentsFilter:
    @pytest.fixture(autouse=True)
    def fake_redis(self, monkeypatch):
        import fakeredis

        r = fakeredis.FakeRedis(decode_responses=True)
        monkeypatch.setattr("domains.rag.bm25_store._redis", r)
        return r

    def _insert(self, chunk_id, document_id, group_id, text):
        from domains.rag import bm25_store

        bm25_store.upsert_document_chunk(chunk_id, document_id, group_id, text)

    def test_document_ids_whitelist_excludes_other_docs(self, fake_redis):
        from domains.rag import bm25_store

        self._insert("gdoc:10:chunk:0", document_id=10, group_id=1, text="납세 고지서")
        self._insert("gdoc:20:chunk:0", document_id=20, group_id=1, text="납세 고지서")

        results = bm25_store.search_documents(
            "납세", group_id=1, top_k=10, document_ids=[10]
        )
        chunk_ids = [r["chunk_id"] for r in results]

        assert "gdoc:10:chunk:0" in chunk_ids
        assert "gdoc:20:chunk:0" not in chunk_ids

    def test_all_mode_returns_all_group_docs(self, fake_redis):
        from domains.rag import bm25_store

        self._insert("gdoc:10:chunk:0", document_id=10, group_id=1, text="납세 고지서")
        self._insert("gdoc:20:chunk:0", document_id=20, group_id=1, text="납세 고지서")

        results = bm25_store.search_documents(
            "납세", group_id=1, top_k=10, document_ids=None
        )
        chunk_ids = [r["chunk_id"] for r in results]
        assert "gdoc:10:chunk:0" in chunk_ids
        assert "gdoc:20:chunk:0" in chunk_ids

    def test_empty_document_ids_returns_empty(self, fake_redis):
        from domains.rag import bm25_store

        self._insert("gdoc:10:chunk:0", document_id=10, group_id=1, text="납세")

        results = bm25_store.search_documents(
            "납세", group_id=1, top_k=10, document_ids=[]
        )
        assert results == []

    def test_document_id_not_in_group_returns_empty(self, fake_redis):
        from domains.rag import bm25_store

        # doc 30은 group 2에 속함
        self._insert("gdoc:30:chunk:0", document_id=30, group_id=2, text="납세")

        results = bm25_store.search_documents(
            "납세", group_id=1, top_k=10, document_ids=[30]
        )
        assert results == []


# ── B. group_document_retrieval_service Python 재검증 ────────────────────────


class TestRetrievalServiceWhitelist:
    def _make_hit(self, document_id, score=0.8):
        return {
            "chunk_id": f"gdoc:{document_id}:chunk:0",
            "document_id": document_id,
            "group_id": 1,
            "file_name": f"doc{document_id}.pdf",
            "source_type": "pdf",
            "chunk_type": "body",
            "section_title": None,
            "order_index": 0,
            "text": f"문서 {document_id} 내용",
            "score": score,
        }

    def test_documents_mode_filters_out_non_whitelisted(self):
        from domains.rag.group_document_retrieval_service import (
            retrieve_group_documents,
        )
        from domains.rag.schemas import SearchMode

        # Qdrant가 whitelist 밖 문서를 반환했다고 가정
        mock_hits = [self._make_hit(10), self._make_hit(99)]

        with (
            patch(
                "domains.rag.group_document_retrieval_service.embed_query",
                return_value=[0.1] * 768,
            ),
            patch("domains.rag.group_document_retrieval_service.vector_store") as mv,
            patch("domains.rag.group_document_retrieval_service.bm25_store"),
        ):
            mv.search.return_value = mock_hits

            results = retrieve_group_documents(
                query="질문",
                group_id=1,
                top_k=5,
                search_mode=SearchMode.dense,
                document_ids=[10],
            )

        doc_ids = [r["document_id"] for r in results]
        assert 10 in doc_ids
        assert 99 not in doc_ids

    def test_all_mode_does_not_filter_by_document_id(self):
        from domains.rag.group_document_retrieval_service import (
            retrieve_group_documents,
        )
        from domains.rag.schemas import SearchMode

        mock_hits = [self._make_hit(10), self._make_hit(20)]

        with (
            patch(
                "domains.rag.group_document_retrieval_service.embed_query",
                return_value=[0.1] * 768,
            ),
            patch("domains.rag.group_document_retrieval_service.vector_store") as mv,
            patch("domains.rag.group_document_retrieval_service.bm25_store"),
        ):
            mv.search.return_value = mock_hits

            results = retrieve_group_documents(
                query="질문",
                group_id=1,
                top_k=5,
                search_mode=SearchMode.dense,
                document_ids=None,
            )

        doc_ids = [r["document_id"] for r in results]
        assert 10 in doc_ids
        assert 20 in doc_ids

    def test_qdrant_filter_includes_match_any_when_document_ids(self):
        """mode='documents'일 때 Qdrant query_filter에 MatchAny 조건이 들어가는지."""
        from qdrant_client.http import models as qmodels

        from domains.rag.group_document_retrieval_service import (
            retrieve_group_documents,
        )
        from domains.rag.schemas import SearchMode

        with (
            patch(
                "domains.rag.group_document_retrieval_service.embed_query",
                return_value=[0.1] * 768,
            ),
            patch("domains.rag.group_document_retrieval_service.vector_store") as mv,
            patch("domains.rag.group_document_retrieval_service.bm25_store"),
        ):
            mv.search.return_value = []

            retrieve_group_documents(
                query="질문",
                group_id=1,
                top_k=5,
                search_mode=SearchMode.dense,
                document_ids=[10, 20],
            )

        call_kwargs = mv.search.call_args[1]
        query_filter = call_kwargs["query_filter"]
        conditions = query_filter.must
        match_any_conditions = [
            c
            for c in conditions
            if isinstance(c, qmodels.FieldCondition)
            and isinstance(c.match, qmodels.MatchAny)
        ]
        assert len(match_any_conditions) == 1
        assert set(match_any_conditions[0].match.any) == {10, 20}


# ── C. WorkspaceKnowledgeRetriever — 복구된 계약 ──────────────────────────────


class TestWorkspaceKnowledgeRetrieverDocumentsMode:
    """
    복구된 계약:
        include_workspace=False 또는 group_id 없음 → 빈 결과, retrieve 호출 안 함
        mode="all"       → document_ids=None 으로 retrieve 호출
        mode="documents" → selection.document_ids 로 retrieve 호출
    """

    def test_all_mode_calls_retrieve_with_document_ids_none(self):
        """mode="all" → retrieve_group_documents 호출, document_ids=None."""
        from domains.knowledge.workspace_knowledge_retriever import (
            WorkspaceKnowledgeRetriever,
        )
        from domains.rag.schemas import SearchMode

        retriever = WorkspaceKnowledgeRetriever()
        req = KnowledgeRetrievalRequest(
            query="질문",
            include_workspace=True,
            group_id=1,
            workspace_selection=WorkspaceSelection(mode="all"),
        )

        with patch(
            "domains.knowledge.workspace_knowledge_retriever.retrieve_group_documents",
            return_value=[],
        ) as mock_retrieve:
            retriever.retrieve(req, search_mode=SearchMode.dense)

        mock_retrieve.assert_called_once()
        assert mock_retrieve.call_args[1]["document_ids"] is None

    def test_documents_mode_calls_retrieve_with_document_ids(self):
        """mode="documents" → retrieve_group_documents 호출, document_ids 전달."""
        from domains.knowledge.workspace_knowledge_retriever import (
            WorkspaceKnowledgeRetriever,
        )
        from domains.rag.schemas import SearchMode

        retriever = WorkspaceKnowledgeRetriever()
        req = KnowledgeRetrievalRequest(
            query="질문",
            include_workspace=True,
            group_id=1,
            workspace_selection=WorkspaceSelection(
                mode="documents", document_ids=[10, 20]
            ),
        )

        with patch(
            "domains.knowledge.workspace_knowledge_retriever.retrieve_group_documents",
            return_value=[],
        ) as mock_retrieve:
            retriever.retrieve(req, search_mode=SearchMode.dense)

        mock_retrieve.assert_called_once()
        assert mock_retrieve.call_args[1]["document_ids"] == [10, 20]

    def test_include_workspace_false_returns_empty_without_retrieve(self):
        """include_workspace=False → retrieve 호출 안 함."""
        from domains.knowledge.workspace_knowledge_retriever import (
            WorkspaceKnowledgeRetriever,
        )

        retriever = WorkspaceKnowledgeRetriever()
        req = KnowledgeRetrievalRequest(
            query="질문",
            include_workspace=False,
            group_id=1,
            workspace_selection=WorkspaceSelection(mode="all"),
        )

        with patch(
            "domains.knowledge.workspace_knowledge_retriever.retrieve_group_documents"
        ) as mock_retrieve:
            results = retriever.retrieve(req)

        assert results == []
        mock_retrieve.assert_not_called()

    def test_group_id_none_returns_empty_without_retrieve(self):
        """group_id=None → retrieve 호출 안 함."""
        from domains.knowledge.workspace_knowledge_retriever import (
            WorkspaceKnowledgeRetriever,
        )

        retriever = WorkspaceKnowledgeRetriever()
        req = KnowledgeRetrievalRequest(
            query="질문",
            include_workspace=True,
            group_id=None,
            workspace_selection=WorkspaceSelection(mode="all"),
        )

        with patch(
            "domains.knowledge.workspace_knowledge_retriever.retrieve_group_documents"
        ) as mock_retrieve:
            results = retriever.retrieve(req)

        assert results == []
        mock_retrieve.assert_not_called()

    def test_selection_none_treated_as_all(self):
        """workspace_selection=None → mode="all"과 동일, document_ids=None 전달."""
        from domains.knowledge.workspace_knowledge_retriever import (
            WorkspaceKnowledgeRetriever,
        )

        retriever = WorkspaceKnowledgeRetriever()
        req = KnowledgeRetrievalRequest(
            query="질문",
            include_workspace=True,
            group_id=1,
            workspace_selection=None,
        )

        with patch(
            "domains.knowledge.workspace_knowledge_retriever.retrieve_group_documents",
            return_value=[],
        ) as mock_retrieve:
            retriever.retrieve(req)

        mock_retrieve.assert_called_once()
        assert mock_retrieve.call_args[1]["document_ids"] is None
