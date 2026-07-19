"""Тесты API просмотра новостей/постов/логов и fake AI генерации."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from aibot.api.deps import (
    get_error_log_service,
    get_news_service,
    get_post_generation_service,
    get_post_service,
    get_publishing_service,
    get_task_queue,
)
from aibot.main import app
from aibot.models.enums import ErrorScope, NewsStatus, PostStatus
from aibot.services.exceptions import EntityNotFoundError


@dataclass
class FakeNewsItem:
    """Минимальный объект новости для response_model."""

    id: uuid.UUID
    title: str
    url: str | None
    summary: str
    source_id: uuid.UUID
    published_at: datetime
    raw_text: str | None
    content_hash: str
    status: NewsStatus
    created_at: datetime


@dataclass
class FakePost:
    """Минимальный объект поста для response_model."""

    id: uuid.UUID
    news_id: uuid.UUID
    generated_text: str
    status: PostStatus
    published_at: datetime | None
    telegram_message_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class FakeErrorLog:
    """Минимальный объект ошибки для response_model."""

    id: uuid.UUID
    scope: ErrorScope
    message: str
    details: str | None
    source_id: uuid.UUID | None
    news_id: uuid.UUID | None
    post_id: uuid.UUID | None
    created_at: datetime


class FakeNewsService:
    """Fake news service для проверки router контракта."""

    news_id = uuid.UUID("55555555-5555-5555-5555-555555555555")
    source_id = uuid.UUID("66666666-6666-6666-6666-666666666666")

    def _news_item(self) -> FakeNewsItem:
        return FakeNewsItem(
            id=self.news_id,
            title="Python release",
            url="https://example.com/python",
            summary="Python got faster.",
            source_id=self.source_id,
            published_at=datetime(2026, 7, 11, tzinfo=UTC),
            raw_text=None,
            content_hash="hash-python",
            status=NewsStatus.READY_FOR_GENERATION,
            created_at=datetime(2026, 7, 11, tzinfo=UTC),
        )

    async def list_news(self, **_: object) -> list[FakeNewsItem]:
        return [self._news_item()]

    async def get_news_item(self, news_id: uuid.UUID) -> FakeNewsItem:
        if news_id != self.news_id:
            raise EntityNotFoundError("News item not found")
        return self._news_item()


class FakePostService:
    """Fake post service для проверки router контракта."""

    post_id = uuid.UUID("77777777-7777-7777-7777-777777777777")
    news_id = FakeNewsService.news_id
    published = False

    def _post(self) -> FakePost:
        return FakePost(
            id=self.post_id,
            news_id=self.news_id,
            generated_text="Generated post",
            status=PostStatus.PUBLISHED if self.published else PostStatus.GENERATED,
            published_at=datetime(2026, 7, 11, tzinfo=UTC) if self.published else None,
            telegram_message_id="dry-run-message" if self.published else None,
            error_message=None,
            created_at=datetime(2026, 7, 11, tzinfo=UTC),
            updated_at=datetime(2026, 7, 11, tzinfo=UTC),
        )

    async def list_posts(self, **_: object) -> list[FakePost]:
        return [self._post()]

    async def get_post(self, post_id: uuid.UUID) -> FakePost:
        if post_id != self.post_id:
            raise EntityNotFoundError("Post not found")
        return self._post()


class FakePostGenerationService:
    """Fake post generation service для проверки news generate endpoint."""

    manual_generation_called = False
    news_generation_called = False

    async def get_generation_candidate(self, news_id: uuid.UUID) -> FakeNewsItem:
        if news_id != FakeNewsService.news_id:
            raise EntityNotFoundError("News item not found")
        return FakeNewsService()._news_item()

    async def generate_manual_post(self, text: str) -> str:
        self.manual_generation_called = True
        raise AssertionError("Heavy manual generation must run in Celery")

    async def generate_post_from_news(self, news_id: uuid.UUID) -> FakePost:
        self.news_generation_called = True
        raise AssertionError("Heavy news generation must run in Celery")


class FakePublishingService:
    """Fake publishing service для проверки publish endpoint."""

    publish_called = False

    async def get_publishable_post(self, post_id: uuid.UUID) -> FakePost:
        if post_id != FakePostService.post_id:
            raise EntityNotFoundError("Post not found")
        return FakePostService()._post()

    async def publish_post(self, post_id: uuid.UUID) -> None:
        self.publish_called = True
        raise AssertionError("Heavy publication must run in Celery")


class FakeTaskQueue:
    """Зафиксировать API-постановку тяжёлых Celery-задач."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def enqueue_news_generation(self, news_id: uuid.UUID) -> str:
        self.calls.append(("generate_news", news_id))
        return "generate-news-task-id"

    def enqueue_post_publication(self, post_id: uuid.UUID) -> str:
        self.calls.append(("publish_post", post_id))
        return "publish-post-task-id"

    def enqueue_manual_generation(self, text: str) -> str:
        self.calls.append(("generate_text", text))
        return "generate-text-task-id"


class FakeErrorLogService:
    """Fake error log service для проверки router контракта."""

    async def list_logs(self, **_: object) -> list[FakeErrorLog]:
        return [
            FakeErrorLog(
                id=uuid.UUID("88888888-8888-8888-8888-888888888888"),
                scope=ErrorScope.API,
                message="Example error",
                details=None,
                source_id=None,
                news_id=None,
                post_id=None,
                created_at=datetime(2026, 7, 11, tzinfo=UTC),
            )
        ]


def test_news_posts_logs_contracts() -> None:
    """Read-only API endpoints возвращают ожидаемые JSON-контракты."""

    task_queue = FakeTaskQueue()
    app.dependency_overrides[get_news_service] = FakeNewsService
    app.dependency_overrides[get_post_service] = FakePostService
    app.dependency_overrides[get_post_generation_service] = FakePostGenerationService
    app.dependency_overrides[get_publishing_service] = FakePublishingService
    app.dependency_overrides[get_error_log_service] = FakeErrorLogService
    app.dependency_overrides[get_task_queue] = lambda: task_queue
    client = TestClient(app)

    try:
        FakePostService.published = False
        FakePostGenerationService.news_generation_called = False
        FakePublishingService.publish_called = False
        news_response = client.get("/api/news/")
        assert news_response.status_code == 200
        assert news_response.json()[0]["status"] == "ready_for_generation"

        queue_generation_response = client.post(f"/api/news/{FakeNewsService.news_id}/generate")
        assert queue_generation_response.status_code == 202
        assert queue_generation_response.json() == {
            "task_id": "generate-news-task-id",
            "status": "queued",
        }
        assert FakePostGenerationService.news_generation_called is False

        posts_response = client.get("/api/posts/")
        assert posts_response.status_code == 200
        assert posts_response.json()[0]["generated_text"] == "Generated post"

        queue_publish_response = client.post(f"/api/posts/{FakePostService.post_id}/publish")
        assert queue_publish_response.status_code == 202
        assert queue_publish_response.json() == {
            "task_id": "publish-post-task-id",
            "status": "queued",
        }
        assert FakePublishingService.publish_called is False
        assert task_queue.calls == [
            ("generate_news", FakeNewsService.news_id),
            ("publish_post", FakePostService.post_id),
        ]

        logs_response = client.get("/api/logs/")
        assert logs_response.status_code == 200
        assert logs_response.json()[0]["scope"] == "api"
    finally:
        FakePostService.published = False
        app.dependency_overrides.clear()


def test_manual_generation_queues_celery_task() -> None:
    """Manual generation возвращает task_id без синхронного AI-вызова."""

    task_queue = FakeTaskQueue()
    FakePostGenerationService.manual_generation_called = False
    app.dependency_overrides[get_post_generation_service] = FakePostGenerationService
    app.dependency_overrides[get_task_queue] = lambda: task_queue
    client = TestClient(app)

    try:
        response = client.post(
            "/api/generate/",
            json={
                "text": "Python получил важное обновление производительности.",
                "source": "manual",
            },
        )

        assert response.status_code == 202
        assert response.json() == {
            "task_id": "generate-text-task-id",
            "status": "queued",
        }
        assert FakePostGenerationService.manual_generation_called is False
        assert task_queue.calls == [
            (
                "generate_text",
                "Python получил важное обновление производительности.",
            )
        ]
    finally:
        app.dependency_overrides.clear()
