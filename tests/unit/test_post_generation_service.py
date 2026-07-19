"""Тесты сохранения AI-сгенерированного Post из NewsItem."""

import uuid
from datetime import UTC, datetime

import pytest

from aibot.config import Settings
from aibot.integrations.ai_client import AIClientTimeoutError
from aibot.models.enums import ErrorScope, NewsStatus, PostStatus
from aibot.models.error_log import ErrorLog
from aibot.models.news_item import NewsItem
from aibot.models.post import Post
from aibot.services.exceptions import ConcurrentGenerationError, InvalidNewsStateError
from aibot.services.post_generation import PostGenerationService


class FakeAIClient:
    """Fake AI client для предсказуемой генерации."""

    async def generate_telegram_post(self, input_text: str) -> str:
        """Вернуть fake-текст поста."""

        return f"Generated: {input_text}"


class FailingAIClient:
    """AI client с безопасно классифицируемой временной ошибкой."""

    async def generate_telegram_post(self, _: str) -> str:
        raise AIClientTimeoutError("api_key=super-secret")


class CountingAIClient:
    """AI client, который не должен вызываться без row lock."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate_telegram_post(self, _: str) -> str:
        self.calls += 1
        return "must not be generated"


class FakeNewsRepository:
    """Fake news repository для PostGenerationService."""

    def __init__(self, news_item: NewsItem | None) -> None:
        self.news_item = news_item

    async def get(self, _: uuid.UUID) -> NewsItem | None:
        return self.news_item

    async def get_for_generation(self, _: uuid.UUID) -> NewsItem | None:
        return self.news_item


class LockedNewsRepository(FakeNewsRepository):
    """Имитировать строку, уже заблокированную другим worker-ом."""

    async def get_for_generation(self, _: uuid.UUID) -> None:
        return None


class FakePostRepository:
    """Fake post repository для PostGenerationService."""

    def __init__(self) -> None:
        self.saved: list[Post] = []

    async def add(self, post: Post) -> Post:
        post.id = uuid.UUID("77777777-7777-7777-7777-777777777777")
        post.created_at = datetime(2026, 7, 11, tzinfo=UTC)
        post.updated_at = datetime(2026, 7, 11, tzinfo=UTC)
        self.saved.append(post)
        return post


class FakeErrorLogRepository:
    """Fake ErrorLog repository."""

    def __init__(self) -> None:
        self.saved: list[ErrorLog] = []

    async def add(self, error_log: ErrorLog) -> ErrorLog:
        self.saved.append(error_log)
        return error_log


class FakeSession:
    """Fake async session with transaction counters."""

    def __init__(self) -> None:
        self.commits = 0
        self.refreshed = 0

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _: object) -> None:
        self.refreshed += 1


def make_news_item(*, status: NewsStatus = NewsStatus.READY_FOR_GENERATION) -> NewsItem:
    """Создать NewsItem для тестов генерации."""

    return NewsItem(
        id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
        title="Python release",
        url="https://example.com/python",
        summary="Python got faster.",
        source_id=uuid.UUID("66666666-6666-6666-6666-666666666666"),
        published_at=datetime(2026, 7, 11, tzinfo=UTC),
        raw_text="Runtime performance update",
        content_hash="hash-python",
        status=status,
        created_at=datetime(2026, 7, 11, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_generate_post_from_news_saves_generated_post() -> None:
    """PostGenerationService создает Post и переводит NewsItem в generated."""

    news_item = make_news_item()
    post_repository = FakePostRepository()
    session = FakeSession()
    service = PostGenerationService(
        session,  # type: ignore[arg-type]
        settings=Settings(),
        ai_client=FakeAIClient(),  # type: ignore[arg-type]
        news_repository=FakeNewsRepository(news_item),  # type: ignore[arg-type]
        post_repository=post_repository,  # type: ignore[arg-type]
    )

    post = await service.generate_post_from_news(news_item.id)

    assert post.status == PostStatus.GENERATED
    assert post.news_id == news_item.id
    assert "Python release" in post.generated_text
    assert news_item.status == NewsStatus.GENERATED
    assert post_repository.saved == [post]
    assert session.commits == 1
    assert session.refreshed == 1


@pytest.mark.asyncio
async def test_generate_post_from_news_rejects_filtered_news() -> None:
    """PostGenerationService не генерирует пост для filtered_out новости."""

    news_item = make_news_item(status=NewsStatus.FILTERED_OUT)
    service = PostGenerationService(
        FakeSession(),  # type: ignore[arg-type]
        settings=Settings(),
        ai_client=FakeAIClient(),  # type: ignore[arg-type]
        news_repository=FakeNewsRepository(news_item),  # type: ignore[arg-type]
        post_repository=FakePostRepository(),  # type: ignore[arg-type]
    )

    with pytest.raises(InvalidNewsStateError):
        await service.generate_post_from_news(news_item.id)


@pytest.mark.asyncio
async def test_generate_post_logs_ai_error_without_secret_and_preserves_type() -> None:
    """AI error сохраняется с news_id, но без provider message и ключей."""

    news_item = make_news_item()
    session = FakeSession()
    error_log_repository = FakeErrorLogRepository()
    service = PostGenerationService(
        session,  # type: ignore[arg-type]
        settings=Settings(),
        ai_client=FailingAIClient(),  # type: ignore[arg-type]
        news_repository=FakeNewsRepository(news_item),  # type: ignore[arg-type]
        post_repository=FakePostRepository(),  # type: ignore[arg-type]
        error_log_repository=error_log_repository,  # type: ignore[arg-type]
    )

    with pytest.raises(AIClientTimeoutError, match="super-secret"):
        await service.generate_post_from_news(news_item.id)

    assert news_item.status == NewsStatus.READY_FOR_GENERATION
    assert session.commits == 1
    assert len(error_log_repository.saved) == 1
    error_log = error_log_repository.saved[0]
    assert error_log.scope == ErrorScope.AI
    assert error_log.news_id == news_item.id
    assert error_log.message == "AI generation failed"
    assert error_log.details == "AIClientTimeoutError"
    assert "secret" not in error_log.details


@pytest.mark.asyncio
async def test_generate_post_rejects_concurrent_worker_before_ai_call() -> None:
    """Worker без row lock не вызывает AI и не создаёт второй Post."""

    news_item = make_news_item()
    ai_client = CountingAIClient()
    post_repository = FakePostRepository()
    service = PostGenerationService(
        FakeSession(),  # type: ignore[arg-type]
        settings=Settings(),
        ai_client=ai_client,  # type: ignore[arg-type]
        news_repository=LockedNewsRepository(news_item),  # type: ignore[arg-type]
        post_repository=post_repository,  # type: ignore[arg-type]
    )

    with pytest.raises(ConcurrentGenerationError):
        await service.generate_post_from_news(news_item.id)

    assert ai_client.calls == 0
    assert post_repository.saved == []
