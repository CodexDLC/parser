"""Healthcheck endpoint для проверки запуска приложения."""

from typing import Annotated

from fastapi import APIRouter, Depends

from aibot.api.schemas.common import HealthCheckResponse
from aibot.config import Settings, get_settings

router = APIRouter(tags=["health"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/health", response_model=HealthCheckResponse, summary="Healthcheck")
def healthcheck(settings: SettingsDep) -> HealthCheckResponse:
    """Проверить, что HTTP-приложение собрано и отвечает."""

    return HealthCheckResponse(
        status="ok",
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
    )
