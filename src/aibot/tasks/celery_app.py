"""Создание и настройка Celery app, broker, backend и расписания."""

from celery import Celery

from aibot.config import get_settings

settings = get_settings()

celery_app = Celery(
    "m4_aibot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "aibot.tasks.parsing",
        "aibot.tasks.filtering",
        "aibot.tasks.generation",
        "aibot.tasks.publishing",
        "aibot.tasks.pipeline",
        "aibot.tasks.maintenance",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_publish_retry=True,
    task_publish_retry_policy={
        "max_retries": 3,
        "interval_start": 0,
        "interval_step": 2,
        "interval_max": 30,
    },
    beat_schedule={
        "run-full-pipeline-every-30-minutes": {
            "task": "aibot.tasks.pipeline.run_pipeline",
            "schedule": settings.pipeline_interval_seconds,
            "kwargs": {
                "parse_limit": settings.pipeline_parse_limit,
                "generation_limit": settings.pipeline_generation_limit,
                "publishing_limit": settings.pipeline_publishing_limit,
            },
        },
        "reconcile-pipeline-runs": {
            "task": "aibot.tasks.maintenance.reconcile_pipeline_runs",
            "schedule": settings.pipeline_reconciliation_interval_seconds,
        },
    },
)
