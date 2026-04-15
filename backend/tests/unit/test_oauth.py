from unittest.mock import patch

from errors import AppException, ErrorCode


def test_social_login_success(client):
    with patch("domains.oauth.service.OAuthService.get_google_auth_url") as mock_url:
        mock_url.return_value = "https://accounts.google.com/o/oauth2/v2/auth"
        response = client.get("/api/auth/social/google/login", follow_redirects=False)
        assert response.status_code == 307
        assert "accounts.google.com" in response.headers["location"]


def test_social_login_failure_invalid_provider(client):
    with patch("domains.oauth.service.OAuthService.get_frontend_url") as mock_url:
        mock_url.return_value = "http://localhost:5173"
        response = client.get("/api/auth/social/invalid/login", follow_redirects=False)
        assert response.status_code == 307
        assert "invalid_provider" in response.headers["location"]


def test_social_callback_success(client):
    with patch(
        "domains.oauth.service.OAuthService.process_social_callback"
    ) as mock_process:
        mock_process.return_value = {
            "action": "login",
            "url": "http://localhost:5173/?login=success",
            "access_token": "acc",
            "refresh_token": "ref",
        }
        response = client.get(
            "/api/auth/social/google/callback?code=testcode", follow_redirects=False
        )
        assert response.status_code == 307
        assert "login=success" in response.headers["location"]
        assert "access_token" in response.cookies


def test_social_callback_failure_process(client):
    with patch(
        "domains.oauth.service.OAuthService.process_social_callback"
    ) as mock_process:
        mock_process.return_value = {
            "action": "redirect",
            "url": "http://localhost:5173/?error=social_auth_failed",
        }
        response = client.get(
            "/api/auth/social/google/callback?code=testcode", follow_redirects=False
        )
        assert response.status_code == 307
        assert "social_auth_failed" in response.headers["location"]


def test_unlink_social_account_success(authenticated_client):
    with patch(
        "domains.oauth.service.OAuthService.unlink_social_account"
    ) as mock_unlink:
        response = authenticated_client.delete("/api/auth/social/google/unlink")
        assert response.status_code == 200
        assert "google" in response.json()["message"]
        mock_unlink.assert_called_once()


def test_unlink_social_account_failure_not_found(authenticated_client):
    with patch(
        "domains.oauth.service.OAuthService.unlink_social_account",
        side_effect=AppException(ErrorCode.AUTH_FORBIDDEN),
    ):
        response = authenticated_client.delete("/api/auth/social/github/unlink")
        assert response.status_code == 403
