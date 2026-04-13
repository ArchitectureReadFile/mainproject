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
    utc_now_naive,
)
from tests.dummy_data import users


# UT-GRP-004-01 사용자가 구독 시작을 정상 요청하면 프리미엄 구독이 활성화된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_subscribe_premium_success(client, db_session, logged_in_user):
    """구독 시작 요청 시 PREMIUM 구독이 활성화되는지 검증한다."""
    payload = {"confirm": True}

    res = client.post("/api/auth/subscription/subscribe", json=payload)
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == logged_in_user.id
    assert data["subscription"]["plan"] == "PREMIUM"
    assert data["subscription"]["status"] == "ACTIVE"
    assert data["subscription"]["auto_renew"] is True
    assert data["subscription"]["started_at"] is not None
    assert data["subscription"]["ended_at"] is not None

    subscription = (
        db_session.query(Subscription)
        .filter(Subscription.user_id == logged_in_user.id)
        .first()
    )
    assert subscription is not None
    assert subscription.plan == SubscriptionPlan.PREMIUM
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.auto_renew is True
    assert subscription.started_at is not None
    assert subscription.ended_at is not None


# UT-GRP-004-02 confirm 값이 false이면 구독 시작할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_subscribe_premium_forbidden_when_not_confirmed(client, logged_in_user):
    """confirm 값이 false이면 구독 시작 요청이 거부되는지 검증한다."""
    payload = {"confirm": False}

    res = client.post("/api/auth/subscription/subscribe", json=payload)
    assert res.status_code == 403


# UT-GRP-004-03 기존 CANCELED 상태의 프리미엄 구독 사용자가 구독 시작하면 ACTIVE로 복구된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_subscribe_premium_reactivates_canceled_subscription(
    client, db_session, logged_in_user
):
    """CANCELED 상태의 PREMIUM 구독이 구독 시작 요청으로 ACTIVE로 복구되는지 검증한다."""
    now = utc_now_naive()
    db_session.add(
        Subscription(
            user_id=logged_in_user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.CANCELED,
            auto_renew=False,
            started_at=now - timedelta(days=5),
            ended_at=now + timedelta(days=25),
        )
    )
    db_session.commit()

    payload = {"confirm": True}

    res = client.post("/api/auth/subscription/subscribe", json=payload)
    assert res.status_code == 200

    data = res.json()
    assert data["subscription"]["plan"] == "PREMIUM"
    assert data["subscription"]["status"] == "ACTIVE"
    assert data["subscription"]["auto_renew"] is True

    subscription = (
        db_session.query(Subscription)
        .filter(Subscription.user_id == logged_in_user.id)
        .first()
    )
    assert subscription is not None
    assert subscription.plan == SubscriptionPlan.PREMIUM
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.auto_renew is True


# UT-GRP-004-04 구독 만료로 DELETE_PENDING 또는 BLOCKED 상태가 된 워크스페이스는 구독 시작 시 ACTIVE로 복구된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
@pytest.mark.parametrize(
    "group_status", [GroupStatus.DELETE_PENDING, GroupStatus.BLOCKED]
)
def test_subscribe_premium_restores_subscription_expired_workspace(
    client, db_session, logged_in_user, group_status
):
    """구독 만료로 비활성화된 워크스페이스가 구독 시작 요청으로 ACTIVE로 복구되는지 검증한다."""
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
    db_session.flush()

    group = Group(
        id=1,
        owner_user_id=logged_in_user.id,
        name="구독 만료 워크스페이스",
        description="복구 테스트",
        status=group_status,
        pending_reason=GroupPendingReason.SUBSCRIPTION_EXPIRED,
        delete_requested_at=now - timedelta(days=1),
        delete_scheduled_at=now + timedelta(days=29),
    )
    db_session.add(group)
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=group.id,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    payload = {"confirm": True}

    res = client.post("/api/auth/subscription/subscribe", json=payload)
    assert res.status_code == 200

    data = res.json()
    assert data["subscription"]["plan"] == "PREMIUM"
    assert data["subscription"]["status"] == "ACTIVE"
    assert data["subscription"]["auto_renew"] is True

    db_session.refresh(group)
    assert group.status == GroupStatus.ACTIVE
    assert group.pending_reason is None
    assert group.delete_requested_at is None
    assert group.delete_scheduled_at is None


# UT-GRP-004-05 비로그인 사용자는 구독 시작을 요청할 수 없다.
def test_subscribe_premium_unauthenticated(client):
    """비로그인 사용자는 구독 시작 요청이 차단되는지 검증한다."""
    payload = {"confirm": True}

    res = client.post("/api/auth/subscription/subscribe", json=payload)
    assert res.status_code == 401
