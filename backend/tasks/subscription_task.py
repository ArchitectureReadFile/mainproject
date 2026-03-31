import logging
from datetime import timedelta

from celery_app import celery_app
from database import SessionLocal
from models.model import (
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    utc_now_naive,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.subscription_task.reconcile_subscriptions")
def reconcile_subscriptions():
    """프리미엄 구독의 만료/자동 연장을 주기적으로 정리"""
    db = SessionLocal()
    try:
        subscriptions = (
            db.query(Subscription)
            .filter(Subscription.plan == SubscriptionPlan.PREMIUM)
            .all()
        )

        updated_count = 0

        now = utc_now_naive()

        for subscription in subscriptions:
            if not subscription.ended_at or subscription.ended_at > now:
                continue

            if (
                subscription.auto_renew
                and subscription.status == SubscriptionStatus.ACTIVE
            ):
                while subscription.ended_at and subscription.ended_at <= now:
                    previous_end = subscription.ended_at
                    subscription.started_at = previous_end
                    subscription.ended_at = previous_end + timedelta(days=30)
                updated_count += 1
                continue

            if subscription.status in (
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.CANCELED,
            ):
                subscription.status = SubscriptionStatus.EXPIRED
                updated_count += 1

        if updated_count > 0:
            db.commit()

        return {"updated_count": updated_count}
    except Exception:
        db.rollback()
        logger.exception("subscription reconcile 실패")
        raise
    finally:
        db.close()
