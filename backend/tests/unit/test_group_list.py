import pytest

from models.model import (
    Group,
    GroupMember,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
)
from tests.dummy_data import groups, users


# UT-GRP-002-01 사용자가 속한 ACTIVE 워크스페이스 목록을 정상 조회한다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_my_workspaces_success(client, db_session, logged_in_user):
    """사용자가 속한 ACTIVE 워크스페이스 목록이 정상 반환되는지 검증한다."""
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get("/api/groups")
    assert res.status_code == 200

    data = res.json()
    assert "groups" in data
    assert "has_blocked_owned_group" in data
    assert "blocked_owned_group_reason" in data

    assert len(data["groups"]) == 1
    assert data["has_blocked_owned_group"] is False
    assert data["blocked_owned_group_reason"] is None

    group = data["groups"][0]
    assert group["id"] == 1
    assert group["name"] == groups[0]["name"]
    assert group["description"] == groups[0]["description"]
    assert group["status"] == "ACTIVE"
    assert group["my_role"] == "OWNER"
    assert group["owner_username"] == users[0]["username"]


# UT-GRP-002-02 속한 워크스페이스가 없으면 빈 목록을 반환한다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_my_workspaces_empty(client, logged_in_user):
    """속한 워크스페이스가 없으면 빈 목록이 반환되는지 검증한다."""
    res = client.get("/api/groups")
    assert res.status_code == 200

    data = res.json()
    assert data["groups"] == []
    assert data["has_blocked_owned_group"] is False
    assert data["blocked_owned_group_reason"] is None


# UT-GRP-002-03 비로그인 사용자는 목록을 조회할 수 없다.
def test_get_my_workspaces_unauthenticated(client):
    """비로그인 사용자는 워크스페이스 목록 조회가 차단되는지 검증한다."""
    res = client.get("/api/groups")
    assert res.status_code == 401
