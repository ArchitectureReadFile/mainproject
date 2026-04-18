from unittest.mock import MagicMock, patch

import pytest

from domains.chat.service import ChatService
from domains.knowledge.schemas import WorkspaceSelection
from errors import AppException, ErrorCode
from redis_client import redis_client


def test_send_message_raises_when_chat_enqueue_fails():
    chat_repo = MagicMock()
    auth_service = MagicMock()
    group_service = MagicMock()
    service = ChatService(chat_repo, auth_service, group_service)
    session = MagicMock()
    session.reference_group_id = 99

    redis_client.delete("chat_task:11")

    with (
        patch.object(service, "_get_session_with_permission", return_value=session),
        patch.object(service, "_require_group_membership"),
        patch(
            "domains.chat.tasks.process_chat_message.delay",
            side_effect=RuntimeError("queue down"),
        ),
    ):
        with pytest.raises(AppException) as exc_info:
            service.send_message(
                user_id=1,
                session_id=11,
                text="질문",
                group_id=10,
                workspace_selection=WorkspaceSelection(mode="all"),
            )

    assert exc_info.value.error_code == ErrorCode.CHAT_ENQUEUE_FAILED
    assert redis_client.get("chat_task:11") is None
    assert chat_repo.commit.call_count == 2
    chat_repo.delete_message.assert_called_once()
    assert session.reference_group_id == 99


def test_send_message_raises_when_chat_already_processing():
    chat_repo = MagicMock()
    auth_service = MagicMock()
    group_service = MagicMock()
    service = ChatService(chat_repo, auth_service, group_service)
    session = MagicMock()
    session.reference_group_id = None

    redis_client.set("chat_task:11", "task-123", ex=60)

    try:
        with patch.object(
            service, "_get_session_with_permission", return_value=session
        ):
            with pytest.raises(AppException) as exc_info:
                service.send_message(
                    user_id=1,
                    session_id=11,
                    text="질문",
                )
    finally:
        redis_client.delete("chat_task:11")

    assert exc_info.value.error_code == ErrorCode.CHAT_ALREADY_PROCESSING
    chat_repo.add_message.assert_not_called()
    chat_repo.commit.assert_not_called()


def test_send_message_raises_when_chat_lock_is_already_held():
    chat_repo = MagicMock()
    auth_service = MagicMock()
    group_service = MagicMock()
    service = ChatService(chat_repo, auth_service, group_service)
    session = MagicMock()
    session.reference_group_id = None

    redis_client.set("chat_task_lock:11", "lock-token", ex=60)

    try:
        with patch.object(
            service, "_get_session_with_permission", return_value=session
        ):
            with pytest.raises(AppException) as exc_info:
                service.send_message(
                    user_id=1,
                    session_id=11,
                    text="질문",
                )
    finally:
        redis_client.delete("chat_task_lock:11")

    assert exc_info.value.error_code == ErrorCode.CHAT_ALREADY_PROCESSING
    chat_repo.add_message.assert_not_called()
    chat_repo.commit.assert_not_called()
