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


# UT-GRP-008-01 OWNER는 사용자를 워크스페이스에 정상 초대할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_invite_member_success_by_owner(client, db_session, logged_in_user):
    """OWNER가 사용자를 워크스페이스에 정상 초대하는지 검증한다."""
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
            description="초대 테스트",
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

    payload = {"username": target.username, "role": "VIEWER"}

    res = client.post("/api/groups/1/members", json=payload)
    assert res.status_code == 201

    data = res.json()
    assert data["user_id"] == target.id
    assert data["username"] == target.username
    assert data["role"] == "VIEWER"
    assert data["invited_at"] is not None

    membership = (
        db_session.query(GroupMember)
        .filter(
            GroupMember.user_id == target.id,
            GroupMember.group_id == 1,
        )
        .first()
    )
    assert membership is not None
    assert membership.role == MembershipRole.VIEWER
    assert membership.status == MembershipStatus.INVITED


# UT-GRP-008-02 ADMIN은 사용자를 워크스페이스에 정상 초대할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_invite_member_success_by_admin(client, db_session, logged_in_user):
    """ADMIN이 사용자를 워크스페이스에 정상 초대하는지 검증한다."""
    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    target_data = {
        "id": 3,
        "email": "viewer@example.com",
        "username": "뷰어유저",
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
            description="초대 테스트",
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

    payload = {"username": target.username, "role": "VIEWER"}

    res = client.post("/api/groups/1/members", json=payload)
    assert res.status_code == 201

    data = res.json()
    assert data["user_id"] == target.id
    assert data["username"] == target.username
    assert data["role"] == "VIEWER"

    membership = (
        db_session.query(GroupMember)
        .filter(
            GroupMember.user_id == target.id,
            GroupMember.group_id == 1,
        )
        .first()
    )
    assert membership is not None
    assert membership.role == MembershipRole.VIEWER
    assert membership.status == MembershipStatus.INVITED


# UT-GRP-008-03 OWNER 또는 ADMIN이 아닌 사용자는 멤버를 초대할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_invite_member_forbidden_for_viewer(client, db_session, logged_in_user):
    """OWNER 또는 ADMIN이 아닌 사용자는 멤버 초대가 차단되는지 검증한다."""
    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    outsider_data = {
        "id": 3,
        "email": "outsider@example.com",
        "username": "외부유저",
        "password": auth_service.hash_password("password123!"),
        "role": "GENERAL",
        "is_active": True,
    }
    outsider = User(**outsider_data)
    db_session.add(outsider)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=owner.id,
            name="테스트 워크스페이스",
            description="초대 테스트",
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
    db_session.commit()

    payload = {"username": outsider.username, "role": "VIEWER"}

    res = client.post("/api/groups/1/members", json=payload)
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ADMIN_OR_OWNER.code


# UT-GRP-008-04 존재하지 않는 사용자는 초대할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_invite_member_not_found_for_unknown_user(client, db_session, logged_in_user):
    """존재하지 않는 사용자는 초대할 수 없는지 검증한다."""
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="테스트 워크스페이스",
            description="초대 테스트",
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

    payload = {"username": "없는사용자", "role": "VIEWER"}

    res = client.post("/api/groups/1/members", json=payload)
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.USER_NOT_FOUND.code


# UT-GRP-008-05 자기 자신은 초대할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_invite_member_forbidden_for_self(client, db_session, logged_in_user):
    """자기 자신은 초대할 수 없는지 검증한다."""
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="테스트 워크스페이스",
            description="초대 테스트",
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

    payload = {"username": logged_in_user.username, "role": "VIEWER"}

    res = client.post("/api/groups/1/members", json=payload)
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_CANNOT_INVITE_SELF.code


# UT-GRP-008-06 이미 ACTIVE 상태인 사용자는 다시 초대할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_invite_member_conflict_for_active_member(client, db_session, logged_in_user):
    """이미 ACTIVE 상태인 사용자는 다시 초대할 수 없는지 검증한다."""
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
            description="초대 테스트",
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

    payload = {"username": target.username, "role": "VIEWER"}

    res = client.post("/api/groups/1/members", json=payload)
    assert res.status_code == 409
    assert res.json()["code"] == ErrorCode.GROUP_MEMBER_ALREADY_EXISTS.code


# UT-GRP-008-07 이미 INVITED 상태인 사용자는 다시 초대할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_invite_member_conflict_for_invited_member(client, db_session, logged_in_user):
    """이미 INVITED 상태인 사용자는 다시 초대할 수 없는지 검증한다."""
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
            description="초대 테스트",
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
            status=MembershipStatus.INVITED,
            invited_by_user_id=logged_in_user.id,
        )
    )
    db_session.commit()

    payload = {"username": target.username, "role": "VIEWER"}

    res = client.post("/api/groups/1/members", json=payload)
    assert res.status_code == 409
    assert res.json()["code"] == ErrorCode.GROUP_MEMBER_ALREADY_EXISTS.code


# UT-GRP-008-08 REMOVED 상태의 사용자는 다시 초대할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_invite_member_success_for_removed_member(client, db_session, logged_in_user):
    """REMOVED 상태의 사용자는 다시 초대할 수 있는지 검증한다."""
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
            description="초대 테스트",
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
            status=MembershipStatus.REMOVED,
            invited_by_user_id=logged_in_user.id,
        )
    )
    db_session.commit()

    payload = {"username": target.username, "role": "ADMIN"}

    res = client.post("/api/groups/1/members", json=payload)
    assert res.status_code == 201

    data = res.json()
    assert data["user_id"] == target.id
    assert data["role"] == "ADMIN"

    membership = (
        db_session.query(GroupMember)
        .filter(
            GroupMember.user_id == target.id,
            GroupMember.group_id == 1,
        )
        .first()
    )
    assert membership is not None
    assert membership.role == MembershipRole.ADMIN
    assert membership.status == MembershipStatus.INVITED


# UT-GRP-008-09 DELETE_PENDING 또는 BLOCKED 상태의 워크스페이스에는 멤버를 초대할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
@pytest.mark.parametrize(
    ("group_status", "pending_reason"),
    [
        (GroupStatus.DELETE_PENDING, GroupPendingReason.OWNER_DELETE_REQUEST),
        (GroupStatus.BLOCKED, GroupPendingReason.SUBSCRIPTION_EXPIRED),
    ],
)
def test_invite_member_forbidden_for_non_active_group(
    client, db_session, logged_in_user, group_status, pending_reason
):
    """DELETE_PENDING 또는 BLOCKED 상태의 워크스페이스에는 멤버를 초대할 수 없는지 검증한다."""
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
            description="초대 테스트",
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
    db_session.commit()

    payload = {"username": target.username, "role": "VIEWER"}

    res = client.post("/api/groups/1/members", json=payload)
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ACTIVE.code


# UT-GRP-008-10 비로그인 사용자는 멤버를 초대할 수 없다.
def test_invite_member_unauthenticated(client):
    """비로그인 사용자는 멤버 초대 요청이 차단되는지 검증한다."""
    payload = {"username": "테스트유저", "role": "VIEWER"}

    res = client.post("/api/groups/1/members", json=payload)
    assert res.status_code == 401
