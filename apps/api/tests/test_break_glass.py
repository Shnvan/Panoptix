from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.tables import AuditLog, BreakGlassUsage
from cctv_api.security.break_glass import (
    BREAK_GLASS_WINDOW_MINUTES,
    ROTATION_CHECKLIST,
    assert_break_glass_active,
    get_active_window,
)


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


def _seed_open_window(
    db: DbSession,
    *,
    opened_minutes_ago: int = 5,
    window_minutes: int = BREAK_GLASS_WINDOW_MINUTES,
) -> BreakGlassUsage:
    now = datetime.now(timezone.utc)
    opened_at = now - timedelta(minutes=opened_minutes_ago)
    usage = BreakGlassUsage(
        id=uuid.uuid4(),
        opened_at=opened_at,
        opened_by_reason="test window",
        auto_disable_at=opened_at + timedelta(minutes=window_minutes),
    )
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage


# ── Open endpoint ──


def test_open_unauthenticated(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post("/api/v1/admin/break-glass/open", json={"reason": "test"})
    assert resp.status_code == 401


def test_open_viewer_forbidden(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/break-glass/open",
        json={"reason": "test"},
        headers=_VIEWER_HEADERS,
    )
    assert resp.status_code == 403


def test_open_success(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/break-glass/open",
        json={"reason": "IdP outage"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "window_id" in data
    assert "opened_at" in data
    assert "auto_disable_at" in data

    row = test_db_session.execute(
        select(BreakGlassUsage).where(BreakGlassUsage.id == data["window_id"])
    ).scalar_one_or_none()
    assert row is not None
    assert row.opened_by_reason == "IdP outage"
    assert row.closed_at is None

    audit = test_db_session.execute(
        select(AuditLog).where(AuditLog.action == "system.break_glass.opened")
    ).scalar_one_or_none()
    assert audit is not None
    assert audit.payload["reason"] == "IdP outage"


def test_open_already_active_conflict(test_db_session: DbSession) -> None:
    _seed_open_window(test_db_session)
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/break-glass/open",
        json={"reason": "second attempt"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "break-glass-already-active"


def test_open_after_expired_window_succeeds(test_db_session: DbSession) -> None:
    _seed_open_window(test_db_session, opened_minutes_ago=100, window_minutes=90)
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/break-glass/open",
        json={"reason": "new window after expired"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "window_id" in data


# ── Close endpoint ──


def test_close_success(test_db_session: DbSession) -> None:
    usage = _seed_open_window(test_db_session)
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/break-glass/close",
        json={"reason": "incident resolved"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_id"] == str(usage.id)
    assert data["closed_at"] is not None
    assert data["rotation_required"] == ROTATION_CHECKLIST

    audit = test_db_session.execute(
        select(AuditLog).where(AuditLog.action == "system.break_glass.closed")
    ).scalar_one_or_none()
    assert audit is not None
    assert audit.payload["rotation_required"] == ROTATION_CHECKLIST


def test_close_no_active_window(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/break-glass/close",
        json={"reason": "nothing to close"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "no-active-break-glass-window"


def test_close_expired_unclosed_window(test_db_session: DbSession) -> None:
    _seed_open_window(test_db_session, opened_minutes_ago=100, window_minutes=90)
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/break-glass/close",
        json={"reason": "cleanup expired window"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["closed_at"] is not None


# ── Status endpoint ──


def test_status_no_window(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.get("/api/v1/admin/internal/break-glass-status")
    assert resp.status_code == 200
    assert resp.json() == {"active": False}


def test_status_active_window(test_db_session: DbSession) -> None:
    _seed_open_window(test_db_session)
    c = _client(test_db_session)
    resp = c.get("/api/v1/admin/internal/break-glass-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is True
    assert "auto_disable_at" in data


def test_status_expired_unclosed_window(test_db_session: DbSession) -> None:
    _seed_open_window(test_db_session, opened_minutes_ago=100, window_minutes=90)
    c = _client(test_db_session)
    resp = c.get("/api/v1/admin/internal/break-glass-status")
    assert resp.status_code == 200
    assert resp.json() == {"active": False}


# ── assert_break_glass_active (T-52 simulated) ──


def test_assert_break_glass_active_denies_after_90_minutes(
    test_db_session: DbSession,
) -> None:
    usage = _seed_open_window(test_db_session, opened_minutes_ago=0, window_minutes=90)
    opened = usage.opened_at
    if opened.tzinfo is None:
        opened = opened.replace(tzinfo=timezone.utc)

    result = get_active_window(test_db_session, now=opened + timedelta(minutes=89))
    assert result is not None

    result = get_active_window(test_db_session, now=opened + timedelta(minutes=91))
    assert result is None

    from cctv_api.api.errors import ProblemDetail

    try:
        assert_break_glass_active(
            test_db_session, now=opened + timedelta(minutes=91)
        )
        assert False, "should have raised"
    except ProblemDetail as exc:
        assert exc.detail == "break-glass-expired"
        assert exc.status == 403
