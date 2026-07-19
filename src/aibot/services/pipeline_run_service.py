"""Application lifecycle persisted Celery operations."""

import uuid
from datetime import UTC, datetime
from typing import Protocol

from aibot.models.enums import (
    PipelineInitiator,
    PipelineOperation,
    PipelineRunStatus,
)
from aibot.models.pipeline_run import PipelineRun


class PipelineRunRepositoryPort(Protocol):
    async def get_by_idempotency_key(self, key: str) -> PipelineRun | None: ...
    async def add(self, run: PipelineRun) -> PipelineRun: ...
    async def get(self, run_id: uuid.UUID) -> PipelineRun | None: ...
    async def commit(self) -> None: ...


class PipelineRunNotFoundError(LookupError):
    """PipelineRun отсутствует."""


class InvalidPipelineRunTransitionError(RuntimeError):
    """Запрещённый lifecycle transition."""


class PipelineRunService:
    """Создавать idempotent run и контролировать его lifecycle."""

    def __init__(self, *, repository: PipelineRunRepositoryPort) -> None:
        self._repository = repository

    async def create_queued(
        self,
        *,
        initiator: PipelineInitiator,
        operation: PipelineOperation,
        idempotency_key: str,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        parameters: dict[str, object] | None = None,
    ) -> tuple[PipelineRun, bool]:
        existing = await self._repository.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing, False
        run = PipelineRun(
            initiator=initiator,
            operation=operation,
            status=PipelineRunStatus.QUEUED,
            idempotency_key=idempotency_key[:128],
            entity_type=entity_type[:64] if entity_type else None,
            entity_id=entity_id,
            parameters=parameters or {},
        )
        await self._repository.add(run)
        await self._repository.commit()
        return run, True

    async def attach_task(self, run_id: uuid.UUID, *, task_id: str) -> PipelineRun:
        run = await self._get(run_id)
        if run.status not in {PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING}:
            raise InvalidPipelineRunTransitionError("Task can only attach to active run")
        run.task_id = task_id[:255]
        await self._repository.commit()
        return run

    async def mark_running(self, run_id: uuid.UUID) -> PipelineRun:
        run = await self._get(run_id)
        if run.status not in {PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING}:
            raise InvalidPipelineRunTransitionError("Run cannot transition to running")
        now = datetime.now(UTC)
        run.status = PipelineRunStatus.RUNNING
        run.started_at = run.started_at or now
        run.heartbeat_at = now
        await self._repository.commit()
        return run

    async def mark_succeeded(
        self,
        run_id: uuid.UUID,
        *,
        result_counts: dict[str, int] | None = None,
    ) -> PipelineRun:
        run = await self._get(run_id)
        if run.status != PipelineRunStatus.RUNNING:
            raise InvalidPipelineRunTransitionError("Only running run can succeed")
        run.status = PipelineRunStatus.SUCCEEDED
        run.result_counts = result_counts
        run.error_category = None
        run.finished_at = datetime.now(UTC)
        await self._repository.commit()
        return run

    async def mark_failed(self, run_id: uuid.UUID, *, category: str) -> PipelineRun:
        run = await self._get(run_id)
        if run.status == PipelineRunStatus.FAILED:
            return run
        if run.status in {
            PipelineRunStatus.SUCCEEDED,
            PipelineRunStatus.REVOKED,
            PipelineRunStatus.STALE,
        }:
            raise InvalidPipelineRunTransitionError("Final run cannot fail")
        run.status = PipelineRunStatus.FAILED
        run.error_category = category[:255]
        run.finished_at = datetime.now(UTC)
        await self._repository.commit()
        return run

    async def _get(self, run_id: uuid.UUID) -> PipelineRun:
        run = await self._repository.get(run_id)
        if run is None:
            raise PipelineRunNotFoundError("PipelineRun not found")
        return run
