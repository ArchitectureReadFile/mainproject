import json
from unittest.mock import MagicMock, patch

from errors import ErrorCode, FailureStage


def _make_processor():
    from domains.chat.processor import ChatProcessor

    with (
        patch("domains.chat.processor.LLMClient"),
        patch("domains.chat.processor.KnowledgeRetrievalService"),
        patch("domains.chat.processor.AnswerContextBuilder"),
    ):
        processor = ChatProcessor(MagicMock(), MagicMock())

    processor.llm_client = MagicMock()
    processor.knowledge_retrieval = MagicMock()
    processor.answer_context_builder = MagicMock()
    processor.notification_service = MagicMock()
    return processor


def test_publish_error_includes_failure_fields_and_legacy_fields():
    processor = _make_processor()
    redis_client = MagicMock()

    processor._publish_error(
        redis_client,
        session_id=1,
        user_id=10,
        stage=FailureStage.PROCESS,
        error_code=ErrorCode.CHAT_HISTORY_LOAD_FAILED,
    )

    payload = json.loads(redis_client.publish.call_args.args[1])
    assert payload["status"] == "error"
    assert payload["failure_stage"] == "process"
    assert payload["failure_code"] == ErrorCode.CHAT_HISTORY_LOAD_FAILED.code
    assert payload["error_message"] == ErrorCode.CHAT_HISTORY_LOAD_FAILED.message
    assert payload["code"] == ErrorCode.CHAT_HISTORY_LOAD_FAILED.code
    assert payload["message"] == ErrorCode.CHAT_HISTORY_LOAD_FAILED.message


def test_process_chat_missing_session_publishes_process_stage_error():
    processor = _make_processor()
    redis_client = MagicMock()
    processor.chat_repo.get_session_by_id_and_user.return_value = None

    processor.process_chat(redis_client, user_id=10, session_id=1)

    error_payload = json.loads(redis_client.publish.call_args_list[-1].args[1])
    assert error_payload["status"] == "error"
    assert error_payload["failure_stage"] == "process"
    assert error_payload["failure_code"] == ErrorCode.CHAT_ROOM_NOT_FOUND.code
    assert error_payload["error_message"] == ErrorCode.CHAT_ROOM_NOT_FOUND.message


def test_process_chat_persists_retrieval_failures_in_metadata():
    from models.model import ChatMessageRole

    processor = _make_processor()
    redis_client = MagicMock()
    session = MagicMock()
    session.reference = None
    user_message = MagicMock(role=ChatMessageRole.USER, content="질문", id=1)

    processor.chat_repo.get_session_by_id_and_user.return_value = session
    processor.chat_repo.get_unsummarized_messages.return_value = [user_message]
    processor.answer_context_builder.build.return_value = ""

    def _retrieve(*args, **kwargs):
        kwargs["failure_metadata"].append(
            {
                "status": "error",
                "failure_stage": "retrieve",
                "failure_code": ErrorCode.CHAT_RETRIEVAL_FAILED.code,
                "error_message": ErrorCode.CHAT_RETRIEVAL_FAILED.message,
                "retryable": False,
                "retriever": "platform",
                "exception_type": "RuntimeError",
            }
        )
        return []

    processor.knowledge_retrieval.retrieve.side_effect = _retrieve
    processor.llm_client.stream_chat.return_value = [
        {"message": {"content": "답변"}},
    ]

    processor.process_chat(redis_client, user_id=10, session_id=1)

    stored_message = processor.chat_repo.add_message.call_args[0][0]
    metadata = json.loads(stored_message.metadata_json)
    assert metadata["retrieval_failures"] == [
        {
            "status": "error",
            "failure_stage": "retrieve",
            "failure_code": ErrorCode.CHAT_RETRIEVAL_FAILED.code,
            "error_message": ErrorCode.CHAT_RETRIEVAL_FAILED.message,
            "retryable": False,
            "retriever": "platform",
            "exception_type": "RuntimeError",
        }
    ]
