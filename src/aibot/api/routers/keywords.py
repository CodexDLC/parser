"""Endpoints для CRUD-управления ключевыми словами."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from aibot.api.deps import KeywordServiceDep
from aibot.api.schemas.keyword import KeywordCreate, KeywordRead, KeywordUpdate
from aibot.services.exceptions import EntityAlreadyExistsError, EntityNotFoundError

router = APIRouter(prefix="/keywords", tags=["keywords"])

LimitQuery = Annotated[int, Query(ge=1, le=500)]
OffsetQuery = Annotated[int, Query(ge=0)]


@router.get("/", response_model=list[KeywordRead], summary="List keywords")
async def list_keywords(
    service: KeywordServiceDep,
    enabled: bool | None = None,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
) -> list[KeywordRead]:
    """Вернуть список ключевых слов."""

    return await service.list_keywords(enabled=enabled, limit=limit, offset=offset)


@router.post("/", response_model=KeywordRead, status_code=status.HTTP_201_CREATED)
async def create_keyword(payload: KeywordCreate, service: KeywordServiceDep) -> KeywordRead:
    """Создать ключевое слово."""

    try:
        return await service.create_keyword(word=payload.word, enabled=payload.enabled)
    except EntityAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/{keyword_id}", response_model=KeywordRead)
async def update_keyword(
    keyword_id: uuid.UUID,
    payload: KeywordUpdate,
    service: KeywordServiceDep,
) -> KeywordRead:
    """Частично обновить ключевое слово."""

    try:
        return await service.update_keyword(
            keyword_id,
            word=payload.word,
            enabled=payload.enabled,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EntityAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(keyword_id: uuid.UUID, service: KeywordServiceDep) -> Response:
    """Удалить ключевое слово."""

    try:
        await service.delete_keyword(keyword_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
