"""Статические контракты будущего административного кабинета."""

import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from aibot.config import Settings
from aibot.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class IsolatedSettings(Settings):
    """Settings без чтения локального `.env` во время проверки defaults."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")


def test_cabinet_uses_exact_pypi_release_without_local_override() -> None:
    """Runtime использует закреплённый PyPI-пакет, а не локальный checkout."""

    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    dependencies = pyproject["project"]["dependencies"]

    assert "codex-fastapi-cabinet==0.1.0" in dependencies
    assert not any(
        dependency.startswith("codex-fastapi-cabinet")
        and dependency != "codex-fastapi-cabinet==0.1.0"
        for dependency in dependencies
    )
    assert "sources" not in pyproject.get("tool", {}).get("uv", {})

    try:
        installed_version = version("codex-fastapi-cabinet")
    except PackageNotFoundError:
        pytest.fail("codex-fastapi-cabinet is not installed in the M4 environment")
    assert installed_version == "0.1.0"


def test_cabinet_feature_flags_are_safe_by_default() -> None:
    """Незавершённый кабинет и production Swagger не включаются неявно."""

    local_settings = IsolatedSettings()
    production_settings = IsolatedSettings(environment="production")

    assert local_settings.cabinet_enabled is False
    assert local_settings.cabinet_mount_path == "/cabinet"
    assert local_settings.docs_enabled is True
    assert production_settings.docs_enabled is False


def test_cabinet_contract_document_exists() -> None:
    """Threat model и stage-gated scope сохранены как проектный контракт."""

    contract_path = PROJECT_ROOT / "docs" / "cabinet-plan.md"

    assert contract_path.is_file()
    contract = contract_path.read_text(encoding="utf-8")
    for required_section in (
        "## Границы ответственности",
        "## Threat model",
        "## Модули кабинета",
        "## Разрешённые операции",
        "## Acceptance",
        "## Этапы реализации",
    ):
        assert required_section in contract


def test_production_docs_are_disabled_unless_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production policy управляет Swagger, ReDoc и OpenAPI schema вместе."""

    production_settings = IsolatedSettings(environment="production")
    monkeypatch.setattr("aibot.main.get_settings", lambda: production_settings)

    application = create_app()
    route_paths = {
        path
        for route in application.routes
        if (path := getattr(route, "path", None)) is not None
    }

    assert "/docs" not in route_paths
    assert "/redoc" not in route_paths
    assert "/openapi.json" not in route_paths
