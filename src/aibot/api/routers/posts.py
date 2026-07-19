"""Endpoints для просмотра постов и ручной публикации."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from aibot.api.deps import PostServiceDep, PublishingServiceDep, TaskQueueDep
from aibot.api.schemas.post import PostRead
from aibot.api.schemas.task import TaskQueuedResponse
from aibot.models.enums import PostStatus
from aibot.models.post import Post
from aibot.services.exceptions import (
    EntityNotFoundError,
    InvalidPostStateError,
)

router = APIRouter(prefix="/posts", tags=["posts"])

LimitQuery = Annotated[int, Query(ge=1, le=500)]
OffsetQuery = Annotated[int, Query(ge=0)]


@router.get("/", response_model=list[PostRead], summary="List posts")
async def list_posts(
    service: PostServiceDep,
    status: PostStatus | None = None,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
) -> list[Post]:
    """Вернуть историю постов."""

    return await service.list_posts(status=status, limit=limit, offset=offset)


@router.get("/{post_id}", response_model=PostRead)
async def get_post(post_id: uuid.UUID, service: PostServiceDep) -> Post:
    """Вернуть один пост."""

    try:
        return await service.get_post(post_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{post_id}/publish",
    response_model=TaskQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def publish_post(
    post_id: uuid.UUID,
    publishing_service: PublishingServiceDep,
    task_queue: TaskQueueDep,
) -> TaskQueuedResponse:
    """Проверить post и поставить публикацию в Celery."""

    try:
        await publishing_service.get_publishable_post(post_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidPostStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    task_id = task_queue.enqueue_post_publication(post_id)
    return TaskQueuedResponse(task_id=task_id)
