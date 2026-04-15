from unittest.mock import patch

from errors import AppException, ErrorCode


def test_get_notification_settings_success(authenticated_client):
    with patch(
        "domains.notification.service.NotificationService.get_all_settings"
    ) as mock_get:
        mock_get.return_value = [
            {
                "notification_type": "WORKSPACE_INVITED",
                "is_enabled": True,
                "is_toast_enabled": True,
            }
        ]
        response = authenticated_client.get("/api/notifications/settings")
        assert response.status_code == 200


def test_get_notification_settings_failure_unauthorized(client):
    response = client.get("/api/notifications/settings")
    assert response.status_code == 401


def test_update_notification_setting_success(authenticated_client):
    payload = {
        "notification_type": "WORKSPACE_INVITED",
        "is_enabled": False,
        "is_toast_enabled": False,
    }
    with patch(
        "domains.notification.service.NotificationService.upsert_setting"
    ) as mock_upsert:
        mock_upsert.return_value = {
            "notification_type": "WORKSPACE_INVITED",
            "is_enabled": False,
            "is_toast_enabled": False,
        }
        response = authenticated_client.patch(
            "/api/notifications/settings", json=payload
        )
        assert response.status_code == 200


def test_update_notification_setting_failure_unauthorized(client):
    payload = {
        "notification_type": "WORKSPACE_INVITED",
        "is_enabled": False,
        "is_toast_enabled": False,
    }
    response = client.patch("/api/notifications/settings", json=payload)
    assert response.status_code == 401


def test_get_notifications_success(authenticated_client):
    with patch(
        "domains.notification.service.NotificationService.get_notifications"
    ) as mock_get:
        mock_get.return_value = [
            {
                "id": 1,
                "user_id": 1,
                "actor_user_id": None,
                "group_id": None,
                "type": "WORKSPACE_INVITED",
                "title": "Test",
                "body": None,
                "is_read": False,
                "read_at": None,
                "target_type": None,
                "target_id": None,
                "created_at": "2023-01-01T00:00:00Z",
            }
        ]
        response = authenticated_client.get("/api/notifications")
        assert response.status_code == 200


def test_get_notifications_failure_unauthorized(client):
    response = client.get("/api/notifications")
    assert response.status_code == 401


def test_mark_notification_as_read_success(authenticated_client):
    with patch(
        "domains.notification.service.NotificationService.mark_as_read"
    ) as mock_mark:
        mock_mark.return_value = {
            "id": 1,
            "user_id": 1,
            "actor_user_id": None,
            "group_id": None,
            "type": "WORKSPACE_INVITED",
            "title": "Test",
            "body": None,
            "is_read": True,
            "read_at": "2023-01-01T01:00:00Z",
            "target_type": None,
            "target_id": None,
            "created_at": "2023-01-01T00:00:00Z",
        }
        response = authenticated_client.patch("/api/notifications/1/read")
        assert response.status_code == 200


def test_mark_notification_as_read_failure_not_found(authenticated_client):
    with patch(
        "domains.notification.service.NotificationService.mark_as_read",
        side_effect=AppException(ErrorCode.USER_NOT_FOUND),
    ):
        response = authenticated_client.patch("/api/notifications/999/read")
        assert response.status_code == 404


def test_mark_all_notifications_as_read_success(authenticated_client):
    with patch(
        "domains.notification.service.NotificationService.mark_all_as_read"
    ) as mock_mark_all:
        response = authenticated_client.patch("/api/notifications/read-all")
        assert response.status_code == 204
        mock_mark_all.assert_called_once()


def test_mark_all_notifications_as_read_failure_unauthorized(client):
    response = client.patch("/api/notifications/read-all")
    assert response.status_code == 401


def test_delete_notification_success(authenticated_client):
    with patch(
        "domains.notification.service.NotificationService.delete_notification"
    ) as mock_delete:
        response = authenticated_client.delete("/api/notifications/1")
        assert response.status_code == 204
        mock_delete.assert_called_once()


def test_delete_notification_failure_not_found(authenticated_client):
    with patch(
        "domains.notification.service.NotificationService.delete_notification",
        side_effect=AppException(ErrorCode.USER_NOT_FOUND),
    ):
        response = authenticated_client.delete("/api/notifications/999")
        assert response.status_code == 404
