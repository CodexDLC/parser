"""Endpoints для просмотра новостей и запуска генерации по новости."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from aibot.api.deps import NewsServiceDep, PostGenerationServiceDep, TaskQueueDep
from aibot.api.schemas.news_item import NewsItemRead
from aibot.api.schemas.task import TaskQueuedResponse
from aibot.models.enums import NewsStatus
from aibot.models.news_item import NewsItem
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
) -> list[NewsItem]:
    """Вернуть список новостей."""

    return await service.list_news(source_id=source_id, status=status, limit=limit, offset=offset)


@router.get("/{news_id}", response_model=NewsItemRead)
async def get_news_item(news_id: uuid.UUID, service: NewsServiceDep) -> NewsItem:
    """Вернуть одну новость."""

    try:
        return await service.get_news_item(news_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{news_id}/generate",
    response_model=TaskQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_news_post(
    news_id: uuid.UUID,
    service: PostGenerationServiceDep,
    task_queue: TaskQueueDep,
) -> TaskQueuedResponse:
    """Проверить news и поставить генерацию поста в Celery."""

    try:
        await service.get_generation_candidate(news_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidNewsStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    task_id = task_queue.enqueue_news_generation(news_id)
    return TaskQueuedResponse(task_id=task_id)
