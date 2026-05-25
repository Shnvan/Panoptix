from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.tables import AuditLog


_ADMIN_HEADERS = {
    "x-panoptix-dev-auth": "1",
    "x-panoptix-dev-email": "admin@example.test",
    "x-panoptix-dev-subject": "admin@example.test",
    "x-panoptix-dev-roles": "admin",
}

_VIEWER_HEADERS = {
    "x-panoptix-dev-auth": "1",
    "x-panoptix-dev-email": "viewer@example.test",
    "x-panoptix-dev-subject": "viewer@example.test",
    "x-panoptix-dev-roles": "viewer",
}


def _client(test_db_session: DbSession) -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            AUDIT_HMAC_KEY_VERSION=1,
            AUDIT_HMAC_KEY="test-audit-key-with-enough-entropy",
        )
    )

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


def test_fallback_unauthenticated(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/livekit/fallback",
        json={"mode": "fallback", "reason": "test"},
    )
    assert resp.status_code == 401


def test_fallback_viewer_forbidden(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/livekit/fallback",
        json={"mode": "fallback", "reason": "test"},
        headers=_VIEWER_HEADERS,
    )
    assert resp.status_code == 403


def test_fallback_switch_to_fallback(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/livekit/fallback",
        json={"mode": "fallback", "reason": "LiveKit Cloud outage"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["media_plane_mode"] == "fallback"
    assert data["previous_mode"] == "cloud"
    assert "switched_at" in data
    audit = test_db_session.query(AuditLog).filter(
        AuditLog.action == "system.media_plane.switched_to_fallback"
    ).first()
    assert audit is not None


def test_fallback_switch_to_primary(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    c.post(
        "/api/v1/admin/livekit/fallback",
        json={"mode": "fallback", "reason": "outage"},
        headers=_ADMIN_HEADERS,
    )
    resp = c.post(
        "/api/v1/admin/livekit/fallback",
        json={"mode": "cloud", "reason": "restored"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["media_plane_mode"] == "cloud"
    assert data["previous_mode"] == "fallback"
    audit = test_db_session.query(AuditLog).filter(
        AuditLog.action == "system.media_plane.switched_to_primary"
    ).first()
    assert audit is not None


def test_fallback_noop_same_mode(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/livekit/fallback",
        json={"mode": "cloud", "reason": "already cloud"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "mode-already-active"


def test_fallback_invalid_mode(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/livekit/fallback",
        json={"mode": "invalid", "reason": "test"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 422
