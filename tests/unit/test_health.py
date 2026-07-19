"""Тесты первого HTTP healthcheck прототипа."""

from fastapi.testclient import TestClient

from aibot.main import app


def test_healthcheck_returns_application_status() -> None:
    """Healthcheck возвращает базовые сведения о приложении."""

    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": "Project M4 AI Telegram News Bot",
        "app_version": "0.1.0",
        "environment": "local",
    }


def test_swagger_docs_are_available() -> None:
    """Swagger UI доступен по /docs."""

    client = TestClient(app)

    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()
