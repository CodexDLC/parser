"""Append-only audit service административных мутаций."""

import uuid

from aibot.models.admin_audit_log import AdminAuditLog
from aibot.models.enums import AdminAuditOutcome
from aibot.repositories.admin_audit_log_repository import AdminAuditLogRepository


class AdminAuditService:
    """Записывать только bounded безопасные метаданные действия."""

    def __init__(self, repository: AdminAuditLogRepository) -> None:
        self._repository = repository

    async def record(
        self,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        outcome: AdminAuditOutcome,
        detail: str | None = None,
    ) -> AdminAuditLog:
        entry = AdminAuditLog(
            actor=actor[:255],
            action=action[:128],
            entity_type=entity_type[:64],
            entity_id=entity_id,
            outcome=outcome,
            detail=detail[:512] if detail else None,
        )
        await self._repository.add(entry)
        await self._repository.commit()
        return entry
