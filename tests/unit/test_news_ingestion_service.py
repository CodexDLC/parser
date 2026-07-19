"""Тесты ручного ingestion pipeline без PostgreSQL."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from aibot.models.enums import SourceType
from aibot.models.news_item import NewsItem
from aibot.parsers.base import ParsedNewsItem
from aibot.services.news_ingestion import NewsIngestionService


@dataclass
class FakeSource:
    """Минимальный источник для ingestion service."""

    id: uuid.UUID
    type: SourceType
    name: str
    url: str


@dataclass
class FakeKeyword:
    """Минимальное ключевое слово для ingestion service."""

    word: str
    enabled: bool = True


class FakeSourceRepository:
    """Fake source repository."""

    source = FakeSource(
        id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
        type=SourceType.SITE,
        name="Demo",
        url="demo://news",
    )

    async def get(self, _: uuid.UUID) -> FakeSource:
        return self.source


class FakeTelegramSourceRepository:
    """Fake source repository с Telegram-источником."""

    source = FakeSource(
        id=uuid.UUID("88888888-8888-8888-8888-888888888888"),
        type=SourceType.TELEGRAM,
        name="Demo Telegram",
        url="@demo_channel",
    )

    async def get(self, _: uuid.UUID) -> FakeSource:
        return self.source


class FakeKeywordRepository:
    """Fake keyword repository."""

    async def list_enabled(self) -> list[FakeKeyword]:
        return [FakeKeyword("python")]


class FakeNewsRepository:
    """Fake news repository."""

    def __init__(self) -> None:
        self.saved: list[NewsItem] = []

    async def get_by_url(self, _: str | None) -> None:
        return None

    async def get_by_content_hash(self, _: str) -> None:
        return None

    async def add(self, news_item: NewsItem) -> NewsItem:
        self.saved.append(news_item)
        return news_item


class FakeSession:
    """Fake async session with commit counter."""

    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeParser:
    """Fake parser with one matching and one filtered news item."""

    async def parse(self, **_: object) -> list[ParsedNewsItem]:
        return [
            ParsedNewsItem(
                title="Python update",
                url="demo://news/python",
                summary="Python got faster.",
                source="Demo",
                published_at=datetime(2026, 7, 11, tzinfo=UTC),
            ),
            ParsedNewsItem(
                title="Cooking update",
                url="demo://news/cooking",
                summary="New recipe.",
                source="Demo",
                published_at=datetime(2026, 7, 11, tzinfo=UTC),
            ),
        ]


class FailingParser:
    """Parser, который не должен вызываться в тесте выбора источника."""

    async def parse(self, **_: object) -> list[ParsedNewsItem]:
        raise AssertionError("Wrong parser selected")


@pytest.mark.asyncio
async def test_news_ingestion_saves_ready_and_filtered_news() -> None:
    """NewsIngestionService сохраняет новости со статусами после фильтрации."""

    session = FakeSession()
    news_repository = FakeNewsRepository()
    service = NewsIngestionService(
        session,  # type: ignore[arg-type]
        source_repository=FakeSourceRepository(),  # type: ignore[arg-type]
        news_repository=news_repository,  # type: ignore[arg-type]
        keyword_repository=FakeKeywordRepository(),  # type: ignore[arg-type]
        site_parser=FakeParser(),  # type: ignore[arg-type]
    )

    result = await service.parse_source(FakeSourceRepository.source.id)

    assert result.parsed_count == 2
    assert result.saved_count == 2
    assert result.ready_for_generation_count == 1
    assert result.filtered_out_count == 1
    assert result.duplicate_count == 0
    assert session.commits == 1
    assert {news.status.value for news in news_repository.saved} == {
        "ready_for_generation",
        "filtered_out",
    }


@pytest.mark.asyncio
async def test_news_ingestion_supports_telegram_sources() -> None:
    """NewsIngestionService выбирает Telegram parser для tg-источников."""

    session = FakeSession()
    news_repository = FakeNewsRepository()
    service = NewsIngestionService(
        session,  # type: ignore[arg-type]
        source_repository=FakeTelegramSourceRepository(),  # type: ignore[arg-type]
        news_repository=news_repository,  # type: ignore[arg-type]
        keyword_repository=FakeKeywordRepository(),  # type: ignore[arg-type]
        site_parser=FailingParser(),
        telegram_parser=FakeParser(),
    )

    result = await service.parse_source(FakeTelegramSourceRepository.source.id)

    assert result.parsed_count == 2
    assert result.saved_count == 2
    assert result.ready_for_generation_count == 1
    assert result.filtered_out_count == 1
    assert session.commits == 1
