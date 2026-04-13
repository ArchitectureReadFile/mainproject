import pytest

from models.model import (
    Group,
    GroupMember,
    GroupPendingReason,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    User,
)
from services.auth_service import AuthService
from tests.dummy_data import groups, users

auth_service = AuthService(None)


# UT-GRP-003-01 워크스페이스 멤버는 상세 정보를 정상 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_workspace_detail_success(client, db_session, logged_in_user):
    """워크스페이스 멤버가 ACTIVE 워크스페이스 상세 정보를 정상 조회하는지 검증한다."""
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

    res = client.get("/api/groups/1")
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == 1
    assert data["name"] == groups[0]["name"]
    assert data["description"] == groups[0]["description"]
    assert data["status"] == "ACTIVE"
    assert data["my_role"] == "OWNER"
    assert data["owner_id"] == logged_in_user.id
    assert data["owner_username"] == users[0]["username"]


# UT-GRP-003-02 비멤버는 워크스페이스 상세 정보를 조회할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_workspace_detail_not_found_for_non_member(
    client, db_session, logged_in_user
):
    """워크스페이스 비멤버는 상세 조회 시 404를 반환하는지 검증한다."""
    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    db_session.add(User(**owner_data))
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=2,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get("/api/groups/1")
    assert res.status_code == 404


# UT-GRP-003-03 존재하지 않는 워크스페이스는 조회할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_workspace_detail_not_found(client, logged_in_user):
    """존재하지 않는 워크스페이스 상세 조회 시 404를 반환하는지 검증한다."""
    res = client.get("/api/groups/9999")
    assert res.status_code == 404


# UT-GRP-003-04 비로그인 사용자는 워크스페이스 상세 정보를 조회할 수 없다.
def test_get_workspace_detail_unauthenticated(client):
    """비로그인 사용자는 워크스페이스 상세 조회가 차단되는지 검증한다."""
    res = client.get("/api/groups/1")
    assert res.status_code == 401


# UT-GRP-003-05 DELETE_PENDING 상태의 워크스페이스는 상세 조회가 가능하다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_workspace_detail_success_for_delete_pending_group(
    client, db_session, logged_in_user
):
    """DELETE_PENDING 상태의 워크스페이스는 상세 조회가 가능한지 검증한다."""
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

    res = client.get("/api/groups/1")
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == 1
    assert data["status"] == "DELETE_PENDING"
    assert data["pending_reason"] == "OWNER_DELETE_REQUEST"
    assert data["my_role"] == "OWNER"


# UT-GRP-003-06 BLOCKED 상태의 워크스페이스는 상세 조회할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_workspace_detail_forbidden_for_blocked_group(
    client, db_session, logged_in_user
):
    """BLOCKED 상태의 워크스페이스는 상세 조회가 차단되는지 검증한다."""
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

    res = client.get("/api/groups/1")
    assert res.status_code == 400
