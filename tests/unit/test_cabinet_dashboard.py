"""Контракты read-only dashboard и пассивной диагностики кабинета."""

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from aibot.cabinet.auth import CabinetSession
from aibot.cabinet.dashboard import (
    CabinetDashboardSnapshot,
    DashboardMetrics,
    HealthCheck,
    PassiveHealthService,
    RecentError,
    RecentPost,
)
from aibot.cabinet.passwords import hash_password
from aibot.config import Settings
from aibot.main import create_app

ADMIN_PASSWORD = "correct horse battery staple"


class MemoryCabinetSecurityStore:
    """Минимальный server-side session store для dashboard HTTP-теста."""

    def __init__(self) -> None:
        self.sessions: dict[str, CabinetSession] = {}

    async def save_session(self, session: CabinetSession, *, ttl_seconds: int) -> None:
        assert ttl_seconds > 0
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


class FakeDashboardService:
    """Возвращает один детерминированный снимок и считает обращения."""

    def __init__(self) -> None:
        self.calls = 0

    async def load_overview(self) -> CabinetDashboardSnapshot:
        self.calls += 1
        return CabinetDashboardSnapshot(
            database_available=True,
            metrics=DashboardMetrics(
                active_sources=3,
                news_today=12,
                ready_for_generation=4,
                posts_total=8,
                published_today=2,
                errors_24h=1,
            ),
            news_by_status={"new": 5, "ready_for_generation": 4},
            published_by_day={
                date(2026, 7, 18): 1,
                date(2026, 7, 19): 2,
            },
            recent_posts=(
                RecentPost(
                    news_title="Новая версия Python",
                    status="published",
                    updated_at=datetime(2026, 7, 19, 10, 15, tzinfo=UTC),
                ),
            ),
            recent_errors=(
                RecentError(
                    scope="parser",
                    message="Invalid RSS/Atom feed <script>alert(1)</script>",
                    created_at=datetime(2026, 7, 19, 9, 0, tzinfo=UTC),
                ),
            ),
            health=(
                HealthCheck(service="PostgreSQL", status="доступен", detail="read-only SQL"),
                HealthCheck(service="OpenAI", status="настроен", detail="без сетевой проверки"),
            ),
            generated_at=datetime(2026, 7, 19, 10, 30, tzinfo=UTC),
            timezone="Europe/Berlin",
        )


class CountingRedisProbe:
    """Считает только безопасные Redis PING-вызовы."""

    def __init__(self, result: bool = True) -> None:
        self.calls = 0
        self.result = result

    async def ping(self) -> bool:
        self.calls += 1
        return self.result


def dashboard_settings() -> Settings:
    """Собрать включённый кабинет без реальных provider-вызовов."""

    return Settings.model_validate(
        {
            "cabinet_enabled": True,
            "cabinet_username": "admin",
            "cabinet_password_hash": hash_password(ADMIN_PASSWORD),
            "cabinet_session_secret": "test-session-secret-with-at-least-32-bytes",
            "cabinet_timezone": "Europe/Berlin",
            "openai_api_key": "configured-but-must-not-be-called",
            "gemini_api_key": "configured-but-must-not-be-called",
            "telegram_api_id": 123,
            "telegram_api_hash": "configured-but-must-not-be-called",
            "telegram_target_channel": "@project_m4",
            "telegram_dry_run": True,
            "debug": False,
        }
    )


def _login(client: TestClient) -> None:
    page = client.get("/cabinet/login")
    token = page.text.split('name="csrf_token" value="', maxsplit=1)[1].split('"', maxsplit=1)[0]
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


def test_dashboard_renders_all_widgets_from_one_request_snapshot() -> None:
    """Несколько providers не повторяют SQL snapshot в пределах одного request."""

    service = FakeDashboardService()
    application = create_app(
        settings=dashboard_settings(),
        cabinet_security_store=MemoryCabinetSecurityStore(),
        cabinet_dashboard_service=service,
    )
    client = TestClient(application)
    _login(client)

    response = client.get("/cabinet")

    assert response.status_code == 200
    assert service.calls == 1
    for expected in (
        "Активные источники",
        "12",
        "Готовы к генерации",
        "Публикации за 7 дней",
        "Новая версия Python",
        "Invalid RSS/Atom feed",
        "PostgreSQL",
        "без сетевой проверки",
    ):
        assert expected in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text
    assert "<script>alert(1)</script>" not in response.text
    assert "<form" not in response.text.split('<header class="fc-page-header">', maxsplit=1)[1]


async def test_passive_health_is_cached_and_does_not_probe_external_providers() -> None:
    """Health вызывает только Redis PING и описывает AI/Telegram по config."""

    probe = CountingRedisProbe()
    service = PassiveHealthService(
        settings=dashboard_settings(),
        redis_probe=probe,
        cache_ttl_seconds=30,
    )

    first = await service.load(database_available=True)
    second = await service.load(database_available=True)

    assert first == second
    assert probe.calls == 1
    health = {item.service: item for item in first}
    assert health["PostgreSQL"].status == "доступен"
    assert health["Redis"].status == "доступен"
    assert health["AI"].status == "настроен"
    assert health["AI"].detail == "primary=openai; fallback=gemini; без сетевой проверки"
    assert health["Telegram"].status == "dry-run"
    assert health["Celery"].detail == "без опроса worker"
    assert health["Beat"].detail == "расписание настроено"


async def test_passive_health_uses_selected_bot_api_configuration() -> None:
    """Bot API health не требует Telethon credentials и остаётся пассивным."""

    settings = dashboard_settings().model_copy(
        update={
            "telegram_publisher": "bot_api",
            "telegram_bot_token": "configured-but-must-not-be-called",
            "telegram_api_id": None,
            "telegram_api_hash": None,
            "telegram_dry_run": False,
        }
    )
    service = PassiveHealthService(
        settings=settings,
        redis_probe=CountingRedisProbe(),
    )

    health = {item.service: item for item in await service.load(database_available=True)}

    assert health["Telegram"].status == "настроен"
    assert health["Telegram"].detail == "publisher=bot_api; без отправки сообщений"


def test_invalid_cabinet_timezone_is_rejected() -> None:
    """Операторская timezone валидируется при старте."""

    settings = dashboard_settings().model_dump()
    settings["cabinet_timezone"] = "Mars/Olympus"

    try:
        Settings.model_validate(settings)
    except ValueError as exc:
        assert "CABINET_TIMEZONE" in str(exc)
    else:
        raise AssertionError("invalid timezone must be rejected")
