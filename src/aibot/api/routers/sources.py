"""Endpoints для CRUD-управления источниками новостей."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from aibot.api.deps import NewsIngestionServiceDep, SourceServiceDep
from aibot.api.schemas.source import SourceCreate, SourceParseResponse, SourceRead, SourceUpdate
from aibot.models.enums import SourceType
from aibot.services.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    UnsupportedSourceTypeError,
)

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
) -> list[SourceRead]:
    """Вернуть список источников новостей."""

    return await service.list_sources(
        enabled=enabled,
        source_type=type,
        limit=limit,
        offset=offset,
    )


@router.post("/", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
async def create_source(payload: SourceCreate, service: SourceServiceDep) -> SourceRead:
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
async def get_source(source_id: uuid.UUID, service: SourceServiceDep) -> SourceRead:
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
) -> SourceRead:
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
async def disable_source(source_id: uuid.UUID, service: SourceServiceDep) -> SourceRead:
    """Мягко удалить источник через enabled=false."""

    try:
        return await service.disable_source(source_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{source_id}/parse", response_model=SourceParseResponse)
async def parse_source(
    source_id: uuid.UUID,
    service: NewsIngestionServiceDep,
    limit: LimitQuery = 10,
) -> SourceParseResponse:
    """Ручно распарсить источник и сохранить новости."""

    try:
        return await service.parse_source(source_id, limit=limit)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnsupportedSourceTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
