"""Read-only AdminAuditLog list/detail adapter."""

from fastapi import HTTPException, Request
from fastapi_cabinet import CabinetAdmin
from fastapi_cabinet.contracts.pages import (
    DetailFieldMap,
    DetailPage,
    DetailPageMap,
    FilterFieldMap,
    ListPage,
    ListPageMap,
)
from fastapi_cabinet.contracts.widgets import TableColumnMap

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
    timezone,
)


async def audit_list_provider(request: Request) -> ListPageMap:
    page = requested_page(request)
    outcome = query_value(request, "outcome")
    action = query_value(request, "action")
    result = await request.app.state.cabinet_operational_reader.list_audit_logs(
        offset=(page - 1) * PAGE_SIZE,
        limit=PAGE_SIZE,
        outcome=outcome,
        action=action,
    )
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return ListPageMap(
        title="Административный аудит",
        columns=[
            TableColumnMap(key="action", label="Действие"),
            TableColumnMap(key="entity", label="Сущность"),
            TableColumnMap(key="outcome", label="Результат"),
            TableColumnMap(key="created", label="Время"),
        ],
        rows=[
            {
                "action": item.action,
                "entity": item.entity_type,
                "outcome": item.outcome,
                "created": format_datetime(item.created_at, timezone(request)),
                "_href": f"{base}/audit/{item.id}",
            }
            for item in result.items
        ],
        filters=[
            FilterFieldMap(name="action", label="Действие", value=action),
            FilterFieldMap(
                name="outcome",
                label="Результат",
                input_type="select",
                choices=choices(
                    (
                        ("", "Все"),
                        ("succeeded", "Succeeded"),
                        ("rejected", "Rejected"),
                        ("failed", "Failed"),
                    ),
                    selected=outcome,
                ),
            ),
        ],
        pagination=pagination(request, page=page, total=result.total),
        row_href_key="_href",
        empty_message="Записей аудита пока нет.",
    )


async def audit_detail_provider(request: Request) -> DetailPageMap:
    item = await request.app.state.cabinet_operational_reader.get_audit_log(
        parse_entity_id(request, "audit_id")
    )
    if item is None:
        raise HTTPException(status_code=404, detail="AdminAuditLog not found")
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return DetailPageMap(
        title=item.action,
        subtitle=str(item.id),
        fields=[
            DetailFieldMap(label="Actor", value=item.actor),
            DetailFieldMap(label="Сущность", value=item.entity_type),
            DetailFieldMap(label="Entity UUID", value=str(item.entity_id or "—")),
            DetailFieldMap(label="Результат", value=item.outcome),
            DetailFieldMap(label="Категория", value=item.detail or "—"),
            DetailFieldMap(
                label="Время",
                value=format_datetime(item.created_at, timezone(request)),
            ),
        ],
        back_url=f"{base}/audit/list",
    )


class AuditAdmin(CabinetAdmin):
    key = "audit"
    label = "Аудит"
    icon = "◇"
    order = 80
    permission = "cabinet.view"
    sidebar = list_sidebar("Все события")
    pages = (
        ListPage(key="list", label="Аудит", path="list", provider="list"),
        DetailPage(key="detail", label="Событие", path="{audit_id}", provider="detail"),
    )
    providers = {"list": audit_list_provider, "detail": audit_detail_provider}

    async def get_dashboard_context(self, request: Request) -> dict[str, object]:
        return module_context(request, self.key)
