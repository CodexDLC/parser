"""Composition root защищённого server-rendered кабинета."""

from pathlib import Path

from fastapi import FastAPI
from fastapi_cabinet import CabinetSite, include_cabinet

from aibot.cabinet.admin import OverviewAdmin
from aibot.cabinet.audit_admin import AuditAdmin
from aibot.cabinet.auth import CabinetAuthService, CabinetSecurityStore
from aibot.cabinet.dashboard import (
    CabinetDashboardReader,
    CabinetDashboardService,
    PassiveHealthService,
    RedisPassiveHealthProbe,
)
from aibot.cabinet.dashboard_repository import SqlAlchemyCabinetDashboardRepository
from aibot.cabinet.entity_read import CabinetEntityReader
from aibot.cabinet.entity_repository import SqlAlchemyCabinetEntityReader
from aibot.cabinet.errors_admin import ErrorsAdmin
from aibot.cabinet.keywords_admin import KeywordsAdmin
from aibot.cabinet.middleware import CabinetSecurityMiddleware
from aibot.cabinet.mutations import CabinetMutationPort, CabinetMutationService
from aibot.cabinet.news_admin import NewsAdmin
from aibot.cabinet.operation_routes import build_cabinet_operation_router
from aibot.cabinet.operational_read import CabinetOperationalReader
from aibot.cabinet.operational_repository import SqlAlchemyCabinetOperationalReader
from aibot.cabinet.operations import (
    CabinetOperationPort,
    CabinetOperationService,
    SqlOperationAudit,
    SqlOperationValidator,
    SqlPipelineRunStore,
)
from aibot.cabinet.permissions import CabinetPermissionProvider
from aibot.cabinet.pipeline_admin import PipelineAdmin
from aibot.cabinet.posts_admin import PostsAdmin
from aibot.cabinet.redis_store import RedisCabinetSecurityStore
from aibot.cabinet.routes import build_cabinet_auth_router
from aibot.cabinet.sources_admin import SourcesAdmin
from aibot.config import Settings
from aibot.db.session import AsyncSessionFactory
from aibot.integrations.celery_task_queue import CeleryTaskQueue

_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def include_management_cabinet(
    app: FastAPI,
    *,
    settings: Settings,
    security_store: CabinetSecurityStore | None = None,
    dashboard_service: CabinetDashboardReader | None = None,
    entity_reader: CabinetEntityReader | None = None,
    operational_reader: CabinetOperationalReader | None = None,
    mutation_service: CabinetMutationPort | None = None,
    operation_service: CabinetOperationPort | None = None,
) -> None:
    """Подключить защищённый кабинет с read-only dashboard providers."""

    active_store = security_store or RedisCabinetSecurityStore(settings.redis_url)
    redis_health_probe: RedisPassiveHealthProbe | None = None
    active_dashboard_service = dashboard_service
    if active_dashboard_service is None:
        redis_health_probe = RedisPassiveHealthProbe(settings.redis_url)
        active_dashboard_service = CabinetDashboardService(
            settings=settings,
            repository=SqlAlchemyCabinetDashboardRepository(AsyncSessionFactory),
            health_service=PassiveHealthService(
                settings=settings,
                redis_probe=redis_health_probe,
            ),
        )
    auth_service = CabinetAuthService(settings, active_store)
    site = CabinetSite(
        brand_name="M4 Управление",
        permission_provider=CabinetPermissionProvider(),
        template_directories=(_TEMPLATE_DIR,),
    )
    site.register(OverviewAdmin)
    site.register(SourcesAdmin)
    site.register(KeywordsAdmin)
    site.register(NewsAdmin)
    site.register(PostsAdmin)
    site.register(ErrorsAdmin)
    site.register(PipelineAdmin)
    site.register(AuditAdmin)

    app.state.cabinet_auth_service = auth_service
    app.state.cabinet_security_store = active_store
    app.state.cabinet_dashboard_service = active_dashboard_service
    app.state.cabinet_entity_reader = entity_reader or SqlAlchemyCabinetEntityReader(
        AsyncSessionFactory
    )
    app.state.cabinet_operational_reader = (
        operational_reader or SqlAlchemyCabinetOperationalReader(AsyncSessionFactory)
    )
    app.state.cabinet_mutation_service = mutation_service or CabinetMutationService(
        AsyncSessionFactory
    )
    app.state.cabinet_operation_service = operation_service or CabinetOperationService(
        run_store=SqlPipelineRunStore(AsyncSessionFactory),
        validator=SqlOperationValidator(AsyncSessionFactory),
        task_queue=CeleryTaskQueue(),
        audit=SqlOperationAudit(AsyncSessionFactory),
    )
    app.state.cabinet_pipeline_limits = (
        settings.pipeline_parse_limit,
        settings.pipeline_generation_limit,
        settings.pipeline_publishing_limit,
    )
    app.state.cabinet_telegram_dry_run = settings.telegram_dry_run
    app.state.cabinet_mount_path = settings.cabinet_mount_path
    app.state.cabinet_timezone = settings.cabinet_timezone
    app.include_router(
        build_cabinet_auth_router(
            settings=settings,
            auth_service=auth_service,
            templates=site.templates,
        )
    )
    app.include_router(build_cabinet_operation_router(settings))
    include_cabinet(
        app,
        site=site,
        mount_path=settings.cabinet_mount_path,
    )
    app.add_middleware(
        CabinetSecurityMiddleware,
        auth_service=auth_service,
        mount_path=settings.cabinet_mount_path,
    )

    close = getattr(active_store, "close", None)
    if callable(close):
        app.router.add_event_handler("shutdown", close)
    if redis_health_probe is not None:
        app.router.add_event_handler("shutdown", redis_health_probe.close)
