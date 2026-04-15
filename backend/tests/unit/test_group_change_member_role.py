import pytest

from domains.auth.service import AuthService
from errors import ErrorCode
from models.model import (
    Group,
    GroupMember,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    User,
)
from tests.dummy_data import users

auth_service = AuthService(None)


# UT-GRP-012-01 OWNER는 일반 멤버 역할을 정상 변경할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_change_member_role_success_by_owner(client, db_session, logged_in_user):
    """OWNER는 일반 멤버 역할을 정상 변경하는지 검증한다."""
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
            description="역할 변경 테스트",
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
    db_session.add(
        GroupMember(
            user_id=target.id,
            group_id=1,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    payload = {"role": "EDITOR"}

    res = client.patch(f"/api/groups/1/members/{target.id}", json=payload)
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
    assert membership.role == MembershipRole.EDITOR
    assert membership.status == MembershipStatus.ACTIVE


# UT-GRP-012-02 OWNER 또는 ADMIN이 아닌 사용자는 멤버 역할을 변경할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_change_member_role_forbidden_for_viewer(client, db_session, logged_in_user):
    """OWNER 또는 ADMIN이 아닌 사용자는 멤버 역할 변경이 차단되는지 검증한다."""
    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    target_data = {
        "id": 3,
        "email": "editor@example.com",
        "username": "편집자",
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
            description="역할 변경 테스트",
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

    payload = {"role": "EDITOR"}

    res = client.patch(f"/api/groups/1/members/{target.id}", json=payload)
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ADMIN_OR_OWNER.code


# UT-GRP-012-03 자기 자신의 역할은 변경할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_change_member_role_forbidden_for_self(client, db_session, logged_in_user):
    """자기 자신의 역할은 변경할 수 없는지 검증한다."""
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="테스트 워크스페이스",
            description="역할 변경 테스트",
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

    payload = {"role": "ADMIN"}

    res = client.patch(f"/api/groups/1/members/{logged_in_user.id}", json=payload)
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.GROUP_CANNOT_CHANGE_SELF_ROLE.code


# UT-GRP-012-04 멤버 역할을 OWNER로 변경할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_change_member_role_forbidden_to_owner(client, db_session, logged_in_user):
    """멤버 역할을 OWNER로 직접 변경할 수 없는지 검증한다."""
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
            description="역할 변경 테스트",
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
    db_session.add(
        GroupMember(
            user_id=target.id,
            group_id=1,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    payload = {"role": "OWNER"}

    res = client.patch(f"/api/groups/1/members/{target.id}", json=payload)
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_OWNER.code


# UT-GRP-012-05 ADMIN은 다른 ADMIN의 역할을 변경할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_change_member_role_forbidden_for_admin_to_admin(
    client, db_session, logged_in_user
):
    """ADMIN은 다른 ADMIN의 역할을 변경할 수 없는지 검증한다."""
    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    target_data = {
        "id": 3,
        "email": "admin2@example.com",
        "username": "관리자2",
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
            description="역할 변경 테스트",
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
    db_session.add(
        GroupMember(
            user_id=target.id,
            group_id=1,
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    payload = {"role": "EDITOR"}

    res = client.patch(f"/api/groups/1/members/{target.id}", json=payload)
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_OWNER.code
