"""Интеграционные тесты CRUD API через реальную PostgreSQL-БД."""

from collections.abc import AsyncIterator, Callable
from typing import NoReturn

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError, OperationalError

from aibot.api.deps import get_task_queue
from aibot.config import Settings
from aibot.db.base import Base
from aibot.db.session import AsyncSessionFactory, engine
from aibot.integrations.ai_client import AIClientTimeoutError
from aibot.main import app
from aibot.models.enums import ErrorScope, NewsStatus, PostStatus, SourceType
from aibot.models.source import Source
from aibot.parsers.base import ParsedNewsItem
from aibot.parsers.rss import RssFeedParseError
from aibot.parsers.sites import DemoSiteParser
from aibot.repositories.error_log_repository import ErrorLogRepository
from aibot.repositories.news_repository import NewsRepository
from aibot.repositories.post_repository import PostRepository
from aibot.repositories.source_repository import SourceRepository
from aibot.services.exceptions import ConcurrentGenerationError
from aibot.services.keyword_service import KeywordService
from aibot.services.news_ingestion import NewsIngestionService
from aibot.services.pipeline import PipelineService
from aibot.services.post_generation import PostGenerationService
from aibot.services.publishing import PublishingService
from aibot.services.source_service import SourceService
from aibot.smoke import run_smoke_scenario

pytestmark = pytest.mark.integration


class FakeAIClient:
    """AI test double для DB integration и smoke без внешней сети."""

    async def generate_telegram_post(self, input_text: str) -> str:
        return f"Generated: {input_text}"


class CountingAIClient(FakeAIClient):
    """AI test double с подсчётом вызовов."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate_telegram_post(self, input_text: str) -> str:
        self.calls += 1
        return await super().generate_telegram_post(input_text)


class FailingAIClient:
    """AI test double с сообщением, которое нельзя сохранять."""

    async def generate_telegram_post(self, _: str) -> str:
        raise AIClientTimeoutError("api_key=super-secret")


class InvalidFeedParser:
    """Не обращаться к сети и вернуть ошибку некорректной ленты."""

    async def parse(self, **_: object) -> list[ParsedNewsItem]:
        raise RssFeedParseError(
            "Source is not a valid RSS/Atom feed: https://news.example/feed.xml"
        )


class FakeTaskQueue:
    """Зафиксировать постановку Celery-задачи в DB integration-тесте."""

    def __init__(self) -> None:
        self.parse_calls: list[tuple[str, int]] = []

    def enqueue_source_parsing(self, source_id: object, *, limit: int) -> str:
        self.parse_calls.append((str(source_id), limit))
        return "integration-parse-task-id"


async def reset_database() -> None:
    """Пересоздать таблицы прототипа в тестовой PostgreSQL-БД."""

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


@pytest.fixture()
async def prepared_database(
    unavailable_infrastructure: Callable[[str, BaseException], NoReturn],
) -> AsyncIterator[None]:
    """Подготовить БД или пропустить тест, если PostgreSQL не запущен."""

    try:
        await reset_database()
    except (ConnectionRefusedError, DBAPIError, OSError, OperationalError) as exc:
        unavailable_infrastructure("PostgreSQL", exc)
    await engine.dispose()
    yield
    await engine.dispose()


def test_sources_and_keywords_crud_with_database(prepared_database: None) -> None:
    """CRUD endpoints работают через настоящий SQLAlchemy/PostgreSQL слой."""

    assert prepared_database is None
    with TestClient(app) as client:
        source_response = client.post(
            "/api/sources/",
            json={
                "type": "site",
                "name": "Example News",
                "url": "https://example.com/news",
                "enabled": True,
            },
        )
        assert source_response.status_code == 201
        source_payload = source_response.json()
        source_id = source_payload["id"]

        duplicate_source_response = client.post(
            "/api/sources/",
            json={
                "type": "site",
                "name": "Example News Clone",
                "url": "https://example.com/news",
                "enabled": True,
            },
        )
        assert duplicate_source_response.status_code == 409

        list_sources_response = client.get("/api/sources/")
        assert list_sources_response.status_code == 200
        assert len(list_sources_response.json()) == 1

        disable_source_response = client.delete(f"/api/sources/{source_id}")
        assert disable_source_response.status_code == 200
        assert disable_source_response.json()["enabled"] is False

        keyword_response = client.post(
            "/api/keywords/",
            json={"word": "python", "enabled": True},
        )
        assert keyword_response.status_code == 201
        keyword_payload = keyword_response.json()
        keyword_id = keyword_payload["id"]

        duplicate_keyword_response = client.post(
            "/api/keywords/",
            json={"word": "PYTHON", "enabled": True},
        )
        assert duplicate_keyword_response.status_code == 409

        patch_keyword_response = client.patch(
            f"/api/keywords/{keyword_id}",
            json={"enabled": False},
        )
        assert patch_keyword_response.status_code == 200
        assert patch_keyword_response.json()["enabled"] is False

        delete_keyword_response = client.delete(f"/api/keywords/{keyword_id}")
        assert delete_keyword_response.status_code == 204


def test_parse_api_queues_task_with_database(prepared_database: None) -> None:
    """Parse API валидирует реальный Source и возвращает Celery task_id."""

    assert prepared_database is None
    task_queue = FakeTaskQueue()
    app.dependency_overrides[get_task_queue] = lambda: task_queue
    with TestClient(app) as client:
        source_response = client.post(
            "/api/sources/",
            json={
                "type": "site",
                "name": "Demo News",
                "url": "https://example.test/news",
                "enabled": True,
            },
        )
        assert source_response.status_code == 201
        source_id = source_response.json()["id"]

        keyword_response = client.post(
            "/api/keywords/",
            json={"word": "python", "enabled": True},
        )
        assert keyword_response.status_code == 201

        parse_response = client.post(f"/api/sources/{source_id}/parse?limit=2")
        assert parse_response.status_code == 202
        assert parse_response.json() == {
            "task_id": "integration-parse-task-id",
            "status": "queued",
        }
        assert task_queue.parse_calls == [(source_id, 2)]

        news_response = client.get("/api/news/?status=ready_for_generation")
        assert news_response.status_code == 200
        assert news_response.json() == []
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_smoke_scenario_runs_against_database(prepared_database: None) -> None:
    """Smoke CLI scenario проходит полный dry-run pipeline через PostgreSQL."""

    assert prepared_database is None
    result = await run_smoke_scenario(
        reset=True,
        ai_client=FakeAIClient(),  # type: ignore[arg-type]
        site_parser=DemoSiteParser(),
    )
    await engine.dispose()

    assert result.parsed_count == 2
    assert result.saved_count == 2
    assert result.ready_for_generation_count == 1
    assert result.filtered_out_count == 1
    assert result.generated_post_status == "generated"
    assert result.published_post_status == "published"
    assert result.telegram_message_id.startswith("dry-run-")
    assert result.telegram_dry_run is True


@pytest.mark.asyncio
async def test_automatic_pipeline_runs_all_stages_against_database(
    prepared_database: None,
) -> None:
    """PipelineService проходит parse → generate → publish через PostgreSQL."""

    assert prepared_database is None
    async with AsyncSessionFactory() as session:
        await SourceService(session).create_source(
            source_type=SourceType.SITE,
            name="Automatic Demo",
            url="https://example.test/automatic",
            enabled=True,
        )
        await KeywordService(session).create_keyword(word="python", enabled=True)

        result = await PipelineService(
            session,
            news_ingestion_service=NewsIngestionService(
                session,
                site_parser=DemoSiteParser(),
            ),
            post_generation_service=PostGenerationService(
                session,
                ai_client=FakeAIClient(),  # type: ignore[arg-type]
            ),
            publishing_service=PublishingService(
                session,
                settings=Settings(telegram_dry_run=True),
            ),
        ).run_once(parse_limit=2, generation_limit=10, publishing_limit=10)
        published_posts = await PostRepository(session).list_by_status(PostStatus.PUBLISHED)

    await engine.dispose()
    assert result.parsed_sources_count == 1
    assert result.failed_sources_count == 0
    assert result.parsed_items_count == 2
    assert result.saved_items_count == 2
    assert result.ready_items_count == 1
    assert result.generated_posts_count == 1
    assert result.published_posts_count == 1
    assert len(published_posts) == 1
    assert published_posts[0].telegram_message_id is not None
    assert published_posts[0].telegram_message_id.startswith("dry-run-")


@pytest.mark.asyncio
async def test_postgresql_row_lock_blocks_concurrent_generation(
    prepared_database: None,
) -> None:
    """Вторая DB session не вызывает AI для уже заблокированной news."""

    assert prepared_database is None
    async with AsyncSessionFactory() as first_session:
        await SourceService(first_session).create_source(
            source_type=SourceType.SITE,
            name="Lock Demo",
            url="https://example.test/lock",
            enabled=True,
        )
        await KeywordService(first_session).create_keyword(word="python", enabled=True)
        await NewsIngestionService(
            first_session,
            site_parser=DemoSiteParser(),
        ).parse_source(
            (
                await SourceService(first_session).list_sources(
                    enabled=True,
                    limit=1,
                )
            )[0].id,
            limit=2,
        )
        ready_news = await NewsRepository(first_session).list_by_status(
            NewsStatus.READY_FOR_GENERATION,
            limit=1,
        )
        assert len(ready_news) == 1
        locked_news = await NewsRepository(first_session).get_for_generation(ready_news[0].id)
        assert locked_news is not None

        ai_client = CountingAIClient()
        async with AsyncSessionFactory() as second_session:
            service = PostGenerationService(
                second_session,
                ai_client=ai_client,  # type: ignore[arg-type]
            )
            with pytest.raises(ConcurrentGenerationError):
                await service.generate_post_from_news(ready_news[0].id)

        assert ai_client.calls == 0
        await first_session.rollback()

    await engine.dispose()


@pytest.mark.asyncio
async def test_ai_error_log_is_persisted_without_secret(
    prepared_database: None,
) -> None:
    """AI failure сохраняется в PostgreSQL с news_id и безопасными details."""

    assert prepared_database is None
    async with AsyncSessionFactory() as session:
        source = await SourceService(session).create_source(
            source_type=SourceType.SITE,
            name="AI Error Demo",
            url="https://example.test/ai-error",
            enabled=True,
        )
        await KeywordService(session).create_keyword(word="python", enabled=True)
        await NewsIngestionService(
            session,
            site_parser=DemoSiteParser(),
        ).parse_source(source.id, limit=2)
        ready_news = await NewsRepository(session).list_by_status(
            NewsStatus.READY_FOR_GENERATION,
            limit=1,
        )
        assert len(ready_news) == 1

        with pytest.raises(AIClientTimeoutError, match="super-secret"):
            await PostGenerationService(
                session,
                ai_client=FailingAIClient(),  # type: ignore[arg-type]
            ).generate_post_from_news(ready_news[0].id)

        error_logs = await ErrorLogRepository(session).list_by_scope(ErrorScope.AI)

    await engine.dispose()
    assert len(error_logs) == 1
    assert error_logs[0].news_id == ready_news[0].id
    assert error_logs[0].message == "AI generation failed"
    assert error_logs[0].details == "AIClientTimeoutError"
    assert "secret" not in error_logs[0].details


@pytest.mark.asyncio
async def test_parser_error_is_persisted_with_source_id(prepared_database: None) -> None:
    """Parser error сохраняется в PostgreSQL и связывается с Source."""

    assert prepared_database is None
    async with AsyncSessionFactory() as session:
        source = await SourceRepository(session).add(
            Source(
                type=SourceType.SITE,
                name="Broken Feed",
                url="https://news.example/feed.xml",
                enabled=True,
            )
        )
        await session.commit()

        service = NewsIngestionService(session, site_parser=InvalidFeedParser())
        with pytest.raises(RssFeedParseError):
            await service.parse_source(source.id)

        error_logs = await ErrorLogRepository(session).list_by_scope(ErrorScope.PARSER)

    await engine.dispose()
    assert len(error_logs) == 1
    assert error_logs[0].source_id == source.id
    assert error_logs[0].message == "Invalid RSS/Atom feed"
    assert error_logs[0].details == (
        "Source is not a valid RSS/Atom feed: https://news.example/feed.xml"
    )
