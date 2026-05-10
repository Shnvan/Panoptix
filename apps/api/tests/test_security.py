from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

import cctv_api.security.dependencies as dependencies
from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.tables import Role, User, UserRole
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


def _browser_client(test_db_session: DbSession, monkeypatch) -> TestClient:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(dependencies, "CloudflareAccessVerifier", _StubVerifier)
    app = create_app(
        settings=Settings(
            APP_ENV="production",
            SESSION_SIGNING_KEY=SESSION_SIGNING_KEY,
            CSRF_SIGNING_KEY=CSRF_SIGNING_KEY,
            AUDIT_HMAC_KEY_VERSION=1,
            AUDIT_HMAC_KEY="test-audit-key-with-enough-entropy",
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
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert "default-src 'none'" in response.headers["content-security-policy"]


def test_security_headers_are_added_to_problem_response(client: TestClient) -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"


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
    app = create_app(settings=Settings(APP_ENV="staging", ALLOW_DEV_AUTH=True))
    client = TestClient(app)

    response = client.get("/api/v1/me", headers={"x-panoptix-dev-auth": "1"})

    assert response.status_code == 401
    assert response.json()["detail"] == "dev-auth-forbidden-outside-development"


def test_browser_get_sets_session_and_csrf_cookies(test_db_session: DbSession, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _grant_admin_role(test_db_session)
    client = _browser_client(test_db_session, monkeypatch)

    response = client.get("/api/v1/me")

    assert response.status_code == 200
    assert client.cookies.get("panoptix_session") is not None
    assert client.cookies.get("panoptix_csrf") is not None


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
    assert response.json() == {"expired_commands": 0, "stops_enqueued": 0}


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
