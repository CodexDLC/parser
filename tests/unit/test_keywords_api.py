"""Тесты API ключевых слов с подмененным сервисом."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from aibot.api.deps import get_keyword_service
from aibot.main import app
from aibot.services.exceptions import EntityNotFoundError


@dataclass
class FakeKeyword:
    """Минимальный объект ключевого слова для response_model."""

    id: uuid.UUID
    word: str
    enabled: bool
    created_at: datetime


class FakeKeywordService:
    """Fake keyword service для unit-тестов router слоя."""

    keyword_id = uuid.UUID("33333333-3333-3333-3333-333333333333")

    def _keyword(self, *, enabled: bool = True) -> FakeKeyword:
        return FakeKeyword(
            id=self.keyword_id,
            word="python",
            enabled=enabled,
            created_at=datetime(2026, 7, 11, tzinfo=UTC),
        )

    async def list_keywords(self, **_: object) -> list[FakeKeyword]:
        return [self._keyword()]

    async def create_keyword(self, **_: object) -> FakeKeyword:
        return self._keyword()

    async def update_keyword(self, keyword_id: uuid.UUID, **_: object) -> FakeKeyword:
        if keyword_id != self.keyword_id:
            raise EntityNotFoundError("Keyword not found")
        return self._keyword(enabled=False)

    async def delete_keyword(self, keyword_id: uuid.UUID) -> None:
        if keyword_id != self.keyword_id:
            raise EntityNotFoundError("Keyword not found")


def override_keyword_service() -> FakeKeywordService:
    """Вернуть fake keyword service."""

    return FakeKeywordService()


def test_keywords_crud_contract() -> None:
    """Keywords API возвращает ожидаемые статусы и JSON-контракт."""

    app.dependency_overrides[get_keyword_service] = override_keyword_service
    client = TestClient(app)

    try:
        response = client.get("/api/keywords/")
        assert response.status_code == 200
        assert response.json()[0]["word"] == "python"

        response = client.post("/api/keywords/", json={"word": "python", "enabled": True})
        assert response.status_code == 201
        assert response.json()["enabled"] is True

        response = client.patch(
            f"/api/keywords/{FakeKeywordService.keyword_id}",
            json={"enabled": False},
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is False

        response = client.delete(f"/api/keywords/{FakeKeywordService.keyword_id}")
        assert response.status_code == 204
        assert response.content == b""
    finally:
        app.dependency_overrides.clear()


def test_delete_keyword_returns_404_for_missing_keyword() -> None:
    """Keywords API возвращает 404, если сервис не нашел keyword."""

    app.dependency_overrides[get_keyword_service] = override_keyword_service
    client = TestClient(app)

    try:
        response = client.delete("/api/keywords/44444444-4444-4444-4444-444444444444")
        assert response.status_code == 404
        assert response.json() == {"detail": "Keyword not found"}
    finally:
        app.dependency_overrides.clear()
