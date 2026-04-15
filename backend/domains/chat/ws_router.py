import asyncio
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis import asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

router = APIRouter()


@router.websocket("/ws/chat/{session_id}/{user_id}")
async def chat_ws(websocket: WebSocket, session_id: int, user_id: int):
    await websocket.accept()
    redis = aioredis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"chat:{session_id}:{user_id}")

    async def listen_redis():
        while True:
            try:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=None
                )
            except RedisConnectionError:
                logger.warning("chat ws: Redis connection lost, closing listener")
                return
            except Exception:
                logger.exception("chat ws: unexpected error in listen_redis")
                return
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
        await asyncio.wait(
            [redis_task, client_task], return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        for task in (redis_task, client_task):
            if not task.done():
                task.cancel()
        try:
            await pubsub.unsubscribe(f"chat:{session_id}:{user_id}")
        except Exception:
            pass
        try:
            await pubsub.close()
        except Exception:
            pass
        try:
            await redis.aclose()
        except Exception:
            pass


@router.websocket("/ws/notifications/{user_id}")
async def notifications_ws(websocket: WebSocket, user_id: int):
    await websocket.accept()
    redis = aioredis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"notifications:{user_id}")

    async def listen_redis():
        while True:
            try:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=None
                )
            except RedisConnectionError:
                logger.warning(
                    "notifications ws: Redis connection lost, closing listener"
                )
                return
            except Exception:
                logger.exception("notifications ws: unexpected error in listen_redis")
                return
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
        await asyncio.wait(
            [redis_task, client_task], return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        for task in (redis_task, client_task):
            if not task.done():
                task.cancel()
        try:
            await pubsub.unsubscribe(f"notifications:{user_id}")
        except Exception:
            pass
        try:
            await pubsub.close()
        except Exception:
            pass
        try:
            await redis.aclose()
        except Exception:
            pass
