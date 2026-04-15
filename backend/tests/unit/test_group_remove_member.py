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


# UT-GRP-011-01 OWNER 또는 ADMIN은 활성 멤버를 정상적으로 제거할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
@pytest.mark.parametrize("remover_role", [MembershipRole.OWNER, MembershipRole.ADMIN])
def test_remove_active_member_success(client, db_session, logged_in_user, remover_role):
    """OWNER 또는 ADMIN은 활성 멤버를 정상적으로 제거하는지 검증한다."""
    target_data = users[1].copy()
    target_data["password"] = auth_service.hash_password(target_data["password"])
    target = User(**target_data)
    db_session.add(target)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="테스트 워크스페이스",
            description="멤버 제거 테스트",
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

    if remover_role == MembershipRole.ADMIN:
        admin_data = {
            "id": 3,
            "email": "admin2@example.com",
            "username": "관리자2",
            "password": auth_service.hash_password("password123!"),
            "role": "GENERAL",
            "is_active": True,
        }
        admin = User(**admin_data)
        db_session.add(admin)
        db_session.flush()

        db_session.add(
            GroupMember(
                user_id=admin.id,
                group_id=1,
                role=MembershipRole.ADMIN,
                status=MembershipStatus.ACTIVE,
            )
        )

    db_session.add(
        GroupMember(
            user_id=target.id,
            group_id=1,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.delete(f"/api/groups/1/members/{target.id}")
    assert res.status_code == 204

    membership = (
        db_session.query(GroupMember)
        .filter(
            GroupMember.user_id == target.id,
            GroupMember.group_id == 1,
        )
        .first()
    )
    assert membership is not None
    assert membership.status == MembershipStatus.REMOVED
    assert membership.removed_at is not None


# UT-GRP-011-02 OWNER 또는 ADMIN은 초대 대기 멤버의 초대를 정상적으로 취소할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
@pytest.mark.parametrize("remover_role", [MembershipRole.OWNER, MembershipRole.ADMIN])
def test_cancel_invited_member_success(
    client, db_session, logged_in_user, remover_role
):
    """OWNER 또는 ADMIN은 초대 대기 멤버의 초대를 정상적으로 취소하는지 검증한다."""
    target_data = users[1].copy()
    target_data["password"] = auth_service.hash_password(target_data["password"])
    target = User(**target_data)
    db_session.add(target)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="테스트 워크스페이스",
            description="초대 취소 테스트",
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

    if remover_role == MembershipRole.ADMIN:
        admin_data = {
            "id": 3,
            "email": "admin2@example.com",
            "username": "관리자2",
            "password": auth_service.hash_password("password123!"),
            "role": "GENERAL",
            "is_active": True,
        }
        admin = User(**admin_data)
        db_session.add(admin)
        db_session.flush()

        db_session.add(
            GroupMember(
                user_id=admin.id,
                group_id=1,
                role=MembershipRole.ADMIN,
                status=MembershipStatus.ACTIVE,
            )
        )

    db_session.add(
        GroupMember(
            user_id=target.id,
            group_id=1,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.INVITED,
            invited_by_user_id=logged_in_user.id,
        )
    )
    db_session.commit()

    res = client.delete(f"/api/groups/1/members/{target.id}")
    assert res.status_code == 204

    membership = (
        db_session.query(GroupMember)
        .filter(
            GroupMember.user_id == target.id,
            GroupMember.group_id == 1,
        )
        .first()
    )
    assert membership is not None
    assert membership.status == MembershipStatus.REMOVED
    assert membership.removed_at is not None


# UT-GRP-011-03 OWNER 또는 ADMIN이 아닌 사용자는 멤버를 제거하거나 초대를 취소할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_remove_member_forbidden_for_viewer(client, db_session, logged_in_user):
    """OWNER 또는 ADMIN이 아닌 사용자는 멤버 제거 또는 초대 취소가 차단되는지 검증한다."""
    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    target_data = {
        "id": 3,
        "email": "viewer2@example.com",
        "username": "뷰어2",
        "password": auth_service.hash_password("password123!"),
        "role": "GENERAL",
        "is_active": True,
    }
    target = User(**target_data)
    db_session.add(target)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=owner.id,
            name="테스트 워크스페이스",
            description="멤버 제거 테스트",
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
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=target.id,
            group_id=1,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.delete(f"/api/groups/1/members/{target.id}")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ADMIN_OR_OWNER.code


# UT-GRP-011-04 자기 자신은 제거할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_remove_member_forbidden_for_self(client, db_session, logged_in_user):
    """자기 자신은 제거할 수 없는지 검증한다."""
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="테스트 워크스페이스",
            description="멤버 제거 테스트",
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

    res = client.delete(f"/api/groups/1/members/{logged_in_user.id}")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_CANNOT_REMOVE_SELF.code


# UT-GRP-011-05 OWNER는 제거할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
def test_remove_member_forbidden_for_owner(client, db_session, logged_in_user):
    """OWNER는 제거할 수 없는지 검증한다."""
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
            description="멤버 제거 테스트",
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

    res = client.delete(f"/api/groups/1/members/{owner.id}")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_CANNOT_REMOVE_OWNER.code


# UT-GRP-011-06 존재하지 않는 멤버는 제거할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_remove_member_not_found(client, db_session, logged_in_user):
    """존재하지 않는 멤버는 제거할 수 없는지 검증한다."""
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="테스트 워크스페이스",
            description="멤버 제거 테스트",
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

    res = client.delete("/api/groups/1/members/999")
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.GROUP_MEMBER_NOT_FOUND.code


# UT-GRP-011-07 비활성 상태의 워크스페이스에서는 멤버를 제거하거나 초대를 취소할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
@pytest.mark.parametrize(
    ("group_status", "pending_reason"),
    [
        (GroupStatus.DELETE_PENDING, GroupPendingReason.OWNER_DELETE_REQUEST),
        (GroupStatus.BLOCKED, GroupPendingReason.SUBSCRIPTION_EXPIRED),
    ],
)
def test_remove_member_forbidden_for_non_active_group(
    client, db_session, logged_in_user, group_status, pending_reason
):
    """비활성 상태의 워크스페이스에서는 멤버 제거 또는 초대 취소가 차단되는지 검증한다."""
    target_data = users[1].copy()
    target_data["password"] = auth_service.hash_password(target_data["password"])
    target = User(**target_data)
    db_session.add(target)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="비활성 워크스페이스",
            description="멤버 제거 테스트",
            status=group_status,
            pending_reason=pending_reason,
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
    db_session.add(
        GroupMember(
            user_id=target.id,
            group_id=1,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.delete(f"/api/groups/1/members/{target.id}")
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ACTIVE.code


# UT-GRP-011-08 비로그인 사용자는 멤버 제거 또는 초대 취소를 할 수 없다.
def test_remove_member_unauthenticated(client):
    """비로그인 사용자는 멤버 제거 또는 초대 취소 요청이 차단되는지 검증한다."""
    res = client.delete("/api/groups/1/members/1")
    assert res.status_code == 401
