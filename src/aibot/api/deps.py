"""FastAPI-зависимости: БД-сессия, сервисы и общие параметры."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from aibot.db.session import get_session
from aibot.integrations.celery_task_queue import CeleryTaskQueue
from aibot.services.error_log_service import ErrorLogService
from aibot.services.keyword_service import KeywordService
from aibot.services.news_service import NewsService
from aibot.services.post_generation import PostGenerationService
from aibot.services.post_service import PostService
from aibot.services.publishing import PublishingService
from aibot.services.source_service import SourceService
from aibot.services.task_queue import TaskQueue

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_source_service(session: SessionDep) -> SourceService:
    """Вернуть сервис управления источниками."""

    return SourceService(session)


def get_keyword_service(session: SessionDep) -> KeywordService:
    """Вернуть сервис управления ключевыми словами."""

    return KeywordService(session)


def get_news_service(session: SessionDep) -> NewsService:
    """Вернуть сервис просмотра новостей."""

    return NewsService(session)


def get_post_service(session: SessionDep) -> PostService:
    """Вернуть сервис просмотра постов."""

    return PostService(session)


def get_publishing_service(session: SessionDep) -> PublishingService:
    """Вернуть сервис публикации постов."""

    return PublishingService(session)


def get_error_log_service(session: SessionDep) -> ErrorLogService:
    """Вернуть сервис просмотра ошибок."""

    return ErrorLogService(session)


def get_post_generation_service(session: SessionDep) -> PostGenerationService:
    """Вернуть сервис AI-генерации постов."""

    return PostGenerationService(session)


def get_task_queue() -> TaskQueue:
    """Вернуть Celery adapter для постановки фоновых задач."""

    return CeleryTaskQueue()


SourceServiceDep = Annotated[SourceService, Depends(get_source_service)]
KeywordServiceDep = Annotated[KeywordService, Depends(get_keyword_service)]
NewsServiceDep = Annotated[NewsService, Depends(get_news_service)]
PostServiceDep = Annotated[PostService, Depends(get_post_service)]
PublishingServiceDep = Annotated[PublishingService, Depends(get_publishing_service)]
ErrorLogServiceDep = Annotated[ErrorLogService, Depends(get_error_log_service)]
PostGenerationServiceDep = Annotated[PostGenerationService, Depends(get_post_generation_service)]
TaskQueueDep = Annotated[TaskQueue, Depends(get_task_queue)]
