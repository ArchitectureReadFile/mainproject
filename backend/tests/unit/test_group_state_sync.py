from datetime import timedelta

import pytest

from models.model import (
    Group,
    GroupMember,
    GroupPendingReason,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    User,
    utc_now_naive,
)
from services.auth_service import AuthService
from tests.dummy_data import users

auth_service = AuthService(None)


# UT-GRP-006-01 구독 만료 상태의 OWNER 워크스페이스는 목록 조회 시 DELETE_PENDING 상태로 반영된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_group_state_sync_reflects_delete_pending_in_list(
    client, db_session, logged_in_user
):
    """구독 만료 직후 OWNER 워크스페이스가 목록 조회 시 DELETE_PENDING으로 반영되는지 검증한다."""
    now = utc_now_naive()
    ended_at = now - timedelta(days=1)

    db_session.add(
        Subscription(
            user_id=logged_in_user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.EXPIRED,
            auto_renew=False,
            started_at=now - timedelta(days=31),
            ended_at=ended_at,
        )
    )
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="구독 만료 워크스페이스",
            description="상태 반영 테스트",
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

    res = client.get("/api/groups")
    assert res.status_code == 200

    data = res.json()
    assert len(data["groups"]) == 1
    assert data["has_blocked_owned_group"] is False
    assert data["blocked_owned_group_reason"] is None
    assert data["groups"][0]["status"] == "DELETE_PENDING"
    assert data["groups"][0]["pending_reason"] == "SUBSCRIPTION_EXPIRED"


# UT-GRP-006-02 삭제 예정일이 지난 구독 만료 OWNER 워크스페이스는 목록 조회 시 BLOCKED 상태로 반영된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_group_state_sync_reflects_blocked_in_list_after_due_date(
    client, db_session, logged_in_user
):
    """삭제 예정일이 지난 구독 만료 OWNER 워크스페이스가 BLOCKED로 반영되는지 검증한다."""
    now = utc_now_naive()
    ended_at = now - timedelta(days=31)

    db_session.add(
        Subscription(
            user_id=logged_in_user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.EXPIRED,
            auto_renew=False,
            started_at=now - timedelta(days=61),
            ended_at=ended_at,
        )
    )
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="차단 예정 워크스페이스",
            description="상태 반영 테스트",
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

    res = client.get("/api/groups")
    assert res.status_code == 200

    data = res.json()
    assert data["groups"] == []
    assert data["has_blocked_owned_group"] is True
    assert data["blocked_owned_group_reason"] == "SUBSCRIPTION_EXPIRED"


# UT-GRP-006-03 OWNER인 BLOCKED 워크스페이스는 목록에서 제외되고 차단 플래그가 반환된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_group_state_sync_excludes_owned_blocked_group_and_returns_flag(
    client, db_session, logged_in_user
):
    """OWNER인 BLOCKED 워크스페이스가 목록에서 제외되고 차단 플래그가 반환되는지 검증한다."""
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="차단된 워크스페이스",
            description="상태 반영 테스트",
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


# UT-GRP-006-04 DELETE_PENDING 워크스페이스는 목록에 포함되고 상태값이 함께 반환된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_group_state_sync_includes_delete_pending_group_in_list(
    client, db_session, logged_in_user
):
    """DELETE_PENDING 워크스페이스가 목록에 포함되고 상태와 사유가 함께 반환되는지 검증한다."""
    now = utc_now_naive()

    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="삭제 대기 워크스페이스",
            description="상태 반영 테스트",
            status=GroupStatus.DELETE_PENDING,
            pending_reason=GroupPendingReason.SUBSCRIPTION_EXPIRED,
            delete_requested_at=now - timedelta(days=1),
            delete_scheduled_at=now + timedelta(days=29),
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
    assert data["groups"][0]["status"] == "DELETE_PENDING"
    assert data["groups"][0]["pending_reason"] == "SUBSCRIPTION_EXPIRED"
    assert data["groups"][0]["my_role"] == "OWNER"


# UT-GRP-006-05 BLOCKED 상태의 비소유 워크스페이스는 목록에서 제외되고 차단 플래그는 반환되지 않는다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_group_state_sync_excludes_non_owned_blocked_group_without_flag(
    client, db_session, logged_in_user
):
    """비소유 BLOCKED 워크스페이스는 목록에서 제외되고 차단 플래그가 켜지지 않는지 검증한다."""
    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=owner.id,
            name="비소유 차단 워크스페이스",
            description="상태 반영 테스트",
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


# UT-GRP-006-06 구독이 유효한 사용자의 SUBSCRIPTION_EXPIRED 워크스페이스는 목록 조회 시 ACTIVE 상태로 복구 반영된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
@pytest.mark.parametrize(
    "group_status", [GroupStatus.DELETE_PENDING, GroupStatus.BLOCKED]
)
def test_group_state_sync_restores_subscription_expired_group_in_list(
    client, db_session, logged_in_user, group_status
):
    """구독이 유효하면 SUBSCRIPTION_EXPIRED 워크스페이스가 목록 조회 시 ACTIVE로 복구되는지 검증한다."""
    now = utc_now_naive()

    db_session.add(
        Subscription(
            user_id=logged_in_user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.ACTIVE,
            auto_renew=True,
            started_at=now - timedelta(days=5),
            ended_at=now + timedelta(days=25),
        )
    )
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="복구 대상 워크스페이스",
            description="상태 반영 테스트",
            status=group_status,
            pending_reason=GroupPendingReason.SUBSCRIPTION_EXPIRED,
            delete_requested_at=now - timedelta(days=1),
            delete_scheduled_at=now + timedelta(days=29),
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
    assert data["groups"][0]["status"] == "ACTIVE"
    assert data["groups"][0]["pending_reason"] is None


# UT-GRP-006-07 DELETE_PENDING 상태의 워크스페이스는 상세 조회 시 상태와 사유가 반영되어 반환된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_group_state_sync_reflects_delete_pending_in_detail(
    client, db_session, logged_in_user
):
    """구독 만료 직후 상세 조회에서 DELETE_PENDING 상태와 사유가 반영되는지 검증한다."""
    now = utc_now_naive()
    ended_at = now - timedelta(days=1)

    db_session.add(
        Subscription(
            user_id=logged_in_user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.EXPIRED,
            auto_renew=False,
            started_at=now - timedelta(days=31),
            ended_at=ended_at,
        )
    )
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="상세 조회 워크스페이스",
            description="상태 반영 테스트",
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
    assert data["status"] == "DELETE_PENDING"
    assert data["pending_reason"] == "SUBSCRIPTION_EXPIRED"


# UT-GRP-006-08 BLOCKED 상태의 워크스페이스는 상세 조회 시 조회가 차단된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_group_state_sync_blocks_detail_after_due_date(
    client, db_session, logged_in_user
):
    """삭제 예정일이 지난 구독 만료 워크스페이스는 상세 조회가 차단되는지 검증한다."""
    now = utc_now_naive()
    ended_at = now - timedelta(days=31)

    db_session.add(
        Subscription(
            user_id=logged_in_user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.EXPIRED,
            auto_renew=False,
            started_at=now - timedelta(days=61),
            ended_at=ended_at,
        )
    )
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="차단 상세 워크스페이스",
            description="상태 반영 테스트",
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
    assert res.status_code == 400


# UT-GRP-006-09 SUBSCRIPTION_EXPIRED 상태의 DELETE_PENDING 또는 BLOCKED 워크스페이스는 구독 시작 시 ACTIVE 상태로 복구된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
@pytest.mark.parametrize(
    "group_status", [GroupStatus.DELETE_PENDING, GroupStatus.BLOCKED]
)
def test_group_state_sync_restores_group_on_subscribe(
    client, db_session, logged_in_user, group_status
):
    """구독 시작 요청 시 SUBSCRIPTION_EXPIRED 워크스페이스가 ACTIVE로 복구되는지 검증한다."""
    now = utc_now_naive()

    db_session.add(
        Subscription(
            user_id=logged_in_user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.EXPIRED,
            auto_renew=False,
            started_at=now - timedelta(days=60),
            ended_at=now - timedelta(days=1),
        )
    )
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="구독 복구 워크스페이스",
            description="상태 반영 테스트",
            status=group_status,
            pending_reason=GroupPendingReason.SUBSCRIPTION_EXPIRED,
            delete_requested_at=now - timedelta(days=1),
            delete_scheduled_at=now + timedelta(days=29),
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

    res = client.post("/api/auth/subscription/subscribe", json={"confirm": True})
    assert res.status_code == 200

    group = db_session.query(Group).filter(Group.id == 1).first()
    assert group is not None
    db_session.refresh(group)

    assert group.status == GroupStatus.ACTIVE
    assert group.pending_reason is None
    assert group.delete_requested_at is None
    assert group.delete_scheduled_at is None
