from datetime import timedelta

import pytest

from errors import ErrorCode
from models.model import (
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    utc_now_naive,
)
from tests.dummy_data import users


# UT-GRP-005-01 사용자가 구독 해지를 정상 요청하면 자동 갱신이 비활성화되고 구독 상태가 CANCELED로 변경된다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_cancel_subscription_success(client, db_session, logged_in_user):
    """구독 해지 요청 시 PREMIUM 구독이 CANCELED 상태로 변경되는지 검증한다."""
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
    db_session.commit()

    payload = {"confirm": True}

    res = client.post("/api/auth/subscription/cancel", json=payload)
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == logged_in_user.id
    assert data["subscription"]["plan"] == "PREMIUM"
    assert data["subscription"]["status"] == "CANCELED"
    assert data["subscription"]["auto_renew"] is False
    assert data["subscription"]["started_at"] is not None
    assert data["subscription"]["ended_at"] is not None

    subscription = (
        db_session.query(Subscription)
        .filter(Subscription.user_id == logged_in_user.id)
        .first()
    )
    assert subscription is not None
    assert subscription.plan == SubscriptionPlan.PREMIUM
    assert subscription.status == SubscriptionStatus.CANCELED
    assert subscription.auto_renew is False


# UT-GRP-005-02 confirm 값이 false이면 구독 해지할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_cancel_subscription_forbidden_when_not_confirmed(client, logged_in_user):
    """confirm 값이 false이면 구독 해지 요청이 거부되는지 검증한다."""
    payload = {"confirm": False}

    res = client.post("/api/auth/subscription/cancel", json=payload)
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.AUTH_FORBIDDEN.code


# UT-GRP-005-03 FREE 구독 사용자가 구독 해지를 요청하면 상태 변화 없이 정상 응답한다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_cancel_subscription_success_for_free_plan(client, db_session, logged_in_user):
    """FREE 구독 사용자는 해지 요청 시 상태 변화 없이 정상 응답하는지 검증한다."""
    now = utc_now_naive()
    db_session.add(
        Subscription(
            user_id=logged_in_user.id,
            plan=SubscriptionPlan.FREE,
            status=SubscriptionStatus.ACTIVE,
            auto_renew=False,
            started_at=now,
            ended_at=None,
        )
    )
    db_session.commit()

    payload = {"confirm": True}

    res = client.post("/api/auth/subscription/cancel", json=payload)
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == logged_in_user.id
    assert data["subscription"]["plan"] == "FREE"
    assert data["subscription"]["status"] == "ACTIVE"
    assert data["subscription"]["auto_renew"] is False

    subscription = (
        db_session.query(Subscription)
        .filter(Subscription.user_id == logged_in_user.id)
        .first()
    )
    assert subscription is not None
    assert subscription.plan == SubscriptionPlan.FREE
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.auto_renew is False


# UT-GRP-005-04 비로그인 사용자는 구독 해지를 요청할 수 없다.
def test_cancel_subscription_unauthenticated(client):
    """비로그인 사용자는 구독 해지 요청이 차단되는지 검증한다."""
    payload = {"confirm": True}

    res = client.post("/api/auth/subscription/cancel", json=payload)
    assert res.status_code == 401
