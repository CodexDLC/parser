"""Бизнес-логика записи и просмотра ошибок приложения."""

from sqlalchemy.ext.asyncio import AsyncSession

from aibot.models.enums import ErrorScope
from aibot.models.error_log import ErrorLog
from aibot.repositories.error_log_repository import ErrorLogRepository


class ErrorLogService:
    """Бизнес-логика просмотра ошибок приложения."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = ErrorLogRepository(session)

    async def list_logs(
        self,
        *,
        scope: ErrorScope | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ErrorLog]:
        """Вернуть список ошибок приложения."""

        return await self.repository.list_filtered(scope=scope, limit=limit, offset=offset)
