"""Точка входа FastAPI-приложения и сборка HTTP API."""

from fastapi import FastAPI

from aibot.api.routers.generation import router as generation_router
from aibot.api.routers.health import router as health_router
from aibot.api.routers.keywords import router as keywords_router
from aibot.api.routers.logs import router as logs_router
from aibot.api.routers.news import router as news_router
from aibot.api.routers.posts import router as posts_router
from aibot.api.routers.sources import router as sources_router
from aibot.config import get_settings


def create_app() -> FastAPI:
    """Создать и настроить экземпляр FastAPI-приложения."""

    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(sources_router, prefix=settings.api_prefix)
    app.include_router(keywords_router, prefix=settings.api_prefix)
    app.include_router(news_router, prefix=settings.api_prefix)
    app.include_router(posts_router, prefix=settings.api_prefix)
    app.include_router(generation_router, prefix=settings.api_prefix)
    app.include_router(logs_router, prefix=settings.api_prefix)
    return app


app = create_app()
