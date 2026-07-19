"""Безопасная запись финальных сбоев Celery в ErrorLog."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aibot.models.enums import ErrorScope
from aibot.models.error_log import ErrorLog
from aibot.repositories.error_log_repository import ErrorLogRepository


class CeleryFailureLoggingService:
    """Сохранить task failure без traceback и потенциальных секретов."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        repository: ErrorLogRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or ErrorLogRepository(session)

    async def record_failure(
        self,
        *,
        task_name: str,
        exc: BaseException,
        source_id: uuid.UUID | None = None,
        news_id: uuid.UUID | None = None,
        post_id: uuid.UUID | None = None,
    ) -> ErrorLog:
        """Записать финальную ошибку task с безопасным типом исключения."""

        error_log = await self.repository.add(
            ErrorLog(
                scope=ErrorScope.CELERY,
                message=f"Celery task failed: {task_name}"[:512],
                details=exc.__class__.__name__,
                source_id=source_id,
                news_id=news_id,
                post_id=post_id,
            )
        )
        await self.session.commit()
        return error_log
