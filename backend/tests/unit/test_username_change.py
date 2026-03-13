import pytest

from tests.dummy_data import users


# --------------------------------------------------
# 정상적인 이름 변경
# --------------------------------------------------
@pytest.mark.parametrize("logged_in_user", users, indirect=True)
def test_update_username_success(client, logged_in_user):
    response = client.patch("/api/auth/username", json={"username": "newname"})
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newname"
    assert logged_in_user.username == "newname"


# --------------------------------------------------
# 최소 길이 제한(2차) 검증 -> 422 반환
# --------------------------------------------------
@pytest.mark.parametrize("logged_in_user", users, indirect=True)
def test_update_username_too_short(client, logged_in_user):
    response = client.patch(
        "/api/auth/username",
        json={"username": "a"},  # 1글자 -> 실패
    )
    assert response.status_code == 422


# --------------------------------------------------
# 최대 길이 제한(10자) 검증 -> 422 반환
# --------------------------------------------------
@pytest.mark.parametrize("logged_in_user", users, indirect=True)
def test_update_username_too_long(client, logged_in_user):
    response = client.patch(
        "/api/auth/username",
        json={"username": "a" * 11},  # 11글자 -> 실패
    )
    assert response.status_code == 422


# --------------------------------------------------
# username 필드 없을 경우 -> FastAPI가 자동으로 422 반환
# --------------------------------------------------
@pytest.mark.parametrize("logged_in_user", users, indirect=True)
def test_update_username_empty(client, logged_in_user):
    response = client.patch(
        "/api/auth/username",
        json={},  # 필드 없음
    )
    assert response.status_code == 422
