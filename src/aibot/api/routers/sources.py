"""Endpoints для CRUD-управления источниками новостей."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from aibot.api.deps import SourceServiceDep, TaskQueueDep
from aibot.api.schemas.source import SourceCreate, SourceRead, SourceUpdate
from aibot.api.schemas.task import TaskQueuedResponse
from aibot.models.enums import SourceType
from aibot.models.source import Source
from aibot.services.exceptions import EntityAlreadyExistsError, EntityNotFoundError

router = APIRouter(prefix="/sources", tags=["sources"])

LimitQuery = Annotated[int, Query(ge=1, le=500)]
OffsetQuery = Annotated[int, Query(ge=0)]


@router.get("/", response_model=list[SourceRead], summary="List sources")
async def list_sources(
    service: SourceServiceDep,
    enabled: bool | None = None,
    type: SourceType | None = None,  # noqa: A002
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
) -> list[Source]:
    """Вернуть список источников новостей."""

    return await service.list_sources(
        enabled=enabled,
        source_type=type,
        limit=limit,
        offset=offset,
    )


@router.post("/", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
async def create_source(payload: SourceCreate, service: SourceServiceDep) -> Source:
    """Создать источник новостей."""

    try:
        return await service.create_source(
            source_type=payload.type,
            name=payload.name,
            url=payload.url,
            enabled=payload.enabled,
        )
    except EntityAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{source_id}", response_model=SourceRead)
async def get_source(source_id: uuid.UUID, service: SourceServiceDep) -> Source:
    """Вернуть один источник новостей."""

    try:
        return await service.get_source(source_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{source_id}", response_model=SourceRead)
async def update_source(
    source_id: uuid.UUID,
    payload: SourceUpdate,
    service: SourceServiceDep,
) -> Source:
    """Частично обновить источник новостей."""

    try:
        return await service.update_source(
            source_id,
            source_type=payload.type,
            name=payload.name,
            url=payload.url,
            enabled=payload.enabled,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EntityAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{source_id}", response_model=SourceRead)
async def disable_source(source_id: uuid.UUID, service: SourceServiceDep) -> Source:
    """Мягко удалить источник через enabled=false."""

    try:
        return await service.disable_source(source_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{source_id}/parse",
    response_model=TaskQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def parse_source(
    source_id: uuid.UUID,
    source_service: SourceServiceDep,
    task_queue: TaskQueueDep,
    limit: LimitQuery = 10,
) -> TaskQueuedResponse:
    """Проверить source и поставить его парсинг в Celery."""

    try:
        await source_service.get_source(source_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    task_id = task_queue.enqueue_source_parsing(source_id, limit=limit)
    return TaskQueuedResponse(task_id=task_id)
