"""Celery-задачи для запуска парсинга источников."""

import asyncio
import uuid

from aibot.db.worker_session import WorkerSessionFactory
from aibot.integrations.http_client import HttpTemporaryError
from aibot.repositories.source_repository import SourceRepository
from aibot.services.news_ingestion import NewsIngestionService
from aibot.services.source_batch_parsing import (
    SourceBatchParseResult,
    SourceBatchParsingService,
)
from aibot.tasks.base import LoggedTask
from aibot.tasks.celery_app import celery_app


@celery_app.task(
    base=LoggedTask,
    name="aibot.tasks.parsing.parse_source",
    autoretry_for=(HttpTemporaryError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def parse_source(
    source_id: str,
    limit: int = 10,
    pipeline_run_id: str | None = None,
) -> dict[str, object]:
    """Запустить ручной парсинг одного источника."""

    del pipeline_run_id
    return asyncio.run(_parse_source(uuid.UUID(source_id), limit=limit))


@celery_app.task(
    base=LoggedTask,
    name="aibot.tasks.parsing.parse_enabled_sources",
)
def parse_enabled_sources(limit: int = 10) -> list[dict[str, object]]:
    """Запустить парсинг всех включенных источников."""

    return asyncio.run(_parse_enabled_sources(limit=limit))


async def _parse_source(source_id: uuid.UUID, *, limit: int) -> dict[str, object]:
    """Async-реализация задачи парсинга одного источника."""

    async with WorkerSessionFactory() as session:
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

    async with WorkerSessionFactory() as session:
        source_repository = SourceRepository(session)
        batch_result = await SourceBatchParsingService(
            source_repository=source_repository,
            ingestion_service=NewsIngestionService(
                session,
                source_repository=source_repository,
            ),
        ).parse_enabled_sources(limit=limit)
        return _serialize_batch_result(batch_result)


def _serialize_batch_result(batch_result: SourceBatchParseResult) -> list[dict[str, object]]:
    """Преобразовать batch result в безопасный JSON-контракт Celery."""

    successful: list[dict[str, object]] = [
        {
            "source_id": str(result.source_id),
            "status": "success",
            "parsed_count": result.parsed_count,
            "saved_count": result.saved_count,
            "duplicate_count": result.duplicate_count,
            "filtered_out_count": result.filtered_out_count,
            "ready_for_generation_count": result.ready_for_generation_count,
        }
        for result in batch_result.successful
    ]
    failed: list[dict[str, object]] = [
        {
            "source_id": str(failure.source_id),
            "status": "failed",
            "error_type": failure.error_type,
        }
        for failure in batch_result.failed
    ]
    return [*successful, *failed]
