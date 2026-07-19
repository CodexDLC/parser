"""Celery-задачи для запуска парсинга источников."""

import asyncio
import uuid

from aibot.db.session import AsyncSessionFactory
from aibot.repositories.source_repository import SourceRepository
from aibot.services.news_ingestion import NewsIngestionService
from aibot.tasks.celery_app import celery_app


@celery_app.task(name="aibot.tasks.parsing.parse_source")
def parse_source(source_id: str, limit: int = 10) -> dict[str, object]:
    """Запустить ручной парсинг одного источника."""

    return asyncio.run(_parse_source(uuid.UUID(source_id), limit=limit))


@celery_app.task(name="aibot.tasks.parsing.parse_enabled_sources")
def parse_enabled_sources(limit: int = 10) -> list[dict[str, object]]:
    """Запустить парсинг всех включенных источников."""

    return asyncio.run(_parse_enabled_sources(limit=limit))


async def _parse_source(source_id: uuid.UUID, *, limit: int) -> dict[str, object]:
    """Async-реализация задачи парсинга одного источника."""

    async with AsyncSessionFactory() as session:
        result = await NewsIngestionService(session).parse_source(source_id, limit=limit)
        return {
            "source_id": str(result.source_id),
            "parsed_count": result.parsed_count,
            "saved_count": result.saved_count,
            "duplicate_count": result.duplicate_count,
            "filtered_out_count": result.filtered_out_count,
            "ready_for_generation_count": result.ready_for_generation_count,
        }


async def _parse_enabled_sources(*, limit: int) -> list[dict[str, object]]:
    """Async-реализация задачи парсинга всех включенных источников."""

    async with AsyncSessionFactory() as session:
        source_repository = SourceRepository(session)
        sources = await source_repository.list_filtered(enabled=True)
        results = []
        for source in sources:
            results.append(
                await NewsIngestionService(session).parse_source(source.id, limit=limit)
            )
        return [
            {
                "source_id": str(result.source_id),
                "parsed_count": result.parsed_count,
                "saved_count": result.saved_count,
                "duplicate_count": result.duplicate_count,
                "filtered_out_count": result.filtered_out_count,
                "ready_for_generation_count": result.ready_for_generation_count,
            }
            for result in results
        ]
