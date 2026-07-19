"""Создание таблиц PostgreSQL для первого рабочего прототипа."""

import asyncio

from aibot.db.base import Base
from aibot.db.session import engine


async def init_db() -> None:
    """Создать все таблицы из SQLAlchemy metadata."""

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


def main() -> None:
    """Запустить инициализацию БД из командной строки."""

    asyncio.run(init_db())


if __name__ == "__main__":
    main()
