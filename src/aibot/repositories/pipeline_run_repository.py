"""Repository lifecycle-записей Celery operations."""

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult

from aibot.models.enums import PipelineRunStatus
from aibot.models.pipeline_run import PipelineRun
from aibot.repositories.base_repository import BaseRepository


class PipelineRunRepository(BaseRepository[PipelineRun]):
    model = PipelineRun

    async def get_by_idempotency_key(self, key: str) -> PipelineRun | None:
        return await self.session.scalar(
            select(PipelineRun).where(PipelineRun.idempotency_key == key)
        )

    async def get_by_task_id(self, task_id: str) -> PipelineRun | None:
        return await self.session.scalar(
            select(PipelineRun).where(PipelineRun.task_id == task_id)
        )

    async def commit(self) -> None:
        await self.session.commit()

    async def mark_stale_before(self, cutoff: datetime) -> int:
        result = cast(
            "CursorResult[Any]",
            await self.session.execute(
                update(PipelineRun)
                .where(
                    PipelineRun.status.in_(
                        (PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING)
                    ),
                    PipelineRun.updated_at < cutoff,
                )
                .values(status=PipelineRunStatus.STALE, finished_at=cutoff)
            )
        )
        await self.session.commit()
        return int(result.rowcount or 0)

    async def get_locked(self, run_id: uuid.UUID) -> PipelineRun | None:
        return await self.session.scalar(
            select(PipelineRun).where(PipelineRun.id == run_id).with_for_update()
        )
