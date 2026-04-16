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
from tests.dummy_data import users

auth_service = AuthService(None)


# UT-GRP-009-01 초대받은 사용자는 초대를 정상 수락할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
def test_accept_invite_success(client, db_session, logged_in_user):
    """초대받은 사용자는 워크스페이스 초대를 정상 수락하는지 검증한다."""
    owner_data = users[0].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=owner.id,
            name="테스트 워크스페이스",
            description="초대 수락 테스트",
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
            role=MembershipRole.VIEWER,
            status=MembershipStatus.INVITED,
            invited_by_user_id=owner.id,
        )
    )
    db_session.commit()

    res = client.post("/api/groups/1/members/accept")
    assert res.status_code == 204

    membership = (
        db_session.query(GroupMember)
        .filter(
            GroupMember.user_id == logged_in_user.id,
            GroupMember.group_id == 1,
        )
        .first()
    )
    assert membership is not None
    assert membership.status == MembershipStatus.ACTIVE
    assert membership.role == MembershipRole.VIEWER
    assert membership.joined_at is not None


# UT-GRP-009-02 초대받지 않은 사용자는 초대를 수락할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
def test_accept_invite_not_found_for_non_invited_user(
    client, db_session, logged_in_user
):
    """초대받지 않은 사용자는 워크스페이스 초대를 수락할 수 없는지 검증한다."""
    owner_data = users[0].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=owner.id,
            name="테스트 워크스페이스",
            description="초대 수락 테스트",
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
    db_session.commit()

    res = client.post("/api/groups/1/members/accept")
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.GROUP_MEMBER_NOT_FOUND.code


# UT-GRP-009-03 비활성 상태의 워크스페이스 초대는 수락할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
@pytest.mark.parametrize(
    ("group_status", "pending_reason"),
    [
        (GroupStatus.DELETE_PENDING, GroupPendingReason.OWNER_DELETE_REQUEST),
        (GroupStatus.BLOCKED, GroupPendingReason.SUBSCRIPTION_EXPIRED),
    ],
)
def test_accept_invite_forbidden_for_non_active_group(
    client, db_session, logged_in_user, group_status, pending_reason
):
    """비활성 상태의 워크스페이스 초대는 수락할 수 없는지 검증한다."""
    owner_data = users[0].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=owner.id,
            name="비활성 워크스페이스",
            description="초대 수락 테스트",
            status=group_status,
            pending_reason=pending_reason,
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
            role=MembershipRole.VIEWER,
            status=MembershipStatus.INVITED,
            invited_by_user_id=owner.id,
        )
    )
    db_session.commit()

    res = client.post("/api/groups/1/members/accept")
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ACTIVE.code


# UT-GRP-009-04 비로그인 사용자는 초대를 수락할 수 없다.
def test_accept_invite_unauthenticated(client):
    """비로그인 사용자는 워크스페이스 초대 수락이 차단되는지 검증한다."""
    res = client.post("/api/groups/1/members/accept")
    assert res.status_code == 401
