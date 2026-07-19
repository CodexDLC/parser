"""Тесты ручного ingestion pipeline без PostgreSQL."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from aibot.integrations.http_client import HttpTemporaryError
from aibot.models.enums import ErrorScope, SourceType
from aibot.models.error_log import ErrorLog
from aibot.models.news_item import NewsItem
from aibot.parsers.base import ParsedNewsItem
from aibot.parsers.rss import RssAtomParser, RssFeedParseError
from aibot.services.filtering import KeywordFilterService
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


class FakeErrorLogRepository:
    """Fake error log repository."""

    def __init__(self) -> None:
        self.saved: list[ErrorLog] = []

    async def add(self, error_log: ErrorLog) -> ErrorLog:
        self.saved.append(error_log)
        return error_log


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


class TemporaryFailingParser:
    """Parser с типизированной временной HTTP-ошибкой."""

    async def parse(self, **_: object) -> list[ParsedNewsItem]:
        raise HttpTemporaryError(
            "HTTP timeout while fetching https://news.example/feed.xml"
        )


class InvalidFeedParser:
    """Parser с ошибкой некорректной RSS/Atom-ленты."""

    async def parse(self, **_: object) -> list[ParsedNewsItem]:
        raise RssFeedParseError(
            "Source is not a valid RSS/Atom feed: https://news.example/feed.xml"
        )


class UnexpectedSecretFailingParser:
    """Parser с неизвестной ошибкой, текст которой нельзя сохранять."""

    async def parse(self, **_: object) -> list[ParsedNewsItem]:
        raise RuntimeError("token=super-secret")


class FixedLanguageDetector:
    """Вернуть заданный язык без зависимости от langdetect."""

    def __init__(self, language: str | None) -> None:
        self.language = language

    def detect(self, _: str) -> str | None:
        return self.language


def test_news_ingestion_uses_real_rss_parser_by_default() -> None:
    """Production site path больше не подставляет DemoSiteParser."""

    service = NewsIngestionService(FakeSession())  # type: ignore[arg-type]

    assert isinstance(service.site_parser, RssAtomParser)


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
        site_parser=FakeParser(),
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


@pytest.mark.asyncio
async def test_news_ingestion_filters_keyword_match_in_disallowed_language() -> None:
    """Ingestion сохраняет совпавшую новость как filtered_out из-за языка."""

    session = FakeSession()
    news_repository = FakeNewsRepository()
    service = NewsIngestionService(
        session,  # type: ignore[arg-type]
        source_repository=FakeSourceRepository(),  # type: ignore[arg-type]
        news_repository=news_repository,  # type: ignore[arg-type]
        keyword_repository=FakeKeywordRepository(),  # type: ignore[arg-type]
        site_parser=FakeParser(),
        keyword_filter_service=KeywordFilterService(
            allowed_languages={"ru", "en"},
            language_detector=FixedLanguageDetector("de"),
        ),
    )

    result = await service.parse_source(FakeSourceRepository.source.id)

    assert result.ready_for_generation_count == 0
    assert result.filtered_out_count == 2
    assert {news.status.value for news in news_repository.saved} == {"filtered_out"}


@pytest.mark.asyncio
async def test_news_ingestion_logs_temporary_parser_error_and_preserves_type() -> None:
    """Временная parser-ошибка пишется в ErrorLog и пробрасывается без обёртки."""

    session = FakeSession()
    error_log_repository = FakeErrorLogRepository()
    service = NewsIngestionService(
        session,  # type: ignore[arg-type]
        source_repository=FakeSourceRepository(),  # type: ignore[arg-type]
        news_repository=FakeNewsRepository(),  # type: ignore[arg-type]
        keyword_repository=FakeKeywordRepository(),  # type: ignore[arg-type]
        error_log_repository=error_log_repository,  # type: ignore[arg-type]
        site_parser=TemporaryFailingParser(),
    )

    with pytest.raises(HttpTemporaryError):
        await service.parse_source(FakeSourceRepository.source.id)

    assert session.commits == 1
    assert len(error_log_repository.saved) == 1
    error_log = error_log_repository.saved[0]
    assert error_log.scope == ErrorScope.PARSER
    assert error_log.source_id == FakeSourceRepository.source.id
    assert error_log.message == "Temporary source parsing failure"
    assert error_log.details == "HTTP timeout while fetching https://news.example/feed.xml"


@pytest.mark.asyncio
async def test_news_ingestion_logs_invalid_feed_error() -> None:
    """Некорректная лента получает отдельное безопасное описание ошибки."""

    error_log_repository = FakeErrorLogRepository()
    service = NewsIngestionService(
        FakeSession(),  # type: ignore[arg-type]
        source_repository=FakeSourceRepository(),  # type: ignore[arg-type]
        news_repository=FakeNewsRepository(),  # type: ignore[arg-type]
        keyword_repository=FakeKeywordRepository(),  # type: ignore[arg-type]
        error_log_repository=error_log_repository,  # type: ignore[arg-type]
        site_parser=InvalidFeedParser(),
    )

    with pytest.raises(RssFeedParseError):
        await service.parse_source(FakeSourceRepository.source.id)

    error_log = error_log_repository.saved[0]
    assert error_log.message == "Invalid RSS/Atom feed"
    assert error_log.details == (
        "Source is not a valid RSS/Atom feed: https://news.example/feed.xml"
    )


@pytest.mark.asyncio
async def test_news_ingestion_does_not_log_unknown_exception_message() -> None:
    """Неизвестная ошибка не раскрывает токен через ErrorLog.details."""

    error_log_repository = FakeErrorLogRepository()
    service = NewsIngestionService(
        FakeSession(),  # type: ignore[arg-type]
        source_repository=FakeSourceRepository(),  # type: ignore[arg-type]
        news_repository=FakeNewsRepository(),  # type: ignore[arg-type]
        keyword_repository=FakeKeywordRepository(),  # type: ignore[arg-type]
        error_log_repository=error_log_repository,  # type: ignore[arg-type]
        site_parser=UnexpectedSecretFailingParser(),
    )

    with pytest.raises(RuntimeError, match="super-secret"):
        await service.parse_source(FakeSourceRepository.source.id)

    error_log = error_log_repository.saved[0]
    assert error_log.message == "Unexpected source parsing failure"
    assert error_log.details == "RuntimeError"
    assert "secret" not in error_log.details
