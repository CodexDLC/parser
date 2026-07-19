"""Idempotency-контракты постановки cabinet operations в Celery."""

import uuid
from dataclasses import dataclass

from aibot.cabinet.operations import CabinetOperationService
from aibot.models.enums import PipelineOperation

RUN_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
SOURCE_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@dataclass
class FakeRun:
    id: uuid.UUID
    operation: PipelineOperation
    task_id: str | None = None


class FakeRunStore:
    def __init__(self) -> None:
        self.by_key: dict[str, FakeRun] = {}
        self.attached: list[tuple[uuid.UUID, str]] = []

    async def create_queued(self, **values: object) -> tuple[FakeRun, bool]:
        key = str(values["idempotency_key"])
        if key in self.by_key:
            return self.by_key[key], False
        run = FakeRun(RUN_ID, values["operation"])  # type: ignore[arg-type]
        self.by_key[key] = run
        return run, True

    async def attach_task(self, run_id: uuid.UUID, task_id: str) -> None:
        self.attached.append((run_id, task_id))

    async def mark_failed(self, run_id: uuid.UUID, category: str) -> None:
        raise AssertionError((run_id, category))


class FakeValidator:
    def __init__(self) -> None:
        self.sources: list[uuid.UUID] = []

    async def validate_source(self, source_id: uuid.UUID) -> None:
        self.sources.append(source_id)

    async def validate_news(self, news_id: uuid.UUID) -> None:
        return None

    async def validate_post(self, post_id: uuid.UUID) -> None:
        return None


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, int, uuid.UUID | None]] = []

    def enqueue_source_parsing(
        self,
        source_id: uuid.UUID,
        *,
        limit: int,
        pipeline_run_id: uuid.UUID | None = None,
    ) -> str:
        self.calls.append((source_id, limit, pipeline_run_id))
        return "celery-task-id"


class FakeAudit:
    def __init__(self) -> None:
        self.actions: list[tuple[str, str, uuid.UUID | None, str]] = []

    async def record(
        self,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        outcome: str,
        detail: str | None = None,
    ) -> None:
        self.actions.append((actor, action, entity_id, outcome))


async def test_repeated_idempotency_key_enqueues_only_once() -> None:
    run_store = FakeRunStore()
    queue = FakeQueue()
    validator = FakeValidator()
    audit = FakeAudit()
    service = CabinetOperationService(
        run_store=run_store,  # type: ignore[arg-type]
        validator=validator,
        task_queue=queue,  # type: ignore[arg-type]
        audit=audit,
    )

    first = await service.enqueue_source_parse(
        actor="admin",
        source_id=SOURCE_ID,
        limit=10,
        idempotency_key="same-browser-submit",
    )
    second = await service.enqueue_source_parse(
        actor="admin",
        source_id=SOURCE_ID,
        limit=10,
        idempotency_key="same-browser-submit",
    )

    assert first.id == second.id == RUN_ID
    assert validator.sources == [SOURCE_ID, SOURCE_ID]
    assert queue.calls == [(SOURCE_ID, 10, RUN_ID)]
    assert run_store.attached == [(RUN_ID, "celery-task-id")]
    assert audit.actions == [("admin", "source.parse", SOURCE_ID, "succeeded")]
