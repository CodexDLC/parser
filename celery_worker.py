"""Точка входа Celery worker для запуска фоновых задач проекта."""

from aibot.tasks.celery_app import celery_app

__all__ = ["celery_app"]
