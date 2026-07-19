"""Создание engine, session factory и зависимостей для работы с БД."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aibot.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.debug)
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Вернуть async SQLAlchemy session для FastAPI dependency."""

    async with AsyncSessionFactory() as session:
        yield session
