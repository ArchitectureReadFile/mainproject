import os

import redis

from celery_app import celery_app
from database import SessionLocal
from schemas.knowledge import WorkspaceSelection
from services.chat.chat_processor import ChatProcessor

REDIS_HOST = os.getenv("REDIS_HOST", "redis")


@celery_app.task(name="tasks.process_chat_message")
def process_chat_message(payload: dict):
    user_id = payload.get("user_id")
    session_id = payload.get("session_id")
    group_id = payload.get("group_id")

    # workspace_selection 복원
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
        processor = ChatProcessor()
        processor.process_chat(
            db=db,
            redis_client=redis_client,
            user_id=user_id,
            session_id=session_id,
            group_id=group_id,
            workspace_selection=workspace_selection,
        )
    finally:
        db.close()
        redis_client.close()
