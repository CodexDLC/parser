"""Интеграционная проверка доступности Redis из runtime-конфигурации."""

from collections.abc import Callable
from typing import NoReturn

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from aibot.config import get_settings

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_redis_accepts_ping(
    unavailable_infrastructure: Callable[[str, BaseException], NoReturn],
) -> None:
    """Redis отвечает на PING или integration-тест корректно пропускается."""

    client = Redis.from_url(
        get_settings().redis_url,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        assert await client.ping() is True
    except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
        unavailable_infrastructure("Redis", exc)
    finally:
        await client.aclose()
