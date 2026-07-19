"""Общие Pydantic-схемы: пагинация, ошибки и базовые ответы."""

from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    """Ответ healthcheck endpoint."""

    status: str = Field(description="Текущий статус приложения.")
    app_name: str = Field(description="Название приложения.")
    app_version: str = Field(description="Версия приложения.")
    environment: str = Field(description="Название runtime-окружения.")


class TaskQueuedResponse(BaseModel):
    """Ответ API, когда фоновая Celery-задача поставлена в очередь."""

    task_id: str = Field(description="Идентификатор Celery-задачи.")
    status: str = Field(default="queued", description="Статус постановки задачи в очередь.")


class MessageResponse(BaseModel):
    """Простой ответ с человекочитаемым сообщением."""

    message: str = Field(description="Описание результата операции.")
