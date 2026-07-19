"""Read-only Post list/detail adapter."""

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
from aibot.services.exceptions import EntityNotFoundError, InvalidPostStateError

_STATUS_CHOICES = (
    ("", "Все"),
    ("new", "Новые"),
    ("generated", "Сгенерированы"),
    ("publishing", "Публикуются"),
    ("published", "Опубликованы"),
    ("failed", "Ошибка"),
)


async def posts_list_provider(request: Request) -> ListPageMap:
    page = requested_page(request)
    search = query_value(request, "q")
    status = query_value(request, "status")
    result = await entity_reader(request).list_posts(
        offset=(page - 1) * PAGE_SIZE,
        limit=PAGE_SIZE,
        search=search,
        status=status,
    )
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return ListPageMap(
        title="Посты",
        subtitle="AI-тексты и состояние Telegram-публикации.",
        columns=[
            TableColumnMap(key="news", label="Новость"),
            TableColumnMap(key="status", label="Статус"),
            TableColumnMap(key="updated", label="Обновлён"),
        ],
        rows=[
            {
                "news": item.news_title,
                "status": item.status,
                "updated": format_datetime(item.updated_at, timezone(request)),
                "_href": f"{base}/posts/{item.id}",
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
        ],
        pagination=pagination(request, page=page, total=result.total),
        row_href_key="_href",
        empty_message="Посты не найдены.",
    )


async def post_detail_provider(request: Request) -> DetailPageMap:
    item = await entity_reader(request).get_post(parse_entity_id(request, "post_id"))
    if item is None:
        raise HTTPException(status_code=404, detail="Post not found")
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return DetailPageMap(
        title=item.news_title,
        subtitle=str(item.id),
        fields=[
            DetailFieldMap(label="Статус", value=item.status),
            DetailFieldMap(label="News UUID", value=str(item.news_id)),
            DetailFieldMap(
                label="Опубликовано",
                value=format_datetime(item.published_at, timezone(request)),
            ),
            DetailFieldMap(label="Telegram message ID", value=item.telegram_message_id or "—"),
            DetailFieldMap(
                label="Обновлён",
                value=format_datetime(item.updated_at, timezone(request)),
            ),
        ],
        sections=[
            DetailSectionMap(
                title="Текст поста",
                fields=[DetailFieldMap(label="Preview", value=item.generated_text)],
            ),
            DetailSectionMap(
                title="Последняя ошибка",
                fields=[DetailFieldMap(label="Сообщение", value=item.error_message or "—")],
            ),
        ],
        actions=[
            PageLinkMap(label="Публикация", url=f"{base}/posts/{item.id}/manage")
        ],
        back_url=f"{base}/posts/list",
    )


async def post_manage_provider(request: Request) -> OperationPageMap:
    item = await entity_reader(request).get_post(parse_entity_id(request, "post_id"))
    if item is None:
        raise HTTPException(status_code=404, detail="Post not found")
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    actions: list[OperationActionMap] = []
    notices = [
        (
            "Включён Telegram dry-run: сообщение не будет отправлено."
            if request.app.state.cabinet_telegram_dry_run
            else "ВНИМАНИЕ: сообщение будет реально отправлено в целевой Telegram-канал."
        )
    ]
    if item.status == "generated":
        actions.append(
            OperationActionMap(
                key="publish",
                label="Подтвердить публикацию",
                action_url=(
                    f"{base}/posts/{item.id}/publish"
                    f"?idempotency_key={secrets.token_urlsafe(18)}"
                ),
                description=item.generated_text,
                confirmation="Подтвердить отправку этого текста в Telegram?",
                css_class="is-danger",
            )
        )
    else:
        notices.append("Публикация доступна только для статуса generated.")
    return OperationPageMap(
        title=f"Публикация: {item.news_title}",
        description="Текст показан ниже как escaped plain text.",
        actions=actions,
        notices=notices,
    )


class PostsAdmin(CabinetAdmin):
    key = "posts"
    label = "Посты"
    icon = "▣"
    order = 50
    permission = "cabinet.view"
    sidebar = list_sidebar("Все посты")
    pages = (
        ListPage(key="list", label="Посты", path="list", provider="list"),
        DetailPage(key="detail", label="Пост", path="{post_id}", provider="detail"),
        OperationPage(
            key="manage",
            label="Публикация",
            path="{post_id}/manage",
            provider="manage",
        ),
    )
    providers = {
        "list": posts_list_provider,
        "detail": post_detail_provider,
        "manage": post_manage_provider,
    }
    actions = (
        ActionRoute(path="{post_id}/publish", method="POST", handler="publish_post"),
    )

    async def get_dashboard_context(self, request: Request) -> dict[str, object]:
        return module_context(request, self.key)

    async def publish_post(self, request: Request) -> Response:
        post_id = parse_entity_id(request, "post_id")
        operation_service: CabinetOperationPort = (
            request.app.state.cabinet_operation_service
        )
        try:
            run = await operation_service.enqueue_post_publication(
                actor=session_actor(request),
                post_id=post_id,
                idempotency_key=query_value(request, "idempotency_key", max_length=128),
            )
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Post not found") from exc
        except InvalidPostStateError as exc:
            raise HTTPException(status_code=409, detail="Post is not publishable") from exc
        base = str(request.app.state.cabinet_mount_path).rstrip("/")
        return RedirectResponse(url=f"{base}/pipeline/{run.id}", status_code=303)
