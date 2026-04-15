from unittest.mock import patch

from errors import AppException, ErrorCode


def test_get_sessions_success(authenticated_client):
    with patch("domains.chat.service.ChatService.get_sessions") as mock_get:
        mock_get.return_value = [
            {
                "id": 1,
                "user_id": 1,
                "title": "Test Session",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
            }
        ]
        response = authenticated_client.get("/api/chat/sessions")
        assert response.status_code == 200


def test_get_sessions_failure_unauthorized(client):
    response = client.get("/api/chat/sessions")
    assert response.status_code == 401


def test_create_session_success(authenticated_client):
    payload = {"title": "New Session"}
    with patch("domains.chat.service.ChatService.create_session") as mock_create:
        mock_create.return_value = {
            "id": 1,
            "user_id": 1,
            "title": "New Session",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        }
        response = authenticated_client.post("/api/chat/sessions", json=payload)
        assert response.status_code == 200


def test_create_session_failure_unauthorized(client):
    payload = {"title": "New Session"}
    response = client.post("/api/chat/sessions", json=payload)
    assert response.status_code == 401


def test_update_session_success(authenticated_client):
    payload = {"title": "Updated Session"}
    with patch("domains.chat.service.ChatService.update_session") as mock_update:
        mock_update.return_value = {
            "id": 1,
            "user_id": 1,
            "title": "Updated Session",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        }
        response = authenticated_client.put("/api/chat/sessions/1", json=payload)
        assert response.status_code == 200


def test_update_session_failure_not_found(authenticated_client):
    payload = {"title": "Updated Session"}
    with patch(
        "domains.chat.service.ChatService.update_session",
        side_effect=AppException(ErrorCode.CHAT_ROOM_NOT_FOUND),
    ):
        response = authenticated_client.put("/api/chat/sessions/999", json=payload)
        assert response.status_code == 404


def test_delete_session_success(authenticated_client):
    with patch("domains.chat.service.ChatService.delete_session") as mock_delete:
        response = authenticated_client.delete("/api/chat/sessions/1")
        assert response.status_code == 204
        mock_delete.assert_called_once()


def test_delete_session_failure_unauthorized(client):
    response = client.delete("/api/chat/sessions/1")
    assert response.status_code == 401


def test_get_messages_success(authenticated_client):
    with patch("domains.chat.service.ChatService.get_messages") as mock_get:
        mock_get.return_value = {
            "messages": [
                {
                    "id": 1,
                    "session_id": 1,
                    "role": "user",
                    "content": "Hello",
                    "created_at": "2023-01-01T00:00:00Z",
                }
            ],
            "is_processing": False,
        }
        response = authenticated_client.get("/api/chat/sessions/1/messages")
        assert response.status_code == 200


def test_get_messages_failure_not_found(authenticated_client):
    with patch(
        "domains.chat.service.ChatService.get_messages",
        side_effect=AppException(ErrorCode.CHAT_ROOM_NOT_FOUND),
    ):
        response = authenticated_client.get("/api/chat/sessions/999/messages")
        assert response.status_code == 404


def test_get_messages_failure_unauthorized_access(authenticated_client):
    with patch(
        "domains.chat.service.ChatService.get_messages",
        side_effect=AppException(ErrorCode.CHAT_UNAUTHORIZED),
    ):
        response = authenticated_client.get("/api/chat/sessions/999/messages")
        assert response.status_code == 403


def test_send_message_success(authenticated_client):
    payload = {"text": "Hello Chat"}
    with patch("domains.chat.service.ChatService.send_message") as mock_send:
        mock_send.return_value = {"status": "success", "task_id": "12345"}
        response = authenticated_client.post(
            "/api/chat/sessions/1/messages", data=payload
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"


def test_send_message_failure_unauthorized(client):
    response = client.post("/api/chat/sessions/1/messages", data={"text": "Hello"})
    assert response.status_code == 401


def test_send_message_failure_workspace_without_group(authenticated_client):
    payload = {
        "text": "Hello",
        "workspace_selection_json": '{"mode": "all", "document_ids": []}',
    }
    response = authenticated_client.post("/api/chat/sessions/1/messages", data=payload)
    assert response.status_code == 422
    assert "group_id" in response.json()["detail"]


def test_stop_message_success(authenticated_client):
    with patch("domains.chat.service.ChatService.stop_message") as mock_stop:
        mock_stop.return_value = {"status": "success", "message": "Task stopped"}
        response = authenticated_client.post("/api/chat/sessions/1/stop")
        assert response.status_code == 200
        mock_stop.assert_called_once()


def test_stop_message_failure_not_found(authenticated_client):
    with patch(
        "domains.chat.service.ChatService.stop_message",
        side_effect=AppException(ErrorCode.CHAT_ROOM_NOT_FOUND),
    ):
        response = authenticated_client.post("/api/chat/sessions/999/stop")
        assert response.status_code == 404


def test_delete_reference_document_success(authenticated_client):
    with patch(
        "domains.chat.service.ChatService.delete_reference_document"
    ) as mock_delete:
        mock_delete.return_value = {
            "id": 1,
            "user_id": 1,
            "title": "Session",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        }
        response = authenticated_client.delete("/api/chat/sessions/1/reference")
        assert response.status_code == 200
        mock_delete.assert_called_once()


def test_delete_reference_document_failure_not_found(authenticated_client):
    with patch(
        "domains.chat.service.ChatService.delete_reference_document",
        side_effect=AppException(ErrorCode.CHAT_ROOM_NOT_FOUND),
    ):
        response = authenticated_client.delete("/api/chat/sessions/999/reference")
        assert response.status_code == 404


def test_delete_reference_group_success(authenticated_client):
    with patch(
        "domains.chat.service.ChatService.delete_reference_group"
    ) as mock_delete:
        mock_delete.return_value = {
            "id": 1,
            "user_id": 1,
            "title": "Session",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        }
        response = authenticated_client.delete("/api/chat/sessions/1/reference-group")
        assert response.status_code == 200
        mock_delete.assert_called_once()


def test_delete_reference_group_failure_not_found(authenticated_client):
    with patch(
        "domains.chat.service.ChatService.delete_reference_group",
        side_effect=AppException(ErrorCode.CHAT_ROOM_NOT_FOUND),
    ):
        response = authenticated_client.delete("/api/chat/sessions/999/reference-group")
        assert response.status_code == 404
