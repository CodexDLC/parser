"""SQLAlchemy read-only repository для overview кабинета."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aibot.cabinet.dashboard import (
    DashboardMetrics,
    DashboardReadModel,
    RecentError,
    RecentPost,
)
from aibot.models.enums import NewsStatus, PostStatus
from aibot.models.error_log import ErrorLog
from aibot.models.news_item import NewsItem
from aibot.models.post import Post
from aibot.models.source import Source


class SqlAlchemyCabinetDashboardRepository:
    """Собрать dashboard пятью bounded SQL-запросами без ORM relationships."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def load_snapshot(
        self,
        *,
        now: datetime,
        timezone: str,
        recent_limit: int,
    ) -> DashboardReadModel:
        """Загрузить метрики, две серии и две последние выборки."""

        local_timezone = ZoneInfo(timezone)
        local_now = now.astimezone(local_timezone)
        local_today = local_now.date()
        today_start = datetime.combine(
            local_today,
            time.min,
            tzinfo=local_timezone,
        ).astimezone(UTC)
        seven_days_start = today_start - timedelta(days=6)
        errors_start = now - timedelta(hours=24)

        async with self._session_factory() as session:
            metrics = await self._load_metrics(
                session,
                today_start=today_start,
                errors_start=errors_start,
            )
            news_by_status = await self._load_news_statuses(session)
            published_by_day = await self._load_published_series(
                session,
                start=seven_days_start,
                local_today=local_today,
                timezone=timezone,
            )
            recent_posts = await self._load_recent_posts(session, limit=recent_limit)
            recent_errors = await self._load_recent_errors(session, limit=recent_limit)

        return DashboardReadModel(
            metrics=metrics,
            news_by_status=news_by_status,
            published_by_day=published_by_day,
            recent_posts=recent_posts,
            recent_errors=recent_errors,
        )

    @staticmethod
    async def _load_metrics(
        session: AsyncSession,
        *,
        today_start: datetime,
        errors_start: datetime,
    ) -> DashboardMetrics:
        statement = select(
            select(func.count(Source.id))
            .where(Source.enabled.is_(True))
            .scalar_subquery()
            .label("active_sources"),
            select(func.count(NewsItem.id))
            .where(NewsItem.created_at >= today_start)
            .scalar_subquery()
            .label("news_today"),
            select(func.count(NewsItem.id))
            .where(NewsItem.status == NewsStatus.READY_FOR_GENERATION)
            .scalar_subquery()
            .label("ready_for_generation"),
            select(func.count(Post.id)).scalar_subquery().label("posts_total"),
            select(func.count(Post.id))
            .where(
                Post.status == PostStatus.PUBLISHED,
                Post.published_at >= today_start,
            )
            .scalar_subquery()
            .label("published_today"),
            select(func.count(ErrorLog.id))
            .where(ErrorLog.created_at >= errors_start)
            .scalar_subquery()
            .label("errors_24h"),
        )
        row = (await session.execute(statement)).one()
        return DashboardMetrics(
            active_sources=int(row.active_sources),
            news_today=int(row.news_today),
            ready_for_generation=int(row.ready_for_generation),
            posts_total=int(row.posts_total),
            published_today=int(row.published_today),
            errors_24h=int(row.errors_24h),
        )

    @staticmethod
    async def _load_news_statuses(session: AsyncSession) -> dict[str, int]:
        rows = (
            await session.execute(
                select(NewsItem.status, func.count(NewsItem.id))
                .group_by(NewsItem.status)
                .order_by(NewsItem.status)
            )
        ).all()
        return {
            status.value if isinstance(status, NewsStatus) else str(status): int(count)
            for status, count in rows
        }

    @staticmethod
    async def _load_published_series(
        session: AsyncSession,
        *,
        start: datetime,
        local_today: date,
        timezone: str,
    ) -> dict[date, int]:
        local_published_day = func.date(func.timezone(timezone, Post.published_at))
        rows = (
            await session.execute(
                select(local_published_day, func.count(Post.id))
                .where(
                    Post.status == PostStatus.PUBLISHED,
                    Post.published_at >= start,
                )
                .group_by(local_published_day)
                .order_by(local_published_day)
            )
        ).all()
        result = {local_today - timedelta(days=offset): 0 for offset in range(6, -1, -1)}
        for day_value, count in rows:
            normalized_day = (
                day_value if isinstance(day_value, date) else date.fromisoformat(str(day_value))
            )
            if normalized_day in result:
                result[normalized_day] = int(count)
        return result

    @staticmethod
    async def _load_recent_posts(
        session: AsyncSession,
        *,
        limit: int,
    ) -> tuple[RecentPost, ...]:
        rows = (
            await session.execute(
                select(NewsItem.title, Post.status, Post.updated_at)
                .join(NewsItem, NewsItem.id == Post.news_id)
                .order_by(Post.updated_at.desc(), Post.id.desc())
                .limit(limit)
            )
        ).all()
        return tuple(
            RecentPost(
                news_title=title,
                status=status.value if isinstance(status, PostStatus) else str(status),
                updated_at=updated_at,
            )
            for title, status, updated_at in rows
        )

    @staticmethod
    async def _load_recent_errors(
        session: AsyncSession,
        *,
        limit: int,
    ) -> tuple[RecentError, ...]:
        rows = (
            await session.execute(
                select(ErrorLog.scope, ErrorLog.message, ErrorLog.created_at)
                .order_by(ErrorLog.created_at.desc(), ErrorLog.id.desc())
                .limit(limit)
            )
        ).all()
        return tuple(
            RecentError(
                scope=scope.value if hasattr(scope, "value") else str(scope),
                message=message,
                created_at=created_at,
            )
            for scope, message, created_at in rows
        )
