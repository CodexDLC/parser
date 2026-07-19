"""HTTP-контракты read-only страниц доменных сущностей кабинета."""

import re
import uuid
from datetime import UTC, datetime
from typing import cast

from fastapi.testclient import TestClient

from aibot.cabinet.auth import CabinetSession
from aibot.cabinet.dashboard import CabinetDashboardSnapshot, DashboardMetrics
from aibot.cabinet.entity_read import (
    EntityPage,
    ErrorLogView,
    KeywordView,
    NewsView,
    PostView,
    SourceView,
)
from aibot.cabinet.operational_read import (
    CabinetOperationalReader,
    PipelineRunView,
)
from aibot.cabinet.passwords import hash_password
from aibot.config import Settings
from aibot.main import create_app

ADMIN_PASSWORD = "correct horse battery staple"
SOURCE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
KEYWORD_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
NEWS_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
POST_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
ERROR_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
RUN_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


class MemorySecurityStore:
    def __init__(self) -> None:
        self.sessions: dict[str, CabinetSession] = {}

    async def save_session(self, session: CabinetSession, *, ttl_seconds: int) -> None:
        self.sessions[session.session_id] = session

    async def get_session(self, session_id: str) -> CabinetSession | None:
        return self.sessions.get(session_id)

    async def delete_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    async def get_login_failures(self, key: str) -> int:
        return 0

    async def record_login_failure(self, key: str, *, window_seconds: int) -> int:
        return 1

    async def clear_login_failures(self, key: str) -> None:
        return None


class EmptyDashboard:
    async def load_overview(self) -> CabinetDashboardSnapshot:
        return CabinetDashboardSnapshot(
            database_available=True,
            metrics=DashboardMetrics(0, 0, 0, 0, 0, 0),
            news_by_status={},
            published_by_day={},
            recent_posts=(),
            recent_errors=(),
            health=(),
            generated_at=NOW,
            timezone="Europe/Berlin",
        )


class FakeEntityReader:
    """Детерминированный read port без PostgreSQL."""

    def __init__(self) -> None:
        self.source_queries: list[tuple[int, int, str, str, str]] = []

    async def list_sources(
        self,
        *,
        offset: int,
        limit: int,
        search: str,
        source_type: str,
        enabled: str,
    ) -> EntityPage[SourceView]:
        self.source_queries.append((offset, limit, search, source_type, enabled))
        return EntityPage(
            items=(
                SourceView(
                    id=SOURCE_ID,
                    type="site",
                    name='<script>alert("x")</script>',
                    url="https://example.test/feed.xml",
                    enabled=True,
                    created_at=NOW,
                    updated_at=NOW,
                ),
            ),
            total=41,
        )

    async def get_source(self, entity_id: uuid.UUID) -> SourceView | None:
        if entity_id != SOURCE_ID:
            return None
        return (
            await self.list_sources(
                offset=0,
                limit=1,
                search="",
                source_type="",
                enabled="",
            )
        ).items[0]

    async def list_keywords(
        self, *, offset: int, limit: int, search: str, enabled: str
    ) -> EntityPage[KeywordView]:
        return EntityPage(
            items=(KeywordView(KEYWORD_ID, "python", True, NOW, NOW),),
            total=1,
        )

    async def get_keyword(self, entity_id: uuid.UUID) -> KeywordView | None:
        return (
            KeywordView(KEYWORD_ID, "python", True, NOW, NOW)
            if entity_id == KEYWORD_ID
            else None
        )

    async def list_news(
        self, *, offset: int, limit: int, search: str, status: str, source_id: str
    ) -> EntityPage[NewsView]:
        return EntityPage(
            items=(
                NewsView(
                    NEWS_ID,
                    "Новость",
                    "https://example.test/news",
                    "Краткое описание",
                    "Исходный текст",
                    SOURCE_ID,
                    "Feed",
                    "ready_for_generation",
                    NOW,
                    NOW,
                ),
            ),
            total=1,
        )

    async def get_news(self, entity_id: uuid.UUID) -> NewsView | None:
        page = await self.list_news(offset=0, limit=1, search="", status="", source_id="")
        return page.items[0] if entity_id == NEWS_ID else None

    async def list_posts(
        self, *, offset: int, limit: int, search: str, status: str
    ) -> EntityPage[PostView]:
        return EntityPage(
            items=(
                PostView(
                    POST_ID,
                    NEWS_ID,
                    "Новость",
                    "Сгенерированный текст",
                    "generated",
                    None,
                    None,
                    None,
                    NOW,
                    NOW,
                ),
            ),
            total=1,
        )

    async def get_post(self, entity_id: uuid.UUID) -> PostView | None:
        page = await self.list_posts(offset=0, limit=1, search="", status="")
        return page.items[0] if entity_id == POST_ID else None

    async def list_errors(
        self, *, offset: int, limit: int, search: str, scope: str
    ) -> EntityPage[ErrorLogView]:
        return EntityPage(
            items=(
                ErrorLogView(
                    ERROR_ID,
                    "parser",
                    "Invalid feed",
                    "RssFeedParseError",
                    SOURCE_ID,
                    None,
                    None,
                    NOW,
                ),
            ),
            total=1,
        )

    async def get_error(self, entity_id: uuid.UUID) -> ErrorLogView | None:
        page = await self.list_errors(offset=0, limit=1, search="", scope="")
        return page.items[0] if entity_id == ERROR_ID else None


class FakeOperationalReader:
    async def get_pipeline_run(self, entity_id: uuid.UUID) -> PipelineRunView | None:
        if entity_id != RUN_ID:
            return None
        return PipelineRunView(
            RUN_ID,
            "cabinet",
            "parse_source",
            "running",
            "source",
            SOURCE_ID,
            "celery-task-id",
            {"limit": 10},
            None,
            None,
            NOW,
            None,
            NOW,
            NOW,
        )


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "cabinet_enabled": True,
            "cabinet_username": "admin",
            "cabinet_password_hash": hash_password(ADMIN_PASSWORD),
            "cabinet_session_secret": "test-session-secret-with-at-least-32-bytes",
            "debug": False,
        }
    )


def _client(reader: FakeEntityReader) -> TestClient:
    application = create_app(
        settings=_settings(),
        cabinet_security_store=MemorySecurityStore(),
        cabinet_dashboard_service=EmptyDashboard(),
        cabinet_entity_reader=reader,
        cabinet_operational_reader=cast(
            "CabinetOperationalReader",
            FakeOperationalReader(),
        ),
    )
    client = TestClient(application)
    login = client.get("/cabinet/login")
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', login.text)
    assert token is not None
    response = client.post(
        "/cabinet/login",
        data={
            "username": "admin",
            "password": ADMIN_PASSWORD,
            "csrf_token": token.group(1),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def test_all_read_only_entity_sections_are_registered() -> None:
    client = _client(FakeEntityReader())

    expected_routes = {
        "/cabinet/sources/list",
        "/cabinet/keywords/list",
        "/cabinet/news/list",
        "/cabinet/posts/list",
        "/cabinet/errors/list",
    }
    for route in expected_routes:
        response = client.get(route)
        assert response.status_code == 200, route
        assert "<form" in response.text  # GET filter form only
        assert response.text.count('method="post"') == 1  # только logout в topbar


def test_source_list_has_server_pagination_filters_and_xss_escape() -> None:
    reader = FakeEntityReader()
    client = _client(reader)

    response = client.get(
        "/cabinet/sources/list?page=2&q=python&type=site&enabled=true"
    )

    assert response.status_code == 200
    assert reader.source_queries == [(20, 20, "python", "site", "true")]
    assert "Page 2 of 3" in response.text
    assert "page=3" in response.text
    assert "&lt;script&gt;alert(&#34;x&#34;)&lt;/script&gt;" in response.text
    assert '<script>alert("x")</script>' not in response.text


def test_entity_detail_and_invalid_uuid_return_expected_statuses() -> None:
    client = _client(FakeEntityReader())

    detail = client.get(f"/cabinet/sources/{SOURCE_ID}")
    missing = client.get("/cabinet/sources/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    malformed = client.get("/cabinet/sources/not-a-uuid")

    assert detail.status_code == 200
    assert "https://example.test/feed.xml" in detail.text
    assert missing.status_code == 404
    assert malformed.status_code == 404


def test_post_publication_page_shows_escaped_preview_and_confirmation() -> None:
    client = _client(FakeEntityReader())

    response = client.get(f"/cabinet/posts/{POST_ID}/manage")

    assert response.status_code == 200
    assert "Сгенерированный текст" in response.text
    assert "Подтвердить публикацию" in response.text
    assert 'data-confirm="Подтвердить отправку этого текста в Telegram?"' in response.text
    assert "Telegram dry-run" in response.text


def test_pipeline_status_polling_returns_safe_authenticated_payload() -> None:
    client = _client(FakeEntityReader())

    response = client.get(f"/cabinet/pipeline/{RUN_ID}/status")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(RUN_ID),
        "operation": "parse_source",
        "status": "running",
        "task_id": "celery-task-id",
        "result_counts": None,
        "error_category": None,
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
        "finished_at": None,
    }
