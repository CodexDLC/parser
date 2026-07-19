"""Reconciliation зависших PipelineRun."""

from datetime import UTC, datetime, timedelta

from aibot.repositories.pipeline_run_repository import PipelineRunRepository


class PipelineReconciliationService:
    """Помечать queued/running записи stale после operator-defined threshold."""

    def __init__(self, repository: PipelineRunRepository) -> None:
        self._repository = repository

    async def reconcile(self, *, stale_after_seconds: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        return await self._repository.mark_stale_before(cutoff)
