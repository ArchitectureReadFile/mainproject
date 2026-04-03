from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from models.model import Notification, NotificationSetting, NotificationType


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, notification: Notification):
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def get_by_id(self, notification_id: int, user_id: int):
        return (
            self.db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )

    def get_list_by_user(self, user_id: int, skip: int = 0, limit: int = 20):
        return (
            self.db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update_as_read(self, notification: Notification):
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def update_all_as_read(self, user_id: int):
        self.db.query(Notification).filter(
            Notification.user_id == user_id, Notification.is_read.is_(False)
        ).update(
            {
                "is_read": True,
                "read_at": datetime.now(timezone.utc).replace(tzinfo=None),
            },
            synchronize_session=False,
        )
        self.db.commit()

    def delete(self, notification: Notification):
        self.db.delete(notification)
        self.db.commit()

    def get_all_settings_by_user(self, user_id: int) -> list[NotificationSetting]:
        return (
            self.db.query(NotificationSetting)
            .filter(NotificationSetting.user_id == user_id)
            .all()
        )

    def get_setting(
        self, user_id: int, notification_type: NotificationType
    ) -> Optional[NotificationSetting]:
        return (
            self.db.query(NotificationSetting)
            .filter(
                NotificationSetting.user_id == user_id,
                NotificationSetting.notification_type == notification_type,
            )
            .first()
        )

    def upsert_setting(
        self,
        user_id: int,
        notification_type: NotificationType,
        is_enabled: bool,
        is_toast_enabled: bool,
    ) -> NotificationSetting:
        setting = self.get_setting(user_id, notification_type)
        if setting:
            setting.is_enabled = is_enabled
            setting.is_toast_enabled = is_toast_enabled
            setting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            setting = NotificationSetting(
                user_id=user_id,
                notification_type=notification_type,
                is_enabled=is_enabled,
                is_toast_enabled=is_toast_enabled,
            )
            self.db.add(setting)

        self.db.commit()
        self.db.refresh(setting)
        return setting
