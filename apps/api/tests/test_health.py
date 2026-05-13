from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import GatewayStatus
from cctv_api.models.tables import EdgeGateway


def _client_with_db(test_db_session: DbSession, **settings_kwargs: object) -> TestClient:
    defaults = {
        "APP_ENV": "development",
        "ALLOW_DEV_AUTH": True,
        "AUDIT_HMAC_KEY_VERSION": 1,
        "AUDIT_HMAC_KEY": "test-audit-key-with-enough-entropy",
    }
    defaults.update(settings_kwargs)
    app = create_app(settings=Settings(**defaults))  # type: ignore[arg-type]

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


# ── Basic health ──


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ── Deep health: DB ──


def test_deep_health_db_connected(client: TestClient) -> None:
    response = client.get("/api/v1/admin/health/deep")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"
    assert data["livekit"] == "not_configured"
    assert data["gateway"] == "no_gateways"


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
    data = response.json()
    assert data["status"] == "degraded"
    assert data["db"] == "error"
    assert data["livekit"] == "not_configured"
    assert data["gateway"] == "error"


# ── Deep health: LiveKit ──


@patch("cctv_api.api.health.httpx.post")
def test_deep_health_livekit_connected(mock_post: MagicMock, test_db_session: DbSession) -> None:
    mock_post.return_value = MagicMock(status_code=200)
    client = _client_with_db(
        test_db_session,
        LIVEKIT_CLOUD_API_KEY="real-key",
        LIVEKIT_CLOUD_API_SECRET="real-secret-with-enough-entropy",
    )

    response = client.get("/api/v1/admin/health/deep")
    assert response.status_code == 200
    assert response.json()["livekit"] == "connected"
    mock_post.assert_called_once()


@patch("cctv_api.api.health.httpx.post")
def test_deep_health_livekit_error_network(mock_post: MagicMock, test_db_session: DbSession) -> None:
    mock_post.side_effect = httpx.ConnectError("Connection refused")
    client = _client_with_db(
        test_db_session,
        LIVEKIT_CLOUD_API_KEY="real-key",
        LIVEKIT_CLOUD_API_SECRET="real-secret-with-enough-entropy",
    )

    response = client.get("/api/v1/admin/health/deep")
    assert response.status_code == 200
    assert response.json()["livekit"] == "error"


@patch("cctv_api.api.health.httpx.post")
def test_deep_health_livekit_error_non_200(mock_post: MagicMock, test_db_session: DbSession) -> None:
    mock_post.return_value = MagicMock(status_code=401)
    client = _client_with_db(
        test_db_session,
        LIVEKIT_CLOUD_API_KEY="real-key",
        LIVEKIT_CLOUD_API_SECRET="real-secret-with-enough-entropy",
    )

    response = client.get("/api/v1/admin/health/deep")
    assert response.status_code == 200
    assert response.json()["livekit"] == "error"


# ── Deep health: Gateway ──


def test_deep_health_gateway_connected(test_db_session: DbSession) -> None:
    test_db_session.add(EdgeGateway(
        id=uuid.uuid4(),
        name="Healthy GW",
        status=GatewayStatus.enabled,
        last_seen_at=datetime.now(timezone.utc),
    ))
    test_db_session.commit()

    client = _client_with_db(test_db_session)
    response = client.get("/api/v1/admin/health/deep")
    assert response.status_code == 200
    assert response.json()["gateway"] == "connected"


def test_deep_health_gateway_stale(test_db_session: DbSession) -> None:
    test_db_session.add(EdgeGateway(
        id=uuid.uuid4(),
        name="Stale GW",
        status=GatewayStatus.enabled,
        last_seen_at=datetime.now(timezone.utc) - timedelta(seconds=300),
    ))
    test_db_session.commit()

    client = _client_with_db(test_db_session)
    response = client.get("/api/v1/admin/health/deep")
    assert response.status_code == 200
    assert response.json()["gateway"] == "stale"


def test_deep_health_gateway_null_last_seen(test_db_session: DbSession) -> None:
    test_db_session.add(EdgeGateway(
        id=uuid.uuid4(),
        name="Never-seen GW",
        status=GatewayStatus.enabled,
        last_seen_at=None,
    ))
    test_db_session.commit()

    client = _client_with_db(test_db_session)
    response = client.get("/api/v1/admin/health/deep")
    assert response.status_code == 200
    assert response.json()["gateway"] == "stale"


def test_deep_health_gateway_disabled_only(test_db_session: DbSession) -> None:
    test_db_session.add(EdgeGateway(
        id=uuid.uuid4(),
        name="Disabled GW",
        status=GatewayStatus.disabled,
        disabled_at=datetime.now(timezone.utc),
    ))
    test_db_session.commit()

    client = _client_with_db(test_db_session)
    response = client.get("/api/v1/admin/health/deep")
    assert response.status_code == 200
    assert response.json()["gateway"] == "no_gateways"


# ── Deep health: Overall status ──


@patch("cctv_api.api.health.httpx.post")
def test_deep_health_overall_degraded_livekit_error(mock_post: MagicMock, test_db_session: DbSession) -> None:
    mock_post.side_effect = httpx.ConnectError("Connection refused")
    client = _client_with_db(
        test_db_session,
        LIVEKIT_CLOUD_API_KEY="real-key",
        LIVEKIT_CLOUD_API_SECRET="real-secret-with-enough-entropy",
    )

    response = client.get("/api/v1/admin/health/deep")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["db"] == "connected"
    assert data["livekit"] == "error"
