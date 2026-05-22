from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

import cctv_api.security.dependencies as dependencies
from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.tables import LoginBaseline, Role, Session as UserSession, User, UserRole
from cctv_api.security.identity import Principal, PrincipalKind


SESSION_SIGNING_KEY = "test-session-signing-key-with-enough-entropy"
CSRF_SIGNING_KEY = "test-csrf-signing-key-with-enough-entropy"


class _StubVerifier:
    def __init__(_self, _settings: Settings) -> None:
        pass

    def verify_browser_request(_self, _request):  # type: ignore[no-untyped-def]
        return Principal(
            kind=PrincipalKind.USER,
            subject="admin@example.test",
            email="admin@example.test",
            roles=frozenset({"admin"}),
            is_dev=False,
        )


_SAFE_PRODUCTION_OVERRIDES = {
    "CF_ACCESS_ISSUER": "https://team.cloudflareaccess.com",
    "CF_ACCESS_AUD_DASHBOARD": "dashboard-aud",
    "CF_ACCESS_AUD_ADMIN": "admin-aud",
    "CF_ACCESS_AUD_GATEWAY": "gateway-aud",
    "CF_ACCESS_JWKS_URL": "https://team.cloudflareaccess.com/cdn-cgi/access/certs",
    "DATABASE_URL": "postgresql+psycopg://user:pass@db:5432/panoptix",
    "MIGRATION_DATABASE_URL": "postgresql+psycopg://migrator:pass@db:5432/panoptix",
    "GATEWAY_SERVICE_TOKEN": "real-gateway-token",
    "GATEWAY_COMMAND_SIGNING_KEY": "real-signing-key",
}


def _browser_client(
    test_db_session: DbSession,
    monkeypatch,  # type: ignore[no-untyped-def]
    **setting_overrides: object,
) -> TestClient:
    monkeypatch.setattr(dependencies, "CloudflareAccessVerifier", _StubVerifier)
    app = create_app(
        settings=Settings(
            APP_ENV="production",
            ALLOW_DEV_AUTH=False,
            SESSION_SIGNING_KEY=SESSION_SIGNING_KEY,
            CSRF_SIGNING_KEY=CSRF_SIGNING_KEY,
            AUDIT_HMAC_KEY_VERSION=1,
            AUDIT_HMAC_KEY="test-audit-key-with-enough-entropy",
            **_SAFE_PRODUCTION_OVERRIDES,
            **setting_overrides,
        )
    )

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app, base_url="https://testserver")


def _grant_admin_role(db: DbSession) -> None:
    user = User(email="admin@example.test", idp_subject="admin@example.test")
    role = Role(id=1, name="admin")
    db.add(user)
    db.add(role)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "cf-access-token-required"


def test_cameras_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/cameras")
    assert response.status_code == 401
    assert response.json()["detail"] == "cf-access-token-required"


def test_security_headers_are_added_to_success_response() -> None:
    app = create_app(settings=Settings(APP_ENV="development", ALLOW_DEV_AUTH=True))
    client = TestClient(app)

    response = client.get("/api/v1/me", headers={"x-panoptix-dev-auth": "1"})

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert "camera=()" in response.headers["permissions-policy"]
    assert "microphone=()" in response.headers["permissions-policy"]
    assert "display-capture=()" in response.headers["permissions-policy"]
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "connect-src 'self'" in response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["strict-transport-security"] == "max-age=63072000; includeSubDomains; preload"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"


def test_development_docs_csp_allows_swagger_ui_assets() -> None:
    app = create_app(settings=Settings(APP_ENV="development", ALLOW_DEV_AUTH=True))
    client = TestClient(app)

    response = client.get("/docs")

    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    assert "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in csp
    assert "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in csp
    assert "img-src 'self' data: https://fastapi.tiangolo.com" in csp
    assert "connect-src 'self'" in csp


def test_regular_api_csp_stays_strict_in_development() -> None:
    app = create_app(settings=Settings(APP_ENV="development", ALLOW_DEV_AUTH=True))
    client = TestClient(app)

    response = client.get("/api/v1/me", headers={"x-panoptix-dev-auth": "1"})

    csp = response.headers["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "script-src" not in csp
    assert "style-src" not in csp


def test_security_headers_are_added_to_problem_response(client: TestClient) -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["strict-transport-security"] == "max-age=63072000; includeSubDomains; preload"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"


def test_csp_includes_livekit_connect_src_when_configured() -> None:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            LIVEKIT_CONNECT_SRC="wss://my-project.livekit.cloud",
        )
    )
    client = TestClient(app)

    response = client.get("/api/v1/me", headers={"x-panoptix-dev-auth": "1"})

    csp = response.headers["content-security-policy"]
    assert "connect-src 'self' wss://my-project.livekit.cloud" in csp


def test_csp_omits_placeholder_livekit_connect_src() -> None:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            LIVEKIT_CONNECT_SRC="wss://replace-me.livekit.cloud",
        )
    )
    client = TestClient(app)

    response = client.get("/api/v1/me", headers={"x-panoptix-dev-auth": "1"})

    csp = response.headers["content-security-policy"]
    assert "replace-me" not in csp
    assert "connect-src 'self'" in csp


def test_csp_uses_fallback_livekit_url_when_mode_is_fallback() -> None:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            LIVEKIT_MODE="fallback",
            LIVEKIT_FALLBACK_URL="wss://livekit.mysite.test",
        )
    )
    client = TestClient(app)

    response = client.get("/api/v1/me", headers={"x-panoptix-dev-auth": "1"})

    csp = response.headers["content-security-policy"]
    assert "wss://livekit.mysite.test" in csp


def test_cors_not_emitted_for_gateway_routes() -> None:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            APP_PUBLIC_BASE_URL="https://cctv.real-domain.test",
        )
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/gateways/00000000-0000-0000-0000-000000000001/heartbeat",
        headers={"x-panoptix-dev-gateway-id": "00000000-0000-0000-0000-000000000001"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_cors_emitted_for_browser_routes_with_real_origin() -> None:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            APP_PUBLIC_BASE_URL="https://cctv.real-domain.test",
        )
    )
    client = TestClient(app)

    response = client.get("/api/v1/me", headers={"x-panoptix-dev-auth": "1"})

    assert response.headers["access-control-allow-origin"] == "https://cctv.real-domain.test"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_not_emitted_with_placeholder_origin() -> None:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            APP_PUBLIC_BASE_URL="https://cctv.example.test",
        )
    )
    client = TestClient(app)

    response = client.get("/api/v1/me", headers={"x-panoptix-dev-auth": "1"})

    assert "access-control-allow-origin" not in response.headers


def test_csp_includes_media_src_blob() -> None:
    app = create_app(settings=Settings(APP_ENV="development", ALLOW_DEV_AUTH=True))
    client = TestClient(app)

    response = client.get("/api/v1/me", headers={"x-panoptix-dev-auth": "1"})

    csp = response.headers["content-security-policy"]
    assert "media-src blob:" in csp


def test_dev_auth_header_fails_when_disabled(client: TestClient) -> None:
    response = client.get("/api/v1/me", headers={"x-panoptix-dev-auth": "1"})
    assert response.status_code == 401
    assert response.json()["detail"] == "dev-auth-disabled"


def test_dev_auth_returns_principal_when_enabled() -> None:
    app = create_app(settings=Settings(APP_ENV="development", ALLOW_DEV_AUTH=True))
    client = TestClient(app)

    response = client.get(
        "/api/v1/me",
        headers={
            "x-panoptix-dev-auth": "1",
            "x-panoptix-dev-subject": "dev-subject",
            "x-panoptix-dev-email": "dev-user@example.test",
            "x-panoptix-dev-roles": "viewer,admin",
            "x-panoptix-dev-permissions": "camera:view",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "kind": "user",
        "subject": "dev-subject",
        "email": "dev-user@example.test",
        "roles": ["admin", "viewer"],
        "permissions": ["camera:view"],
        "gateway_id": None,
        "is_dev": True,
    }


def test_dev_auth_forbidden_outside_development() -> None:
    import pytest

    with pytest.raises(ValueError, match="ALLOW_DEV_AUTH"):
        create_app(settings=Settings(
            APP_ENV="staging",
            ALLOW_DEV_AUTH=True,
            SESSION_SIGNING_KEY=SESSION_SIGNING_KEY,
            CSRF_SIGNING_KEY=CSRF_SIGNING_KEY,
            AUDIT_HMAC_KEY="test-audit-key",
            **_SAFE_PRODUCTION_OVERRIDES,
        ))


def test_browser_get_sets_session_and_csrf_cookies(test_db_session: DbSession, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _grant_admin_role(test_db_session)
    client = _browser_client(test_db_session, monkeypatch)

    response = client.get("/api/v1/me")

    assert response.status_code == 200
    assert client.cookies.get("panoptix_session") is not None
    assert client.cookies.get("panoptix_csrf") is not None


def test_browser_session_and_login_baseline_use_trusted_cf_client_ip(
    test_db_session: DbSession,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    _grant_admin_role(test_db_session)
    client = _browser_client(
        test_db_session,
        monkeypatch,
        TRUST_CF_CONNECTING_IP=True,
        SUSPICIOUS_LOGIN_DETECTION_ENABLED=True,
    )

    response = client.get(
        "/api/v1/me",
        headers={"cf-connecting-ip": "203.0.113.42", "cf-ipcountry": "PH"},
    )

    assert response.status_code == 200
    session_row = test_db_session.execute(select(UserSession)).scalar_one()
    baseline = test_db_session.execute(select(LoginBaseline)).scalar_one()
    assert session_row.ip == "203.0.113.42"
    assert baseline.known_ips == ["203.0.113.42"]
    assert baseline.last_login_country == "PH"


def test_browser_admin_post_requires_csrf(test_db_session: DbSession, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _grant_admin_role(test_db_session)
    client = _browser_client(test_db_session, monkeypatch)
    assert client.get("/api/v1/me").status_code == 200
    session_cookie = client.cookies.get("panoptix_session")
    client.cookies.clear()
    client.cookies.set("panoptix_session", session_cookie or "", domain="testserver.local", path="/")

    response = client.post(
        "/api/v1/admin/jobs/run-maintenance",
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "csrf-token-required"


def test_browser_admin_post_rejects_invalid_csrf(test_db_session: DbSession, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _grant_admin_role(test_db_session)
    client = _browser_client(test_db_session, monkeypatch)
    assert client.get("/api/v1/me").status_code == 200

    response = client.post(
        "/api/v1/admin/jobs/run-maintenance",
        headers={"x-panoptix-csrf-token": "invalid-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "csrf-token-invalid"


def test_browser_admin_post_accepts_valid_csrf(test_db_session: DbSession, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _grant_admin_role(test_db_session)
    client = _browser_client(test_db_session, monkeypatch)
    assert client.get("/api/v1/me").status_code == 200
    csrf_token = client.cookies.get("panoptix_csrf")

    response = client.post(
        "/api/v1/admin/jobs/run-maintenance",
        headers={"x-panoptix-csrf-token": csrf_token or ""},
    )

    assert response.status_code == 200
    assert response.json() == {
        "expired_commands": 0,
        "stops_enqueued": 0,
        "purged_visitor_visits": 0,
    }


def test_dev_auth_admin_post_does_not_require_csrf(test_db_session: DbSession) -> None:
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
    client = TestClient(app)

    response = client.post(
        "/api/v1/admin/jobs/run-maintenance",
        headers={"x-panoptix-dev-auth": "1", "x-panoptix-dev-roles": "admin"},
    )

    assert response.status_code == 200
