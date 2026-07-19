"""Celery-задача полного pipeline запуска."""

import asyncio
import uuid

from celery import current_task

from aibot.db.worker_session import WorkerSessionFactory
from aibot.services.pipeline import PipelineService
from aibot.services.pipeline_run_tracking import PipelineRunTaskLifecycle
from aibot.tasks.base import LoggedTask
from aibot.tasks.celery_app import celery_app


@celery_app.task(base=LoggedTask, name="aibot.tasks.pipeline.run_pipeline")
def run_pipeline(
    parse_limit: int = 10,
    generation_limit: int = 10,
    publishing_limit: int = 10,
    pipeline_run_id: str | None = None,
) -> dict[str, int]:
    """Запустить один полный проход parse -> generate -> publish."""

    if pipeline_run_id is None:
        task_id = str(getattr(current_task.request, "id", None) or uuid.uuid4())
        return asyncio.run(
            _run_beat_pipeline(
                task_id=task_id,
                parse_limit=parse_limit,
                generation_limit=generation_limit,
                publishing_limit=publishing_limit,
            )
        )
    return asyncio.run(
        _run_pipeline(
            parse_limit=parse_limit,
            generation_limit=generation_limit,
            publishing_limit=publishing_limit,
        )
    )


async def _run_beat_pipeline(
    *,
    task_id: str,
    parse_limit: int,
    generation_limit: int,
    publishing_limit: int,
) -> dict[str, int]:
    """Создать persisted BEAT run и завершить его вместе с pipeline."""

    lifecycle = PipelineRunTaskLifecycle(WorkerSessionFactory)
    run_id = await lifecycle.create_beat_run(
        task_id=task_id,
        parameters={
            "parse_limit": parse_limit,
            "generation_limit": generation_limit,
            "publishing_limit": publishing_limit,
        },
    )
    try:
        result = await _run_pipeline(
            parse_limit=parse_limit,
            generation_limit=generation_limit,
            publishing_limit=publishing_limit,
        )
    except Exception as exc:
        await lifecycle.mark_failed(run_id, exc)
        raise
    await lifecycle.mark_succeeded(run_id, result)
    return result


async def _run_pipeline(
    *,
    parse_limit: int,
    generation_limit: int,
    publishing_limit: int,
) -> dict[str, int]:
    """Async-реализация полного pipeline запуска."""

    async with WorkerSessionFactory() as session:
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
