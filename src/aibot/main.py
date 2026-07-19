"""Точка входа FastAPI-приложения и сборка HTTP API."""

from fastapi import FastAPI

from aibot.api.routers.generation import router as generation_router
from aibot.api.routers.health import router as health_router
from aibot.api.routers.keywords import router as keywords_router
from aibot.api.routers.logs import router as logs_router
from aibot.api.routers.news import router as news_router
from aibot.api.routers.posts import router as posts_router
from aibot.api.routers.sources import router as sources_router
from aibot.cabinet.auth import CabinetSecurityStore
from aibot.cabinet.dashboard import CabinetDashboardReader
from aibot.cabinet.entity_read import CabinetEntityReader
from aibot.cabinet.mutations import CabinetMutationPort
from aibot.cabinet.operational_read import CabinetOperationalReader
from aibot.cabinet.operations import CabinetOperationPort
from aibot.cabinet.site import include_management_cabinet
from aibot.config import Settings, get_settings


def create_app(
    *,
    settings: Settings | None = None,
    cabinet_security_store: CabinetSecurityStore | None = None,
    cabinet_dashboard_service: CabinetDashboardReader | None = None,
    cabinet_entity_reader: CabinetEntityReader | None = None,
    cabinet_operational_reader: CabinetOperationalReader | None = None,
    cabinet_mutation_service: CabinetMutationPort | None = None,
    cabinet_operation_service: CabinetOperationPort | None = None,
) -> FastAPI:
    """Создать и настроить экземпляр FastAPI-приложения."""

    active_settings = settings or get_settings()
    app = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        debug=active_settings.debug,
        docs_url="/docs" if active_settings.docs_enabled else None,
        redoc_url="/redoc" if active_settings.docs_enabled else None,
        openapi_url="/openapi.json" if active_settings.docs_enabled else None,
    )
    app.include_router(health_router, prefix=active_settings.api_prefix)
    app.include_router(sources_router, prefix=active_settings.api_prefix)
    app.include_router(keywords_router, prefix=active_settings.api_prefix)
    app.include_router(news_router, prefix=active_settings.api_prefix)
    app.include_router(posts_router, prefix=active_settings.api_prefix)
    app.include_router(generation_router, prefix=active_settings.api_prefix)
    app.include_router(logs_router, prefix=active_settings.api_prefix)
    if active_settings.cabinet_enabled:
        include_management_cabinet(
            app,
            settings=active_settings,
            security_store=cabinet_security_store,
            dashboard_service=cabinet_dashboard_service,
            entity_reader=cabinet_entity_reader,
            operational_reader=cabinet_operational_reader,
            mutation_service=cabinet_mutation_service,
            operation_service=cabinet_operation_service,
        )
    return app


app = create_app()
