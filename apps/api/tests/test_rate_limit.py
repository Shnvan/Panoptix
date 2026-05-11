"""Tests for in-memory rate limiter and endpoint rate limiting (§16.17)."""
from __future__ import annotations

import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import CameraSourceType
from cctv_api.models.tables import Camera, CameraAcl, User
from cctv_api.security.rate_limit import RateLimitConfig, RateLimiter, get_rate_limiter


# ── Unit tests for the RateLimiter core ──


def test_rate_limiter_allows_within_limit() -> None:
    limiter = RateLimiter()
    config = RateLimitConfig(max_requests=3, window_seconds=60)

    for _ in range(3):
        result = limiter.check("key-a", config)
        assert result.allowed is True

    assert result.remaining == 0


def test_rate_limiter_blocks_when_exceeded() -> None:
    limiter = RateLimiter()
    config = RateLimitConfig(max_requests=2, window_seconds=60)

    limiter.check("key-b", config)
    limiter.check("key-b", config)

    result = limiter.check("key-b", config)
    assert result.allowed is False
    assert result.retry_after > 0


def test_rate_limiter_different_keys_are_independent() -> None:
    limiter = RateLimiter()
    config = RateLimitConfig(max_requests=1, window_seconds=60)

    limiter.check("key-c", config)
    result = limiter.check("key-d", config)
    assert result.allowed is True


def test_rate_limiter_reset_clears_all() -> None:
    limiter = RateLimiter()
    config = RateLimitConfig(max_requests=1, window_seconds=60)

    limiter.check("key-e", config)
    result = limiter.check("key-e", config)
    assert result.allowed is False

    limiter.reset()

    result = limiter.check("key-e", config)
    assert result.allowed is True


def test_rate_limiter_window_expires() -> None:
    limiter = RateLimiter()
    config = RateLimitConfig(max_requests=1, window_seconds=1)

    limiter.check("key-f", config)
    result = limiter.check("key-f", config)
    assert result.allowed is False

    time.sleep(1.1)

    result = limiter.check("key-f", config)
    assert result.allowed is True


def test_rate_limiter_remaining_decrements() -> None:
    limiter = RateLimiter()
    config = RateLimitConfig(max_requests=5, window_seconds=60)

    r1 = limiter.check("key-g", config)
    assert r1.remaining == 4

    r2 = limiter.check("key-g", config)
    assert r2.remaining == 3


def test_rate_limiter_retry_after_is_positive() -> None:
    limiter = RateLimiter()
    config = RateLimitConfig(max_requests=1, window_seconds=60)

    limiter.check("key-h", config)
    result = limiter.check("key-h", config)
    assert result.allowed is False
    assert result.retry_after >= 1


# ── Integration tests: viewer token rate limiting ──


LIVEKIT_SECRET = "test-livekit-secret-with-at-least-32-bytes"
AUDIT_HMAC_KEY = "test-audit-hmac-key-with-enough-entropy"


def _rl_settings(**overrides: object) -> Settings:
    base = dict(
        APP_ENV="development",
        ALLOW_DEV_AUTH=True,
        LIVEKIT_CLOUD_URL="wss://livekit.example.test",
        LIVEKIT_CLOUD_API_KEY="test-livekit-key",
        LIVEKIT_CLOUD_API_SECRET=LIVEKIT_SECRET,
        AUDIT_HMAC_KEY=AUDIT_HMAC_KEY,
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _rl_client(test_db_session: DbSession, **overrides: object) -> TestClient:
    app = create_app(settings=_rl_settings(**overrides))
    app.dependency_overrides[db_session] = lambda: test_db_session
    return TestClient(app)


def _auth_headers(email: str = "rl@example.test") -> dict[str, str]:
    return {
        "x-panoptix-dev-auth": "1",
        "x-panoptix-dev-email": email,
        "x-panoptix-dev-subject": email,
    }


def _seed_user(db: DbSession, *, email: str = "rl@example.test") -> User:
    user = User(id=uuid.uuid4(), email=email, idp_subject=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_camera(db: DbSession) -> Camera:
    camera = Camera(
        id=uuid.uuid4(),
        display_name="RL Test Cam",
        source_type=CameraSourceType.rtsp,
        livekit_room_name=f"rl-cam-{uuid.uuid4().hex[:8]}",
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


def test_viewer_token_rate_limit_returns_429(test_db_session: DbSession) -> None:
    get_rate_limiter().reset()

    user = _seed_user(test_db_session)
    camera = _seed_camera(test_db_session)
    test_db_session.add(CameraAcl(user_id=user.id, camera_id=camera.id))
    test_db_session.commit()

    client = _rl_client(
        test_db_session,
        RATE_LIMIT_VIEWER_TOKEN_MAX=2,
        RATE_LIMIT_VIEWER_TOKEN_WINDOW=60,
    )

    # First two requests should succeed
    for _ in range(2):
        resp = client.get(
            f"/api/v1/cameras/{camera.id}/view-token",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200

    # Third request should be rate-limited
    resp = client.get(
        f"/api/v1/cameras/{camera.id}/view-token",
        headers=_auth_headers(),
    )
    assert resp.status_code == 429
    body = resp.json()
    assert body["detail"] == "rate-limit-exceeded"
    assert "retry-after" in resp.headers

    get_rate_limiter().reset()


def test_viewer_token_within_limit_succeeds(test_db_session: DbSession) -> None:
    get_rate_limiter().reset()

    user = _seed_user(test_db_session, email="rl-ok@example.test")
    camera = _seed_camera(test_db_session)
    test_db_session.add(CameraAcl(user_id=user.id, camera_id=camera.id))
    test_db_session.commit()

    client = _rl_client(
        test_db_session,
        RATE_LIMIT_VIEWER_TOKEN_MAX=100,
        RATE_LIMIT_VIEWER_TOKEN_WINDOW=60,
    )

    resp = client.get(
        f"/api/v1/cameras/{camera.id}/view-token",
        headers=_auth_headers("rl-ok@example.test"),
    )
    assert resp.status_code == 200

    get_rate_limiter().reset()
