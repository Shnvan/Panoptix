from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from cctv_api.db import db_session
from cctv_api.main import create_app


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_deep_health_db_connected(client: TestClient) -> None:
    response = client.get("/api/v1/admin/health/deep")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "db": "connected",
        "livekit": "not_connected",
        "gateway": "not_connected",
    }


def test_deep_health_db_error() -> None:
    app = create_app()
    mock_session = MagicMock(spec=DbSession)
    mock_session.execute.side_effect = RuntimeError("connection refused")

    def _broken_db() -> Generator[DbSession, None, None]:
        yield mock_session  # type: ignore[misc]

    app.dependency_overrides[db_session] = _broken_db
    client = TestClient(app)

    response = client.get("/api/v1/admin/health/deep")
    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "db": "error",
        "livekit": "not_connected",
        "gateway": "not_connected",
    }
