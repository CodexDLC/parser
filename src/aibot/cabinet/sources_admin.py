"""Read-only Source list/detail adapter."""

import secrets

from fastapi import HTTPException, Request
from fastapi_cabinet import CabinetAdmin
from fastapi_cabinet.contracts.admin import ActionRoute
from fastapi_cabinet.contracts.pages import (
    DetailFieldMap,
    DetailPage,
    DetailPageMap,
    FilterFieldMap,
    FormChoiceMap,
    FormFieldMap,
    FormPage,
    FormPageMap,
    ListPage,
    ListPageMap,
    OperationActionMap,
    OperationPage,
    OperationPageMap,
    PageLinkMap,
)
from fastapi_cabinet.contracts.widgets import TableColumnMap
from pydantic import ValidationError
from starlette.responses import RedirectResponse, Response

from aibot.api.schemas.source import SourceCreate
from aibot.cabinet.mutations import (
    CabinetMutationPort,
    ConcurrentEntityUpdateError,
)
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
    parse_version,
    query_value,
    requested_page,
    session_actor,
    timezone,
)
from aibot.services.exceptions import EntityAlreadyExistsError, EntityNotFoundError


async def sources_list_provider(request: Request) -> ListPageMap:
    page = requested_page(request)
    search = query_value(request, "q")
    source_type = query_value(request, "type")
    enabled = query_value(request, "enabled")
    result = await entity_reader(request).list_sources(
        offset=(page - 1) * PAGE_SIZE,
        limit=PAGE_SIZE,
        search=search,
        source_type=source_type,
        enabled=enabled,
    )
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return ListPageMap(
        title="Источники",
        subtitle="RSS/Atom-ленты и публичные Telegram-каналы.",
        columns=[
            TableColumnMap(key="name", label="Название"),
            TableColumnMap(key="type", label="Тип"),
            TableColumnMap(key="enabled", label="Активен"),
            TableColumnMap(key="updated", label="Обновлён"),
        ],
        rows=[
            {
                "name": item.name,
                "type": "Сайт" if item.type == "site" else "Telegram",
                "enabled": "Да" if item.enabled else "Нет",
                "updated": format_datetime(item.updated_at, timezone(request)),
                "_href": f"{base}/sources/{item.id}",
            }
            for item in result.items
        ],
        filters=[
            FilterFieldMap(name="q", label="Поиск", input_type="search", value=search),
            FilterFieldMap(
                name="type",
                label="Тип",
                input_type="select",
                choices=choices(
                    (("", "Все"), ("site", "Сайт"), ("tg", "Telegram")),
                    selected=source_type,
                ),
            ),
            FilterFieldMap(
                name="enabled",
                label="Активность",
                input_type="select",
                choices=choices(
                    (("", "Все"), ("true", "Активные"), ("false", "Отключённые")),
                    selected=enabled,
                ),
            ),
        ],
        pagination=pagination(request, page=page, total=result.total),
        row_href_key="_href",
        create_url=f"{base}/sources/new",
        create_label="Добавить источник",
        empty_message="Источники не найдены.",
    )


async def source_detail_provider(request: Request) -> DetailPageMap:
    item = await entity_reader(request).get_source(parse_entity_id(request, "source_id"))
    if item is None:
        raise HTTPException(status_code=404, detail="Source not found")
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return DetailPageMap(
        title=item.name,
        subtitle=str(item.id),
        fields=[
            DetailFieldMap(label="Тип", value="Сайт" if item.type == "site" else "Telegram"),
            DetailFieldMap(label="URL / канал", value=item.url),
            DetailFieldMap(label="Активен", value="Да" if item.enabled else "Нет"),
            DetailFieldMap(
                label="Создан",
                value=format_datetime(item.created_at, timezone(request)),
            ),
            DetailFieldMap(
                label="Обновлён",
                value=format_datetime(item.updated_at, timezone(request)),
            ),
        ],
        actions=[
            PageLinkMap(label="Изменить", url=f"{base}/sources/{item.id}/edit"),
            PageLinkMap(label="Управление", url=f"{base}/sources/{item.id}/manage"),
        ],
        back_url=f"{base}/sources/list",
    )


async def source_create_form_provider(request: Request) -> FormPageMap:
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return FormPageMap(
        title="Новый источник",
        action_url=f"{base}/sources/create",
        fields=[
            FormFieldMap(
                name="type",
                label="Тип",
                input_type="select",
                choices=[
                    FormChoiceMap(value="site", label="Сайт", selected=True),
                    FormChoiceMap(value="tg", label="Telegram"),
                ],
                required=True,
            ),
            FormFieldMap(name="name", label="Название", required=True),
            FormFieldMap(name="url", label="URL / канал", required=True),
            FormFieldMap(
                name="enabled",
                label="Активен",
                input_type="checkbox",
                value=True,
            ),
        ],
        submit_label="Создать",
        cancel_url=f"{base}/sources/list",
        errors=_form_errors(request),
    )


async def source_edit_form_provider(request: Request) -> FormPageMap:
    item = await entity_reader(request).get_source(parse_entity_id(request, "source_id"))
    if item is None:
        raise HTTPException(status_code=404, detail="Source not found")
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return FormPageMap(
        title=f"Изменить: {item.name}",
        action_url=f"{base}/sources/{item.id}/update",
        method="PATCH",
        fields=[
            FormFieldMap(
                name="expected_updated_at",
                label="Version",
                input_type="hidden",
                value=item.updated_at.isoformat(),
            ),
            FormFieldMap(
                name="type",
                label="Тип",
                input_type="select",
                choices=[
                    FormChoiceMap(
                        value="site",
                        label="Сайт",
                        selected=item.type == "site",
                    ),
                    FormChoiceMap(
                        value="tg",
                        label="Telegram",
                        selected=item.type == "tg",
                    ),
                ],
                required=True,
            ),
            FormFieldMap(name="name", label="Название", value=item.name, required=True),
            FormFieldMap(name="url", label="URL / канал", value=item.url, required=True),
            FormFieldMap(
                name="enabled",
                label="Активен",
                input_type="checkbox",
                value=item.enabled,
            ),
        ],
        submit_label="Сохранить",
        cancel_url=f"{base}/sources/{item.id}",
        errors=_form_errors(request),
    )


async def source_manage_provider(request: Request) -> OperationPageMap:
    item = await entity_reader(request).get_source(parse_entity_id(request, "source_id"))
    if item is None:
        raise HTTPException(status_code=404, detail="Source not found")
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    label = "Отключить" if item.enabled else "Включить"
    return OperationPageMap(
        title=f"Управление: {item.name}",
        description="Изменение активности влияет на автоматический parsing pipeline.",
        actions=[
            OperationActionMap(
                key="parse",
                label="Запустить парсинг",
                action_url=(
                    f"{base}/sources/{item.id}/parse"
                    f"?idempotency_key={secrets.token_urlsafe(18)}"
                ),
                confirmation="Поставить парсинг источника в Celery?",
                css_class="is-primary",
            ),
            OperationActionMap(
                key="toggle",
                label=label,
                action_url=f"{base}/sources/{item.id}/toggle",
                confirmation=f"{label} источник?",
                css_class="is-danger" if item.enabled else "is-primary",
            )
        ],
        notices=[f"Версия: {item.updated_at.isoformat()}"],
    )


def _form_errors(request: Request) -> list[str]:
    codes = {
        "validation": "Проверьте обязательные поля.",
        "duplicate": "Источник с таким типом и URL уже существует.",
        "stale": "Источник уже изменён. Откройте форму повторно.",
    }
    error = request.query_params.get("error", "")
    return [codes[error]] if error in codes else []


def _mutation(request: Request) -> CabinetMutationPort:
    return request.app.state.cabinet_mutation_service


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


class SourcesAdmin(CabinetAdmin):
    key = "sources"
    label = "Источники"
    icon = "◎"
    order = 20
    permission = "cabinet.view"
    sidebar = list_sidebar("Все источники")
    pages = (
        ListPage(
            key="list",
            label="Источники",
            path="list",
            provider="list",
            order=10,
        ),
        DetailPage(
            key="detail",
            label="Источник",
            path="{source_id}",
            provider="detail",
            order=20,
        ),
        FormPage(
            key="create",
            label="Новый источник",
            path="new",
            provider="create_form",
            order=30,
        ),
        FormPage(
            key="edit",
            label="Изменить источник",
            path="{source_id}/edit",
            provider="edit_form",
            order=40,
        ),
        OperationPage(
            key="manage",
            label="Управление источником",
            path="{source_id}/manage",
            provider="manage",
            order=50,
        ),
    )
    providers = {
        "list": sources_list_provider,
        "detail": source_detail_provider,
        "create_form": source_create_form_provider,
        "edit_form": source_edit_form_provider,
        "manage": source_manage_provider,
    }
    actions = (
        ActionRoute(path="create", method="POST", handler="create_source"),
        ActionRoute(path="{source_id}/update", method="POST", handler="update_source"),
        ActionRoute(path="{source_id}/toggle", method="POST", handler="toggle_source"),
        ActionRoute(path="{source_id}/parse", method="POST", handler="parse_source"),
    )

    async def get_dashboard_context(self, request: Request) -> dict[str, object]:
        return module_context(request, self.key)

    async def create_source(self, request: Request) -> Response:
        form = await request.form()
        base = str(request.app.state.cabinet_mount_path).rstrip("/")
        try:
            payload = SourceCreate.model_validate(
                {
                    "type": form.get("type"),
                    "name": form.get("name"),
                    "url": form.get("url"),
                    "enabled": form.get("enabled") == "1",
                }
            )
            entity_id = await _mutation(request).create_source(
                actor=session_actor(request),
                source_type=payload.type.value,
                name=payload.name,
                url=payload.url,
                enabled=payload.enabled,
            )
        except ValidationError:
            return _redirect(f"{base}/sources/new?error=validation")
        except (EntityAlreadyExistsError, ValueError):
            return _redirect(f"{base}/sources/new?error=duplicate")
        return _redirect(f"{base}/sources/{entity_id}")

    async def update_source(self, request: Request) -> Response:
        source_id = parse_entity_id(request, "source_id")
        form = await request.form()
        base = str(request.app.state.cabinet_mount_path).rstrip("/")
        try:
            payload = SourceCreate.model_validate(
                {
                    "type": form.get("type"),
                    "name": form.get("name"),
                    "url": form.get("url"),
                    "enabled": form.get("enabled") == "1",
                }
            )
            await _mutation(request).update_source(
                actor=session_actor(request),
                source_id=source_id,
                expected_updated_at=parse_version(form.get("expected_updated_at")),
                source_type=payload.type.value,
                name=payload.name,
                url=payload.url,
                enabled=payload.enabled,
            )
        except ValidationError:
            return _redirect(f"{base}/sources/{source_id}/edit?error=validation")
        except EntityAlreadyExistsError:
            return _redirect(f"{base}/sources/{source_id}/edit?error=duplicate")
        except ConcurrentEntityUpdateError:
            return _redirect(f"{base}/sources/{source_id}/edit?error=stale")
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Source not found") from exc
        return _redirect(f"{base}/sources/{source_id}")

    async def toggle_source(self, request: Request) -> Response:
        source_id = parse_entity_id(request, "source_id")
        item = await entity_reader(request).get_source(source_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Source not found")
        try:
            await _mutation(request).toggle_source(
                actor=session_actor(request),
                source_id=source_id,
                expected_updated_at=item.updated_at,
            )
        except ConcurrentEntityUpdateError:
            raise HTTPException(status_code=409, detail="Source was changed") from None
        base = str(request.app.state.cabinet_mount_path).rstrip("/")
        return _redirect(f"{base}/sources/{source_id}")

    async def parse_source(self, request: Request) -> Response:
        source_id = parse_entity_id(request, "source_id")
        operation_service: CabinetOperationPort = (
            request.app.state.cabinet_operation_service
        )
        run = await operation_service.enqueue_source_parse(
            actor=session_actor(request),
            source_id=source_id,
            limit=int(request.app.state.cabinet_pipeline_limits[0]),
            idempotency_key=query_value(request, "idempotency_key", max_length=128),
        )
        base = str(request.app.state.cabinet_mount_path).rstrip("/")
        return _redirect(f"{base}/pipeline/{run.id}")
