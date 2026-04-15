from datetime import datetime

from domains.auth.service import AuthService
from errors import ErrorCode
from models.model import User
from tests.dummy_data import (
    confirm_account_data,
    login_data,
    password_reset_data,
    refresh_token_data,
    signup_data,
)

auth_service = AuthService(None)


def test_signup_success(client, db_session, fake_redis):
    payload = signup_data["payload"].copy()
    email = payload["email"]
    fake_redis.setex(f"email_verified:{email}", 600, "1")
    response = client.post("/api/auth/signup", json=payload)
    assert response.status_code == 201
    assert fake_redis.get(f"email_verified:{email}") is None
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.username == payload["username"]


def test_signup_failure_no_verification(client, fake_redis):
    payload = signup_data["payload"].copy()
    response = client.post("/api/auth/signup", json=payload)
    assert response.status_code == 401
    assert response.json()["code"] == ErrorCode.USER_EMAIL_NOT_VERIFIED.code


def test_signup_failure_already_exists(client, registered_user, fake_redis):
    payload = signup_data["payload"].copy()
    payload["email"] = registered_user.email
    fake_redis.setex(f"email_verified:{payload['email']}", 600, "1")
    response = client.post("/api/auth/signup", json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == ErrorCode.USER_EMAIL_ALREADY_EXISTS.code


def test_signup_failure_username_exists(client, registered_user, fake_redis):
    payload = signup_data["payload"].copy()
    payload["username"] = registered_user.username
    fake_redis.setex(f"email_verified:{payload['email']}", 600, "1")
    response = client.post("/api/auth/signup", json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == ErrorCode.USER_USERNAME_ALREADY_EXISTS.code


def test_login_success(client, registered_user, fake_redis):
    payload = login_data["payload"].copy()
    payload["email"] = registered_user.email
    client_key = f"testclient:{payload['email']}"
    fake_redis.set(f"attempts:{client_key}", "1")
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    assert response.json()["email"] == payload["email"]
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    refresh_token = response.cookies.get("refresh_token")
    assert fake_redis.get(f"refresh_token:{refresh_token}") == payload["email"]
    assert fake_redis.get(f"attempts:{client_key}") is None


def test_login_failure_invalid_credentials(client, registered_user, fake_redis):
    payload = login_data["wrong_password_payload"].copy()
    payload["email"] = registered_user.email
    client_key = f"testclient:{payload['email']}"
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    assert response.json()["code"] == ErrorCode.USER_INVALID_CREDENTIALS.code
    assert fake_redis.get(f"attempts:{client_key}") == "1"


def test_login_failure_inactive(client, db_session, fake_redis):
    user_data = login_data["inactive_user"].copy()
    raw_password = user_data["password"]
    user_data["password"] = auth_service.hash_password(raw_password)
    user = User(**user_data)
    db_session.add(user)
    db_session.commit()
    payload = {"email": user_data["email"], "password": raw_password}
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCode.USER_INACTIVE.code


def test_login_failure_rate_limit(client, registered_user, fake_redis):
    payload = login_data["payload"].copy()
    payload["email"] = registered_user.email
    client_key = f"testclient:{payload['email']}"
    fake_redis.set(f"block:{client_key}", "1")
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 429
    assert response.json()["code"] == ErrorCode.USER_RATE_LIMIT_EXCEEDED.code


def test_login_failure_deactivate_pending(
    client, db_session, fake_redis, registered_user
):
    registered_user.is_active = False
    registered_user.deactivated_at = datetime.now()
    db_session.commit()
    payload = login_data["payload"].copy()
    payload["email"] = registered_user.email
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCode.USER_DEACTIVATE_PENDING.code


def test_refresh_token_success(client, registered_user, fake_redis):
    email = registered_user.email
    old_refresh_token = auth_service.create_refresh_token(email)
    fake_redis.set(f"refresh_token:{old_refresh_token}", email)
    client.cookies.set("refresh_token", old_refresh_token)
    response = client.post("/api/auth/refresh")
    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    new_refresh_token = response.cookies.get("refresh_token")
    assert fake_redis.get(f"refresh_token:{new_refresh_token}") == email


def test_refresh_token_failure_missing_cookie(client, fake_redis):
    response = client.post("/api/auth/refresh")
    assert response.status_code == 401
    assert response.json()["code"] == ErrorCode.AUTH_REFRESH_TOKEN_MISSING.code


def test_refresh_token_failure_expired_in_redis(client, fake_redis):
    test_email = login_data["payload"]["email"]
    refresh_token = auth_service.create_refresh_token(test_email)
    client.cookies.set("refresh_token", refresh_token)
    response = client.post("/api/auth/refresh")
    assert response.status_code == 401
    assert response.json()["code"] == ErrorCode.AUTH_REFRESH_TOKEN_EXPIRED.code


def test_refresh_token_failure_invalid_user(client, fake_redis):
    unregistered_email = refresh_token_data["payload"]["unregistered_email"]
    refresh_token = auth_service.create_refresh_token(unregistered_email)
    fake_redis.set(f"refresh_token:{refresh_token}", unregistered_email)
    client.cookies.set("refresh_token", refresh_token)
    response = client.post("/api/auth/refresh")
    assert response.status_code == 401
    assert response.json()["code"] == ErrorCode.AUTH_USER_INVALID.code


def test_logout_success(client, registered_user, fake_redis):
    email = registered_user.email
    refresh_token = auth_service.create_refresh_token(email)
    fake_redis.set(f"refresh_token:{refresh_token}", email)
    client.cookies.set("access_token", "valid_access_token")
    client.cookies.set("refresh_token", refresh_token)
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    assert fake_redis.get(f"refresh_token:{refresh_token}") is None
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(
        "access_token=;" in h or 'access_token=""' in h for h in set_cookie_headers
    )
    assert any(
        "refresh_token=;" in h or 'refresh_token=""' in h for h in set_cookie_headers
    )


def test_logout_no_cookie(client):
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(
        "access_token=;" in h or 'access_token=""' in h for h in set_cookie_headers
    )
    assert any(
        "refresh_token=;" in h or 'refresh_token=""' in h for h in set_cookie_headers
    )


def test_me_success(authenticated_client):
    response = authenticated_client.get("/api/auth/me")
    assert response.status_code == 200
    assert "email" in response.json()


def test_me_failure_unauthorized(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_confirm_account_success(client, registered_user, fake_redis):
    email = registered_user.email
    fake_redis.set(f"email_verified:{email}", "1")
    payload = {"email": email}
    response = client.post("/api/auth/confirm-account", json=payload)
    assert response.status_code == 200
    assert response.json()["email"] == email


def test_confirm_account_failure_not_verified(client, fake_redis):
    payload = {"email": confirm_account_data["payload"]["email"]}
    response = client.post("/api/auth/confirm-account", json=payload)
    assert response.status_code == 401
    assert response.json()["code"] == ErrorCode.USER_EMAIL_NOT_VERIFIED.code


def test_confirm_account_failure_user_not_found(client, fake_redis):
    unregistered_email = confirm_account_data["payload"]["unregistered_email"]
    fake_redis.set(f"email_verified:{unregistered_email}", "1")
    payload = {"email": unregistered_email}
    response = client.post("/api/auth/confirm-account", json=payload)
    assert response.status_code == 404
    assert response.json()["code"] == ErrorCode.USER_ACCOUNT_NOT_FOUND.code


def test_reset_password_success(client, db_session, registered_user, fake_redis):
    email = registered_user.email
    new_password = password_reset_data["payload"]["new_password"]
    fake_redis.set(f"email_verified:{email}", "1")
    payload = {"email": email, "new_password": new_password}
    response = client.post("/api/auth/reset-password", json=payload)
    assert response.status_code == 204
    assert fake_redis.get(f"email_verified:{email}") is None
    db_session.refresh(registered_user)
    assert auth_service.verify_password(new_password, registered_user.password) is True


def test_reset_password_failure_not_verified(client, fake_redis):
    payload = {
        "email": password_reset_data["payload"]["email"],
        "new_password": password_reset_data["payload"]["new_password"],
    }
    response = client.post("/api/auth/reset-password", json=payload)
    assert response.status_code == 401
    assert response.json()["code"] == ErrorCode.USER_EMAIL_NOT_VERIFIED.code


def test_reset_password_failure_user_not_found(client, fake_redis):
    unregistered_email = password_reset_data["payload"]["unregistered_email"]
    new_password = password_reset_data["payload"]["new_password"]
    fake_redis.set(f"email_verified:{unregistered_email}", "1")
    payload = {"email": unregistered_email, "new_password": new_password}
    response = client.post("/api/auth/reset-password", json=payload)
    assert response.status_code == 404
    assert response.json()["code"] == ErrorCode.USER_NOT_FOUND.code


def test_deactivate_account_success(authenticated_client, db_session, fake_redis):
    from models.model import Group

    db_session.query(Group).filter(Group.owner_user_id == 1).delete()
    db_session.commit()

    fake_redis.set("email_verified:testuser@example.com", "1")
    response = authenticated_client.delete("/api/auth/deactivate")
    assert response.status_code == 204


def test_deactivate_account_failure_as_owner(
    authenticated_client, db_session, fake_redis
):
    from models.model import Group, User

    user = db_session.query(User).filter(User.email == "testuser@example.com").first()
    group = Group(name="Test Group", owner_user_id=user.id)
    db_session.add(group)
    db_session.commit()

    fake_redis.set("email_verified:testuser@example.com", "1")
    response = authenticated_client.delete("/api/auth/deactivate")

    assert response.status_code == 400
    assert response.json()["code"] == ErrorCode.USER_WITHDRAWAL_AS_OWNER_RESTRICTED.code


def test_deactivate_account_failure_not_verified(authenticated_client):
    response = authenticated_client.delete("/api/auth/deactivate")
    assert response.status_code == 401


def test_reactivate_account_success(client, db_session, registered_user):
    registered_user.is_active = False
    db_session.commit()
    payload = {
        "email": registered_user.email,
        "password": login_data["payload"]["password"],
    }
    response = client.post("/api/auth/reactivate", json=payload)
    assert response.status_code == 200


def test_reactivate_account_failure_invalid_credentials(client, registered_user):
    payload = {"email": registered_user.email, "password": "wrong_password"}
    response = client.post("/api/auth/reactivate", json=payload)
    assert response.status_code == 401


def test_reactivate_account_failure_rate_limit(client, registered_user, fake_redis):
    payload = {
        "email": registered_user.email,
        "password": login_data["payload"]["password"],
    }
    client_key = f"testclient:{payload['email']}"
    fake_redis.set(f"block:{client_key}", "1")
    response = client.post("/api/auth/reactivate", json=payload)
    assert response.status_code == 429
    assert response.json()["code"] == ErrorCode.USER_RATE_LIMIT_EXCEEDED.code


def test_update_username_success(authenticated_client):
    payload = {"new_username": "new_name"}
    response = authenticated_client.patch("/api/auth/username", json=payload)
    assert response.status_code == 200


def test_update_username_failure_already_exists(authenticated_client):
    payload = {"new_username": "관리자"}
    response = authenticated_client.patch("/api/auth/username", json=payload)
    assert response.status_code == 409


def test_update_password_success(authenticated_client):
    payload = {
        "current_password": "password123!",
        "new_password": "newpassword456!",
        "confirm_new_password": "newpassword456!",
    }
    response = authenticated_client.patch("/api/auth/password", json=payload)
    assert response.status_code == 204


def test_update_password_failure_invalid_credentials(authenticated_client):
    payload = {
        "current_password": "wrong_password",
        "new_password": "newpassword456!",
        "confirm_new_password": "newpassword456!",
    }
    response = authenticated_client.patch("/api/auth/password", json=payload)
    assert response.status_code == 401


def test_subscribe_premium_success(authenticated_client):
    payload = {"confirm": True}
    response = authenticated_client.post(
        "/api/auth/subscription/subscribe", json=payload
    )
    assert response.status_code == 200


def test_subscribe_premium_failure_not_confirmed(authenticated_client):
    payload = {"confirm": False}
    response = authenticated_client.post(
        "/api/auth/subscription/subscribe", json=payload
    )
    assert response.status_code == 403


def test_cancel_subscription_success(authenticated_client):
    payload = {"confirm": True}
    response = authenticated_client.post("/api/auth/subscription/cancel", json=payload)
    assert response.status_code == 200


def test_cancel_subscription_failure_not_confirmed(authenticated_client):
    payload = {"confirm": False}
    response = authenticated_client.post("/api/auth/subscription/cancel", json=payload)
    assert response.status_code == 403
