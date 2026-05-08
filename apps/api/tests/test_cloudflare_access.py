from __future__ import annotations

import importlib
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession, sessionmaker

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.security.cloudflare_access import CloudflareAccessVerifier

importlib.import_module("cctv_api.models.tables")


def _client_with_test_key(
    monkeypatch: pytest.MonkeyPatch,
    test_db_factory: sessionmaker[DbSession],
    **settings_overrides: Any,
) -> tuple[TestClient, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = key.public_key()
    settings = Settings(
        APP_ENV="production",
        CF_ACCESS_ISSUER="https://team.cloudflareaccess.com",
        CF_ACCESS_AUD_DASHBOARD="dashboard-aud",
        CF_ACCESS_AUD_ADMIN="admin-aud",
        CF_ACCESS_JWKS_URL="https://team.cloudflareaccess.com/cdn-cgi/access/certs",
        **settings_overrides,
    )

    def fake_get_signing_key(
        _verifier: CloudflareAccessVerifier,
        _token: str,
    ) -> SimpleNamespace:
        return SimpleNamespace(key=public_key)

    monkeypatch.setattr(CloudflareAccessVerifier, "_get_signing_key", fake_get_signing_key)
    app = create_app(settings=settings)

    def _override_db() -> Generator[DbSession, None, None]:
        session = test_db_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app), key


def _browser_token(
    key: rsa.RSAPrivateKey,
    **claim_overrides: Any,
) -> str:
    now = datetime.now(timezone.utc)
    claims: dict[str, Any] = {
        "iss": "https://team.cloudflareaccess.com",
        "aud": "dashboard-aud",
        "sub": "user-123",
        "email": "viewer@example.test",
        "roles": ["viewer"],
        "permissions": ["camera:view"],
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(claim_overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


def test_cloudflare_access_jwt_returns_non_dev_principal(
    monkeypatch: pytest.MonkeyPatch,
    _test_db: sessionmaker[DbSession],
) -> None:
    client, key = _client_with_test_key(monkeypatch, _test_db)
    token = _browser_token(key)

    response = client.get("/api/v1/me", headers={"cf-access-jwt-assertion": token})

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "user"
    assert body["subject"] == "user-123"
    assert body["email"] == "viewer@example.test"
    assert body["is_dev"] is False
    assert body["gateway_id"] is None


def test_cloudflare_access_jwt_rejects_malformed_token(
    monkeypatch: pytest.MonkeyPatch,
    _test_db: sessionmaker[DbSession],
) -> None:
    client, _key = _client_with_test_key(monkeypatch, _test_db)

    response = client.get("/api/v1/me", headers={"cf-access-jwt-assertion": "not-a-jwt"})

    assert response.status_code == 401
    assert response.json()["detail"] == "cf-access-token-invalid"


def test_cloudflare_access_jwt_rejects_wrong_issuer(
    monkeypatch: pytest.MonkeyPatch,
    _test_db: sessionmaker[DbSession],
) -> None:
    client, key = _client_with_test_key(monkeypatch, _test_db)
    token = _browser_token(key, iss="https://wrong.example.test")

    response = client.get("/api/v1/me", headers={"cf-access-jwt-assertion": token})

    assert response.status_code == 401
    assert response.json()["detail"] == "cf-access-token-invalid"


def test_cloudflare_access_jwt_rejects_wrong_audience(
    monkeypatch: pytest.MonkeyPatch,
    _test_db: sessionmaker[DbSession],
) -> None:
    client, key = _client_with_test_key(monkeypatch, _test_db)
    token = _browser_token(key, aud="wrong-audience")

    response = client.get("/api/v1/me", headers={"cf-access-jwt-assertion": token})

    assert response.status_code == 401
    assert response.json()["detail"] == "cf-access-token-invalid"


def test_cloudflare_access_jwt_rejects_expired_token(
    monkeypatch: pytest.MonkeyPatch,
    _test_db: sessionmaker[DbSession],
) -> None:
    client, key = _client_with_test_key(monkeypatch, _test_db, CLOCK_SKEW_SECONDS=0)
    now = datetime.now(timezone.utc)
    token = _browser_token(
        key,
        iat=now - timedelta(minutes=10),
        nbf=now - timedelta(minutes=10),
        exp=now - timedelta(minutes=1),
    )

    response = client.get("/api/v1/me", headers={"cf-access-jwt-assertion": token})

    assert response.status_code == 401
    assert response.json()["detail"] == "cf-access-token-invalid"


def test_gateway_routes_do_not_accept_browser_jwt(
    monkeypatch: pytest.MonkeyPatch,
    _test_db: sessionmaker[DbSession],
) -> None:
    client, key = _client_with_test_key(monkeypatch, _test_db)
    token = _browser_token(key)

    response = client.post(
        "/api/v1/gateways/gateway-1/heartbeat",
        headers={"cf-access-jwt-assertion": token},
        json={"status": "online", "agent_version": "0.1.0", "cameras": []},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "gateway-identity-required"
