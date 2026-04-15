from datetime import timedelta

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
    utc_now_naive,
)
from services.auth_service import AuthService
from tests.dummy_data import groups, users

auth_service = AuthService(None)


# UT-GRP-016-01 OWNER는 삭제 요청 상태의 워크스페이스를 정상적으로 삭제 취소할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_cancel_delete_group_success(client, db_session, logged_in_user):
    """OWNER는 삭제 요청 상태의 워크스페이스를 정상적으로 삭제 취소하는지 검증한다."""
    now = utc_now_naive()

    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.DELETE_PENDING,
            pending_reason=GroupPendingReason.OWNER_DELETE_REQUEST,
            delete_requested_at=now,
            delete_scheduled_at=now + timedelta(days=30),
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

    res = client.post("/api/groups/1/cancel-delete")
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == 1
    assert data["status"] == "ACTIVE"
    assert data["pending_reason"] is None
    assert data["delete_scheduled_at"] is None

    group = db_session.query(Group).filter(Group.id == 1).first()
    assert group is not None
    assert group.status == GroupStatus.ACTIVE
    assert group.pending_reason is None
    assert group.delete_requested_at is None
    assert group.delete_scheduled_at is None


# UT-GRP-016-02 OWNER가 아닌 사용자는 워크스페이스 삭제 취소를 할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_cancel_delete_group_forbidden_for_non_owner(
    client, db_session, logged_in_user
):
    """OWNER가 아닌 사용자는 워크스페이스 삭제 취소가 차단되는지 검증한다."""
    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    now = utc_now_naive()

    db_session.add(
        Group(
            id=1,
            owner_user_id=owner.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.DELETE_PENDING,
            pending_reason=GroupPendingReason.OWNER_DELETE_REQUEST,
            delete_requested_at=now,
            delete_scheduled_at=now + timedelta(days=30),
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

    res = client.post("/api/groups/1/cancel-delete")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_OWNER.code


# UT-GRP-016-03 삭제 요청 상태가 아닌 워크스페이스는 삭제 취소할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_cancel_delete_group_bad_request_for_non_delete_pending_group(
    client, db_session, logged_in_user
):
    """삭제 요청 상태가 아닌 워크스페이스는 삭제 취소할 수 없는지 검증한다."""
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

    res = client.post("/api/groups/1/cancel-delete")
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.GROUP_NOT_DELETE_PENDING.code


# UT-GRP-016-04 이미 다른 활성 워크스페이스를 소유한 OWNER는 삭제 취소할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_cancel_delete_group_conflict_when_owner_already_has_active_group(
    client, db_session, logged_in_user
):
    """이미 다른 활성 워크스페이스를 소유한 OWNER는 삭제 취소할 수 없는지 검증한다."""
    now = utc_now_naive()

    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="삭제 대기 워크스페이스",
            description="삭제 취소 테스트",
            status=GroupStatus.DELETE_PENDING,
            pending_reason=GroupPendingReason.OWNER_DELETE_REQUEST,
            delete_requested_at=now,
            delete_scheduled_at=now + timedelta(days=30),
        )
    )
    db_session.add(
        Group(
            id=2,
            owner_user_id=logged_in_user.id,
            name="활성 워크스페이스",
            description="기존 활성 워크스페이스",
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
            user_id=logged_in_user.id,
            group_id=2,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.post("/api/groups/1/cancel-delete")
    assert res.status_code == 409
    assert res.json()["code"] == ErrorCode.GROUP_RESTORE_OWNER_LIMIT.code


# UT-GRP-016-05 비로그인 사용자는 워크스페이스 삭제 취소를 할 수 없다.
def test_cancel_delete_group_unauthenticated(client):
    """비로그인 사용자는 워크스페이스 삭제 취소 요청이 차단되는지 검증한다."""
    res = client.post("/api/groups/1/cancel-delete")
    assert res.status_code == 401
