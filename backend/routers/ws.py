import asyncio
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis import asyncio as aioredis

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

router = APIRouter()


@router.websocket("/ws/upload/{user_id}")
async def upload_ws(websocket: WebSocket, user_id: int):
    await websocket.accept()

    redis = aioredis.Redis(
        host=REDIS_HOST,
        port=6379,
        db=0,
        decode_responses=True,
    )
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"upload:{user_id}")

    async def listen_redis():
        while True:
            # timeout=None — 메시지 올 때까지 이벤트 루프에 양보하며 대기 (CPU 0%)
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=None,
            )
            if message and message.get("data"):
                try:
                    await websocket.send_text(message["data"])
                except Exception:
                    return

    async def listen_client():
        """클라이언트 연결 해제 감지"""
        try:
            while True:
                await websocket.receive_text()
        except (WebSocketDisconnect, Exception):
            pass

    redis_task = asyncio.create_task(listen_redis())
    client_task = asyncio.create_task(listen_client())

    try:
        # 둘 중 하나가 끝나면 나머지도 취소
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
        await pubsub.unsubscribe(f"upload:{user_id}")
        await pubsub.close()
        await redis.close()
