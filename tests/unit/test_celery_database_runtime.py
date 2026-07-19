"""Контракт отдельного SQLAlchemy runtime для Celery Worker."""

from pathlib import Path

from sqlalchemy.pool import NullPool


def test_worker_engine_does_not_reuse_connections_between_event_loops() -> None:
    """Каждый asyncio.run Celery должен получать новое asyncpg-соединение."""

    from aibot.db.worker_session import worker_engine

    assert isinstance(worker_engine.sync_engine.pool, NullPool)


def test_celery_tasks_do_not_use_api_session_factory() -> None:
    """Task adapters не должны обращаться к pooled FastAPI session factory."""

    tasks_directory = Path(__file__).parents[2] / "src" / "aibot" / "tasks"
    forbidden_import = "from aibot.db.session import AsyncSessionFactory"
    offenders = sorted(
        path.name
        for path in tasks_directory.glob("*.py")
        if forbidden_import in path.read_text(encoding="utf-8")
    )

    assert offenders == []
