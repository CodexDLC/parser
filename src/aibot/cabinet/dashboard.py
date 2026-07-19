"""Read-only dashboard application service и passive health boundary."""

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from aibot.config import Settings


@dataclass(frozen=True, slots=True)
class DashboardMetrics:
    """Агрегированные счётчики overview."""

    active_sources: int
    news_today: int
    ready_for_generation: int
    posts_total: int
    published_today: int
    errors_24h: int


@dataclass(frozen=True, slots=True)
class RecentPost:
    """Безопасная read-model строка последнего поста."""

    news_title: str
    status: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RecentError:
    """Безопасная read-model строка ErrorLog без details."""

    scope: str
    message: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DashboardReadModel:
    """Результат ограниченного набора SQL dashboard-запросов."""

    metrics: DashboardMetrics
    news_by_status: dict[str, int]
    published_by_day: dict[date, int]
    recent_posts: tuple[RecentPost, ...]
    recent_errors: tuple[RecentError, ...]


@dataclass(frozen=True, slots=True)
class HealthCheck:
    """Один пассивный infrastructure/config status."""

    service: str
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class CabinetDashboardSnapshot:
    """Полный immutable snapshot одного dashboard request."""

    database_available: bool
    metrics: DashboardMetrics
    news_by_status: dict[str, int]
    published_by_day: dict[date, int]
    recent_posts: tuple[RecentPost, ...]
    recent_errors: tuple[RecentError, ...]
    health: tuple[HealthCheck, ...]
    generated_at: datetime
    timezone: str


class DashboardRepository(Protocol):
    """Порт агрегирующего read-only repository."""

    async def load_snapshot(
        self,
        *,
        now: datetime,
        timezone: str,
        recent_limit: int,
    ) -> DashboardReadModel:
        """Загрузить согласованный bounded snapshot."""


class CabinetDashboardReader(Protocol):
    """Порт, используемый Jinja widget providers."""

    async def load_overview(self) -> CabinetDashboardSnapshot:
        """Вернуть snapshot overview без side effects."""


class RedisHealthProbe(Protocol):
    """Минимальный порт разрешённой Redis-проверки."""

    async def ping(self) -> bool:
        """Выполнить пассивный PING."""


class RedisPassiveHealthProbe:
    """Redis PING adapter с коротким timeout, без раскрытия URL."""

    def __init__(self, redis_url: str, *, timeout_seconds: float = 1.0) -> None:
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._timeout_seconds = timeout_seconds

    async def ping(self) -> bool:
        """Проверить Redis без чтения прикладных данных."""

        return bool(
            await asyncio.wait_for(
                self._redis.ping(),
                timeout=self._timeout_seconds,
            )
        )

    async def close(self) -> None:
        """Закрыть отдельный read-only connection pool."""

        await self._redis.aclose()


class PassiveHealthService:
    """Собрать безопасные статусы без OpenAI/Telegram/worker вызовов."""

    def __init__(
        self,
        *,
        settings: Settings,
        redis_probe: RedisHealthProbe,
        cache_ttl_seconds: float = 15.0,
    ) -> None:
        self._settings = settings
        self._redis_probe = redis_probe
        self._cache_ttl_seconds = cache_ttl_seconds
        self._redis_cache: tuple[float, bool] | None = None
        self._lock = asyncio.Lock()

    async def load(self, *, database_available: bool) -> tuple[HealthCheck, ...]:
        """Вернуть snapshot; сеть разрешена только для cached Redis PING."""

        redis_available = await self._redis_available()
        telegram_status = "dry-run" if self._settings.telegram_dry_run else "настроен"
        if not self._settings.telegram_dry_run and not self._telegram_configured():
            telegram_status = "не настроен"
        telegram_detail = f"publisher={self._settings.telegram_publisher}; без отправки сообщений"

        return (
            HealthCheck(
                service="PostgreSQL",
                status="доступен" if database_available else "недоступен",
                detail="read-only SQL" if database_available else "агрегаты недоступны",
            ),
            HealthCheck(
                service="Redis",
                status="доступен" if redis_available else "недоступен",
                detail="cached PING",
            ),
            HealthCheck(
                service="OpenAI",
                status="настроен" if self._settings.openai_api_key else "не настроен",
                detail="без сетевой проверки",
            ),
            HealthCheck(
                service="Telegram",
                status=telegram_status,
                detail=telegram_detail,
            ),
            HealthCheck(
                service="Celery",
                status="настроен",
                detail="без опроса worker",
            ),
            HealthCheck(
                service="Beat",
                status="настроен",
                detail="расписание настроено",
            ),
        )

    def _telegram_configured(self) -> bool:
        """Проверить только настройки выбранного publisher без внешнего вызова."""

        if not self._settings.telegram_target_channel:
            return False
        if self._settings.telegram_publisher == "bot_api":
            return bool(self._settings.telegram_bot_token)
        return bool(self._settings.telegram_api_id and self._settings.telegram_api_hash)

    async def _redis_available(self) -> bool:
        now = time.monotonic()
        if self._redis_cache is not None and self._redis_cache[0] > now:
            return self._redis_cache[1]
        async with self._lock:
            now = time.monotonic()
            if self._redis_cache is not None and self._redis_cache[0] > now:
                return self._redis_cache[1]
            try:
                available = await self._redis_probe.ping()
            except (ConnectionError, OSError, RedisError, TimeoutError):
                available = False
            self._redis_cache = (now + self._cache_ttl_seconds, available)
            return available


class CabinetDashboardService:
    """Оркестрировать SQL read-model и passive health."""

    def __init__(
        self,
        *,
        settings: Settings,
        repository: DashboardRepository,
        health_service: PassiveHealthService,
        recent_limit: int = 8,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._health_service = health_service
        self._recent_limit = recent_limit

    async def load_overview(self) -> CabinetDashboardSnapshot:
        """Вернуть dashboard, сохраняя безопасный degraded state при сбое БД."""

        now = datetime.now(UTC)
        database_available = True
        try:
            data = await self._repository.load_snapshot(
                now=now,
                timezone=self._settings.cabinet_timezone,
                recent_limit=self._recent_limit,
            )
        except (ConnectionError, OSError, SQLAlchemyError):
            database_available = False
            data = _empty_read_model(now)
        health = await self._health_service.load(database_available=database_available)
        return CabinetDashboardSnapshot(
            database_available=database_available,
            metrics=data.metrics,
            news_by_status=data.news_by_status,
            published_by_day=data.published_by_day,
            recent_posts=data.recent_posts,
            recent_errors=data.recent_errors,
            health=health,
            generated_at=now,
            timezone=self._settings.cabinet_timezone,
        )


def _empty_read_model(now: datetime) -> DashboardReadModel:
    """Построить нейтральный degraded snapshot без ложных SQL-данных."""

    return DashboardReadModel(
        metrics=DashboardMetrics(0, 0, 0, 0, 0, 0),
        news_by_status={},
        published_by_day={now.date(): 0},
        recent_posts=(),
        recent_errors=(),
    )
