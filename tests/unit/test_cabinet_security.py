"""Security-контракты защищённой оболочки административного кабинета."""

import re
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from aibot.cabinet.auth import CabinetSession
from aibot.cabinet.credentials import build_credentials, render_env
from aibot.cabinet.dashboard import CabinetDashboardSnapshot, DashboardMetrics
from aibot.cabinet.passwords import hash_password, verify_password
from aibot.config import Settings
from aibot.main import create_app

ADMIN_PASSWORD = "correct horse battery staple"


class EmptyDashboardService:
    """Не позволяет security-тестам обращаться к PostgreSQL."""

    async def load_overview(self) -> CabinetDashboardSnapshot:
        return CabinetDashboardSnapshot(
            database_available=True,
            metrics=DashboardMetrics(0, 0, 0, 0, 0, 0),
            news_by_status={},
            published_by_day={},
            recent_posts=(),
            recent_errors=(),
            health=(),
            generated_at=datetime.now(UTC),
            timezone="Europe/Berlin",
        )


class MemoryCabinetSecurityStore:
    """In-memory adapter для HTTP security-тестов без Redis."""

    def __init__(self) -> None:
        self.sessions: dict[str, CabinetSession] = {}
        self.failures: dict[str, int] = {}

    async def save_session(self, session: CabinetSession, *, ttl_seconds: int) -> None:
        """Сохранить session; TTL проверяется Redis integration отдельно."""

        assert ttl_seconds > 0
        self.sessions[session.session_id] = session

    async def get_session(self, session_id: str) -> CabinetSession | None:
        """Вернуть session."""

        return self.sessions.get(session_id)

    async def delete_session(self, session_id: str) -> None:
        """Инвалидировать session."""

        self.sessions.pop(session_id, None)

    async def get_login_failures(self, key: str) -> int:
        """Вернуть число неудачных попыток."""

        return self.failures.get(key, 0)

    async def record_login_failure(self, key: str, *, window_seconds: int) -> int:
        """Увеличить счётчик попыток."""

        assert window_seconds > 0
        self.failures[key] = self.failures.get(key, 0) + 1
        return self.failures[key]

    async def clear_login_failures(self, key: str) -> None:
        """Очистить счётчик после успешного входа."""

        self.failures.pop(key, None)


def cabinet_settings(**overrides: object) -> Settings:
    """Собрать полностью настроенный single-admin runtime."""

    values: dict[str, object] = {
        "cabinet_enabled": True,
        "cabinet_username": "admin",
        "cabinet_password_hash": hash_password(ADMIN_PASSWORD),
        "cabinet_session_secret": "test-session-secret-with-at-least-32-bytes",
        "cabinet_login_max_attempts": 2,
        "cabinet_login_window_seconds": 60,
        "debug": False,
    }
    values.update(overrides)
    return Settings.model_validate(values)


def csrf_from_html(html: str) -> str:
    """Извлечь hidden CSRF token из server-rendered формы."""

    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def login(client: TestClient) -> None:
    """Выполнить успешный browser login."""

    login_page = client.get("/cabinet/login")
    token = csrf_from_html(login_page.text)
    response = client.post(
        "/cabinet/login",
        data={
            "username": "admin",
            "password": ADMIN_PASSWORD,
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_cabinet_is_not_mounted_when_feature_flag_is_disabled() -> None:
    """Выключенный feature flag оставляет API без cabinet routes."""

    application = create_app(settings=Settings.model_validate({"cabinet_enabled": False}))
    client = TestClient(application)

    assert client.get("/cabinet", follow_redirects=False).status_code == 404
    assert client.get("/api/health").status_code == 200


def test_credentials_helper_never_renders_plaintext_password() -> None:
    """CLI helper возвращает только username, Argon2 hash и session secret."""

    credentials = build_credentials(
        username=" admin ",
        password=ADMIN_PASSWORD,
        session_secret="s" * 48,
    )
    rendered = render_env(credentials)

    assert ADMIN_PASSWORD not in rendered
    assert credentials.username == "admin"
    assert credentials.password_hash.startswith("$argon2")
    assert verify_password(ADMIN_PASSWORD, credentials.password_hash) is True
    assert 'CABINET_SESSION_SECRET="' in rendered


def test_custom_cabinet_mount_path_is_used_by_login_form() -> None:
    """Shell не содержит жёстко заданный `/cabinet` при другом mount path."""

    application = create_app(
        settings=cabinet_settings(cabinet_mount_path="/management"),
        cabinet_security_store=MemoryCabinetSecurityStore(),
    )
    client = TestClient(application)

    response = client.get("/management/login")

    assert response.status_code == 200
    assert 'action="/management/login"' in response.text
    assert client.get("/cabinet/login").status_code == 404


def test_anonymous_access_redirects_to_login_with_security_headers() -> None:
    """Все private routes закрыты до выполнения provider-а."""

    application = create_app(
        settings=cabinet_settings(),
        cabinet_security_store=MemoryCabinetSecurityStore(),
    )
    client = TestClient(application)

    response = client.get("/cabinet", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/cabinet/login")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_login_rotates_session_and_opens_library_shell() -> None:
    """Успешный вход создаёт opaque server-side session и открывает shell."""

    store = MemoryCabinetSecurityStore()
    application = create_app(
        settings=cabinet_settings(),
        cabinet_security_store=store,
        cabinet_dashboard_service=EmptyDashboardService(),
    )
    client = TestClient(application)

    login(client)
    response = client.get("/cabinet")

    assert response.status_code == 200
    assert "M4 Управление" in response.text
    assert "Обзор" in response.text
    assert len(store.sessions) == 1
    set_cookie = client.cookies.get("m4_cabinet_session")
    assert set_cookie is not None


def test_production_session_cookie_is_secure_and_httponly() -> None:
    """Production login устанавливает обязательные browser cookie flags."""

    application = create_app(
        settings=cabinet_settings(environment="production", docs_enabled=False),
        cabinet_security_store=MemoryCabinetSecurityStore(),
    )
    client = TestClient(application, base_url="https://testserver")
    login_page = client.get("/cabinet/login")

    response = client.post(
        "/cabinet/login",
        data={
            "username": "admin",
            "password": ADMIN_PASSWORD,
            "csrf_token": csrf_from_html(login_page.text),
        },
        follow_redirects=False,
    )

    session_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "SameSite=lax" in session_cookie


def test_login_is_rate_limited_without_disclosing_username() -> None:
    """Повторные неверные credentials блокируются единым ответом."""

    settings = cabinet_settings()
    application = create_app(
        settings=settings,
        cabinet_security_store=MemoryCabinetSecurityStore(),
    )
    client = TestClient(application)

    for username in ("admin", "unknown"):
        login_page = client.get("/cabinet/login")
        response = client.post(
            "/cabinet/login",
            data={
                "username": username,
                "password": "wrong",
                "csrf_token": csrf_from_html(login_page.text),
            },
        )
        assert response.status_code == 401
        assert "Неверный логин или пароль" in response.text

    login_page = client.get("/cabinet/login")
    blocked = client.post(
        "/cabinet/login",
        data={
            "username": "admin",
            "password": "wrong",
            "csrf_token": csrf_from_html(login_page.text),
        },
    )
    assert blocked.status_code == 429


def test_logout_requires_csrf_and_invalidates_server_session() -> None:
    """Logout без CSRF запрещён, валидный logout удаляет server session."""

    store = MemoryCabinetSecurityStore()
    application = create_app(
        settings=cabinet_settings(),
        cabinet_security_store=store,
        cabinet_dashboard_service=EmptyDashboardService(),
    )
    client = TestClient(application)
    login(client)

    rejected = client.post(
        "/cabinet/logout",
        data={"csrf_token": "invalid"},
        follow_redirects=False,
    )
    assert rejected.status_code == 403
    assert len(store.sessions) == 1

    shell = client.get("/cabinet")
    token = csrf_from_html(shell.text)
    accepted = client.post(
        "/cabinet/logout",
        data={"csrf_token": token},
        follow_redirects=False,
    )

    assert accepted.status_code == 303
    assert accepted.headers["location"] == "/cabinet/login"
    assert store.sessions == {}
    assert client.get("/cabinet", follow_redirects=False).status_code == 303
