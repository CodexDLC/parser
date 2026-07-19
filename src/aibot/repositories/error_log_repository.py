"""Repository для записи и чтения ошибок приложения."""

from sqlalchemy import desc, select

from aibot.models.enums import ErrorScope
from aibot.models.error_log import ErrorLog
from aibot.repositories.base_repository import BaseRepository


class ErrorLogRepository(BaseRepository[ErrorLog]):
    """Repository для записи и чтения ошибок приложения."""

    model = ErrorLog

    async def list_recent(self, *, limit: int = 100) -> list[ErrorLog]:
        """Вернуть последние ошибки приложения."""

        result = await self.session.scalars(
            select(ErrorLog).order_by(desc(ErrorLog.created_at)).limit(limit)
        )
        return list(result)

    async def list_filtered(
        self,
        *,
        scope: ErrorScope | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ErrorLog]:
        """Вернуть ошибки с опциональным фильтром по зоне приложения."""

        statement = select(ErrorLog).order_by(desc(ErrorLog.created_at)).limit(limit).offset(offset)
        if scope is not None:
            statement = statement.where(ErrorLog.scope == scope)
        result = await self.session.scalars(statement)
        return list(result)

    async def list_by_scope(self, scope: ErrorScope, *, limit: int = 100) -> list[ErrorLog]:
        """Вернуть последние ошибки выбранной зоны приложения."""

        result = await self.session.scalars(
            select(ErrorLog)
            .where(ErrorLog.scope == scope)
            .order_by(desc(ErrorLog.created_at))
            .limit(limit)
        )
        return list(result)
