"""Сервис ручного парсинга источника и сохранения новостей."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from aibot.config import Settings, get_settings
from aibot.integrations.http_client import (
    HttpClientError,
    HttpPermanentError,
    HttpTemporaryError,
)
from aibot.models.enums import ErrorScope, NewsStatus, SourceType
from aibot.models.error_log import ErrorLog
from aibot.models.news_item import NewsItem
from aibot.parsers.base import NewsParser, ParsedNewsItem
from aibot.parsers.rss import RssAtomParser, RssFeedParseError
from aibot.parsers.telegram import TelegramChannelParser
from aibot.repositories.error_log_repository import ErrorLogRepository
from aibot.repositories.keyword_repository import KeywordRepository
from aibot.repositories.news_repository import NewsRepository
from aibot.repositories.source_repository import SourceRepository
from aibot.services.deduplication import DeduplicationService, build_content_hash
from aibot.services.exceptions import EntityNotFoundError, UnsupportedSourceTypeError
from aibot.services.filtering import KeywordFilterService


@dataclass(frozen=True)
class SourceParseResult:
    """Сводка результата ручного парсинга источника."""

    source_id: uuid.UUID
    parsed_count: int
    saved_count: int
    duplicate_count: int
    filtered_out_count: int
    ready_for_generation_count: int


class NewsIngestionService:
    """Сервис ingestion pipeline: parse -> dedup -> filter -> save."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        source_repository: SourceRepository | None = None,
        news_repository: NewsRepository | None = None,
        keyword_repository: KeywordRepository | None = None,
        error_log_repository: ErrorLogRepository | None = None,
        settings: Settings | None = None,
        site_parser: NewsParser | None = None,
        telegram_parser: NewsParser | None = None,
        deduplication_service: DeduplicationService | None = None,
        keyword_filter_service: KeywordFilterService | None = None,
    ) -> None:
        runtime_settings = settings or get_settings()
        self.session = session
        self.source_repository = source_repository or SourceRepository(session)
        self.news_repository = news_repository or NewsRepository(session)
        self.keyword_repository = keyword_repository or KeywordRepository(session)
        self.error_log_repository = error_log_repository or ErrorLogRepository(session)
        self.site_parser = site_parser or RssAtomParser(settings=runtime_settings)
        self.telegram_parser = telegram_parser or TelegramChannelParser()
        self.deduplication_service = deduplication_service or DeduplicationService()
        self.keyword_filter_service = keyword_filter_service or KeywordFilterService(
            allowed_languages=runtime_settings.allowed_news_languages
        )

    async def parse_source(self, source_id: uuid.UUID, *, limit: int = 10) -> SourceParseResult:
        """Ручно распарсить источник и сохранить новые новости."""

        source = await self.source_repository.get(source_id)
        if source is None:
            raise EntityNotFoundError("Source not found")
        parser = self._select_parser(source.type)

        try:
            parsed_items = await parser.parse(
                source_name=source.name,
                url=source.url,
                limit=limit,
            )
        except Exception as exc:
            await self._log_parser_error(source.id, exc)
            raise

        enabled_keywords = await self.keyword_repository.list_enabled()

        duplicate_count = 0
        filtered_out_count = 0
        ready_for_generation_count = 0
        saved_count = 0

        for parsed_item in parsed_items:
            content_hash = build_content_hash(parsed_item)
            is_duplicate = await self._is_duplicate(parsed_item, content_hash)
            if is_duplicate:
                duplicate_count += 1
                continue

            filter_decision = self.keyword_filter_service.evaluate(parsed_item, enabled_keywords)
            status = (
                NewsStatus.READY_FOR_GENERATION
                if filter_decision.accepted
                else NewsStatus.FILTERED_OUT
            )
            if status == NewsStatus.READY_FOR_GENERATION:
                ready_for_generation_count += 1
            else:
                filtered_out_count += 1

            await self.news_repository.add(
                NewsItem(
                    title=parsed_item.title,
                    url=parsed_item.url,
                    summary=parsed_item.summary,
                    source_id=source.id,
                    published_at=parsed_item.published_at,
                    raw_text=parsed_item.raw_text,
                    content_hash=content_hash,
                    status=status,
                )
            )
            saved_count += 1

        await self.session.commit()
        return SourceParseResult(
            source_id=source.id,
            parsed_count=len(parsed_items),
            saved_count=saved_count,
            duplicate_count=duplicate_count,
            filtered_out_count=filtered_out_count,
            ready_for_generation_count=ready_for_generation_count,
        )

    def _select_parser(self, source_type: SourceType) -> NewsParser:
        """Выбрать parser по типу источника."""

        if source_type == SourceType.SITE:
            return self.site_parser
        if source_type == SourceType.TELEGRAM:
            return self.telegram_parser
        raise UnsupportedSourceTypeError(f"Unsupported source type: {source_type}")

    async def _is_duplicate(self, parsed_item: ParsedNewsItem, content_hash: str) -> bool:
        """Проверить дубль через repository и локальный dedup-сервис."""

        existing_url = (
            await self.news_repository.get_by_url(parsed_item.url) if parsed_item.url else None
        )
        existing_hash = await self.news_repository.get_by_content_hash(content_hash)
        existing_urls = {existing_url.url} if existing_url and existing_url.url else set()
        existing_hashes = {existing_hash.content_hash} if existing_hash else set()
        return self.deduplication_service.is_duplicate(
            parsed_item,
            existing_urls=existing_urls,
            existing_hashes=existing_hashes,
        )

    async def _log_parser_error(self, source_id: uuid.UUID, exc: Exception) -> None:
        """Безопасно сохранить ошибку parser-а, не меняя её тип."""

        message, details = self._parser_error_payload(exc)
        await self.error_log_repository.add(
            ErrorLog(
                scope=ErrorScope.PARSER,
                message=message,
                details=details,
                source_id=source_id,
            )
        )
        await self.session.commit()

    @staticmethod
    def _parser_error_payload(exc: Exception) -> tuple[str, str]:
        """Классифицировать parser-ошибку и скрыть детали неизвестных исключений."""

        if isinstance(exc, HttpTemporaryError):
            return "Temporary source parsing failure", str(exc)
        if isinstance(exc, HttpPermanentError):
            return "Permanent source parsing failure", str(exc)
        if isinstance(exc, RssFeedParseError):
            return "Invalid RSS/Atom feed", str(exc)
        if isinstance(exc, HttpClientError):
            return "Source HTTP parsing failure", str(exc)
        return "Unexpected source parsing failure", exc.__class__.__name__
