"""Endpoints для просмотра постов и ручной публикации."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from aibot.api.deps import PostServiceDep, PublishingServiceDep
from aibot.api.schemas.post import PostRead
from aibot.models.enums import PostStatus
from aibot.services.exceptions import (
    EntityNotFoundError,
    InvalidPostStateError,
    PublishingFailedError,
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
) -> list[PostRead]:
    """Вернуть историю постов."""

    return await service.list_posts(status=status, limit=limit, offset=offset)


@router.get("/{post_id}", response_model=PostRead)
async def get_post(post_id: uuid.UUID, service: PostServiceDep) -> PostRead:
    """Вернуть один пост."""

    try:
        return await service.get_post(post_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{post_id}/publish", response_model=PostRead)
async def publish_post(
    post_id: uuid.UUID,
    post_service: PostServiceDep,
    publishing_service: PublishingServiceDep,
) -> PostRead:
    """Опубликовать пост или выполнить Telegram dry-run публикацию."""

    try:
        await publishing_service.publish_post(post_id)
        return await post_service.get_post(post_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidPostStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except PublishingFailedError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
