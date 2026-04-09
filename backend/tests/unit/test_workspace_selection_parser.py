"""
tests/unit/test_workspace_selection_parser.py

workspace_selection_parser + ChatWorkspaceSelectionInput validation 테스트.
"""

from __future__ import annotations

import json

import pytest

from schemas.knowledge import WorkspaceSelection
from services.chat.workspace_selection_parser import parse_workspace_selection


class TestParseNone:
    def test_none_returns_none(self):
        assert parse_workspace_selection(None) is None

    def test_empty_string_returns_none(self):
        assert parse_workspace_selection("") is None

    def test_whitespace_returns_none(self):
        assert parse_workspace_selection("   ") is None


class TestParseValid:
    def test_mode_all(self):
        raw = json.dumps({"mode": "all", "document_ids": []})
        result = parse_workspace_selection(raw)
        assert isinstance(result, WorkspaceSelection)
        assert result.mode == "all"
        assert result.document_ids == []

    def test_mode_documents_with_ids(self):
        raw = json.dumps({"mode": "documents", "document_ids": [1, 2, 3]})
        result = parse_workspace_selection(raw)
        assert result.mode == "documents"
        assert result.document_ids == [1, 2, 3]

    def test_mode_all_no_document_ids_field(self):
        raw = json.dumps({"mode": "all"})
        result = parse_workspace_selection(raw)
        assert result.mode == "all"
        assert result.document_ids == []


class TestParseInvalid:
    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="JSON 파싱 실패"):
            parse_workspace_selection("{not valid json}")

    def test_mode_documents_empty_ids_raises(self):
        raw = json.dumps({"mode": "documents", "document_ids": []})
        with pytest.raises(ValueError):
            parse_workspace_selection(raw)

    def test_unknown_mode_raises(self):
        raw = json.dumps({"mode": "unknown", "document_ids": []})
        with pytest.raises(ValueError):
            parse_workspace_selection(raw)


class TestChatProcessorWorkspaceReflection:
    """ChatProcessor가 workspace_selection을 request에 반영하는지 확인."""

    def _make_session(self, reference_document_text=None):
        from unittest.mock import MagicMock

        session = MagicMock()
        session.id = 1
        session.user_id = 10
        session.reference_document_text = reference_document_text
        session.reference_document_title = None
        return session

    def _make_message(self, content="질문"):
        from unittest.mock import MagicMock

        msg = MagicMock()
        msg.content = content
        msg.role = MagicMock()
        msg.role.name = "USER"
        return msg

    def _run(
        self, processor, session, messages, group_id=None, workspace_selection=None
    ):
        from unittest.mock import MagicMock

        db = MagicMock()
        redis = MagicMock()
        redis.get.return_value = None
        db.query.return_value.filter.return_value.first.return_value = session
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = messages

        processor.chat_repo.get_session_by_id_and_user.return_value = session
        processor.chat_repo.get_unsummarized_messages.return_value = messages

        processor.process_chat(
            redis,
            user_id=10,
            session_id=1,
            group_id=group_id,
            workspace_selection=workspace_selection,
        )

    def _make_processor(self):
        from unittest.mock import MagicMock, patch

        from services.chat.chat_processor import ChatProcessor

        with (
            patch("services.chat.chat_processor.LLMClient"),
            patch("services.chat.chat_processor.KnowledgeRetrievalService"),
            patch("services.chat.chat_processor.AnswerContextBuilder"),
        ):
            p = ChatProcessor(MagicMock(), MagicMock())
        p.llm_client = MagicMock()
        p.llm_client.stream_chat.return_value = []
        p.knowledge_retrieval = MagicMock()
        p.knowledge_retrieval.retrieve.return_value = []
        p.answer_context_builder = MagicMock()
        p.answer_context_builder.build.return_value = ""
        return p

    def test_no_selection_include_workspace_false(self):
        p = self._make_processor()
        self._run(p, self._make_session(), [self._make_message()])
        req = p.knowledge_retrieval.retrieve.call_args[0][0]
        assert req.include_workspace is False

    def test_with_selection_include_workspace_true(self):
        p = self._make_processor()
        sel = WorkspaceSelection(mode="all")
        self._run(
            p,
            self._make_session(),
            [self._make_message()],
            group_id=5,
            workspace_selection=sel,
        )
        req = p.knowledge_retrieval.retrieve.call_args[0][0]
        assert req.include_workspace is True
        assert req.group_id == 5
        assert req.workspace_selection.mode == "all"

    def test_selection_mode_documents_forwarded(self):
        p = self._make_processor()
        sel = WorkspaceSelection(mode="documents", document_ids=[10, 20])
        self._run(
            p,
            self._make_session(),
            [self._make_message()],
            group_id=3,
            workspace_selection=sel,
        )
        req = p.knowledge_retrieval.retrieve.call_args[0][0]
        assert req.workspace_selection.mode == "documents"
        assert req.workspace_selection.document_ids == [10, 20]
