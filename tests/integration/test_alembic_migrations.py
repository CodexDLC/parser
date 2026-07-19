"""Интеграционная проверка Alembic upgrade/check/downgrade на PostgreSQL."""

import asyncio
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import NoReturn

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import create_async_engine

from aibot.config import Settings
from aibot.db.base import Base

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_DATABASE_NAME = "m4_alembic_test"


def build_alembic_config(database_url: str) -> Config:
    """Собрать Alembic config для отдельной migration test DB."""

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


async def list_tables(database_url: str) -> set[str]:
    """Прочитать имена таблиц отдельной migration DB."""

    migration_engine = create_async_engine(database_url)
    try:
        async with migration_engine.connect() as connection:
            return set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
    finally:
        await migration_engine.dispose()


@pytest.fixture()
async def migration_database(
    unavailable_infrastructure: Callable[[str, BaseException], NoReturn],
) -> AsyncIterator[str]:
    """Создать и затем удалить отдельную PostgreSQL DB для Alembic."""

    configured_url = make_url(Settings().database_url)
    admin_url = configured_url.set(database="postgres")
    migration_url = configured_url.set(database=MIGRATION_DATABASE_NAME)
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        async with admin_engine.connect() as connection:
            await connection.execute(
                text(f'DROP DATABASE IF EXISTS "{MIGRATION_DATABASE_NAME}" WITH (FORCE)')
            )
            await connection.execute(text(f'CREATE DATABASE "{MIGRATION_DATABASE_NAME}"'))
    except (ConnectionRefusedError, DBAPIError, OSError, OperationalError) as exc:
        unavailable_infrastructure("PostgreSQL migration database", exc)

    await admin_engine.dispose()
    yield migration_url.render_as_string(hide_password=False)

    cleanup_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with cleanup_engine.connect() as connection:
            await connection.execute(
                text(f'DROP DATABASE IF EXISTS "{MIGRATION_DATABASE_NAME}" WITH (FORCE)')
            )
    finally:
        await cleanup_engine.dispose()


@pytest.mark.asyncio
async def test_initial_migration_upgrade_check_downgrade(
    migration_database: str,
) -> None:
    """Initial revision совпадает с metadata и обратима на чистой PostgreSQL DB."""

    config = build_alembic_config(migration_database)
    application_tables = set(Base.metadata.tables)

    await asyncio.to_thread(command.upgrade, config, "head")
    upgraded_tables = await list_tables(migration_database)
    assert application_tables <= upgraded_tables
    assert "alembic_version" in upgraded_tables

    await asyncio.to_thread(command.check, config)

    await asyncio.to_thread(command.downgrade, config, "base")
    downgraded_tables = await list_tables(migration_database)
    assert application_tables.isdisjoint(downgraded_tables)

    await asyncio.to_thread(command.upgrade, config, "head")
    assert application_tables <= await list_tables(migration_database)
