from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app


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


# ── POST /api/v1/admin/users/invite ──


def test_invite_requires_auth(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/users/invite")
    assert response.status_code == 401


def test_invite_requires_admin_role(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/users/invite", headers=_VIEWER_HEADERS)
    assert response.status_code == 403


def test_invite_returns_501(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/users/invite", headers=_ADMIN_HEADERS)
    assert response.status_code == 501
    data = response.json()
    assert data["detail"] == "idp-invite-not-implemented"
    assert data["status"] == 501
    assert data["title"] == "Not Implemented"
    assert data["type"] == "about:blank"


# ── GET /api/v1/admin/backups/status ──


def test_backups_status_requires_auth(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/backups/status")
    assert response.status_code == 401


def test_backups_status_requires_admin_role(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/backups/status", headers=_VIEWER_HEADERS)
    assert response.status_code == 403


def test_backups_status_returns_501(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/backups/status", headers=_ADMIN_HEADERS)
    assert response.status_code == 501
    data = response.json()
    assert data["detail"] == "backup-status-not-implemented"
    assert data["status"] == 501
    assert data["title"] == "Not Implemented"
    assert data["type"] == "about:blank"
