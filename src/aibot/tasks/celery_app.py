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
        "parse-enabled-sources-every-30-minutes": {
            "task": "aibot.tasks.parsing.parse_enabled_sources",
            "schedule": 30 * 60,
        }
    },
)
