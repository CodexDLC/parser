"""Read-only ErrorLog list/detail adapter."""

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
    entity_reader,
    format_datetime,
    list_sidebar,
    module_context,
    pagination,
    parse_entity_id,
    query_value,
    requested_page,
    timezone,
)

_SCOPE_CHOICES = (
    ("", "Все"),
    ("parser", "Парсер"),
    ("ai", "AI"),
    ("telegram", "Telegram"),
    ("celery", "Celery"),
    ("api", "API"),
)


async def errors_list_provider(request: Request) -> ListPageMap:
    page = requested_page(request)
    search = query_value(request, "q")
    scope = query_value(request, "scope")
    result = await entity_reader(request).list_errors(
        offset=(page - 1) * PAGE_SIZE,
        limit=PAGE_SIZE,
        search=search,
        scope=scope,
    )
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return ListPageMap(
        title="Ошибки",
        subtitle="Безопасный журнал parser, AI, Telegram, Celery и API.",
        columns=[
            TableColumnMap(key="scope", label="Зона"),
            TableColumnMap(key="message", label="Сообщение"),
            TableColumnMap(key="created", label="Время"),
        ],
        rows=[
            {
                "scope": item.scope,
                "message": item.message,
                "created": format_datetime(item.created_at, timezone(request)),
                "_href": f"{base}/errors/{item.id}",
            }
            for item in result.items
        ],
        filters=[
            FilterFieldMap(name="q", label="Поиск", input_type="search", value=search),
            FilterFieldMap(
                name="scope",
                label="Зона",
                input_type="select",
                choices=choices(_SCOPE_CHOICES, selected=scope),
            ),
        ],
        pagination=pagination(request, page=page, total=result.total),
        row_href_key="_href",
        empty_message="Ошибки не найдены.",
    )


async def error_detail_provider(request: Request) -> DetailPageMap:
    item = await entity_reader(request).get_error(parse_entity_id(request, "error_id"))
    if item is None:
        raise HTTPException(status_code=404, detail="ErrorLog not found")
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return DetailPageMap(
        title=item.message,
        subtitle=str(item.id),
        fields=[
            DetailFieldMap(label="Зона", value=item.scope),
            DetailFieldMap(label="Категория", value=item.details or "—"),
            DetailFieldMap(label="Source UUID", value=str(item.source_id or "—")),
            DetailFieldMap(label="News UUID", value=str(item.news_id or "—")),
            DetailFieldMap(label="Post UUID", value=str(item.post_id or "—")),
            DetailFieldMap(
                label="Время",
                value=format_datetime(item.created_at, timezone(request)),
            ),
        ],
        back_url=f"{base}/errors/list",
    )


class ErrorsAdmin(CabinetAdmin):
    key = "errors"
    label = "Ошибки"
    icon = "!"
    order = 60
    permission = "cabinet.view"
    sidebar = list_sidebar("Все ошибки")
    pages = (
        ListPage(key="list", label="Ошибки", path="list", provider="list"),
        DetailPage(key="detail", label="Ошибка", path="{error_id}", provider="detail"),
    )
    providers = {"list": errors_list_provider, "detail": error_detail_provider}

    async def get_dashboard_context(self, request: Request) -> dict[str, object]:
        return module_context(request, self.key)
