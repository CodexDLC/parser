"""Repository append-only административного аудита."""

from aibot.models.admin_audit_log import AdminAuditLog
from aibot.repositories.base_repository import BaseRepository


class AdminAuditLogRepository(BaseRepository[AdminAuditLog]):
    model = AdminAuditLog

    async def commit(self) -> None:
        await self.session.commit()
