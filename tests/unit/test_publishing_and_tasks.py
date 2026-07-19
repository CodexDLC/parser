"""Тесты dry-run публикации и Celery task wiring."""

import uuid
from datetime import UTC, datetime

import pytest

from aibot.config import Settings
from aibot.integrations.telegram_client import TelegramClient
from aibot.models.enums import ErrorScope, PostStatus
from aibot.models.error_log import ErrorLog
from aibot.models.post import Post
from aibot.services.exceptions import InvalidPostStateError, PublishingFailedError
from aibot.services.publishing import PublishingService
from aibot.tasks.celery_app import celery_app
from aibot.tasks.filtering import filter_news
from aibot.tasks.generation import generate_post, generate_text
from aibot.tasks.parsing import parse_enabled_sources, parse_source
from aibot.tasks.pipeline import run_pipeline
from aibot.tasks.publishing import publish_post


class FakePostRepository:
    """Fake post repository for publishing service tests."""

    def __init__(self, post: Post | None) -> None:
        self.post = post

    async def get(self, _: uuid.UUID) -> Post | None:
        return self.post


class FakeErrorLogRepository:
    """Fake error log repository for publishing service tests."""

    def __init__(self) -> None:
        self.saved: list[ErrorLog] = []

    async def add(self, error_log: ErrorLog) -> ErrorLog:
        self.saved.append(error_log)
        return error_log


class FailingTelegramClient:
    """Telegram client, который имитирует сбой публикации."""

    async def publish_message(self, _: str) -> str:
        raise RuntimeError("telegram timeout")


class FakeSession:
    """Fake async session with transaction counters."""

    def __init__(self) -> None:
        self.flushed = 0
        self.commits = 0
        self.refreshed = 0

    async def flush(self) -> None:
        self.flushed += 1

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _: object) -> None:
        self.refreshed += 1


def make_post(*, status: PostStatus = PostStatus.GENERATED) -> Post:
    """Create a post object for publishing tests."""

    return Post(
        id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
        news_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        generated_text="Generated text",
        status=status,
        created_at=datetime(2026, 7, 11, tzinfo=UTC),
        updated_at=datetime(2026, 7, 11, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_publishing_service_uses_telegram_dry_run() -> None:
    """PublishingService publishes generated posts through dry-run Telegram client."""

    post = make_post()
    session = FakeSession()
    settings = Settings(telegram_dry_run=True)
    service = PublishingService(
        session,  # type: ignore[arg-type]
        settings=settings,
        repository=FakePostRepository(post),  # type: ignore[arg-type]
        telegram_client=TelegramClient(settings),
    )

    result = await service.publish_post(post.id)

    assert result.dry_run is True
    assert result.telegram_message_id.startswith("dry-run-")
    assert result.status == PostStatus.PUBLISHED
    assert post.status == PostStatus.PUBLISHED
    assert post.telegram_message_id == result.telegram_message_id
    assert session.flushed == 1
    assert session.commits == 1
    assert session.refreshed == 1


@pytest.mark.asyncio
async def test_publishing_service_rejects_already_published_post() -> None:
    """PublishingService refuses to publish already published posts."""

    post = make_post(status=PostStatus.PUBLISHED)
    service = PublishingService(
        FakeSession(),  # type: ignore[arg-type]
        settings=Settings(telegram_dry_run=True),
        repository=FakePostRepository(post),  # type: ignore[arg-type]
    )

    with pytest.raises(InvalidPostStateError):
        await service.publish_post(post.id)


@pytest.mark.asyncio
async def test_publishing_service_logs_telegram_errors() -> None:
    """PublishingService помечает пост failed и пишет ErrorLog при сбое Telegram."""

    post = make_post()
    session = FakeSession()
    error_log_repository = FakeErrorLogRepository()
    service = PublishingService(
        session,  # type: ignore[arg-type]
        settings=Settings(telegram_dry_run=False),
        repository=FakePostRepository(post),  # type: ignore[arg-type]
        error_log_repository=error_log_repository,  # type: ignore[arg-type]
        telegram_client=FailingTelegramClient(),  # type: ignore[arg-type]
    )

    with pytest.raises(PublishingFailedError):
        await service.publish_post(post.id)

    assert post.status == PostStatus.FAILED
    assert post.error_message == "telegram timeout"
    assert len(error_log_repository.saved) == 1
    assert error_log_repository.saved[0].scope == ErrorScope.TELEGRAM
    assert error_log_repository.saved[0].post_id == post.id
    assert error_log_repository.saved[0].details == "telegram timeout"
    assert session.flushed == 1
    assert session.commits == 1
    assert session.refreshed == 1


def test_celery_app_registers_project_tasks() -> None:
    """Celery app knows core project tasks without connecting to Redis."""

    assert parse_source.name in celery_app.tasks
    assert parse_enabled_sources.name in celery_app.tasks
    assert filter_news.name in celery_app.tasks
    assert generate_text.name in celery_app.tasks
    assert generate_post.name in celery_app.tasks
    assert publish_post.name in celery_app.tasks
    assert run_pipeline.name in celery_app.tasks


def test_celery_retry_settings_are_configured() -> None:
    """Celery has broker publish retry and AI task retry settings."""

    assert celery_app.conf.task_publish_retry is True
    assert celery_app.conf.task_publish_retry_policy["max_retries"] == 3
    assert parse_source.max_retries == 3
    assert generate_text.max_retries == 3
    assert generate_post.max_retries == 3


def test_beat_schedules_full_pipeline_with_runtime_limits() -> None:
    """Beat запускает полный pipeline вместо отдельного parsing batch."""

    schedule = celery_app.conf.beat_schedule

    assert set(schedule) == {"run-full-pipeline-every-30-minutes"}
    entry = schedule["run-full-pipeline-every-30-minutes"]
    assert entry["task"] == run_pipeline.name
    assert entry["schedule"] == 30 * 60
    assert entry["kwargs"] == {
        "parse_limit": 10,
        "generation_limit": 10,
        "publishing_limit": 10,
    }
    assert entry["task"] != parse_enabled_sources.name


def test_generation_task_contract_uses_injected_ai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generation task возвращает production-контракт без fake_mode."""

    class FakeTaskGenerationService:
        def __init__(self, _: object) -> None:
            pass

        async def generate_manual_post(self, text: str) -> str:
            return f"Generated: {text}"

    monkeypatch.setattr(
        "aibot.tasks.generation.PostGenerationService",
        FakeTaskGenerationService,
    )
    result = generate_text.run("Python получил обновление")

    assert result == {"generated_text": "Generated: Python получил обновление"}
