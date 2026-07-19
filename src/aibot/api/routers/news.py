"""Endpoints для просмотра новостей и запуска генерации по новости."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from aibot.api.deps import NewsServiceDep, PostGenerationServiceDep
from aibot.api.schemas.news_item import NewsItemRead
from aibot.api.schemas.post import PostRead
from aibot.integrations.ai_client import (
    AIClientAuthenticationError,
    AIClientInvalidResponseError,
    AIClientRateLimitError,
    AIClientTimeoutError,
)
from aibot.models.enums import NewsStatus
from aibot.services.exceptions import EntityNotFoundError, InvalidNewsStateError

router = APIRouter(prefix="/news", tags=["news"])

LimitQuery = Annotated[int, Query(ge=1, le=500)]
OffsetQuery = Annotated[int, Query(ge=0)]


@router.get("/", response_model=list[NewsItemRead], summary="List news")
async def list_news(
    service: NewsServiceDep,
    source_id: uuid.UUID | None = None,
    status: NewsStatus | None = None,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
) -> list[NewsItemRead]:
    """Вернуть список новостей."""

    return await service.list_news(source_id=source_id, status=status, limit=limit, offset=offset)


@router.get("/{news_id}", response_model=NewsItemRead)
async def get_news_item(news_id: uuid.UUID, service: NewsServiceDep) -> NewsItemRead:
    """Вернуть одну новость."""

    try:
        return await service.get_news_item(news_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{news_id}/generate", response_model=PostRead)
async def generate_news_post(
    news_id: uuid.UUID,
    service: PostGenerationServiceDep,
) -> PostRead:
    """Сгенерировать и сохранить Telegram-пост для новости."""

    try:
        return await service.generate_post_from_news(news_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidNewsStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AIClientRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except AIClientTimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc
    except (AIClientAuthenticationError, AIClientInvalidResponseError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
