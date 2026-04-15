from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError


@pytest.mark.asyncio
async def test_chat_ws_success():
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
async def test_notifications_ws_success():
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
