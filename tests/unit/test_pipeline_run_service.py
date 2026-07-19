"""Контракты lifecycle, idempotency, reconciliation и audit."""

import uuid
from datetime import UTC, datetime

from aibot.models.enums import (
    AdminAuditOutcome,
    PipelineInitiator,
    PipelineOperation,
    PipelineRunStatus,
)
from aibot.models.pipeline_run import PipelineRun
from aibot.services.pipeline_run_service import PipelineRunService

RUN_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")


class FakePipelineRunRepository:
    def __init__(self) -> None:
        self.run: PipelineRun | None = None
        self.commits = 0

    async def get_by_idempotency_key(self, key: str) -> PipelineRun | None:
        return self.run if self.run and self.run.idempotency_key == key else None

    async def add(self, run: PipelineRun) -> PipelineRun:
        run.id = RUN_ID
        run.created_at = datetime.now(UTC)
        run.updated_at = run.created_at
        self.run = run
        return run

    async def get(self, run_id: uuid.UUID) -> PipelineRun | None:
        return self.run if self.run and self.run.id == run_id else None

    async def commit(self) -> None:
        self.commits += 1


async def test_pipeline_run_is_idempotent_and_has_explicit_lifecycle() -> None:
    repository = FakePipelineRunRepository()
    service = PipelineRunService(repository=repository)

    first, created = await service.create_queued(
        initiator=PipelineInitiator.CABINET,
        operation=PipelineOperation.PARSE_SOURCE,
        idempotency_key="cabinet:parse:one",
        entity_type="source",
        entity_id=uuid.uuid4(),
        parameters={"limit": 10},
    )
    second, duplicate_created = await service.create_queued(
        initiator=PipelineInitiator.CABINET,
        operation=PipelineOperation.PARSE_SOURCE,
        idempotency_key="cabinet:parse:one",
        entity_type="source",
        entity_id=uuid.uuid4(),
        parameters={"limit": 99},
    )
    await service.attach_task(first.id, task_id="celery-task-id")
    await service.mark_running(first.id)
    await service.mark_succeeded(first.id, result_counts={"saved_count": 3})

    assert created is True
    assert duplicate_created is False
    assert second is first
    assert first.task_id == "celery-task-id"
    assert first.status == PipelineRunStatus.SUCCEEDED
    assert first.started_at is not None
    assert first.finished_at is not None
    assert first.result_counts == {"saved_count": 3}
    assert repository.commits == 4


def test_operational_enums_cover_documented_contract() -> None:
    assert {item.value for item in PipelineRunStatus} == {
        "queued",
        "running",
        "succeeded",
        "failed",
        "revoked",
        "stale",
    }
    assert {item.value for item in PipelineInitiator} == {"beat", "cabinet", "api"}
    assert {item.value for item in PipelineOperation} == {
        "parse_source",
        "generate_news",
        "publish_post",
        "run_pipeline",
    }
    assert {item.value for item in AdminAuditOutcome} == {
        "succeeded",
        "rejected",
        "failed",
    }
