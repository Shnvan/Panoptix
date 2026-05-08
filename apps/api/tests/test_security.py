from __future__ import annotations

from fastapi.testclient import TestClient

from cctv_api.core.config import Settings
from cctv_api.main import create_app


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "cf-access-token-required"


def test_cameras_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/cameras")
    assert response.status_code == 401
    assert response.json()["detail"] == "cf-access-token-required"


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
