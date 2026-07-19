"""Изолированный SQLAlchemy runtime для синхронных Celery task adapters."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from aibot.config import get_settings

settings = get_settings()
worker_engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    poolclass=NullPool,
)
WorkerSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=worker_engine,
    autoflush=False,
    expire_on_commit=False,
)
