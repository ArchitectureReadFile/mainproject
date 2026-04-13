import pytest

from errors import ErrorCode
from models.model import (
    Group,
    GroupMember,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    User,
)
from services.auth_service import AuthService
from tests.dummy_data import groups, users

auth_service = AuthService(None)


# UT-GRP-014-01 OWNER가 아닌 활성 멤버는 워크스페이스를 정상적으로 탈퇴할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
def test_leave_group_success_for_non_owner(client, db_session, logged_in_user):
    """OWNER가 아닌 활성 멤버는 워크스페이스를 정상적으로 탈퇴하는지 검증한다."""
    owner_data = users[0].copy()
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

    res = client.post("/api/groups/1/leave")
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
    assert membership.status == MembershipStatus.REMOVED
    assert membership.removed_at is not None


# UT-GRP-014-02 OWNER는 워크스페이스를 바로 탈퇴할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_leave_group_forbidden_for_owner(client, db_session, logged_in_user):
    """OWNER는 워크스페이스를 바로 탈퇴할 수 없는지 검증한다."""
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

    res = client.post("/api/groups/1/leave")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_OWNER_CANNOT_LEAVE.code


# UT-GRP-014-03 워크스페이스 멤버가 아닌 사용자는 탈퇴할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_leave_group_not_found_for_non_member(client, db_session, logged_in_user):
    """워크스페이스 멤버가 아닌 사용자는 탈퇴할 수 없는지 검증한다."""
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
    db_session.add(
        GroupMember(
            user_id=owner.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.post("/api/groups/1/leave")
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.GROUP_NOT_FOUND.code


# UT-GRP-014-04 비로그인 사용자는 워크스페이스를 탈퇴할 수 없다.
def test_leave_group_unauthenticated(client):
    """비로그인 사용자는 워크스페이스 탈퇴 요청이 차단되는지 검증한다."""
    res = client.post("/api/groups/1/leave")
    assert res.status_code == 401
