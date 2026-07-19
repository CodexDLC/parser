"""Security и HTTP-контракты Source/Keyword mutations."""

import re
import uuid
from datetime import UTC, datetime
from typing import cast

from fastapi.testclient import TestClient

from aibot.cabinet.auth import CabinetSession
from aibot.cabinet.dashboard import CabinetDashboardSnapshot, DashboardMetrics
from aibot.cabinet.mutations import CabinetMutationPort
from aibot.cabinet.passwords import hash_password
from aibot.config import Settings
from aibot.main import create_app

ADMIN_PASSWORD = "correct horse battery staple"
CREATED_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


class MemoryStore:
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
        now = datetime.now(UTC)
        return CabinetDashboardSnapshot(
            True,
            DashboardMetrics(0, 0, 0, 0, 0, 0),
            {},
            {},
            (),
            (),
            (),
            now,
            "Europe/Berlin",
        )


class FakeMutationService:
    def __init__(self) -> None:
        self.source_creates: list[tuple[str, str, str, str, bool]] = []
        self.keyword_creates: list[tuple[str, str, bool]] = []

    async def create_source(
        self,
        *,
        actor: str,
        source_type: str,
        name: str,
        url: str,
        enabled: bool,
    ) -> uuid.UUID:
        self.source_creates.append((actor, source_type, name, url, enabled))
        return CREATED_ID

    async def create_keyword(
        self,
        *,
        actor: str,
        word: str,
        enabled: bool,
    ) -> uuid.UUID:
        self.keyword_creates.append((actor, word, enabled))
        return CREATED_ID


def _client(service: FakeMutationService) -> TestClient:
    settings = Settings.model_validate(
        {
            "cabinet_enabled": True,
            "cabinet_username": "admin",
            "cabinet_password_hash": hash_password(ADMIN_PASSWORD),
            "cabinet_session_secret": "test-session-secret-with-at-least-32-bytes",
            "debug": False,
        }
    )
    app = create_app(
        settings=settings,
        cabinet_security_store=MemoryStore(),
        cabinet_dashboard_service=EmptyDashboard(),
        cabinet_mutation_service=cast("CabinetMutationPort", service),
    )
    client = TestClient(app)
    login_page = client.get("/cabinet/login")
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page.text)
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


def _csrf(html: str) -> str:
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert token is not None
    return token.group(1)


def test_source_create_requires_session_csrf_before_handler() -> None:
    service = FakeMutationService()
    client = _client(service)
    form = client.get("/cabinet/sources/new")
    assert form.status_code == 200

    rejected = client.post(
        "/cabinet/sources/create",
        data={
            "type": "site",
            "name": "Feed",
            "url": "https://example.test/feed.xml",
            "enabled": "1",
            "csrf_token": "invalid",
        },
        follow_redirects=False,
    )
    accepted = client.post(
        "/cabinet/sources/create",
        data={
            "type": "site",
            "name": "Feed",
            "url": "https://example.test/feed.xml",
            "enabled": "1",
            "csrf_token": _csrf(form.text),
        },
        follow_redirects=False,
    )

    assert rejected.status_code == 403
    assert accepted.status_code == 303
    assert accepted.headers["location"] == f"/cabinet/sources/{CREATED_ID}"
    assert service.source_creates == [
        ("admin", "site", "Feed", "https://example.test/feed.xml", True)
    ]


def test_keyword_create_uses_same_csrf_and_redirect_contract() -> None:
    service = FakeMutationService()
    client = _client(service)
    form = client.get("/cabinet/keywords/new")

    response = client.post(
        "/cabinet/keywords/create",
        data={
            "word": "python",
            "enabled": "1",
            "csrf_token": _csrf(form.text),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/cabinet/keywords/{CREATED_ID}"
    assert service.keyword_creates == [("admin", "python", True)]
