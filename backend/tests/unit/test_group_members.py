import pytest

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
from services.auth_service import AuthService
from tests.dummy_data import users

auth_service = AuthService(None)


# UT-GRP-007-01 워크스페이스 멤버는 멤버 목록을 정상 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_group_members_success(client, db_session, logged_in_user):
    """워크스페이스 멤버가 멤버 목록을 정상 조회하는지 검증한다."""
    second_user_data = users[1].copy()
    second_user_data["password"] = auth_service.hash_password(
        second_user_data["password"]
    )
    second_user = User(**second_user_data)
    db_session.add(second_user)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="테스트 워크스페이스",
            description="멤버 조회 테스트",
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
            user_id=second_user.id,
            group_id=1,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get("/api/groups/1/members")
    assert res.status_code == 200

    data = res.json()
    assert "members" in data
    assert "invited" in data
    assert len(data["members"]) == 2
    assert data["invited"] == []

    member_ids = [member["user_id"] for member in data["members"]]
    assert logged_in_user.id in member_ids
    assert second_user.id in member_ids

    roles_by_user_id = {member["user_id"]: member["role"] for member in data["members"]}
    assert roles_by_user_id[logged_in_user.id] == "OWNER"
    assert roles_by_user_id[second_user.id] == "VIEWER"


# UT-GRP-007-02 초대 대기 멤버가 있으면 invited 목록에 함께 반환된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_group_members_includes_invited_members(client, db_session, logged_in_user):
    """초대 대기 멤버가 invited 목록에 함께 반환되는지 검증한다."""
    invited_user_data = users[1].copy()
    invited_user_data["password"] = auth_service.hash_password(
        invited_user_data["password"]
    )
    invited_user = User(**invited_user_data)
    db_session.add(invited_user)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="테스트 워크스페이스",
            description="초대 조회 테스트",
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
            user_id=invited_user.id,
            group_id=1,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.INVITED,
            invited_by_user_id=logged_in_user.id,
        )
    )
    db_session.commit()

    res = client.get("/api/groups/1/members")
    assert res.status_code == 200

    data = res.json()
    assert len(data["members"]) == 1
    assert len(data["invited"]) == 1
    assert data["invited"][0]["user_id"] == invited_user.id
    assert data["invited"][0]["username"] == invited_user.username
    assert data["invited"][0]["role"] == "VIEWER"


# UT-GRP-007-03 비멤버는 멤버 목록을 조회할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_group_members_not_found_for_non_member(client, db_session, logged_in_user):
    """워크스페이스 비멤버는 멤버 목록 조회 시 404를 반환하는지 검증한다."""
    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=owner.id,
            name="타인 워크스페이스",
            description="비멤버 테스트",
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

    res = client.get("/api/groups/1/members")
    assert res.status_code == 404


# UT-GRP-007-04 존재하지 않는 워크스페이스의 멤버 목록은 조회할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_group_members_not_found(client, logged_in_user):
    """존재하지 않는 워크스페이스의 멤버 목록 조회 시 404를 반환하는지 검증한다."""
    res = client.get("/api/groups/9999/members")
    assert res.status_code == 404


# UT-GRP-007-05 비로그인 사용자는 멤버 목록을 조회할 수 없다.
def test_get_group_members_unauthenticated(client):
    """비로그인 사용자는 멤버 목록 조회가 차단되는지 검증한다."""
    res = client.get("/api/groups/1/members")
    assert res.status_code == 401


# UT-GRP-007-06 DELETE_PENDING 상태의 워크스페이스는 멤버 목록 조회가 가능하다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_group_members_success_for_delete_pending_group(
    client, db_session, logged_in_user
):
    """DELETE_PENDING 상태의 워크스페이스는 멤버 목록 조회가 가능한지 검증한다."""
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

    res = client.get("/api/groups/1/members")
    assert res.status_code == 200

    data = res.json()
    assert len(data["members"]) == 1
    assert data["members"][0]["user_id"] == logged_in_user.id


# UT-GRP-007-07 BLOCKED 상태의 워크스페이스는 멤버 목록을 조회할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_group_members_forbidden_for_blocked_group(
    client, db_session, logged_in_user
):
    """BLOCKED 상태의 워크스페이스는 멤버 목록 조회가 차단되는지 검증한다."""
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

    res = client.get("/api/groups/1/members")
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ACTIVE.code
