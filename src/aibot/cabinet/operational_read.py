"""Read port operational журналов кабинета."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from aibot.cabinet.entity_read import EntityPage


@dataclass(frozen=True, slots=True)
class PipelineRunView:
    id: uuid.UUID
    initiator: str
    operation: str
    status: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    task_id: str | None
    parameters: dict[str, object]
    result_counts: dict[str, int] | None
    error_category: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AdminAuditView:
    id: uuid.UUID
    actor: str
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    outcome: str
    detail: str | None
    created_at: datetime


class CabinetOperationalReader(Protocol):
    async def list_pipeline_runs(
        self,
        *,
        offset: int,
        limit: int,
        status: str,
        operation: str,
    ) -> EntityPage[PipelineRunView]: ...

    async def get_pipeline_run(self, entity_id: uuid.UUID) -> PipelineRunView | None: ...

    async def list_audit_logs(
        self,
        *,
        offset: int,
        limit: int,
        outcome: str,
        action: str,
    ) -> EntityPage[AdminAuditView]: ...

    async def get_audit_log(self, entity_id: uuid.UUID) -> AdminAuditView | None: ...
