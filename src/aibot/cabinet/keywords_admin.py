"""Read-only Keyword list/detail adapter."""

from fastapi import HTTPException, Request
from fastapi_cabinet import CabinetAdmin
from fastapi_cabinet.contracts.admin import ActionRoute
from fastapi_cabinet.contracts.pages import (
    DetailFieldMap,
    DetailPage,
    DetailPageMap,
    FilterFieldMap,
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

from aibot.api.schemas.keyword import KeywordCreate
from aibot.cabinet.mutations import (
    CabinetMutationPort,
    ConcurrentEntityUpdateError,
)
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


async def keywords_list_provider(request: Request) -> ListPageMap:
    page = requested_page(request)
    search = query_value(request, "q")
    enabled = query_value(request, "enabled")
    result = await entity_reader(request).list_keywords(
        offset=(page - 1) * PAGE_SIZE,
        limit=PAGE_SIZE,
        search=search,
        enabled=enabled,
    )
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return ListPageMap(
        title="Ключевые слова",
        subtitle="Правила тематической фильтрации новостей.",
        columns=[
            TableColumnMap(key="word", label="Слово"),
            TableColumnMap(key="enabled", label="Активно"),
            TableColumnMap(key="created", label="Создано"),
        ],
        rows=[
            {
                "word": item.word,
                "enabled": "Да" if item.enabled else "Нет",
                "created": format_datetime(item.created_at, timezone(request)),
                "_href": f"{base}/keywords/{item.id}",
            }
            for item in result.items
        ],
        filters=[
            FilterFieldMap(name="q", label="Поиск", input_type="search", value=search),
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
        create_url=f"{base}/keywords/new",
        create_label="Добавить слово",
        empty_message="Ключевые слова не найдены.",
    )


async def keyword_detail_provider(request: Request) -> DetailPageMap:
    item = await entity_reader(request).get_keyword(parse_entity_id(request, "keyword_id"))
    if item is None:
        raise HTTPException(status_code=404, detail="Keyword not found")
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return DetailPageMap(
        title=item.word,
        subtitle=str(item.id),
        fields=[
            DetailFieldMap(label="Активно", value="Да" if item.enabled else "Нет"),
            DetailFieldMap(
                label="Создано",
                value=format_datetime(item.created_at, timezone(request)),
            ),
        ],
        actions=[
            PageLinkMap(label="Изменить", url=f"{base}/keywords/{item.id}/edit"),
            PageLinkMap(label="Управление", url=f"{base}/keywords/{item.id}/manage"),
        ],
        back_url=f"{base}/keywords/list",
    )


async def keyword_create_form_provider(request: Request) -> FormPageMap:
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return FormPageMap(
        title="Новое ключевое слово",
        action_url=f"{base}/keywords/create",
        fields=[
            FormFieldMap(name="word", label="Слово", required=True),
            FormFieldMap(
                name="enabled",
                label="Активно",
                input_type="checkbox",
                value=True,
            ),
        ],
        submit_label="Создать",
        cancel_url=f"{base}/keywords/list",
        errors=_form_errors(request),
    )


async def keyword_edit_form_provider(request: Request) -> FormPageMap:
    item = await entity_reader(request).get_keyword(parse_entity_id(request, "keyword_id"))
    if item is None:
        raise HTTPException(status_code=404, detail="Keyword not found")
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    return FormPageMap(
        title=f"Изменить: {item.word}",
        action_url=f"{base}/keywords/{item.id}/update",
        method="PATCH",
        fields=[
            FormFieldMap(
                name="expected_updated_at",
                label="Version",
                input_type="hidden",
                value=item.updated_at.isoformat(),
            ),
            FormFieldMap(name="word", label="Слово", value=item.word, required=True),
            FormFieldMap(
                name="enabled",
                label="Активно",
                input_type="checkbox",
                value=item.enabled,
            ),
        ],
        submit_label="Сохранить",
        cancel_url=f"{base}/keywords/{item.id}",
        errors=_form_errors(request),
    )


async def keyword_manage_provider(request: Request) -> OperationPageMap:
    item = await entity_reader(request).get_keyword(parse_entity_id(request, "keyword_id"))
    if item is None:
        raise HTTPException(status_code=404, detail="Keyword not found")
    base = str(request.app.state.cabinet_mount_path).rstrip("/")
    label = "Отключить" if item.enabled else "Включить"
    return OperationPageMap(
        title=f"Управление: {item.word}",
        actions=[
            OperationActionMap(
                key="toggle",
                label=label,
                action_url=f"{base}/keywords/{item.id}/toggle",
                confirmation=f"{label} ключевое слово?",
                css_class="is-danger" if item.enabled else "is-primary",
            )
        ],
        notices=[f"Версия: {item.updated_at.isoformat()}"],
    )


def _form_errors(request: Request) -> list[str]:
    codes = {
        "validation": "Проверьте обязательные поля.",
        "duplicate": "Такое ключевое слово уже существует.",
        "stale": "Ключевое слово уже изменено. Откройте форму повторно.",
    }
    error = request.query_params.get("error", "")
    return [codes[error]] if error in codes else []


def _mutation(request: Request) -> CabinetMutationPort:
    return request.app.state.cabinet_mutation_service


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


class KeywordsAdmin(CabinetAdmin):
    key = "keywords"
    label = "Ключевые слова"
    icon = "#"
    order = 30
    permission = "cabinet.view"
    sidebar = list_sidebar("Все слова")
    pages = (
        ListPage(key="list", label="Ключевые слова", path="list", provider="list"),
        DetailPage(
            key="detail",
            label="Ключевое слово",
            path="{keyword_id}",
            provider="detail",
        ),
        FormPage(
            key="create",
            label="Новое слово",
            path="new",
            provider="create_form",
        ),
        FormPage(
            key="edit",
            label="Изменить слово",
            path="{keyword_id}/edit",
            provider="edit_form",
        ),
        OperationPage(
            key="manage",
            label="Управление словом",
            path="{keyword_id}/manage",
            provider="manage",
        ),
    )
    providers = {
        "list": keywords_list_provider,
        "detail": keyword_detail_provider,
        "create_form": keyword_create_form_provider,
        "edit_form": keyword_edit_form_provider,
        "manage": keyword_manage_provider,
    }
    actions = (
        ActionRoute(path="create", method="POST", handler="create_keyword"),
        ActionRoute(path="{keyword_id}/update", method="POST", handler="update_keyword"),
        ActionRoute(path="{keyword_id}/toggle", method="POST", handler="toggle_keyword"),
    )

    async def get_dashboard_context(self, request: Request) -> dict[str, object]:
        return module_context(request, self.key)

    async def create_keyword(self, request: Request) -> Response:
        form = await request.form()
        base = str(request.app.state.cabinet_mount_path).rstrip("/")
        try:
            payload = KeywordCreate.model_validate(
                {
                    "word": form.get("word"),
                    "enabled": form.get("enabled") == "1",
                }
            )
            entity_id = await _mutation(request).create_keyword(
                actor=session_actor(request),
                word=payload.word,
                enabled=payload.enabled,
            )
        except ValidationError:
            return _redirect(f"{base}/keywords/new?error=validation")
        except EntityAlreadyExistsError:
            return _redirect(f"{base}/keywords/new?error=duplicate")
        return _redirect(f"{base}/keywords/{entity_id}")

    async def update_keyword(self, request: Request) -> Response:
        keyword_id = parse_entity_id(request, "keyword_id")
        form = await request.form()
        base = str(request.app.state.cabinet_mount_path).rstrip("/")
        try:
            payload = KeywordCreate.model_validate(
                {
                    "word": form.get("word"),
                    "enabled": form.get("enabled") == "1",
                }
            )
            await _mutation(request).update_keyword(
                actor=session_actor(request),
                keyword_id=keyword_id,
                expected_updated_at=parse_version(form.get("expected_updated_at")),
                word=payload.word,
                enabled=payload.enabled,
            )
        except ValidationError:
            return _redirect(f"{base}/keywords/{keyword_id}/edit?error=validation")
        except EntityAlreadyExistsError:
            return _redirect(f"{base}/keywords/{keyword_id}/edit?error=duplicate")
        except ConcurrentEntityUpdateError:
            return _redirect(f"{base}/keywords/{keyword_id}/edit?error=stale")
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Keyword not found") from exc
        return _redirect(f"{base}/keywords/{keyword_id}")

    async def toggle_keyword(self, request: Request) -> Response:
        keyword_id = parse_entity_id(request, "keyword_id")
        item = await entity_reader(request).get_keyword(keyword_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Keyword not found")
        try:
            await _mutation(request).toggle_keyword(
                actor=session_actor(request),
                keyword_id=keyword_id,
                expected_updated_at=item.updated_at,
            )
        except ConcurrentEntityUpdateError:
            raise HTTPException(status_code=409, detail="Keyword was changed") from None
        base = str(request.app.state.cabinet_mount_path).rstrip("/")
        return _redirect(f"{base}/keywords/{keyword_id}")
