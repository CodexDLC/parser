"""Применение versioned Alembic-миграций к PostgreSQL."""

from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def build_alembic_config() -> Config:
    """Собрать Alembic config относительно корня проекта."""

    return Config(str(PROJECT_ROOT / "alembic.ini"))


def init_db() -> None:
    """Обновить схему базы данных до последней Alembic revision."""

    command.upgrade(build_alembic_config(), "head")


def main() -> None:
    """Запустить инициализацию БД из командной строки."""

    init_db()


if __name__ == "__main__":
    main()
