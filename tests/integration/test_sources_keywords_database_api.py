"""Интеграционные тесты CRUD API через реальную PostgreSQL-БД."""

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError, OperationalError

from aibot.db.base import Base
from aibot.db.session import engine
from aibot.main import app
from aibot.smoke import run_smoke_scenario

pytestmark = pytest.mark.integration


async def reset_database() -> None:
    """Пересоздать таблицы прототипа в тестовой PostgreSQL-БД."""

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


@pytest.fixture()
async def prepared_database() -> AsyncIterator[None]:
    """Подготовить БД или пропустить тест, если PostgreSQL не запущен."""

    try:
        await reset_database()
    except (ConnectionRefusedError, DBAPIError, OSError, OperationalError) as exc:
        pytest.skip(f"PostgreSQL is not available for integration test: {exc}")
    await engine.dispose()
    yield
    await engine.dispose()


def test_sources_and_keywords_crud_with_database(prepared_database: None) -> None:
    """CRUD endpoints работают через настоящий SQLAlchemy/PostgreSQL слой."""

    assert prepared_database is None
    with TestClient(app) as client:
        source_response = client.post(
            "/api/sources/",
            json={
                "type": "site",
                "name": "Example News",
                "url": "https://example.com/news",
                "enabled": True,
            },
        )
        assert source_response.status_code == 201
        source_payload = source_response.json()
        source_id = source_payload["id"]

        duplicate_source_response = client.post(
            "/api/sources/",
            json={
                "type": "site",
                "name": "Example News Clone",
                "url": "https://example.com/news",
                "enabled": True,
            },
        )
        assert duplicate_source_response.status_code == 409

        list_sources_response = client.get("/api/sources/")
        assert list_sources_response.status_code == 200
        assert len(list_sources_response.json()) == 1

        disable_source_response = client.delete(f"/api/sources/{source_id}")
        assert disable_source_response.status_code == 200
        assert disable_source_response.json()["enabled"] is False

        keyword_response = client.post(
            "/api/keywords/",
            json={"word": "python", "enabled": True},
        )
        assert keyword_response.status_code == 201
        keyword_payload = keyword_response.json()
        keyword_id = keyword_payload["id"]

        duplicate_keyword_response = client.post(
            "/api/keywords/",
            json={"word": "PYTHON", "enabled": True},
        )
        assert duplicate_keyword_response.status_code == 409

        patch_keyword_response = client.patch(
            f"/api/keywords/{keyword_id}",
            json={"enabled": False},
        )
        assert patch_keyword_response.status_code == 200
        assert patch_keyword_response.json()["enabled"] is False

        delete_keyword_response = client.delete(f"/api/keywords/{keyword_id}")
        assert delete_keyword_response.status_code == 204


def test_dry_run_news_pipeline_with_database(prepared_database: None) -> None:
    """Dry-run API pipeline сохраняет новости, пост и публикацию в PostgreSQL."""

    assert prepared_database is None
    with TestClient(app) as client:
        source_response = client.post(
            "/api/sources/",
            json={
                "type": "site",
                "name": "Demo News",
                "url": "https://example.test/news",
                "enabled": True,
            },
        )
        assert source_response.status_code == 201
        source_id = source_response.json()["id"]

        keyword_response = client.post(
            "/api/keywords/",
            json={"word": "python", "enabled": True},
        )
        assert keyword_response.status_code == 201

        parse_response = client.post(f"/api/sources/{source_id}/parse?limit=2")
        assert parse_response.status_code == 200
        parse_payload = parse_response.json()
        assert parse_payload["parsed_count"] == 2
        assert parse_payload["saved_count"] == 2
        assert parse_payload["ready_for_generation_count"] == 1
        assert parse_payload["filtered_out_count"] == 1

        news_response = client.get("/api/news/?status=ready_for_generation")
        assert news_response.status_code == 200
        ready_news = news_response.json()
        assert len(ready_news) == 1
        assert "Python" in ready_news[0]["title"]

        generation_response = client.post(f"/api/news/{ready_news[0]['id']}/generate")
        assert generation_response.status_code == 200
        generated_post = generation_response.json()
        assert generated_post["status"] == "generated"
        assert generated_post["news_id"] == ready_news[0]["id"]

        publish_response = client.post(f"/api/posts/{generated_post['id']}/publish")
        assert publish_response.status_code == 200
        published_post = publish_response.json()
        assert published_post["status"] == "published"
        assert published_post["telegram_message_id"].startswith("dry-run-")

        posts_response = client.get("/api/posts/?status=published")
        assert posts_response.status_code == 200
        assert len(posts_response.json()) == 1


@pytest.mark.asyncio
async def test_smoke_scenario_runs_against_database() -> None:
    """Smoke CLI scenario проходит полный dry-run pipeline через PostgreSQL."""

    result = await run_smoke_scenario(reset=True)
    await engine.dispose()

    assert result.parsed_count == 2
    assert result.saved_count == 2
    assert result.ready_for_generation_count == 1
    assert result.filtered_out_count == 1
    assert result.generated_post_status == "generated"
    assert result.published_post_status == "published"
    assert result.telegram_message_id.startswith("dry-run-")
    assert result.fake_mode is True
    assert result.telegram_dry_run is True
