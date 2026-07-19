"""Тесты полного pipeline service без PostgreSQL, Redis и внешних ключей."""

import uuid
from dataclasses import dataclass

import pytest

from aibot.integrations.http_client import HttpTemporaryError
from aibot.models.enums import NewsStatus, PostStatus
from aibot.services.news_ingestion import SourceParseResult
from aibot.services.pipeline import PipelineService


@dataclass(frozen=True)
class FakeSource:
    """Минимальный source для pipeline теста."""

    id: uuid.UUID


@dataclass(frozen=True)
class FakeNews:
    """Минимальная news entity для pipeline теста."""

    id: uuid.UUID
    status: NewsStatus = NewsStatus.READY_FOR_GENERATION


@dataclass(frozen=True)
class FakePost:
    """Минимальный post entity для pipeline теста."""

    id: uuid.UUID
    status: PostStatus = PostStatus.GENERATED


class FakeSourceRepository:
    """Fake source repository."""

    failed_source_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    source_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

    async def list_filtered(self, **_: object) -> list[FakeSource]:
        return [FakeSource(self.failed_source_id), FakeSource(self.source_id)]


class FakeNewsRepository:
    """Fake news repository."""

    news_id = uuid.UUID("22222222-2222-2222-2222-222222222222")

    async def list_by_status(self, status: NewsStatus, *, limit: int = 100) -> list[FakeNews]:
        assert status == NewsStatus.READY_FOR_GENERATION
        assert limit == 3
        return [FakeNews(self.news_id)]


class FakePostRepository:
    """Fake post repository."""

    post_id = uuid.UUID("33333333-3333-3333-3333-333333333333")

    async def list_by_status(self, status: PostStatus, *, limit: int = 100) -> list[FakePost]:
        assert status == PostStatus.GENERATED
        assert limit == 4
        return [FakePost(self.post_id)]


class FakeNewsIngestionService:
    """Fake ingestion service."""

    def __init__(self) -> None:
        self.parsed_source_ids: list[uuid.UUID] = []

    async def parse_source(self, source_id: uuid.UUID, *, limit: int = 10) -> SourceParseResult:
        self.parsed_source_ids.append(source_id)
        assert limit == 2
        if source_id == FakeSourceRepository.failed_source_id:
            raise HttpTemporaryError("first source failed")
        return SourceParseResult(
            source_id=source_id,
            parsed_count=2,
            saved_count=1,
            duplicate_count=1,
            filtered_out_count=0,
            ready_for_generation_count=1,
        )


class FakePostGenerationService:
    """Fake post generation service."""

    def __init__(self) -> None:
        self.generated_news_ids: list[uuid.UUID] = []

    async def generate_post_from_news(self, news_id: uuid.UUID) -> None:
        self.generated_news_ids.append(news_id)


class FakePublishingService:
    """Fake publishing service."""

    def __init__(self) -> None:
        self.published_post_ids: list[uuid.UUID] = []

    async def publish_post(self, post_id: uuid.UUID) -> None:
        self.published_post_ids.append(post_id)


@pytest.mark.asyncio
async def test_pipeline_service_runs_parse_generate_publish_steps() -> None:
    """Pipeline продолжает generate/publish после сбоя одного source."""

    ingestion_service = FakeNewsIngestionService()
    generation_service = FakePostGenerationService()
    publishing_service = FakePublishingService()
    service = PipelineService(
        session=None,  # type: ignore[arg-type]
        source_repository=FakeSourceRepository(),  # type: ignore[arg-type]
        news_repository=FakeNewsRepository(),  # type: ignore[arg-type]
        post_repository=FakePostRepository(),  # type: ignore[arg-type]
        news_ingestion_service=ingestion_service,  # type: ignore[arg-type]
        post_generation_service=generation_service,  # type: ignore[arg-type]
        publishing_service=publishing_service,  # type: ignore[arg-type]
    )

    result = await service.run_once(parse_limit=2, generation_limit=3, publishing_limit=4)

    assert result.parsed_sources_count == 1
    assert result.failed_sources_count == 1
    assert result.parsed_items_count == 2
    assert result.saved_items_count == 1
    assert result.duplicate_items_count == 1
    assert result.ready_items_count == 1
    assert result.generated_posts_count == 1
    assert result.published_posts_count == 1
    assert ingestion_service.parsed_source_ids == [
        FakeSourceRepository.failed_source_id,
        FakeSourceRepository.source_id,
    ]
    assert generation_service.generated_news_ids == [FakeNewsRepository.news_id]
    assert publishing_service.published_post_ids == [FakePostRepository.post_id]
