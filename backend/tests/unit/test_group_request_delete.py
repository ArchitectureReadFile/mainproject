import pytest

from domains.auth.service import AuthService
from errors import ErrorCode
from models.model import (
    Group,
    GroupMember,
    GroupPendingReason,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    User,
)
from tests.dummy_data import groups, users

auth_service = AuthService(None)


# UT-GRP-015-01 OWNER는 활성 워크스페이스에 대해 삭제를 정상 요청할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_request_delete_group_success(client, db_session, logged_in_user):
    """OWNER는 활성 워크스페이스에 대해 삭제를 정상 요청하는지 검증한다."""
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

    res = client.delete("/api/groups/1")
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == 1
    assert data["status"] == "DELETE_PENDING"
    assert data["pending_reason"] == "OWNER_DELETE_REQUEST"
    assert data["delete_scheduled_at"] is not None

    group = db_session.query(Group).filter(Group.id == 1).first()
    assert group is not None
    assert group.status == GroupStatus.DELETE_PENDING
    assert group.pending_reason == GroupPendingReason.OWNER_DELETE_REQUEST
    assert group.delete_requested_at is not None
    assert group.delete_scheduled_at is not None


# UT-GRP-015-02 OWNER가 아닌 사용자는 워크스페이스 삭제를 요청할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_request_delete_group_forbidden_for_non_owner(
    client, db_session, logged_in_user
):
    """OWNER가 아닌 사용자는 워크스페이스 삭제 요청이 차단되는지 검증한다."""
    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=owner.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=owner.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.delete("/api/groups/1")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_OWNER.code


# UT-GRP-015-03 이미 삭제 요청 상태인 워크스페이스에는 다시 삭제를 요청할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_request_delete_group_conflict_for_delete_pending_group(
    client, db_session, logged_in_user
):
    """이미 삭제 요청 상태인 워크스페이스에는 다시 삭제를 요청할 수 없는지 검증한다."""
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="삭제 대기 워크스페이스",
            description="삭제 요청 테스트",
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

    res = client.delete("/api/groups/1")
    assert res.status_code == 409
    assert res.json()["code"] == ErrorCode.GROUP_ALREADY_DELETE_PENDING.code


# UT-GRP-015-04 비로그인 사용자는 워크스페이스 삭제를 요청할 수 없다.
def test_request_delete_group_unauthenticated(client):
    """비로그인 사용자는 워크스페이스 삭제 요청이 차단되는지 검증한다."""
    res = client.delete("/api/groups/1")
    assert res.status_code == 401
