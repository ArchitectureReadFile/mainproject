import os

import redis

from celery_app import celery_app
from database import SessionLocal
from domains.chat.processor import ChatProcessor
from domains.chat.repository import ChatRepository
from domains.knowledge.schemas import WorkspaceSelection
from domains.notification.repository import NotificationRepository

REDIS_HOST = os.getenv("REDIS_HOST", "redis")


@celery_app.task(name="tasks.chat_task.process_chat_message")
def process_chat_message(payload: dict):
    user_id = payload.get("user_id")
    session_id = payload.get("session_id")
    group_id = payload.get("group_id")

    raw_selection = payload.get("workspace_selection")
    workspace_selection: WorkspaceSelection | None = None
    if raw_selection is not None:
        workspace_selection = WorkspaceSelection(
            mode=raw_selection.get("mode", "all"),
            document_ids=raw_selection.get("document_ids", []),
        )

    redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    db = SessionLocal()

    try:
        chat_repo = ChatRepository(db)
        notification_repo = NotificationRepository(db)

        processor = ChatProcessor(chat_repo, notification_repo)
        processor.process_chat(
            redis_client=redis_client,
            user_id=user_id,
            session_id=session_id,
            group_id=group_id,
            workspace_selection=workspace_selection,
        )
    finally:
        redis_client.delete(f"chat_task:{session_id}")
        db.close()
        redis_client.close()
