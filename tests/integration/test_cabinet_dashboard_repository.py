"""Интеграционный контракт агрегирующего read-model dashboard."""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import NoReturn

import pytest
from sqlalchemy import event
from sqlalchemy.exc import DBAPIError, OperationalError

from aibot.cabinet.dashboard_repository import SqlAlchemyCabinetDashboardRepository
from aibot.db.base import Base
from aibot.db.session import AsyncSessionFactory, engine
from aibot.models.enums import ErrorScope, NewsStatus, PostStatus, SourceType
from aibot.models.error_log import ErrorLog
from aibot.models.news_item import NewsItem
from aibot.models.post import Post
from aibot.models.source import Source

pytestmark = pytest.mark.integration


@pytest.fixture()
async def prepared_dashboard_database(
    unavailable_infrastructure: Callable[[str, BaseException], NoReturn],
) -> AsyncIterator[None]:
    """Пересоздать PostgreSQL schema для изолированного dashboard-теста."""

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
    except (ConnectionRefusedError, DBAPIError, OSError, OperationalError) as exc:
        unavailable_infrastructure("PostgreSQL", exc)
    await engine.dispose()
    yield
    await engine.dispose()


async def test_dashboard_repository_returns_bounded_aggregate_snapshot(
    prepared_dashboard_database: None,
) -> None:
    """Весь обзор строится пятью запросами без ORM N+1."""

    assert prepared_dashboard_database is None
    now = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    async with AsyncSessionFactory() as session:
        source = Source(
            type=SourceType.SITE,
            name="Dashboard feed",
            url="https://example.test/dashboard.xml",
            enabled=True,
        )
        session.add(source)
        await session.flush()
        ready_news = NewsItem(
            title="Ready news",
            url="https://example.test/ready",
            summary="Summary",
            source_id=source.id,
            published_at=now - timedelta(hours=2),
            content_hash="dashboard-ready",
            status=NewsStatus.READY_FOR_GENERATION,
            created_at=now - timedelta(hours=1),
        )
        generated_news = NewsItem(
            title="Generated news",
            url="https://example.test/generated",
            summary="Summary",
            source_id=source.id,
            published_at=now - timedelta(days=1),
            content_hash="dashboard-generated",
            status=NewsStatus.GENERATED,
            created_at=now - timedelta(days=1),
        )
        session.add_all((ready_news, generated_news))
        await session.flush()
        session.add(
            Post(
                news_id=generated_news.id,
                generated_text="Published post",
                status=PostStatus.PUBLISHED,
                published_at=now - timedelta(hours=3),
                created_at=now - timedelta(days=1),
                updated_at=now - timedelta(hours=3),
            )
        )
        session.add(
            ErrorLog(
                scope=ErrorScope.PARSER,
                message="Broken feed",
                source_id=source.id,
                created_at=now - timedelta(hours=4),
            )
        )
        await session.commit()

    statements = 0

    def count_statement(*_: object) -> None:
        nonlocal statements
        statements += 1

    event.listen(engine.sync_engine, "before_cursor_execute", count_statement)
    try:
        snapshot = await SqlAlchemyCabinetDashboardRepository(
            AsyncSessionFactory
        ).load_snapshot(
            now=now,
            timezone="Europe/Berlin",
            recent_limit=8,
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", count_statement)
        await engine.dispose()

    assert statements == 5
    assert snapshot.metrics.active_sources == 1
    assert snapshot.metrics.news_today == 1
    assert snapshot.metrics.ready_for_generation == 1
    assert snapshot.metrics.posts_total == 1
    assert snapshot.metrics.published_today == 1
    assert snapshot.metrics.errors_24h == 1
    assert snapshot.news_by_status == {
        NewsStatus.GENERATED.value: 1,
        NewsStatus.READY_FOR_GENERATION.value: 1,
    }
    assert snapshot.published_by_day[now.date()] == 1
    assert snapshot.recent_posts[0].news_title == "Generated news"
    assert snapshot.recent_errors[0].message == "Broken feed"
