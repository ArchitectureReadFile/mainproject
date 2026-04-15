# /Users/dew0211/Desktop/mainproject/backend/tasks/subscription_task.py

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
from repositories.group_repository import GroupRepository

logger = logging.getLogger(__name__)


def _expire_owned_groups_for_subscription(
    *,
    db,
    subscription: Subscription,
) -> tuple[int, list[int]]:
    """구독 만료 사용자의 ACTIVE 워크스페이스를 삭제 예정 상태로 전환한다."""
    owned_groups = (
        db.query(Group)
        .filter(
            Group.owner_user_id == subscription.user_id,
            Group.status == GroupStatus.ACTIVE,
        )
        .all()
    )

    updated_count = 0
    group_ids: list[int] = []

    for group in owned_groups:
        group.status = GroupStatus.DELETE_PENDING
        group.pending_reason = GroupPendingReason.SUBSCRIPTION_EXPIRED
        group.delete_requested_at = subscription.ended_at
        group.delete_scheduled_at = subscription.ended_at + timedelta(days=30)
        updated_count += 1
        group_ids.append(group.id)

    return updated_count, group_ids


def _block_expired_subscription_groups(*, db, now) -> int:
    """구독 만료 유예가 끝난 워크스페이스만 BLOCKED 상태로 전환한다."""
    pending_groups = (
        db.query(Group)
        .filter(
            Group.status == GroupStatus.DELETE_PENDING,
            Group.pending_reason == GroupPendingReason.SUBSCRIPTION_EXPIRED,
            Group.delete_scheduled_at.isnot(None),
            Group.delete_scheduled_at <= now,
        )
        .all()
    )

    updated_count = 0

    for group in pending_groups:
        group.status = GroupStatus.BLOCKED
        updated_count += 1

    return updated_count


def _enqueue_group_rag_deindex(*, db, group_ids: list[int]) -> None:
    """삭제 예정으로 전환된 워크스페이스의 활성 승인 문서를 RAG 제거 큐에 적재한다."""
    from tasks.group_document_task import deindex_document

    group_repository = GroupRepository(db)

    for group_id in group_ids:
        document_ids = group_repository.get_active_approved_document_ids(group_id)
        for document_id in document_ids:
            deindex_document.delay(
                document_id,
                None,
                GroupStatus.DELETE_PENDING.value,
            )


@celery_app.task(name="tasks.subscription_task.reconcile_subscriptions")
def reconcile_subscriptions():
    """프리미엄 구독 만료에 따른 워크스페이스 상태를 정리한다."""
    db = SessionLocal()
    try:
        subscriptions = (
            db.query(Subscription)
            .filter(Subscription.plan == SubscriptionPlan.PREMIUM)
            .all()
        )

        updated_count = 0
        expired_group_ids: list[int] = []
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

                group_updated_count, group_ids = _expire_owned_groups_for_subscription(
                    db=db,
                    subscription=subscription,
                )
                updated_count += group_updated_count
                expired_group_ids.extend(group_ids)

        updated_count += _block_expired_subscription_groups(
            db=db,
            now=now,
        )

        if updated_count > 0:
            db.commit()

        if expired_group_ids:
            _enqueue_group_rag_deindex(
                db=db,
                group_ids=expired_group_ids,
            )

        return {"updated_count": updated_count}
    except Exception:
        db.rollback()
        logger.exception("subscription reconcile 실패")
        raise
    finally:
        db.close()
