from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.tables import AuditLog
from cctv_api.security.users import get_or_create_user


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

_MFA_BODY = {
    "verification_evidence": "video call identity confirmed",
    "reason": "lost hardware key",
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


def test_mfa_reset_unauthenticated(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/mfa/reset",
        json=_MFA_BODY,
    )
    assert resp.status_code == 401


def test_mfa_reset_viewer_forbidden(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/mfa/reset",
        json=_MFA_BODY,
        headers=_VIEWER_HEADERS,
    )
    assert resp.status_code == 403


def test_mfa_reset_user_not_found(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/mfa/reset",
        json=_MFA_BODY,
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "user-not-found"


def test_mfa_reset_success(test_db_session: DbSession) -> None:
    target = get_or_create_user(test_db_session, email="target@example.test", idp_subject="target@example.test")
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/users/{target.id}/mfa/reset",
        json=_MFA_BODY,
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(target.id)
    assert "mfa_reset_recorded_at" in data
    assert "recovery_note" in data
    audit = test_db_session.query(AuditLog).filter(
        AuditLog.action == "admin.user.mfa_reset"
    ).first()
    assert audit is not None


def test_mfa_reset_self_blocked(test_db_session: DbSession) -> None:
    # The admin user will be auto-created with email admin@example.test
    # Pre-create the admin user so we know their ID
    admin_user = get_or_create_user(test_db_session, email="admin@example.test", idp_subject="admin@example.test")
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/users/{admin_user.id}/mfa/reset",
        json=_MFA_BODY,
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "cannot-reset-own-mfa"
