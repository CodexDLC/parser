"""Оркестрация полного dry-run pipeline: parse -> generate -> publish."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from aibot.models.enums import NewsStatus, PostStatus
from aibot.repositories.news_repository import NewsRepository
from aibot.repositories.post_repository import PostRepository
from aibot.repositories.source_repository import SourceRepository
from aibot.services.news_ingestion import NewsIngestionService, SourceParseResult
from aibot.services.post_generation import PostGenerationService
from aibot.services.publishing import PublishingService, PublishResult


@dataclass(frozen=True)
class PipelineResult:
    """Сводка одного полного запуска pipeline."""

    parsed_sources_count: int
    parsed_items_count: int
    saved_items_count: int
    duplicate_items_count: int
    ready_items_count: int
    generated_posts_count: int
    published_posts_count: int


class PipelineService:
    """Сервис оркестрации полного backend pipeline."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        source_repository: SourceRepository | None = None,
        news_repository: NewsRepository | None = None,
        post_repository: PostRepository | None = None,
        news_ingestion_service: NewsIngestionService | None = None,
        post_generation_service: PostGenerationService | None = None,
        publishing_service: PublishingService | None = None,
    ) -> None:
        self.session = session
        self.source_repository = source_repository or SourceRepository(session)
        self.news_repository = news_repository or NewsRepository(session)
        self.post_repository = post_repository or PostRepository(session)
        self.news_ingestion_service = news_ingestion_service or NewsIngestionService(session)
        self.post_generation_service = post_generation_service or PostGenerationService(session)
        self.publishing_service = publishing_service or PublishingService(session)

    async def run_once(
        self,
        *,
        parse_limit: int = 10,
        generation_limit: int = 10,
        publishing_limit: int = 10,
    ) -> PipelineResult:
        """Выполнить один проход pipeline для включенных источников."""

        parse_results = await self._parse_enabled_sources(limit=parse_limit)
        generated_posts_count = await self._generate_ready_news(limit=generation_limit)
        published_posts_count = await self._publish_generated_posts(limit=publishing_limit)

        return PipelineResult(
            parsed_sources_count=len(parse_results),
            parsed_items_count=sum(result.parsed_count for result in parse_results),
            saved_items_count=sum(result.saved_count for result in parse_results),
            duplicate_items_count=sum(result.duplicate_count for result in parse_results),
            ready_items_count=sum(result.ready_for_generation_count for result in parse_results),
            generated_posts_count=generated_posts_count,
            published_posts_count=published_posts_count,
        )

    async def _parse_enabled_sources(self, *, limit: int) -> list[SourceParseResult]:
        """Распарсить все включенные источники."""

        sources = await self.source_repository.list_filtered(enabled=True)
        results: list[SourceParseResult] = []
        for source in sources:
            results.append(await self.news_ingestion_service.parse_source(source.id, limit=limit))
        return results

    async def _generate_ready_news(self, *, limit: int) -> int:
        """Сгенерировать посты для готовых новостей."""

        ready_news = await self.news_repository.list_by_status(
            NewsStatus.READY_FOR_GENERATION,
            limit=limit,
        )
        generated_count = 0
        for news_item in ready_news:
            await self.post_generation_service.generate_post_from_news(news_item.id)
            generated_count += 1
        return generated_count

    async def _publish_generated_posts(self, *, limit: int) -> int:
        """Опубликовать сгенерированные посты."""

        generated_posts = await self.post_repository.list_by_status(
            PostStatus.GENERATED,
            limit=limit,
        )
        results: list[PublishResult] = []
        for post in generated_posts:
            results.append(await self.publishing_service.publish_post(post.id))
        return len(results)
