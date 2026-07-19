"""Endpoints для просмотра ошибок и диагностических записей."""

from typing import Annotated

from fastapi import APIRouter, Query

from aibot.api.deps import ErrorLogServiceDep
from aibot.api.schemas.error_log import ErrorLogRead
from aibot.models.enums import ErrorScope

router = APIRouter(prefix="/logs", tags=["logs"])

LimitQuery = Annotated[int, Query(ge=1, le=500)]
OffsetQuery = Annotated[int, Query(ge=0)]


@router.get("/", response_model=list[ErrorLogRead], summary="List error logs")
async def list_logs(
    service: ErrorLogServiceDep,
    scope: ErrorScope | None = None,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
) -> list[ErrorLogRead]:
    """Вернуть последние ошибки приложения."""

    return await service.list_logs(scope=scope, limit=limit, offset=offset)
