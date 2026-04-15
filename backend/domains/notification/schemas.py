from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from models.model import NotificationType


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    actor_user_id: Optional[int]
    group_id: Optional[int]
    type: str
    title: str
    body: Optional[str]
    is_read: bool
    read_at: Optional[datetime]
    target_type: Optional[str]
    target_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]


class NotificationSettingUpdateRequest(BaseModel):
    notification_type: NotificationType
    is_enabled: bool
    is_toast_enabled: bool


class NotificationSettingResponse(BaseModel):
    notification_type: NotificationType
    is_enabled: bool
    is_toast_enabled: bool

    class Config:
        from_attributes = True
