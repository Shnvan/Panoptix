from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import GatewayStatus
from cctv_api.models.tables import AuditLog, EdgeGateway
from cctv_api.security.service_tokens import generate_service_token, hash_service_token, verify_service_token


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


def _seed_gateway(
    db: DbSession,
    *,
    status: GatewayStatus = GatewayStatus.enabled,
    disabled_at: datetime | None = None,
    service_token_hash: str | None = None,
) -> EdgeGateway:
    gateway = EdgeGateway(
        id=uuid.uuid4(),
        name="Test Gateway",
        status=status,
        disabled_at=disabled_at,
        service_token_hash=service_token_hash,
    )
    db.add(gateway)
    db.commit()
    db.refresh(gateway)
    return gateway


def test_service_tokens_are_unique_and_verifiable() -> None:
    token_a = generate_service_token()
    token_b = generate_service_token()

    assert token_a != token_b
    assert len(token_a) >= 32
    token_hash = hash_service_token(token_a)
    assert token_hash != token_a
    assert verify_service_token(token_a, token_hash)
    assert not verify_service_token(token_b, token_hash)


def test_create_gateway_returns_token_once_and_stores_hash(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/gateways", headers=_ADMIN_HEADERS, json={"name": "Gateway A"})

    assert response.status_code == 201
    body = response.json()
    assert body["service_token"]

    gateway = test_db_session.execute(select(EdgeGateway)).scalar_one()
    assert gateway.service_token_hash is not None
    assert gateway.service_token_hash != body["service_token"]
    assert verify_service_token(body["service_token"], gateway.service_token_hash)

    audit = test_db_session.execute(select(AuditLog).where(AuditLog.action == "gateway.create")).scalar_one()
    assert audit.payload["credential_issued"] == "[REDACTED]"
    assert "service_token" not in audit.payload


def test_rotate_credential_requires_authentication(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/rotate-credential",
        json={"reason": "routine rotation"},
    )
    assert response.status_code == 401


def test_rotate_credential_requires_admin_role(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/rotate-credential",
        headers=_VIEWER_HEADERS,
        json={"reason": "routine rotation"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_rotate_credential_rejects_invalid_gateway_id(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post(
        "/api/v1/admin/gateways/not-a-uuid/rotate-credential",
        headers=_ADMIN_HEADERS,
        json={"reason": "routine rotation"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "gateway-id-invalid"


def test_rotate_credential_rejects_missing_gateway(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{uuid.uuid4()}/rotate-credential",
        headers=_ADMIN_HEADERS,
        json={"reason": "routine rotation"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "gateway-not-found"


def test_rotate_credential_rejects_disabled_gateway(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(
        test_db_session,
        status=GatewayStatus.disabled,
        disabled_at=datetime.now(timezone.utc),
    )
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/rotate-credential",
        headers=_ADMIN_HEADERS,
        json={"reason": "routine rotation"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "gateway-disabled"


def test_rotate_credential_success_returns_new_token_and_audits(test_db_session: DbSession) -> None:
    old_token = generate_service_token()
    gateway = _seed_gateway(test_db_session, service_token_hash=hash_service_token(old_token))

    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/rotate-credential",
        headers=_ADMIN_HEADERS,
        json={"reason": "routine rotation"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["gateway_id"] == str(gateway.id)
    assert body["service_token"]
    assert body["service_token"] != old_token
    assert body["rotated_at"] is not None

    test_db_session.refresh(gateway)
    assert gateway.service_token_hash is not None
    assert not verify_service_token(old_token, gateway.service_token_hash)
    assert verify_service_token(body["service_token"], gateway.service_token_hash)

    audit = test_db_session.execute(select(AuditLog).where(AuditLog.action == "gateway.credential.rotated")).scalar_one()
    assert audit.payload["gateway_id"] == str(gateway.id)
    assert audit.payload["reason"] == "routine rotation"
    assert "service_token" not in audit.payload


def test_second_rotation_invalidates_first_rotated_token(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session, service_token_hash=hash_service_token(generate_service_token()))
    client = _client(test_db_session)

    first = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/rotate-credential",
        headers=_ADMIN_HEADERS,
        json={"reason": "first"},
    ).json()["service_token"]
    second = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/rotate-credential",
        headers=_ADMIN_HEADERS,
        json={"reason": "second"},
    ).json()["service_token"]

    test_db_session.refresh(gateway)
    assert first != second
    assert not verify_service_token(first, gateway.service_token_hash)
    assert verify_service_token(second, gateway.service_token_hash)
