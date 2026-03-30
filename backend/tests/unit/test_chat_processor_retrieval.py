"""
tests/unit/test_chat_processor_retrieval.py

ChatProcessor retrieval 전환 단위 테스트.
LLMClient / KnowledgeRetrievalService / AnswerContextBuilder는 mock으로 격리한다.
스트리밍 / DB 저장 / Redis publish 흐름은 별도 검증하지 않는다.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schemas.knowledge import KnowledgeRetrievalRequest, RetrievedKnowledgeItem


def _make_session(
    session_id: int = 1,
    user_id: int = 10,
    reference_document_text: str | None = None,
    reference_document_title: str | None = None,
):
    session = MagicMock()
    session.id = session_id
    session.user_id = user_id
    session.reference_document_text = reference_document_text
    session.reference_document_title = reference_document_title
    return session


def _make_message(content: str, role="USER"):
    msg = MagicMock()
    msg.content = content
    msg.role = MagicMock()
    msg.role.name = role
    return msg


def _item(knowledge_type: str) -> RetrievedKnowledgeItem:
    return RetrievedKnowledgeItem(
        knowledge_type=knowledge_type,  # type: ignore
        source_type="test",
        source_id=1,
        title="제목",
        chunk_text="내용",
        score=0.9,
    )


@pytest.fixture
def processor():
    from services.chat.chat_processor import ChatProcessor

    with (
        patch("services.chat.chat_processor.LLMClient"),
        patch("services.chat.chat_processor.KnowledgeRetrievalService"),
        patch("services.chat.chat_processor.AnswerContextBuilder"),
    ):
        p = ChatProcessor()
        p.llm_client = MagicMock()
        p.llm_client.stream_chat.return_value = []
        p.knowledge_retrieval = MagicMock()
        p.answer_context_builder = MagicMock()
        return p


def _run(processor, session, messages):
    """process_chat 핵심 흐름만 직접 호출 (DB/Redis 격리)."""
    db = MagicMock()
    redis = MagicMock()
    redis.get.return_value = None

    db.query.return_value.filter.return_value.first.return_value = session
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
        messages
    )

    processor.process_chat(db, redis, user_id=session.user_id, session_id=session.id)
    return db, redis


# ── include_platform 항상 True ────────────────────────────────────────────────


class TestPlatformAlwaysOn:
    def test_include_platform_true(self, processor):
        session = _make_session()
        processor.knowledge_retrieval.retrieve.return_value = []
        processor.answer_context_builder.build.return_value = ""

        _run(processor, session, [_make_message("질문")])

        call_args = processor.knowledge_retrieval.retrieve.call_args
        request: KnowledgeRetrievalRequest = call_args[0][0]
        assert request.include_platform is True


# ── include_session 조건부 ────────────────────────────────────────────────────


class TestSessionConditional:
    def test_include_session_true_when_doc_exists(self, processor):
        session = _make_session(
            reference_document_text="첨부 문서 내용",
            reference_document_title="계약서",
        )
        processor.knowledge_retrieval.retrieve.return_value = []
        processor.answer_context_builder.build.return_value = ""

        _run(processor, session, [_make_message("질문")])

        call_args = processor.knowledge_retrieval.retrieve.call_args
        request: KnowledgeRetrievalRequest = call_args[0][0]
        assert request.include_session is True

    def test_include_session_false_when_no_doc(self, processor):
        session = _make_session(reference_document_text=None)
        processor.knowledge_retrieval.retrieve.return_value = []
        processor.answer_context_builder.build.return_value = ""

        _run(processor, session, [_make_message("질문")])

        call_args = processor.knowledge_retrieval.retrieve.call_args
        request: KnowledgeRetrievalRequest = call_args[0][0]
        assert request.include_session is False

    def test_session_title_forwarded(self, processor):
        session = _make_session(
            reference_document_text="내용",
            reference_document_title="계약서 제목",
        )
        processor.knowledge_retrieval.retrieve.return_value = []
        processor.answer_context_builder.build.return_value = ""

        _run(processor, session, [_make_message("질문")])

        kwargs = processor.knowledge_retrieval.retrieve.call_args[1]
        assert kwargs.get("session_title") == "계약서 제목"


# ── include_workspace 기본 off ────────────────────────────────────────────────


class TestWorkspaceDefaultOff:
    def test_include_workspace_false_by_default(self, processor):
        session = _make_session()
        processor.knowledge_retrieval.retrieve.return_value = []
        processor.answer_context_builder.build.return_value = ""

        _run(processor, session, [_make_message("질문")])

        call_args = processor.knowledge_retrieval.retrieve.call_args
        request: KnowledgeRetrievalRequest = call_args[0][0]
        assert request.include_workspace is False


# ── rag_context system_content 반영 ──────────────────────────────────────────


class TestContextAttached:
    def test_rag_context_appended_to_system_content(self, processor):
        session = _make_session()
        processor.knowledge_retrieval.retrieve.return_value = [_item("platform")]
        processor.answer_context_builder.build.return_value = "[플랫폼 지식]\n판례 내용"
        processor.llm_client.stream_chat.return_value = []

        _run(processor, session, [_make_message("질문")])

        call_args = processor.llm_client.stream_chat.call_args
        messages = call_args[0][0]
        system_msg = next(m for m in messages if m["role"] == "system")
        assert "[플랫폼 지식]" in system_msg["content"]

    def test_empty_rag_context_not_appended(self, processor):
        session = _make_session()
        processor.knowledge_retrieval.retrieve.return_value = []
        processor.answer_context_builder.build.return_value = ""
        processor.llm_client.stream_chat.return_value = []

        _run(processor, session, [_make_message("질문")])

        call_args = processor.llm_client.stream_chat.call_args
        messages = call_args[0][0]
        system_msg = next(m for m in messages if m["role"] == "system")
        assert "[플랫폼 지식]" not in system_msg["content"]
        assert "[워크스페이스 문서]" not in system_msg["content"]
        assert "[임시 문서]" not in system_msg["content"]


# ── retrieval 실패 시 흐름 유지 ───────────────────────────────────────────────


class TestRetrievalFailure:
    def test_retrieval_exception_does_not_crash_processor(self, processor):
        session = _make_session()
        processor.knowledge_retrieval.retrieve.side_effect = RuntimeError("검색 실패")
        processor.llm_client.stream_chat.return_value = []

        # 예외 없이 완료되어야 한다
        _run(processor, session, [_make_message("질문")])
        processor.llm_client.stream_chat.assert_called_once()
