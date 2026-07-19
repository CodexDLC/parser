"""Celery hook adapter для persisted PipelineRun lifecycle."""

import uuid
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aibot.models.enums import PipelineInitiator, PipelineOperation
from aibot.repositories.pipeline_run_repository import PipelineRunRepository
from aibot.services.pipeline_run_service import PipelineRunService


class PipelineRunTaskLifecycle:
    """Обновлять lifecycle из Celery hooks в отдельных DB sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_beat_run(
        self,
        *,
        task_id: str,
        parameters: dict[str, object],
    ) -> uuid.UUID:
        async with self._session_factory() as session:
            service = PipelineRunService(repository=PipelineRunRepository(session))
            run, _ = await service.create_queued(
                initiator=PipelineInitiator.BEAT,
                operation=PipelineOperation.RUN_PIPELINE,
                idempotency_key=f"beat:{task_id}",
                parameters=parameters,
            )
            await service.attach_task(run.id, task_id=task_id)
            await service.mark_running(run.id)
            return run.id

    async def mark_running(self, run_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            await PipelineRunService(
                repository=PipelineRunRepository(session)
            ).mark_running(run_id)

    async def mark_succeeded(self, run_id: uuid.UUID, result: object) -> None:
        counts = _integer_counts(result)
        async with self._session_factory() as session:
            await PipelineRunService(
                repository=PipelineRunRepository(session)
            ).mark_succeeded(run_id, result_counts=counts or None)

    async def mark_failed(self, run_id: uuid.UUID, exc: BaseException) -> None:
        async with self._session_factory() as session:
            await PipelineRunService(
                repository=PipelineRunRepository(session)
            ).mark_failed(run_id, category=exc.__class__.__name__)


def _integer_counts(result: object) -> dict[str, int]:
    if not isinstance(result, Mapping):
        return {}
    return {
        str(key): value
        for key, value in result.items()
        if isinstance(value, int) and not isinstance(value, bool)
    }
