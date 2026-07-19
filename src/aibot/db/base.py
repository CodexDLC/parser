"""Базовый класс SQLAlchemy и общая регистрация ORM-моделей."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый класс всех ORM-моделей проекта."""


def import_models() -> None:
    """Импортировать ORM-модели, чтобы они зарегистрировались в metadata."""

    import aibot.models.admin_audit_log  # noqa: F401
    import aibot.models.error_log  # noqa: F401
    import aibot.models.keyword  # noqa: F401
    import aibot.models.news_item  # noqa: F401
    import aibot.models.pipeline_run  # noqa: F401
    import aibot.models.post  # noqa: F401
    import aibot.models.source  # noqa: F401


import_models()
