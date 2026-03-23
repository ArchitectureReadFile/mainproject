import os

import redis

from celery_app import celery_app
from database import SessionLocal
from services.chat_service import ChatService

REDIS_HOST = os.getenv("REDIS_HOST", "redis")


# 1. 대기가 끝난 셀러리 워커는 Redis Queue형태의 celery를 탈취함
@celery_app.task(name="tasks.process_chat_message")
# 2. 가로챈 데이터를 딕셔너리 형태로 바꿔 payload에 넣고 실행
def process_chat_message(payload: dict):
    user_id = payload.get("user_id")
    session_id = payload.get("session_id")
    message = payload.get("message")
    context_options = payload.get("context_options", {})

    redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    db = SessionLocal()

    try:
        chat_service = ChatService(db, redis_client)
        chat_service.process_chat(
            user_id=user_id,
            session_id=session_id,
            message=message,
            context_options=context_options,
        )
    finally:
        db.close()
        redis_client.close()
