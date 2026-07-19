"""Общие HTTP/Jinja helpers entity admins."""

import uuid
from collections.abc import Iterable
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request
from fastapi_cabinet.contracts.navigation import SidebarItem
from fastapi_cabinet.contracts.pages import (
    FilterChoiceMap,
    PaginationMap,
)

from aibot.cabinet.auth import CabinetSession
from aibot.cabinet.entity_read import CabinetEntityReader

PAGE_SIZE = 20


def entity_reader(request: Request) -> CabinetEntityReader:
    return request.app.state.cabinet_entity_reader


def requested_page(request: Request) -> int:
    try:
        return max(1, min(int(request.query_params.get("page", "1")), 10_000))
    except ValueError:
        return 1


def query_value(request: Request, name: str, *, max_length: int = 200) -> str:
    return request.query_params.get(name, "").strip()[:max_length]


def parse_entity_id(request: Request, parameter: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(request.path_params[parameter]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Cabinet entity not found") from exc


def parse_version(value: object) -> datetime:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail="Invalid entity version") from exc


def session_actor(request: Request) -> str:
    session = getattr(request.state, "cabinet_session", None)
    if not isinstance(session, CabinetSession):
        raise HTTPException(status_code=401, detail="Cabinet session required")
    return session.username


def pagination(
    request: Request,
    *,
    page: int,
    total: int,
    page_size: int = PAGE_SIZE,
) -> PaginationMap:
    pages = max(1, (total + page_size - 1) // page_size)
    return PaginationMap(
        page=page,
        pages=pages,
        total=total,
        previous_url=_page_url(request, page - 1) if page > 1 else None,
        next_url=_page_url(request, page + 1) if page < pages else None,
    )


def choices(
    values: Iterable[tuple[str, str]],
    *,
    selected: str,
) -> list[FilterChoiceMap]:
    return [
        FilterChoiceMap(value=value, label=label, selected=value == selected)
        for value, label in values
    ]


def format_datetime(value: datetime | None, timezone: str) -> str:
    if value is None:
        return "—"
    return value.astimezone(ZoneInfo(timezone)).strftime("%d.%m.%Y %H:%M")


def timezone(request: Request) -> str:
    return str(request.app.state.cabinet_timezone)


def list_sidebar(label: str) -> tuple[SidebarItem, ...]:
    return (
        SidebarItem(
            key="list",
            label=label,
            path="list",
            icon="≡",
            order=10,
            permission="cabinet.view",
        ),
    )


def module_context(request: Request, admin_key: str) -> dict[str, object]:
    mount = str(request.app.state.cabinet_mount_path).rstrip("/")
    return {"primary_url": f"{mount}/{admin_key}/list"}


def _page_url(request: Request, page: int) -> str:
    values = list(request.query_params.multi_items())
    values = [(key, value) for key, value in values if key != "page"]
    values.append(("page", str(page)))
    return f"{request.url.path}?{urlencode(values)}"
