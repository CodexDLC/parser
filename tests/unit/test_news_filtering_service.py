"""Тесты фильтрации сохраненных NewsItem без PostgreSQL."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from aibot.models.enums import NewsStatus
from aibot.models.news_item import NewsItem
from aibot.services.exceptions import InvalidNewsStateError
from aibot.services.news_filtering import SavedNewsFilteringService


@dataclass
class FakeKeyword:
    """Минимальное ключевое слово для фильтрации."""

    word: str
    enabled: bool = True


class FakeNewsRepository:
    """Fake news repository для SavedNewsFilteringService."""

    def __init__(self, news_item: NewsItem | None) -> None:
        self.news_item = news_item

    async def get(self, _: uuid.UUID) -> NewsItem | None:
        return self.news_item


class FakeKeywordRepository:
    """Fake keyword repository для SavedNewsFilteringService."""

    def __init__(self, keywords: list[FakeKeyword]) -> None:
        self.keywords = keywords

    async def list_enabled(self) -> list[FakeKeyword]:
        return self.keywords


class FakeSession:
    """Fake async session with transaction counters."""

    def __init__(self) -> None:
        self.commits = 0
        self.refreshed = 0

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _: object) -> None:
        self.refreshed += 1


def make_news_item(
    *,
    title: str = "Python release",
    status: NewsStatus = NewsStatus.NEW,
) -> NewsItem:
    """Создать NewsItem для тестов фильтрации."""

    return NewsItem(
        id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
        title=title,
        url="https://example.com/news",
        summary="Python got faster.",
        source_id=uuid.UUID("66666666-6666-6666-6666-666666666666"),
        published_at=datetime(2026, 7, 11, tzinfo=UTC),
        raw_text=None,
        content_hash="hash-news",
        status=status,
        created_at=datetime(2026, 7, 11, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_saved_news_filtering_marks_matching_news_ready() -> None:
    """SavedNewsFilteringService переводит совпадающую новость в ready_for_generation."""

    news_item = make_news_item()
    session = FakeSession()
    service = SavedNewsFilteringService(
        session,  # type: ignore[arg-type]
        news_repository=FakeNewsRepository(news_item),  # type: ignore[arg-type]
        keyword_repository=FakeKeywordRepository([FakeKeyword("python")]),  # type: ignore[arg-type]
    )

    result = await service.filter_news(news_item.id)

    assert result.status == NewsStatus.READY_FOR_GENERATION
    assert result.reason == "matched_keywords"
    assert result.matched_keywords == ["python"]
    assert result.detected_language == "en"
    assert news_item.status == NewsStatus.READY_FOR_GENERATION
    assert session.commits == 1
    assert session.refreshed == 1


@pytest.mark.asyncio
async def test_saved_news_filtering_marks_unmatched_news_filtered_out() -> None:
    """SavedNewsFilteringService переводит неподходящую новость в filtered_out."""

    news_item = make_news_item(title="Cooking update")
    session = FakeSession()
    service = SavedNewsFilteringService(
        session,  # type: ignore[arg-type]
        news_repository=FakeNewsRepository(news_item),  # type: ignore[arg-type]
        keyword_repository=FakeKeywordRepository([FakeKeyword("telegram")]),  # type: ignore[arg-type]
    )

    result = await service.filter_news(news_item.id)

    assert result.status == NewsStatus.FILTERED_OUT
    assert result.reason == "no_keyword_match"
    assert result.matched_keywords == []
    assert news_item.status == NewsStatus.FILTERED_OUT


@pytest.mark.asyncio
async def test_saved_news_filtering_rejects_generated_news() -> None:
    """SavedNewsFilteringService не фильтрует уже generated новость."""

    news_item = make_news_item(status=NewsStatus.GENERATED)
    service = SavedNewsFilteringService(
        FakeSession(),  # type: ignore[arg-type]
        news_repository=FakeNewsRepository(news_item),  # type: ignore[arg-type]
        keyword_repository=FakeKeywordRepository([FakeKeyword("python")]),  # type: ignore[arg-type]
    )

    with pytest.raises(InvalidNewsStateError):
        await service.filter_news(news_item.id)
