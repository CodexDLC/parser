"""Интеграционная проверка Redis adapter кабинета."""

import secrets
from collections.abc import Callable
from contextlib import suppress
from typing import NoReturn

import pytest

from aibot.cabinet.auth import CabinetSession
from aibot.cabinet.redis_store import (
    CabinetSecurityStoreError,
    RedisCabinetSecurityStore,
)
from aibot.config import Settings

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_redis_cabinet_session_and_rate_limit_round_trip(
    unavailable_infrastructure: Callable[[str, BaseException], NoReturn],
) -> None:
    """Redis хранит session, инвалидирует logout и атомарно считает login failures."""

    store = RedisCabinetSecurityStore(Settings().redis_url)
    unique = secrets.token_urlsafe(16)
    session = CabinetSession(
        session_id=f"test-{unique}",
        username="admin",
        csrf_token=secrets.token_urlsafe(16),
    )
    rate_key = f"test-{unique}"

    try:
        await store.save_session(session, ttl_seconds=60)
        assert await store.get_session(session.session_id) == session
        assert await store.get_login_failures(rate_key) == 0
        assert await store.record_login_failure(rate_key, window_seconds=60) == 1
        assert await store.record_login_failure(rate_key, window_seconds=60) == 2
        await store.clear_login_failures(rate_key)
        assert await store.get_login_failures(rate_key) == 0
        await store.delete_session(session.session_id)
        assert await store.get_session(session.session_id) is None
    except CabinetSecurityStoreError as exc:
        unavailable_infrastructure("Redis cabinet security store", exc)
    finally:
        with suppress(CabinetSecurityStoreError):
            await store.delete_session(session.session_id)
            await store.clear_login_failures(rate_key)
        await store.close()
