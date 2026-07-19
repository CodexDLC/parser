"""Read-only NewsItem list/detail adapter."""

import secrets

from fastapi import HTTPException, Request
from fastapi_cabinet import CabinetAdmin
from fastapi_cabinet.contracts.admin import ActionRoute
from fastapi_cabinet.contracts.pages import (
    DetailFieldMap,
    DetailPage,
    DetailPageMap,
    DetailSectionMap,
    FilterFieldMap,
    ListPage,
    ListPageMap,
    OperationActionMap,
    OperationPage,
    OperationPageMap,
    PageLinkMap,
)
from fastapi_cabinet.contracts.widgets import TableColumnMap
from starlette.responses import RedirectResponse, Response

from aibot.cabinet.operations import CabinetOperationPort
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
    session_actor,
    timezone,
)
from aibot.services.exceptions import EntityNotFoundError, InvalidNewsStateError

_STATUS_CHOICES = (
    ("", "Все"),
    ("new", "Новые"),
    ("filtered_out", "Отфильтрованы"),
    ("ready_for_generation", "Готовы"),
    ("generated", "Сгенерированы"),
    ("failed", "Ошибка"),
)


async def news_list_provider(request: Request) -> ListPageMap:
    page = requested_page(request)
    search = query_value(request, "q")
    status = query_value(request, "status")
    source_id = query_value(request, "source_id", max_length=36)
    result = await entity_reader(request).list_news(
        offset=(page - 1) * PAGE_SIZE,
        limit=PAGE_SIZE,
        search=search,
        status=status,
        source_id=source_id,
    )
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return ListPageMap(
        title="Новости",
        subtitle="Нормализованные материалы и их pipeline-статусы.",
        columns=[
            TableColumnMap(key="title", label="Заголовок"),
            TableColumnMap(key="source", label="Источник"),
            TableColumnMap(key="status", label="Статус"),
            TableColumnMap(key="published", label="Опубликовано"),
        ],
        rows=[
            {
                "title": item.title,
                "source": item.source_name,
                "status": item.status,
                "published": format_datetime(item.published_at, timezone(request)),
                "_href": f"{base}/news/{item.id}",
            }
            for item in result.items
        ],
        filters=[
            FilterFieldMap(name="q", label="Поиск", input_type="search", value=search),
            FilterFieldMap(
                name="status",
                label="Статус",
                input_type="select",
                choices=choices(_STATUS_CHOICES, selected=status),
            ),
            FilterFieldMap(
                name="source_id",
                label="UUID источника",
                value=source_id,
            ),
        ],
        pagination=pagination(request, page=page, total=result.total),
        row_href_key="_href",
        empty_message="Новости не найдены.",
    )


async def news_detail_provider(request: Request) -> DetailPageMap:
    item = await entity_reader(request).get_news(parse_entity_id(request, "news_id"))
    if item is None:
        raise HTTPException(status_code=404, detail="NewsItem not found")
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return DetailPageMap(
        title=item.title,
        subtitle=str(item.id),
        fields=[
            DetailFieldMap(label="Статус", value=item.status),
            DetailFieldMap(label="Источник", value=item.source_name),
            DetailFieldMap(label="URL", value=item.url or "—"),
            DetailFieldMap(
                label="Опубликовано",
                value=format_datetime(item.published_at, timezone(request)),
            ),
            DetailFieldMap(
                label="Получено",
                value=format_datetime(item.created_at, timezone(request)),
            ),
        ],
        sections=[
            DetailSectionMap(
                title="Содержание",
                fields=[
                    DetailFieldMap(label="Описание", value=item.summary),
                    DetailFieldMap(label="Исходный текст", value=item.raw_text or "—"),
                ],
            )
        ],
        actions=[
            PageLinkMap(label="Генерация", url=f"{base}/news/{item.id}/manage")
        ],
        back_url=f"{base}/news/list",
    )


async def news_manage_provider(request: Request) -> OperationPageMap:
    item = await entity_reader(request).get_news(parse_entity_id(request, "news_id"))
    if item is None:
        raise HTTPException(status_code=404, detail="NewsItem not found")
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    actions: list[OperationActionMap] = []
    notices: list[str] = []
    if item.status == "ready_for_generation":
        actions.append(
            OperationActionMap(
                key="generate",
                label="Поставить генерацию",
                action_url=(
                    f"{base}/news/{item.id}/generate"
                    f"?idempotency_key={secrets.token_urlsafe(18)}"
                ),
                confirmation="Отправить новость в AI-генерацию через Celery?",
                css_class="is-primary",
            )
        )
    else:
        notices.append("Генерация доступна только для ready_for_generation.")
    return OperationPageMap(
        title=f"Генерация: {item.title}",
        description="HTTP-запрос только ставит задачу; AI выполняется worker-ом.",
        actions=actions,
        notices=notices,
    )


class NewsAdmin(CabinetAdmin):
    key = "news"
    label = "Новости"
    icon = "▤"
    order = 40
    permission = "cabinet.view"
    sidebar = list_sidebar("Все новости")
    pages = (
        ListPage(key="list", label="Новости", path="list", provider="list"),
        DetailPage(key="detail", label="Новость", path="{news_id}", provider="detail"),
        OperationPage(
            key="manage",
            label="Генерация",
            path="{news_id}/manage",
            provider="manage",
        ),
    )
    providers = {
        "list": news_list_provider,
        "detail": news_detail_provider,
        "manage": news_manage_provider,
    }
    actions = (
        ActionRoute(path="{news_id}/generate", method="POST", handler="generate_news"),
    )

    async def get_dashboard_context(self, request: Request) -> dict[str, object]:
        return module_context(request, self.key)

    async def generate_news(self, request: Request) -> Response:
        news_id = parse_entity_id(request, "news_id")
        operation_service: CabinetOperationPort = (
            request.app.state.cabinet_operation_service
        )
        try:
            run = await operation_service.enqueue_news_generation(
                actor=session_actor(request),
                news_id=news_id,
                idempotency_key=query_value(request, "idempotency_key", max_length=128),
            )
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail="NewsItem not found") from exc
        except InvalidNewsStateError as exc:
            raise HTTPException(status_code=409, detail="NewsItem is not ready") from exc
        base = str(request.app.state.cabinet_mount_path).rstrip("/")
        return RedirectResponse(url=f"{base}/pipeline/{run.id}", status_code=303)
