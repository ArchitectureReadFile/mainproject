import pytest

from models.model import (
    Group,
    GroupMember,
    GroupPendingReason,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
)
from tests.dummy_data import groups, users


# UT-GRP-002-01 사용자가 속한 ACTIVE 워크스페이스 목록을 정상 조회한다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_my_workspaces_success(client, db_session, logged_in_user):
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status="ACTIVE",
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
    res = client.get("/api/groups")
    assert res.status_code == 200

    data = res.json()
    assert data["groups"] == []
    assert data["has_blocked_owned_group"] is False
    assert data["blocked_owned_group_reason"] is None


# UT-GRP-002-03 비로그인 사용자는 목록을 조회할 수 없다.
def test_get_my_workspaces_unauthenticated(client):
    res = client.get("/api/groups")
    assert res.status_code == 401


# UT-GRP-002-04 OWNER인 BLOCKED 워크스페이스는 목록에서 제외되고 차단 플래그가 반환된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_my_workspaces_excludes_blocked_owned_group_and_returns_flag(
    client, db_session, logged_in_user
):
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="차단된 워크스페이스",
            description="차단 테스트",
            status=GroupStatus.BLOCKED,
            pending_reason=GroupPendingReason.SUBSCRIPTION_EXPIRED,
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
    assert data["groups"] == []
    assert data["has_blocked_owned_group"] is True
    assert data["blocked_owned_group_reason"] == "SUBSCRIPTION_EXPIRED"


# UT-GRP-002-05 DELETE_PENDING 워크스페이스는 목록에 포함되고 상태값이 함께 반환된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_my_workspaces_includes_delete_pending_group(
    client, db_session, logged_in_user
):
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="삭제 대기 워크스페이스",
            description="삭제 대기 테스트",
            status=GroupStatus.DELETE_PENDING,
            pending_reason=GroupPendingReason.OWNER_DELETE_REQUEST,
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
    assert len(data["groups"]) == 1
    assert data["has_blocked_owned_group"] is False
    assert data["blocked_owned_group_reason"] is None

    group = data["groups"][0]
    assert group["id"] == 1
    assert group["name"] == "삭제 대기 워크스페이스"
    assert group["status"] == "DELETE_PENDING"
    assert group["pending_reason"] == "OWNER_DELETE_REQUEST"
    assert group["my_role"] == "OWNER"


# UT-GRP-002-06 BLOCKED 상태의 비소유 워크스페이스는 목록에서 제외되고 차단 플래그는 반환되지 않는다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_my_workspaces_excludes_blocked_non_owned_group_without_flag(
    client, db_session, logged_in_user
):
    from models.model import User
    from services.auth_service import AuthService

    auth_service = AuthService(None)

    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    db_session.add(User(**owner_data))
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=2,
            name="차단된 참여 워크스페이스",
            description="차단 테스트",
            status=GroupStatus.BLOCKED,
            pending_reason=GroupPendingReason.SUBSCRIPTION_EXPIRED,
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get("/api/groups")
    assert res.status_code == 200

    data = res.json()
    assert data["groups"] == []
    assert data["has_blocked_owned_group"] is False
    assert data["blocked_owned_group_reason"] is None
