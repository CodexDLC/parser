"""Общие pytest fixtures для unit и integration тестов."""

from collections.abc import Callable
from typing import Any, NoReturn

import pytest

UnavailableInfrastructure = Callable[[str, BaseException], NoReturn]


def pytest_addoption(parser: Any) -> None:
    """Добавить строгий режим для acceptance-проверок инфраструктуры."""

    parser.addoption(
        "--require-infrastructure",
        action="store_true",
        default=False,
        help="Fail instead of skip when PostgreSQL or Redis is unavailable.",
    )


@pytest.fixture()
def unavailable_infrastructure(request: Any) -> UnavailableInfrastructure:
    """Вернуть обработчик недоступной инфраструктуры для integration-тестов."""

    require_infrastructure = bool(request.config.getoption("--require-infrastructure"))

    def handle(service_name: str, exc: BaseException) -> NoReturn:
        message = f"{service_name} is not available for integration test: {exc}"
        if require_infrastructure:
            pytest.fail(message, pytrace=False)
        pytest.skip(message)

    return handle
