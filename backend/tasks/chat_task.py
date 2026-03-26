import os

import redis

from celery_app import celery_app
from database import SessionLocal
from services.chat.chat_processor import ChatProcessor

REDIS_HOST = os.getenv("REDIS_HOST", "redis")


@celery_app.task(name="tasks.process_chat_message")
def process_chat_message(payload: dict):
    user_id = payload.get("user_id")
    session_id = payload.get("session_id")

    redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    db = SessionLocal()

    try:
        processor = ChatProcessor()
        processor.process_chat(
            db=db,
            redis_client=redis_client,
            user_id=user_id,
            session_id=session_id,
        )
    finally:
        db.close()
        redis_client.close()
