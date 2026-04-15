from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from domains.auth.service import AuthService
from main import app
from models.model import ChatSession, User

# ── 헬퍼 ──────────────────────────────────────────────────────────────────────


def _make_user(user_id: int) -> User:
    user = MagicMock(spec=User)
    user.id = user_id
    user.is_active = True
    return user


def _make_session(session_id: int, user_id: int) -> ChatSession:
    session = MagicMock(spec=ChatSession)
    session.id = session_id
    session.user_id = user_id
    return session


# ── 기존 Redis pubsub 단위 테스트 ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chat_ws_redis_message():
    with patch("domains.chat.ws_router.aioredis.Redis") as mock_redis:
        mock_pubsub = AsyncMock()
        mock_redis.return_value.pubsub.return_value = mock_pubsub

        state = {"called": False}

        async def mock_get_message(**kwargs):
            if not state["called"]:
                state["called"] = True
                return {"type": "message", "data": b"test chat message"}
            return None

        mock_pubsub.get_message.side_effect = mock_get_message
        message = await mock_pubsub.get_message()
        assert message is not None
        assert message["data"].decode("utf-8") == "test chat message"


@pytest.mark.asyncio
async def test_chat_ws_redis_error():
    with patch("domains.chat.ws_router.aioredis.Redis") as mock_redis:
        mock_pubsub = AsyncMock()
        mock_redis.return_value.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.side_effect = RedisConnectionError()

        with pytest.raises(RedisConnectionError):
            await mock_pubsub.get_message()

        mock_pubsub.get_message.assert_called_once()


@pytest.mark.asyncio
async def test_notifications_ws_redis_message():
    with patch("domains.chat.ws_router.aioredis.Redis") as mock_redis:
        mock_pubsub = AsyncMock()
        mock_redis.return_value.pubsub.return_value = mock_pubsub

        state = {"called": False}

        async def mock_get_message(**kwargs):
            if not state["called"]:
                state["called"] = True
                return {"type": "message", "data": b"test notification message"}
            return None

        mock_pubsub.get_message.side_effect = mock_get_message
        message = await mock_pubsub.get_message()
        assert message is not None
        assert message["data"].decode("utf-8") == "test notification message"


@pytest.mark.asyncio
async def test_notifications_ws_redis_error():
    with patch("domains.chat.ws_router.aioredis.Redis") as mock_redis:
        mock_pubsub = AsyncMock()
        mock_redis.return_value.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.side_effect = RedisConnectionError()

        with pytest.raises(RedisConnectionError):
            await mock_pubsub.get_message()

        mock_pubsub.get_message.assert_called_once()


# ── 인증/권한 통합 테스트 ───────────────────────────────────────────────────────

auth_service = AuthService(None)


class TestChatWsAuth:
    """chat websocket 인증/권한 검사."""

    def test_no_token_rejected(self, db_session):
        """토큰 없이 연결하면 거절된다."""
        with TestClient(app) as client:
            with pytest.raises(Exception):
                with client.websocket_connect("/ws/chat/1/1"):
                    pass

    def test_wrong_user_id_rejected(self, db_session, registered_user):
        """토큰 사용자와 path user_id가 다르면 거절된다."""
        token = auth_service.create_access_token(registered_user.email)
        other_user_id = registered_user.id + 999

        with TestClient(app) as client:
            client.cookies.set("access_token", token)
            with pytest.raises(Exception):
                with client.websocket_connect(f"/ws/chat/1/{other_user_id}"):
                    pass

    def test_session_not_owned_rejected(self, db_session, registered_user):
        """세션이 해당 사용자 소유가 아니면 거절된다."""
        token = auth_service.create_access_token(registered_user.email)

        # 세션 없음 → get_session_by_id_and_user → None → 거절
        with TestClient(app) as client:
            client.cookies.set("access_token", token)
            with pytest.raises(Exception):
                with client.websocket_connect(f"/ws/chat/9999/{registered_user.id}"):
                    pass


class TestNotificationsWsAuth:
    """notifications websocket 인증/권한 검사."""

    def test_no_token_rejected(self, db_session):
        """토큰 없이 연결하면 거절된다."""
        with TestClient(app) as client:
            with pytest.raises(Exception):
                with client.websocket_connect("/ws/notifications/1"):
                    pass

    def test_wrong_user_id_rejected(self, db_session, registered_user):
        """토큰 사용자와 path user_id가 다르면 거절된다."""
        token = auth_service.create_access_token(registered_user.email)
        other_user_id = registered_user.id + 999

        with TestClient(app) as client:
            client.cookies.set("access_token", token)
            with pytest.raises(Exception):
                with client.websocket_connect(f"/ws/notifications/{other_user_id}"):
                    pass
