"""Enum-значения статусов, типов источников и зон ошибок."""

from enum import StrEnum


class SourceType(StrEnum):
    """Тип источника новостей."""

    SITE = "site"
    TELEGRAM = "tg"


class NewsStatus(StrEnum):
    """Статус обработки новости."""

    NEW = "new"
    FILTERED_OUT = "filtered_out"
    READY_FOR_GENERATION = "ready_for_generation"
    GENERATED = "generated"
    FAILED = "failed"


class PostStatus(StrEnum):
    """Статус генерации и публикации поста."""

    NEW = "new"
    GENERATED = "generated"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class ErrorScope(StrEnum):
    """Зона приложения, в которой возникла ошибка."""

    PARSER = "parser"
    AI = "ai"
    TELEGRAM = "telegram"
    CELERY = "celery"
    API = "api"


class PipelineRunStatus(StrEnum):
    """Lifecycle фоновой операции."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REVOKED = "revoked"
    STALE = "stale"


class PipelineInitiator(StrEnum):
    """Инициатор фоновой операции."""

    BEAT = "beat"
    CABINET = "cabinet"
    API = "api"


class PipelineOperation(StrEnum):
    """Тип отслеживаемой фоновой операции."""

    PARSE_SOURCE = "parse_source"
    GENERATE_NEWS = "generate_news"
    PUBLISH_POST = "publish_post"
    RUN_PIPELINE = "run_pipeline"


class AdminAuditOutcome(StrEnum):
    """Результат административной мутации."""

    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"
