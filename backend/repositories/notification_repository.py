from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.model import Notification


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
