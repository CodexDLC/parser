"""Celery-задача полного pipeline запуска."""

import asyncio

from aibot.db.session import AsyncSessionFactory
from aibot.services.pipeline import PipelineService
from aibot.tasks.base import LoggedTask
from aibot.tasks.celery_app import celery_app


@celery_app.task(base=LoggedTask, name="aibot.tasks.pipeline.run_pipeline")
def run_pipeline(
    parse_limit: int = 10,
    generation_limit: int = 10,
    publishing_limit: int = 10,
) -> dict[str, int]:
    """Запустить один полный проход parse -> generate -> publish."""

    return asyncio.run(
        _run_pipeline(
            parse_limit=parse_limit,
            generation_limit=generation_limit,
            publishing_limit=publishing_limit,
        )
    )


async def _run_pipeline(
    *,
    parse_limit: int,
    generation_limit: int,
    publishing_limit: int,
) -> dict[str, int]:
    """Async-реализация полного pipeline запуска."""

    async with AsyncSessionFactory() as session:
        result = await PipelineService(session).run_once(
            parse_limit=parse_limit,
            generation_limit=generation_limit,
            publishing_limit=publishing_limit,
        )
        return {
            "parsed_sources_count": result.parsed_sources_count,
            "failed_sources_count": result.failed_sources_count,
            "parsed_items_count": result.parsed_items_count,
            "saved_items_count": result.saved_items_count,
            "duplicate_items_count": result.duplicate_items_count,
            "ready_items_count": result.ready_items_count,
            "generated_posts_count": result.generated_posts_count,
            "published_posts_count": result.published_posts_count,
        }
