from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import GatewayStatus
from cctv_api.models.tables import AuditLog, EdgeGateway
from cctv_api.security.service_tokens import hash_service_token


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


def _seed_gateway(db: DbSession, *, name: str = "Test GW", token_hash: str | None = None) -> EdgeGateway:
    gw = EdgeGateway(
        id=uuid.uuid4(),
        name=name,
        status=GatewayStatus.enabled,
        service_token_hash=token_hash,
        created_at=datetime.now(timezone.utc),
    )
    db.add(gw)
    db.commit()
    db.refresh(gw)
    return gw


def test_rotate_unauthenticated(test_db_session: DbSession) -> None:
    gw = _seed_gateway(test_db_session)
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/gateways/{gw.id}/rotate-credential",
        json={"reason": "routine rotation"},
    )
    assert resp.status_code == 401


def test_rotate_viewer_forbidden(test_db_session: DbSession) -> None:
    gw = _seed_gateway(test_db_session)
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/gateways/{gw.id}/rotate-credential",
        json={"reason": "routine rotation"},
        headers=_VIEWER_HEADERS,
    )
    assert resp.status_code == 403


def test_rotate_gateway_not_found(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/gateways/{uuid.uuid4()}/rotate-credential",
        json={"reason": "routine rotation"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "gateway-not-found"


def test_rotate_success(test_db_session: DbSession) -> None:
    old_hash = hash_service_token("old-token")
    gw = _seed_gateway(test_db_session, name="Rotate GW", token_hash=old_hash)
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/gateways/{gw.id}/rotate-credential",
        json={"reason": "compromised key"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["gateway_id"] == str(gw.id)
    assert "service_token" in data
    assert "rotated_at" in data
    # raw token should verify against the new hash
    test_db_session.refresh(gw)
    new_hash = gw.service_token_hash
    assert new_hash != old_hash
    assert hash_service_token(data["service_token"]) == new_hash
    # audit event
    audit = test_db_session.query(AuditLog).filter(
        AuditLog.action == "gateway.credential.rotated"
    ).first()
    assert audit is not None


def test_rotate_from_no_previous_token(test_db_session: DbSession) -> None:
    gw = _seed_gateway(test_db_session, name="No Token GW", token_hash=None)
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/gateways/{gw.id}/rotate-credential",
        json={"reason": "initial provisioning"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "service_token" in data
    test_db_session.refresh(gw)
    assert gw.service_token_hash is not None
