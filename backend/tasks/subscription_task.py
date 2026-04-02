import logging
from datetime import timedelta

from celery_app import celery_app
from database import SessionLocal
from models.model import (
    Group,
    GroupPendingReason,
    GroupStatus,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    utc_now_naive,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.subscription_task.reconcile_subscriptions")
def reconcile_subscriptions():
    """프리미엄 구독 만료와 워크스페이스 상태 전이를 함께 정리"""
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

                owned_groups = (
                    db.query(Group)
                    .filter(
                        Group.owner_user_id == subscription.user_id,
                        Group.status == GroupStatus.ACTIVE,
                    )
                    .all()
                )

                for group in owned_groups:
                    group.status = GroupStatus.DELETE_PENDING
                    group.pending_reason = GroupPendingReason.SUBSCRIPTION_EXPIRED
                    group.delete_requested_at = subscription.ended_at
                    group.delete_scheduled_at = subscription.ended_at + timedelta(
                        days=30
                    )

                updated_count += 1

        pending_groups = (
            db.query(Group)
            .filter(
                Group.status == GroupStatus.DELETE_PENDING,
                Group.delete_scheduled_at.isnot(None),
                Group.delete_scheduled_at <= now,
            )
            .all()
        )

        for group in pending_groups:
            group.status = GroupStatus.BLOCKED
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
