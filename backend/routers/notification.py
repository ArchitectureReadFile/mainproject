from typing import List

from fastapi import APIRouter, Depends, status

from dependencies import (
    get_current_user,
    get_notification_repository,
    get_notification_service,
)
from models.model import User
from repositories.notification_repository import NotificationRepository
from schemas.notification import NotificationResponse
from services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=List[NotificationResponse])
async def get_notifications(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    return notification_service.get_notifications(
        repository, current_user.id, skip, limit
    )


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    return notification_service.mark_as_read(
        repository, notification_id, current_user.id
    )


@router.patch("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    notification_service.mark_all_as_read(repository, current_user.id)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    notification_service.delete_notification(
        repository, notification_id, current_user.id
    )
