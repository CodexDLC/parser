"""Declarative read-only overview кабинета."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Request
from fastapi_cabinet import CabinetAdmin
from fastapi_cabinet.contracts.widgets import (
    ChartDatasetMap,
    ChartWidget,
    ChartWidgetMap,
    MetricWidget,
    MetricWidgetMap,
    TableColumnMap,
    TableWidget,
    TableWidgetMap,
)

from aibot.cabinet.dashboard import CabinetDashboardReader, CabinetDashboardSnapshot

_REQUEST_SNAPSHOT_KEY = "m4_cabinet_dashboard_snapshot"
_NEWS_STATUS_LABELS = {
    "new": "Новые",
    "filtered_out": "Отфильтрованы",
    "ready_for_generation": "Готовы",
    "generated": "Сгенерированы",
    "failed": "Ошибка",
}
_POST_STATUS_LABELS = {
    "new": "Новый",
    "generated": "Сгенерирован",
    "publishing": "Публикуется",
    "published": "Опубликован",
    "failed": "Ошибка",
}
_ERROR_SCOPE_LABELS = {
    "parser": "Парсер",
    "ai": "AI",
    "telegram": "Telegram",
    "celery": "Celery",
    "api": "API",
}


async def _snapshot(request: Request) -> CabinetDashboardSnapshot:
    cached = getattr(request.state, _REQUEST_SNAPSHOT_KEY, None)
    if isinstance(cached, CabinetDashboardSnapshot):
        return cached
    service: CabinetDashboardReader = request.app.state.cabinet_dashboard_service
    loaded = await service.load_overview()
    setattr(request.state, _REQUEST_SNAPSHOT_KEY, loaded)
    return loaded


def _metric(
    *,
    key: str,
    title: str,
    value: int,
    icon: str,
    available: bool,
) -> MetricWidgetMap:
    return MetricWidgetMap(
        key=key,
        title=title,
        value=str(value) if available else "—",
        subtitle=None if available else "PostgreSQL недоступен",
        icon=icon,
    )


async def active_sources_provider(request: Request) -> MetricWidgetMap:
    snapshot = await _snapshot(request)
    return _metric(
        key="active_sources",
        title="Активные источники",
        value=snapshot.metrics.active_sources,
        icon="◉",
        available=snapshot.database_available,
    )


async def news_today_provider(request: Request) -> MetricWidgetMap:
    snapshot = await _snapshot(request)
    return _metric(
        key="news_today",
        title="Новостей сегодня",
        value=snapshot.metrics.news_today,
        icon="▤",
        available=snapshot.database_available,
    )


async def ready_news_provider(request: Request) -> MetricWidgetMap:
    snapshot = await _snapshot(request)
    return _metric(
        key="ready_news",
        title="Готовы к генерации",
        value=snapshot.metrics.ready_for_generation,
        icon="◇",
        available=snapshot.database_available,
    )


async def posts_total_provider(request: Request) -> MetricWidgetMap:
    snapshot = await _snapshot(request)
    return _metric(
        key="posts_total",
        title="Всего постов",
        value=snapshot.metrics.posts_total,
        icon="▣",
        available=snapshot.database_available,
    )


async def published_today_provider(request: Request) -> MetricWidgetMap:
    snapshot = await _snapshot(request)
    return _metric(
        key="published_today",
        title="Опубликовано сегодня",
        value=snapshot.metrics.published_today,
        icon="✓",
        available=snapshot.database_available,
    )


async def errors_24h_provider(request: Request) -> MetricWidgetMap:
    snapshot = await _snapshot(request)
    return _metric(
        key="errors_24h",
        title="Ошибок за 24 часа",
        value=snapshot.metrics.errors_24h,
        icon="!",
        available=snapshot.database_available,
    )


async def news_status_chart_provider(request: Request) -> ChartWidgetMap:
    snapshot = await _snapshot(request)
    statuses = tuple(snapshot.news_by_status)
    return ChartWidgetMap(
        key="news_statuses",
        title="Новости по статусам",
        chart_type="doughnut",
        labels=[_NEWS_STATUS_LABELS.get(status, status) for status in statuses],
        datasets=[
            ChartDatasetMap(
                label="Новости",
                data=[float(snapshot.news_by_status[status]) for status in statuses],
                color="#315c4d",
            )
        ],
        height=240,
        span=2,
    )


async def published_chart_provider(request: Request) -> ChartWidgetMap:
    snapshot = await _snapshot(request)
    days = tuple(snapshot.published_by_day)
    return ChartWidgetMap(
        key="published_series",
        title="Публикации за 7 дней",
        chart_type="bar",
        labels=[day.strftime("%d.%m") for day in days],
        datasets=[
            ChartDatasetMap(
                label="Опубликовано",
                data=[float(snapshot.published_by_day[day]) for day in days],
                color="#b66a3c",
            )
        ],
        height=240,
        span=2,
    )


async def recent_posts_provider(request: Request) -> TableWidgetMap:
    snapshot = await _snapshot(request)
    return TableWidgetMap(
        key="recent_posts",
        title="Последние посты",
        columns=[
            TableColumnMap(key="title", label="Новость"),
            TableColumnMap(key="status", label="Статус"),
            TableColumnMap(key="updated", label="Обновлён"),
        ],
        rows=[
            {
                "title": post.news_title,
                "status": _POST_STATUS_LABELS.get(post.status, post.status),
                "updated": _format_datetime(post.updated_at, snapshot.timezone),
            }
            for post in snapshot.recent_posts
        ],
        empty_message="Постов пока нет.",
        span=2,
    )


async def recent_errors_provider(request: Request) -> TableWidgetMap:
    snapshot = await _snapshot(request)
    return TableWidgetMap(
        key="recent_errors",
        title="Последние ошибки",
        columns=[
            TableColumnMap(key="scope", label="Зона"),
            TableColumnMap(key="message", label="Сообщение"),
            TableColumnMap(key="created", label="Время"),
        ],
        rows=[
            {
                "scope": _ERROR_SCOPE_LABELS.get(error.scope, error.scope),
                "message": error.message,
                "created": _format_datetime(error.created_at, snapshot.timezone),
            }
            for error in snapshot.recent_errors
        ],
        empty_message="Ошибок нет.",
        span=2,
    )


async def health_provider(request: Request) -> TableWidgetMap:
    snapshot = await _snapshot(request)
    return TableWidgetMap(
        key="passive_health",
        title="Состояние сервисов",
        columns=[
            TableColumnMap(key="service", label="Сервис"),
            TableColumnMap(key="status", label="Статус"),
            TableColumnMap(key="detail", label="Проверка"),
        ],
        rows=[
            {
                "service": check.service,
                "status": check.status,
                "detail": check.detail,
            }
            for check in snapshot.health
        ],
        empty_message="Статусы недоступны.",
        span=4,
    )


def _format_datetime(value: datetime, timezone: str) -> str:
    return value.astimezone(ZoneInfo(timezone)).strftime("%d.%m.%Y %H:%M")


class OverviewAdmin(CabinetAdmin):
    """Read-only dashboard единственного оператора."""

    key = "overview"
    label = "Обзор"
    icon = "▦"
    order = 10
    permission = "cabinet.view"
    dashboard_widgets = (
        MetricWidget(
            key="active_sources",
            title="Активные источники",
            provider="active_sources",
            order=10,
        ),
        MetricWidget(
            key="news_today",
            title="Новостей сегодня",
            provider="news_today",
            order=20,
        ),
        MetricWidget(
            key="ready_news",
            title="Готовы к генерации",
            provider="ready_news",
            order=30,
        ),
        MetricWidget(
            key="posts_total",
            title="Всего постов",
            provider="posts_total",
            order=40,
        ),
        MetricWidget(
            key="published_today",
            title="Опубликовано сегодня",
            provider="published_today",
            order=50,
        ),
        MetricWidget(
            key="errors_24h",
            title="Ошибок за 24 часа",
            provider="errors_24h",
            order=60,
        ),
        ChartWidget(
            key="news_statuses",
            title="Новости по статусам",
            provider="news_status_chart",
            chart_type="doughnut",
            order=70,
            span=2,
        ),
        ChartWidget(
            key="published_series",
            title="Публикации за 7 дней",
            provider="published_chart",
            chart_type="bar",
            order=80,
            span=2,
        ),
        TableWidget(
            key="recent_posts",
            title="Последние посты",
            provider="recent_posts",
            order=90,
            span=2,
        ),
        TableWidget(
            key="recent_errors",
            title="Последние ошибки",
            provider="recent_errors",
            order=100,
            span=2,
        ),
        TableWidget(
            key="passive_health",
            title="Состояние сервисов",
            provider="health",
            order=110,
            span=4,
        ),
    )
    providers = {
        "active_sources": active_sources_provider,
        "news_today": news_today_provider,
        "ready_news": ready_news_provider,
        "posts_total": posts_total_provider,
        "published_today": published_today_provider,
        "errors_24h": errors_24h_provider,
        "news_status_chart": news_status_chart_provider,
        "published_chart": published_chart_provider,
        "recent_posts": recent_posts_provider,
        "recent_errors": recent_errors_provider,
        "health": health_provider,
    }
