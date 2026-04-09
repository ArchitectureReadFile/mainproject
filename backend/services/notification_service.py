import json
import os

import redis
from redis import asyncio as aioredis

from errors.error_codes import ErrorCode
from errors.exceptions import AppException
from models.model import Notification, NotificationType
from repositories.notification_repository import NotificationRepository

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


class NotificationService:
    def __init__(self, notification_repo: NotificationRepository):
        self.notification_repo = notification_repo

    def _is_enabled(
        self,
        user_id: int,
        type: NotificationType,
    ) -> bool:
        setting = self.notification_repo.get_setting(user_id, type)
        return setting.is_enabled if setting else True

    def create_notification_sync(
        self,
        user_id: int,
        type: NotificationType,
        title: str,
        body: str = None,
        actor_user_id: int = None,
        group_id: int = None,
        target_type: str = None,
        target_id: int = None,
    ):
        if not self._is_enabled(user_id, type):
            return None

        # 멤버십 체크가 필요한 경우 라우터나 서비스에서 미리 체크하거나,
        # 필요시 이 메서드를 호출하는 쪽에서 검증하도록 책임을 분리합니다.
        # (기존의 SessionLocal()을 여기서 직접 여는 것은 아키텍처상 좋지 않습니다.)

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
        db_notification = self.notification_repo.create(notification)
        self.send_realtime_notification_sync(user_id, db_notification)
        return db_notification

    def send_realtime_notification_sync(self, user_id: int, notification: Notification):
        if not notification:
            return

        setting = self.notification_repo.get_setting(user_id, notification.type)
        is_toast_enabled = setting.is_toast_enabled if setting else True

        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        try:
            payload = {
                "id": notification.id,
                "type": notification.type.value,
                "title": notification.title,
                "body": notification.body,
                "is_read": notification.is_read,
                "is_toast_enabled": is_toast_enabled,
                "created_at": (
                    notification.created_at.isoformat()
                    if notification.created_at
                    else None
                ),
                "group_id": notification.group_id,
                "target_type": notification.target_type,
                "target_id": notification.target_id,
            }
            r.publish(f"notifications:{user_id}", json.dumps(payload))
        finally:
            r.close()

    async def create_notification(
        self,
        user_id: int,
        type: NotificationType,
        title: str,
        body: str = None,
        actor_user_id: int = None,
        group_id: int = None,
        target_type: str = None,
        target_id: int = None,
    ):
        if not self._is_enabled(user_id, type):
            return None

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
        db_notification = self.notification_repo.create(notification)
        await self.send_realtime_notification(user_id, db_notification)
        return db_notification

    async def send_realtime_notification(
        self, user_id: int, notification: Notification
    ):
        setting = self.notification_repo.get_setting(user_id, notification.type)
        is_toast_enabled = setting.is_toast_enabled if setting else True

        r = aioredis.Redis(
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
                "is_toast_enabled": is_toast_enabled,
                "created_at": (
                    notification.created_at.isoformat()
                    if notification.created_at
                    else None
                ),
                "group_id": notification.group_id,
                "target_type": notification.target_type,
                "target_id": notification.target_id,
            }
            await r.publish(f"notifications:{user_id}", json.dumps(payload))
        finally:
            await r.close()

    def mark_as_read(self, notification_id: int, user_id: int):
        notification = self.notification_repo.get_by_id(notification_id, user_id)
        if not notification:
            raise AppException(ErrorCode.NOTIFICATION_NOT_FOUND)
        return self.notification_repo.update_as_read(notification)

    def mark_all_as_read(self, user_id: int):
        self.notification_repo.update_all_as_read(user_id)

    def get_notifications(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
    ):
        return self.notification_repo.get_list_by_user(user_id, skip, limit)

    def delete_notification(self, notification_id: int, user_id: int):
        notification = self.notification_repo.get_by_id(notification_id, user_id)
        if not notification:
            raise AppException(ErrorCode.NOTIFICATION_NOT_FOUND)
        self.notification_repo.delete(notification)

    def get_all_settings(self, user_id: int):
        return self.notification_repo.get_all_settings_by_user(user_id)

    def upsert_setting(
        self,
        user_id: int,
        notification_type: NotificationType,
        is_enabled: bool,
        is_toast_enabled: bool,
    ):
        return self.notification_repo.upsert_setting(
            user_id, notification_type, is_enabled, is_toast_enabled
        )
