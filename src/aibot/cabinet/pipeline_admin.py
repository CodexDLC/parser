"""Read-only PipelineRun list/detail adapter."""

import secrets

from fastapi import HTTPException, Request
from fastapi_cabinet import CabinetAdmin
from fastapi_cabinet.contracts.admin import ActionRoute
from fastapi_cabinet.contracts.navigation import SidebarItem
from fastapi_cabinet.contracts.pages import (
    DetailFieldMap,
    DetailPage,
    DetailPageMap,
    FilterFieldMap,
    ListPage,
    ListPageMap,
    OperationActionMap,
    OperationPage,
    OperationPageMap,
)
from fastapi_cabinet.contracts.widgets import TableColumnMap
from starlette.responses import RedirectResponse, Response

from aibot.cabinet.operations import CabinetOperationPort
from aibot.cabinet.page_helpers import (
    PAGE_SIZE,
    choices,
    format_datetime,
    list_sidebar,
    module_context,
    pagination,
    parse_entity_id,
    query_value,
    requested_page,
    session_actor,
    timezone,
)


async def pipeline_list_provider(request: Request) -> ListPageMap:
    page = requested_page(request)
    status = query_value(request, "status")
    operation = query_value(request, "operation")
    result = await request.app.state.cabinet_operational_reader.list_pipeline_runs(
        offset=(page - 1) * PAGE_SIZE,
        limit=PAGE_SIZE,
        status=status,
        operation=operation,
    )
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return ListPageMap(
        title="Запуски pipeline",
        columns=[
            TableColumnMap(key="operation", label="Операция"),
            TableColumnMap(key="status", label="Статус"),
            TableColumnMap(key="initiator", label="Инициатор"),
            TableColumnMap(key="created", label="Создан"),
        ],
        rows=[
            {
                "operation": item.operation,
                "status": item.status,
                "initiator": item.initiator,
                "created": format_datetime(item.created_at, timezone(request)),
                "_href": f"{base}/pipeline/{item.id}",
            }
            for item in result.items
        ],
        filters=[
            FilterFieldMap(
                name="status",
                label="Статус",
                input_type="select",
                choices=choices(
                    (
                        ("", "Все"),
                        ("queued", "Queued"),
                        ("running", "Running"),
                        ("succeeded", "Succeeded"),
                        ("failed", "Failed"),
                        ("revoked", "Revoked"),
                        ("stale", "Stale"),
                    ),
                    selected=status,
                ),
            ),
            FilterFieldMap(
                name="operation",
                label="Операция",
                input_type="select",
                choices=choices(
                    (
                        ("", "Все"),
                        ("parse_source", "Parse source"),
                        ("generate_news", "Generate news"),
                        ("publish_post", "Publish post"),
                        ("run_pipeline", "Full pipeline"),
                    ),
                    selected=operation,
                ),
            ),
        ],
        pagination=pagination(request, page=page, total=result.total),
        row_href_key="_href",
        empty_message="Запусков пока нет.",
    )


async def pipeline_detail_provider(request: Request) -> DetailPageMap:
    item = await request.app.state.cabinet_operational_reader.get_pipeline_run(
        parse_entity_id(request, "run_id")
    )
    if item is None:
        raise HTTPException(status_code=404, detail="PipelineRun not found")
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return DetailPageMap(
        title=f"{item.operation}: {item.status}",
        subtitle=str(item.id),
        fields=[
            DetailFieldMap(label="Инициатор", value=item.initiator),
            DetailFieldMap(label="Entity", value=item.entity_type or "—"),
            DetailFieldMap(label="Entity UUID", value=str(item.entity_id or "—")),
            DetailFieldMap(label="Celery task ID", value=item.task_id or "—"),
            DetailFieldMap(label="Параметры", value=str(item.parameters)),
            DetailFieldMap(label="Результат", value=str(item.result_counts or {})),
            DetailFieldMap(label="Ошибка", value=item.error_category or "—"),
            DetailFieldMap(
                label="Создан",
                value=format_datetime(item.created_at, timezone(request)),
            ),
            DetailFieldMap(
                label="Завершён",
                value=format_datetime(item.finished_at, timezone(request)),
            ),
        ],
        back_url=f"{base}/pipeline/list",
    )


async def pipeline_run_provider(request: Request) -> OperationPageMap:
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    parse_limit, generation_limit, publishing_limit = (
        request.app.state.cabinet_pipeline_limits
    )
    return OperationPageMap(
        title="Запустить полный pipeline",
        description="Parse → filter → generate → publish выполняется Celery worker-ом.",
        actions=[
            OperationActionMap(
                key="run",
                label="Поставить полный pipeline",
                action_url=(
                    f"{base}/pipeline/enqueue"
                    f"?idempotency_key={secrets.token_urlsafe(18)}"
                ),
                confirmation="Поставить полный pipeline в очередь?",
                css_class="is-primary",
            )
        ],
        notices=[
            (
                f"Лимиты: parse={parse_limit}, generation={generation_limit}, "
                f"publishing={publishing_limit}."
            )
        ],
    )


class PipelineAdmin(CabinetAdmin):
    key = "pipeline"
    label = "Pipeline"
    icon = "↻"
    order = 70
    permission = "cabinet.view"
    sidebar = (
        *list_sidebar("Все запуски"),
        SidebarItem(
            key="run",
            label="Запустить",
            path="run",
            icon="+",
            order=20,
            permission="cabinet.view",
        ),
    )
    pages = (
        ListPage(key="list", label="Запуски", path="list", provider="list"),
        DetailPage(key="detail", label="Запуск", path="{run_id}", provider="detail"),
        OperationPage(
            key="run",
            label="Запустить pipeline",
            path="run",
            provider="run",
            order=5,
        ),
    )
    providers = {
        "list": pipeline_list_provider,
        "detail": pipeline_detail_provider,
        "run": pipeline_run_provider,
    }
    actions = (
        ActionRoute(path="enqueue", method="POST", handler="enqueue_pipeline"),
    )

    async def get_dashboard_context(self, request: Request) -> dict[str, object]:
        return module_context(request, self.key)

    async def enqueue_pipeline(self, request: Request) -> Response:
        parse_limit, generation_limit, publishing_limit = (
            request.app.state.cabinet_pipeline_limits
        )
        operation_service: CabinetOperationPort = (
            request.app.state.cabinet_operation_service
        )
        run = await operation_service.enqueue_full_pipeline(
            actor=session_actor(request),
            parse_limit=int(parse_limit),
            generation_limit=int(generation_limit),
            publishing_limit=int(publishing_limit),
            idempotency_key=query_value(request, "idempotency_key", max_length=128),
        )
        base = str(request.app.state.cabinet_mount_path).rstrip("/")
        return RedirectResponse(url=f"{base}/pipeline/{run.id}", status_code=303)
