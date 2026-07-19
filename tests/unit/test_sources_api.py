"""Тесты API источников новостей с подмененным сервисом."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from aibot.api.deps import get_source_service, get_task_queue
from aibot.main import app
from aibot.models.enums import SourceType
from aibot.services.exceptions import EntityNotFoundError


@dataclass
class FakeSource:
    """Минимальный объект источника для сериализации response_model."""

    id: uuid.UUID
    type: SourceType
    name: str
    url: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class FakeSourceService:
    """Fake source service для unit-тестов router слоя."""

    source_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

    def _source(self, *, enabled: bool = True) -> FakeSource:
        return FakeSource(
            id=self.source_id,
            type=SourceType.SITE,
            name="Example News",
            url="https://example.com/news",
            enabled=enabled,
            created_at=datetime(2026, 7, 11, tzinfo=UTC),
            updated_at=datetime(2026, 7, 11, tzinfo=UTC),
        )

    async def list_sources(self, **_: object) -> list[FakeSource]:
        return [self._source()]

    async def create_source(self, **_: object) -> FakeSource:
        return self._source()

    async def get_source(self, source_id: uuid.UUID) -> FakeSource:
        if source_id != self.source_id:
            raise EntityNotFoundError("Source not found")
        return self._source()

    async def update_source(self, source_id: uuid.UUID, **_: object) -> FakeSource:
        return await self.get_source(source_id)

    async def disable_source(self, source_id: uuid.UUID) -> FakeSource:
        await self.get_source(source_id)
        return self._source(enabled=False)


class FakeTaskQueue:
    """Зафиксировать постановку parser-задачи без подключения к Redis."""

    def __init__(self) -> None:
        self.parse_calls: list[tuple[uuid.UUID, int]] = []

    def enqueue_source_parsing(self, source_id: uuid.UUID, *, limit: int) -> str:
        self.parse_calls.append((source_id, limit))
        return "parse-task-id"


def override_source_service() -> FakeSourceService:
    """Вернуть fake source service."""

    return FakeSourceService()


def test_sources_crud_contract() -> None:
    """Sources API возвращает ожидаемые статусы и JSON-контракт."""

    app.dependency_overrides[get_source_service] = override_source_service
    client = TestClient(app)

    try:
        response = client.get("/api/sources/")
        assert response.status_code == 200
        assert response.json()[0]["url"] == "https://example.com/news"

        response = client.post(
            "/api/sources/",
            json={
                "type": "site",
                "name": "Example News",
                "url": "https://example.com/news",
                "enabled": True,
            },
        )
        assert response.status_code == 201
        assert response.json()["type"] == "site"

        response = client.patch(
            f"/api/sources/{FakeSourceService.source_id}",
            json={"enabled": False},
        )
        assert response.status_code == 200

        response = client.delete(f"/api/sources/{FakeSourceService.source_id}")
        assert response.status_code == 200
        assert response.json()["enabled"] is False
    finally:
        app.dependency_overrides.clear()


def test_get_source_returns_404_for_missing_source() -> None:
    """Sources API возвращает 404, если сервис не нашел источник."""

    app.dependency_overrides[get_source_service] = override_source_service
    client = TestClient(app)

    try:
        response = client.get("/api/sources/22222222-2222-2222-2222-222222222222")
        assert response.status_code == 404
        assert response.json() == {"detail": "Source not found"}
    finally:
        app.dependency_overrides.clear()


def test_parse_source_contract() -> None:
    """Parse endpoint валидирует source и ставит Celery-задачу."""

    task_queue = FakeTaskQueue()
    app.dependency_overrides[get_source_service] = override_source_service
    app.dependency_overrides[get_task_queue] = lambda: task_queue
    client = TestClient(app)

    try:
        response = client.post(f"/api/sources/{FakeSourceService.source_id}/parse?limit=2")
        assert response.status_code == 202
        assert response.json() == {"task_id": "parse-task-id", "status": "queued"}
        assert task_queue.parse_calls == [(FakeSourceService.source_id, 2)]
    finally:
        app.dependency_overrides.clear()


def test_parse_source_does_not_queue_missing_source() -> None:
    """Отсутствующий source по-прежнему возвращает 404 до постановки задачи."""

    task_queue = FakeTaskQueue()
    app.dependency_overrides[get_source_service] = override_source_service
    app.dependency_overrides[get_task_queue] = lambda: task_queue
    client = TestClient(app)

    try:
        response = client.post(
            "/api/sources/22222222-2222-2222-2222-222222222222/parse"
        )
        assert response.status_code == 404
        assert task_queue.parse_calls == []
    finally:
        app.dependency_overrides.clear()
