import asyncio
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis import asyncio as aioredis

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

router = APIRouter()


# 프론트에서 채팅방 진입 시 websocket 연결을 서버에서 받음
@router.websocket("/ws/chat/{session_id}/{user_id}")
async def chat_ws(websocket: WebSocket, session_id: int, user_id: int):
    await websocket.accept()

    redis = aioredis.Redis(
        host=REDIS_HOST,
        port=6379,
        db=0,
        decode_responses=True,
    )
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"chat:{session_id}:{user_id}")

    # 서버 -> 클라이언트의 발신 처리
    async def listen_redis():
        while True:
            # redis_client.publish -> pubsub에 받은 데이터 get
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=None,
            )
            if message and message.get("data"):
                try:
                    await websocket.send_text(message["data"])
                except Exception:
                    return
                await asyncio.sleep(0.01)

    async def keep_connection_alive():
        try:
            while True:
                await websocket.receive_text()
        except (WebSocketDisconnect, Exception):
            pass

    redis_task = asyncio.create_task(listen_redis())
    client_task = asyncio.create_task(keep_connection_alive())

    try:
        done, pending = await asyncio.wait(
            [redis_task, client_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    finally:
        await pubsub.unsubscribe(f"chat:{user_id}")
        await pubsub.close()
        await redis.close()
