"""DB-backed smoke scenario for the first working prototype."""

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from typing import Any

from aibot.db.base import Base
from aibot.db.session import AsyncSessionFactory, engine
from aibot.models.enums import NewsStatus, PostStatus, SourceType
from aibot.repositories.news_repository import NewsRepository
from aibot.repositories.post_repository import PostRepository
from aibot.services.exceptions import EntityAlreadyExistsError
from aibot.services.keyword_service import KeywordService
from aibot.services.news_ingestion import NewsIngestionService
from aibot.services.post_generation import PostGenerationService
from aibot.services.publishing import PublishingService
from aibot.services.source_service import SourceService


@dataclass(frozen=True)
class SmokeResult:
    """Summary of a DB-backed smoke scenario."""

    source_id: str
    keyword: str
    parsed_count: int
    saved_count: int
    ready_for_generation_count: int
    filtered_out_count: int
    generated_post_id: str
    generated_post_status: str
    published_post_status: str
    telegram_message_id: str
    fake_mode: bool
    telegram_dry_run: bool


async def reset_database() -> None:
    """Drop and recreate all project tables."""

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


async def run_smoke_scenario(*, reset: bool = False) -> SmokeResult:
    """Run source -> parse -> generate -> publish against configured database."""

    if reset:
        await reset_database()

    async with AsyncSessionFactory() as session:
        source = await _ensure_source(session)
        await _ensure_keyword(session)

        parse_result = await NewsIngestionService(session).parse_source(source.id, limit=2)
        ready_news = await NewsRepository(session).list_by_status(
            NewsStatus.READY_FOR_GENERATION,
            limit=1,
        )
        if not ready_news:
            raise RuntimeError("Smoke scenario did not produce ready_for_generation news")

        generated_post = await PostGenerationService(session).generate_post_from_news(
            ready_news[0].id
        )
        publish_result = await PublishingService(session).publish_post(generated_post.id)
        published_post = await PostRepository(session).get(generated_post.id)
        if published_post is None:
            raise RuntimeError("Published post disappeared during smoke scenario")

        return SmokeResult(
            source_id=str(source.id),
            keyword="python",
            parsed_count=parse_result.parsed_count,
            saved_count=parse_result.saved_count,
            ready_for_generation_count=parse_result.ready_for_generation_count,
            filtered_out_count=parse_result.filtered_out_count,
            generated_post_id=str(generated_post.id),
            generated_post_status=PostStatus.GENERATED.value,
            published_post_status=published_post.status.value,
            telegram_message_id=publish_result.telegram_message_id,
            fake_mode=PostGenerationService().settings.ai_fake_mode,
            telegram_dry_run=publish_result.dry_run,
        )


async def _ensure_source(session: Any) -> Any:
    """Create or reuse the demo source."""

    service = SourceService(session)
    try:
        return await service.create_source(
            source_type=SourceType.SITE,
            name="Demo News",
            url="https://example.test/news",
            enabled=True,
        )
    except EntityAlreadyExistsError:
        existing = await service.repository.get_by_type_and_url(
            SourceType.SITE,
            "https://example.test/news",
        )
        if existing is None:
            raise
        return existing


async def _ensure_keyword(session: Any) -> None:
    """Create or reuse the demo keyword."""

    service = KeywordService(session)
    try:
        await service.create_keyword(word="python", enabled=True)
    except EntityAlreadyExistsError:
        existing = await service.repository.get_by_word("python")
        if existing is None:
            raise
        if not existing.enabled:
            existing.enabled = True
            await session.commit()


def result_to_dict(result: SmokeResult) -> dict[str, Any]:
    """Convert smoke result to JSON-friendly dict."""

    return asdict(result)


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI parser for smoke scenario."""

    parser = argparse.ArgumentParser(description="Run Project M4 DB-backed smoke scenario.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate database tables before running the scenario.",
    )
    return parser


def main() -> None:
    """Run smoke scenario from command line."""

    args = build_arg_parser().parse_args()
    result = asyncio.run(run_smoke_scenario(reset=args.reset))
    print(json.dumps(result_to_dict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
