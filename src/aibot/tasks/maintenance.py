"""Периодические operational maintenance tasks."""

import asyncio

from aibot.config import get_settings
from aibot.db.session import AsyncSessionFactory
from aibot.repositories.pipeline_run_repository import PipelineRunRepository
from aibot.services.pipeline_reconciliation import PipelineReconciliationService
from aibot.tasks.base import LoggedTask
from aibot.tasks.celery_app import celery_app


@celery_app.task(
    base=LoggedTask,
    name="aibot.tasks.maintenance.reconcile_pipeline_runs",
)
def reconcile_pipeline_runs() -> dict[str, int]:
    """Пометить зависшие queued/running операции stale."""

    return asyncio.run(_reconcile_pipeline_runs())


async def _reconcile_pipeline_runs() -> dict[str, int]:
    async with AsyncSessionFactory() as session:
        count = await PipelineReconciliationService(
            PipelineRunRepository(session)
        ).reconcile(
            stale_after_seconds=get_settings().pipeline_run_stale_after_seconds
        )
    return {"stale_runs_count": count}
