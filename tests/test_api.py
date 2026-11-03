import os

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    settings = Settings(
        database_url=os.environ.get("DATABASE_URL", "sqlite://"),
        app_version="test",
        base_url="http://short.test",
        log_level="WARNING",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_reports_database(client: TestClient) -> None:
    assert client.get("/readyz").status_code == 200


def test_version_comes_from_settings(client: TestClient) -> None:
    assert client.get("/version").json() == {"version": "test"}


def test_create_and_redirect(client: TestClient) -> None:
    created = client.post("/links", json={"url": "https://entry-point.me/"})
    assert created.status_code == 201
    body = created.json()
    assert len(body["code"]) == 7
    assert body["short_url"] == f"http://short.test/{body['code']}"

    redirect = client.get(f"/{body['code']}", follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "https://entry-point.me/"

    stats = client.get(f"/links/{body['code']}")
    assert stats.json()["clicks"] == 1


def test_unknown_code_returns_404(client: TestClient) -> None:
    assert client.get("/doesnotexist", follow_redirects=False).status_code == 404


def test_rejects_invalid_url(client: TestClient) -> None:
    assert client.post("/links", json={"url": "not-a-url"}).status_code == 422


def test_metrics_exposed(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "shortlink_redirects_total" in response.text
