from unittest.mock import patch

from errors import ErrorCode
from tests.dummy_data import email_verification_data


def test_send_verification_code_success(client, fake_redis):
    email = email_verification_data["payload"]["valid_email"]

    with patch("services.email_service.EmailService._send_email") as mock_send:
        response = client.post(
            "/api/email/send-verification-code", json={"email": email}
        )

        assert response.status_code == 200

        stored_code = fake_redis.get(f"email_verify:{email}")
        assert stored_code is not None
        if isinstance(stored_code, bytes):
            stored_code = stored_code.decode("utf-8")
        assert len(stored_code) == 6
        mock_send.assert_called_once()


def test_send_verification_code_failure_smtp_error(client, fake_redis):
    email = email_verification_data["payload"]["valid_email"]

    with patch(
        "services.email_service.EmailService._send_email",
        side_effect=Exception("SMTP Failed"),
    ):
        response = client.post(
            "/api/email/send-verification-code", json={"email": email}
        )

        assert response.status_code == 500
        assert response.json()["code"] == ErrorCode.EMAIL_SEND_FAILED.code
        assert fake_redis.get(f"email_verify:{email}") is None


def test_verify_code_success(client, fake_redis):
    email = email_verification_data["payload"]["valid_email"]
    code = email_verification_data["payload"]["valid_code"]

    fake_redis.setex(f"email_verify:{email}", 180, code)

    response = client.post(
        "/api/email/verify-code", json={"email": email, "code": code}
    )

    assert response.status_code == 200
    assert fake_redis.get(f"email_verify:{email}") is None
    assert fake_redis.get(f"email_verified:{email}") is not None


def test_verify_code_failure_not_found(client, fake_redis):
    email = email_verification_data["payload"]["valid_email"]
    code = email_verification_data["payload"]["valid_code"]

    response = client.post(
        "/api/email/verify-code", json={"email": email, "code": code}
    )

    assert response.status_code == 400
    assert response.json()["code"] == ErrorCode.EMAIL_CODE_NOT_FOUND.code


def test_verify_code_failure_mismatch(client, fake_redis):
    email = email_verification_data["payload"]["valid_email"]
    valid_code = email_verification_data["payload"]["valid_code"]
    invalid_code = email_verification_data["payload"]["invalid_code"]

    fake_redis.setex(f"email_verify:{email}", 180, valid_code)

    response = client.post(
        "/api/email/verify-code", json={"email": email, "code": invalid_code}
    )

    assert response.status_code == 400
    assert response.json()["code"] == ErrorCode.EMAIL_CODE_MISMATCH.code
