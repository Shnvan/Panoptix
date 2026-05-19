"""Tests for admin mutation endpoint rate limiting (§16.17)."""
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
from cctv_api.models.tables import AuditLog, EdgeGateway, Role, User
from cctv_api.security.rate_limit import get_rate_limiter


AUDIT_HMAC_KEY = "test-audit-hmac-key-with-enough-entropy"

_ADMIN_HEADERS = {
    "x-panoptix-dev-auth": "1",
    "x-panoptix-dev-email": "admin@example.test",
    "x-panoptix-dev-subject": "admin@example.test",
    "x-panoptix-dev-roles": "admin",
}


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = dict(
        APP_ENV="development",
        ALLOW_DEV_AUTH=True,
        AUDIT_HMAC_KEY_VERSION=1,
        AUDIT_HMAC_KEY=AUDIT_HMAC_KEY,
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _client(test_db_session: DbSession, **overrides: object) -> TestClient:
    app = create_app(settings=_settings(**overrides))
    app.dependency_overrides[db_session] = lambda: test_db_session
    return TestClient(app)


def _seed_gateway(
    db: DbSession,
    *,
    name: str = "Test GW",
    status: GatewayStatus = GatewayStatus.enabled,
) -> EdgeGateway:
    gw = EdgeGateway(
        id=uuid.uuid4(),
        name=name,
        status=status,
        created_at=datetime.now(timezone.utc),
    )
    db.add(gw)
    db.commit()
    db.refresh(gw)
    return gw


def _seed_role(db: DbSession, *, name: str = "admin") -> Role:
    role = Role(id=1, name=name)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def _seed_target_user(db: DbSession, *, email: str = "target@example.test") -> User:
    user = User(id=uuid.uuid4(), email=email, idp_subject=email, created_at=datetime.now(timezone.utc))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _audit_actions(db: DbSession) -> list[str]:
    return [row.action for row in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars().all()]


# ── rotate-credential ──


def test_rotate_credential_rate_limited(test_db_session: DbSession) -> None:
    get_rate_limiter().reset()
    gw = _seed_gateway(test_db_session)
    client = _client(
        test_db_session,
        RATE_LIMIT_ADMIN_MUTATION_MAX=2,
        RATE_LIMIT_ADMIN_MUTATION_WINDOW=60,
    )

    # Exhaust the limit
    for _ in range(2):
        resp = client.post(
            f"/api/v1/admin/gateways/{gw.id}/rotate-credential",
            json={"reason": "test rotation"},
            headers=_ADMIN_HEADERS,
        )
        assert resp.status_code == 200

    # Next request must be rate-limited
    resp = client.post(
        f"/api/v1/admin/gateways/{gw.id}/rotate-credential",
        json={"reason": "test rotation"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 429
    assert resp.json()["detail"] == "rate-limit-exceeded"
    assert "retry-after" in resp.headers

    get_rate_limiter().reset()


# ── user role ──


def test_user_role_rate_limited(test_db_session: DbSession) -> None:
    get_rate_limiter().reset()
    target = _seed_target_user(test_db_session)
    role = _seed_role(test_db_session)
    client = _client(
        test_db_session,
        RATE_LIMIT_ADMIN_MUTATION_MAX=2,
        RATE_LIMIT_ADMIN_MUTATION_WINDOW=60,
    )

    # Exhaust the limit (grant then revoke to avoid conflict on second grant)
    resp = client.post(
        f"/api/v1/admin/users/{target.id}/role",
        json={"action": "grant", "role_name": role.name},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200

    resp = client.post(
        f"/api/v1/admin/users/{target.id}/role",
        json={"action": "revoke", "role_name": role.name},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200

    # Third request must be rate-limited
    resp = client.post(
        f"/api/v1/admin/users/{target.id}/role",
        json={"action": "grant", "role_name": role.name},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 429
    assert resp.json()["detail"] == "rate-limit-exceeded"
    assert "retry-after" in resp.headers

    get_rate_limiter().reset()


# ── break-glass open ──


def test_break_glass_open_rate_limited(test_db_session: DbSession) -> None:
    get_rate_limiter().reset()
    client = _client(
        test_db_session,
        RATE_LIMIT_ADMIN_MUTATION_MAX=2,
        RATE_LIMIT_ADMIN_MUTATION_WINDOW=60,
    )

    # Exhaust the limit (open then close to avoid re-open conflict)
    resp = client.post(
        "/api/v1/admin/break-glass/open",
        json={"reason": "test"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200

    resp = client.post(
        "/api/v1/admin/break-glass/close",
        json={"reason": "done"},
        headers=_ADMIN_HEADERS,
    )
    # close uses a separate counter key but the open counter is now at 1;
    # we need a second open to hit 2 — re-open after close
    assert resp.status_code in (200, 409)

    resp = client.post(
        "/api/v1/admin/break-glass/open",
        json={"reason": "second open"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200

    # Third open request must be rate-limited
    resp = client.post(
        "/api/v1/admin/break-glass/open",
        json={"reason": "third open"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 429
    assert resp.json()["detail"] == "rate-limit-exceeded"
    assert "retry-after" in resp.headers

    get_rate_limiter().reset()


# ── admin commands enqueue ──


def test_admin_commands_rate_limited(test_db_session: DbSession) -> None:
    get_rate_limiter().reset()
    gw = _seed_gateway(test_db_session)
    client = _client(
        test_db_session,
        RATE_LIMIT_ADMIN_MUTATION_MAX=2,
        RATE_LIMIT_ADMIN_MUTATION_WINDOW=60,
    )

    # Exhaust the limit
    for _ in range(2):
        resp = client.post(
            f"/api/v1/admin/gateways/{gw.id}/commands",
            json={"kind": "reload_config", "payload": {}, "expires_in_seconds": 300},
            headers=_ADMIN_HEADERS,
        )
        assert resp.status_code == 201

    # Next request must be rate-limited
    resp = client.post(
        f"/api/v1/admin/gateways/{gw.id}/commands",
        json={"kind": "reload_config", "payload": {}, "expires_in_seconds": 300},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 429
    assert resp.json()["detail"] == "rate-limit-exceeded"
    assert "retry-after" in resp.headers

    get_rate_limiter().reset()


# ── counter resets after window ──


def test_admin_rate_limit_resets_after_window(test_db_session: DbSession) -> None:
    get_rate_limiter().reset()
    gw = _seed_gateway(test_db_session)
    client = _client(
        test_db_session,
        RATE_LIMIT_ADMIN_MUTATION_MAX=1,
        RATE_LIMIT_ADMIN_MUTATION_WINDOW=10,  # minimum allowed window
    )

    # First request succeeds
    resp = client.post(
        f"/api/v1/admin/gateways/{gw.id}/rotate-credential",
        json={"reason": "initial"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200

    # Second request is rate-limited
    resp = client.post(
        f"/api/v1/admin/gateways/{gw.id}/rotate-credential",
        json={"reason": "blocked"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 429

    # Reset the limiter to simulate window expiry
    get_rate_limiter().reset()

    # After reset, request succeeds again
    resp = client.post(
        f"/api/v1/admin/gateways/{gw.id}/rotate-credential",
        json={"reason": "after window"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200

    get_rate_limiter().reset()


# ── audit event on rate limit ──


def test_admin_rate_limit_audit_event(test_db_session: DbSession) -> None:
    get_rate_limiter().reset()
    gw = _seed_gateway(test_db_session)
    client = _client(
        test_db_session,
        RATE_LIMIT_ADMIN_MUTATION_MAX=1,
        RATE_LIMIT_ADMIN_MUTATION_WINDOW=60,
    )

    # First request succeeds and records a normal audit event
    resp = client.post(
        f"/api/v1/admin/gateways/{gw.id}/rotate-credential",
        json={"reason": "first"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200

    # Second request is rate-limited and should record an admin.rate_limited audit event
    resp = client.post(
        f"/api/v1/admin/gateways/{gw.id}/rotate-credential",
        json={"reason": "second"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 429

    actions = _audit_actions(test_db_session)
    assert "admin.rate_limited" in actions

    # Verify the rate_limited event has a retry_after payload
    rate_limited_rows = [
        row
        for row in test_db_session.execute(select(AuditLog).order_by(AuditLog.id)).scalars().all()
        if row.action == "admin.rate_limited"
    ]
    assert len(rate_limited_rows) == 1
    assert rate_limited_rows[0].payload is not None
    assert "retry_after" in rate_limited_rows[0].payload

    get_rate_limiter().reset()
