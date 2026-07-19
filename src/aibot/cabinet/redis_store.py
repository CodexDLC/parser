"""Redis adapter для cabinet sessions и login rate limiting."""

import json

from redis.asyncio import Redis
from redis.exceptions import RedisError

from aibot.cabinet.auth import CabinetSecurityStore, CabinetSession


class CabinetSecurityStoreError(RuntimeError):
    """Redis boundary кабинета временно недоступна."""


class RedisCabinetSecurityStore(CabinetSecurityStore):
    """Хранить opaque sessions и rate counters в существующем Redis."""

    def __init__(self, redis_url: str) -> None:
        self._redis = Redis.from_url(redis_url, decode_responses=True)

    async def save_session(
        self,
        session: CabinetSession,
        *,
        ttl_seconds: int,
    ) -> None:
        """Сохранить session JSON с обязательным TTL."""

        payload = json.dumps(
            {
                "session_id": session.session_id,
                "username": session.username,
                "csrf_token": session.csrf_token,
            }
        )
        try:
            await self._redis.setex(self._session_key(session.session_id), ttl_seconds, payload)
        except RedisError as exc:
            raise CabinetSecurityStoreError("Cabinet session store is unavailable") from exc

    async def get_session(self, session_id: str) -> CabinetSession | None:
        """Получить session или None после expiry/logout."""

        try:
            payload = await self._redis.get(self._session_key(session_id))
        except RedisError as exc:
            raise CabinetSecurityStoreError("Cabinet session store is unavailable") from exc
        if payload is None:
            return None
        try:
            data = json.loads(payload)
            return CabinetSession(
                session_id=str(data["session_id"]),
                username=str(data["username"]),
                csrf_token=str(data["csrf_token"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CabinetSecurityStoreError("Cabinet session payload is invalid") from exc

    async def delete_session(self, session_id: str) -> None:
        """Удалить session при logout."""

        try:
            await self._redis.delete(self._session_key(session_id))
        except RedisError as exc:
            raise CabinetSecurityStoreError("Cabinet session store is unavailable") from exc

    async def get_login_failures(self, key: str) -> int:
        """Вернуть текущий login counter."""

        try:
            value = await self._redis.get(self._rate_key(key))
        except RedisError as exc:
            raise CabinetSecurityStoreError("Cabinet rate limiter is unavailable") from exc
        return int(value or 0)

    async def record_login_failure(self, key: str, *, window_seconds: int) -> int:
        """Атомарно увеличить counter и задать TTL при первой попытке."""

        redis_key = self._rate_key(key)
        try:
            value = await self._redis.incr(redis_key)
            if value == 1:
                await self._redis.expire(redis_key, window_seconds)
        except RedisError as exc:
            raise CabinetSecurityStoreError("Cabinet rate limiter is unavailable") from exc
        return int(value)

    async def clear_login_failures(self, key: str) -> None:
        """Очистить counter после успешной авторизации."""

        try:
            await self._redis.delete(self._rate_key(key))
        except RedisError as exc:
            raise CabinetSecurityStoreError("Cabinet rate limiter is unavailable") from exc

    async def close(self) -> None:
        """Закрыть Redis connection pool при остановке приложения."""

        await self._redis.aclose()

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"m4:cabinet:session:{session_id}"

    @staticmethod
    def _rate_key(key: str) -> str:
        return f"m4:cabinet:login:{key}"
