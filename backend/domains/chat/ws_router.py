import asyncio
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis import asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError

from database import db_session
from dependencies import get_user_from_websocket
from domains.chat.repository import ChatRepository
from errors.exceptions import AppException

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

router = APIRouter()


async def _reject(websocket: WebSocket, code: int = 4401) -> None:
    """accept 없이 연결을 거절한다."""
    await websocket.close(code=code)


@router.websocket("/ws/chat/{session_id}/{user_id}")
async def chat_ws(websocket: WebSocket, session_id: int, user_id: int):
    # ── 인증 ─────────────────────────────────────────────────────────────────
    try:
        current_user = get_user_from_websocket(websocket)
    except AppException:
        await _reject(websocket, code=4401)
        return

    # ── user_id 일치 검사 ─────────────────────────────────────────────────────
    if current_user.id != user_id:
        await _reject(websocket, code=4403)
        return

    # ── session 소유권 검사 ───────────────────────────────────────────────────
    with db_session() as db:
        chat_repo = ChatRepository(db)
        session = chat_repo.get_session_by_id_and_user(session_id, current_user.id)

    if session is None:
        await _reject(websocket, code=4403)
        return

    # ── 연결 수립 ─────────────────────────────────────────────────────────────
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
    # ── 인증 ─────────────────────────────────────────────────────────────────
    try:
        current_user = get_user_from_websocket(websocket)
    except AppException:
        await _reject(websocket, code=4401)
        return

    # ── user_id 일치 검사 ─────────────────────────────────────────────────────
    if current_user.id != user_id:
        await _reject(websocket, code=4403)
        return

    # ── 연결 수립 ─────────────────────────────────────────────────────────────
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
