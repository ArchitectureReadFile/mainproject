import json
import os

from redis import asyncio as aioredis

from errors.error_codes import ErrorCode
from errors.exceptions import AppException
from models.model import Notification, NotificationType
from repositories.notification_repository import NotificationRepository

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


class NotificationService:
    def create_notification_sync(
        self,
        repository: NotificationRepository,
        user_id: int,
        type: NotificationType,
        title: str,
        body: str = None,
        actor_user_id: int = None,
        group_id: int = None,
        target_type: str = None,
        target_id: int = None,
    ):
        notification = Notification(
            user_id=user_id,
            actor_user_id=actor_user_id,
            group_id=group_id,
            type=type,
            title=title,
            body=body,
            target_type=target_type,
            target_id=target_id,
        )
        db_notification = repository.create(notification)
        self.send_realtime_notification_sync(user_id, db_notification)
        return db_notification

    def send_realtime_notification_sync(self, user_id: int, notification: Notification):
        import redis

        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        try:
            payload = {
                "id": notification.id,
                "type": notification.type.value,
                "title": notification.title,
                "body": notification.body,
                "is_read": notification.is_read,
                "created_at": notification.created_at.isoformat()
                if notification.created_at
                else None,
                "group_id": notification.group_id,
                "target_type": notification.target_type,
                "target_id": notification.target_id,
            }
            r.publish(f"notifications:{user_id}", json.dumps(payload))
        finally:
            r.close()

    async def create_notification(
        self,
        repository: NotificationRepository,
        user_id: int,
        type: NotificationType,
        title: str,
        body: str = None,
        actor_user_id: int = None,
        group_id: int = None,
        target_type: str = None,
        target_id: int = None,
    ):
        notification = Notification(
            user_id=user_id,
            actor_user_id=actor_user_id,
            group_id=group_id,
            type=type,
            title=title,
            body=body,
            target_type=target_type,
            target_id=target_id,
        )
        db_notification = repository.create(notification)
        await self.send_realtime_notification(user_id, db_notification)
        return db_notification

    async def send_realtime_notification(
        self, user_id: int, notification: Notification
    ):
        redis = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=0,
            decode_responses=True,
        )
        try:
            payload = {
                "id": notification.id,
                "type": notification.type.value,
                "title": notification.title,
                "body": notification.body,
                "is_read": notification.is_read,
                "created_at": notification.created_at.isoformat()
                if notification.created_at
                else None,
                "group_id": notification.group_id,
                "target_type": notification.target_type,
                "target_id": notification.target_id,
            }
            await redis.publish(f"notifications:{user_id}", json.dumps(payload))
        finally:
            await redis.close()

    def mark_as_read(
        self, repository: NotificationRepository, notification_id: int, user_id: int
    ):
        notification = repository.get_by_id(notification_id, user_id)
        if not notification:
            raise AppException(ErrorCode.NOTIFICATION_NOT_FOUND)
        return repository.update_as_read(notification)

    def mark_all_as_read(self, repository: NotificationRepository, user_id: int):
        repository.update_all_as_read(user_id)

    def get_notifications(
        self,
        repository: NotificationRepository,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
    ):
        return repository.get_list_by_user(user_id, skip, limit)

    def delete_notification(
        self, repository: NotificationRepository, notification_id: int, user_id: int
    ):
        notification = repository.get_by_id(notification_id, user_id)
        if not notification:
            raise AppException(ErrorCode.NOTIFICATION_NOT_FOUND)
        repository.delete(notification)
