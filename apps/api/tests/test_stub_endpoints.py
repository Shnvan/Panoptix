from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.integrations.github_invites import GitHubInviteError, GitHubInviteResult
from cctv_api.main import create_app
from cctv_api.models.tables import AuditLog, Role, User, UserRole


def _client(test_db_session: DbSession, *, github_invites_enabled: bool = False) -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            AUDIT_HMAC_KEY_VERSION=1,
            AUDIT_HMAC_KEY="test-audit-key-with-enough-entropy",
            GITHUB_INVITES_ENABLED=github_invites_enabled,
            GITHUB_ORG="panoptix-test",
            GITHUB_INVITE_TOKEN="test-github-token",
        )
    )

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


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


def _seed_role(db: DbSession, *, role_id: int, name: str) -> Role:
    role = Role(id=role_id, name=name)
    db.add(role)
    db.commit()
    return role


def _invite_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "email": "new-user@example.test",
        "role_names": ["viewer"],
        "reason": "new operator",
    }
    body.update(overrides)
    return body


# POST /api/v1/admin/users/invite


def test_invite_requires_auth(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/users/invite", json=_invite_body())
    assert response.status_code == 401


def test_invite_requires_admin_role(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/users/invite", headers=_VIEWER_HEADERS, json=_invite_body())
    assert response.status_code == 403


def test_invite_success_creates_user_assigns_role_and_writes_audit(
    test_db_session: DbSession,
) -> None:
    _seed_role(test_db_session, role_id=2, name="viewer")
    client = _client(test_db_session, github_invites_enabled=True)
    with patch("cctv_api.api.router.create_github_org_invitation") as mock_invite:
        mock_invite.return_value = GitHubInviteResult(
            invitation_id=123,
            org="panoptix-test",
            status="invited",
        )
        response = client.post("/api/v1/admin/users/invite", headers=_ADMIN_HEADERS, json=_invite_body())

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "new-user@example.test"
    assert data["roles"] == ["viewer"]
    assert data["github_invitation_id"] == 123
    assert data["github_org"] == "panoptix-test"
    assert data["status"] == "invited"
    assert "GitHub organization invitation" in data["next_step"]
    assert "test-github-token" not in response.text
    mock_invite.assert_called_once()

    user = test_db_session.execute(select(User).where(User.email == "new-user@example.test")).scalar_one()
    assert user.idp_subject is None
    user_role = test_db_session.execute(select(UserRole).where(UserRole.user_id == str(user.id))).scalar_one()
    assert user_role.role_id == 2

    audit = test_db_session.execute(select(AuditLog).where(AuditLog.action == "admin.user.invited")).scalar_one()
    assert audit.payload["target_email"] == "new-user@example.test"
    assert audit.payload["github_invitation_id"] == 123
    assert audit.payload["role_names"] == ["viewer"]
    assert "test-github-token" not in str(audit.payload)


def test_invite_defaults_to_viewer_role(test_db_session: DbSession) -> None:
    _seed_role(test_db_session, role_id=2, name="viewer")
    client = _client(test_db_session, github_invites_enabled=True)
    with patch("cctv_api.api.router.create_github_org_invitation") as mock_invite:
        mock_invite.return_value = GitHubInviteResult(invitation_id=456, org="panoptix-test", status="invited")
        response = client.post(
            "/api/v1/admin/users/invite",
            headers=_ADMIN_HEADERS,
            json={"email": "default-role@example.test"},
        )

    assert response.status_code == 200
    assert response.json()["roles"] == ["viewer"]


def test_invite_existing_user_is_idempotent_for_local_roles(test_db_session: DbSession) -> None:
    role = _seed_role(test_db_session, role_id=2, name="viewer")
    existing_user = User(id=uuid4(), email="new-user@example.test", idp_subject=None)
    test_db_session.add(existing_user)
    test_db_session.add(UserRole(user_id=existing_user.id, role_id=role.id))
    test_db_session.commit()

    client = _client(test_db_session, github_invites_enabled=True)
    with patch("cctv_api.api.router.create_github_org_invitation") as mock_invite:
        mock_invite.return_value = GitHubInviteResult(
            invitation_id=None,
            org="panoptix-test",
            status="already_invited",
        )
        response = client.post("/api/v1/admin/users/invite", headers=_ADMIN_HEADERS, json=_invite_body())

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(existing_user.id)
    assert data["roles"] == ["viewer"]
    assert data["status"] == "already_invited"
    role_count = test_db_session.execute(
        select(UserRole).where(UserRole.user_id == str(existing_user.id), UserRole.role_id == role.id)
    ).scalars().all()
    assert len(role_count) == 1


def test_invite_rejects_existing_disabled_user_without_roles_or_github_call(test_db_session: DbSession) -> None:
    role = _seed_role(test_db_session, role_id=2, name="viewer")
    disabled_user = User(
        id=uuid4(),
        email="new-user@example.test",
        idp_subject=None,
        disabled_at=datetime.now(timezone.utc),
    )
    test_db_session.add(disabled_user)
    test_db_session.commit()

    client = _client(test_db_session, github_invites_enabled=True)
    with patch("cctv_api.api.router.create_github_org_invitation") as mock_invite:
        response = client.post("/api/v1/admin/users/invite", headers=_ADMIN_HEADERS, json=_invite_body())

    assert response.status_code == 409
    assert response.json()["detail"] == "user-disabled"
    mock_invite.assert_not_called()

    role_count = test_db_session.execute(
        select(UserRole).where(UserRole.user_id == disabled_user.id, UserRole.role_id == role.id)
    ).scalars().all()
    assert role_count == []
    test_db_session.refresh(disabled_user)
    assert disabled_user.disabled_at is not None

    audit = test_db_session.execute(
        select(AuditLog).where(AuditLog.action == "admin.user.invite.denied.user_disabled")
    ).scalar_one()
    assert audit.resource == f"user:{disabled_user.id}"
    assert audit.payload["target_email"] == "new-user@example.test"
    assert audit.payload["reason"] == "new operator"


def test_invite_rejects_empty_roles(test_db_session: DbSession) -> None:
    client = _client(test_db_session, github_invites_enabled=True)
    response = client.post(
        "/api/v1/admin/users/invite",
        headers=_ADMIN_HEADERS,
        json=_invite_body(role_names=[]),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "role-names-required"


def test_invite_rejects_invalid_email(test_db_session: DbSession) -> None:
    client = _client(test_db_session, github_invites_enabled=True)
    response = client.post(
        "/api/v1/admin/users/invite",
        headers=_ADMIN_HEADERS,
        json=_invite_body(email="not-an-email"),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "email-invalid"


def test_invite_rejects_unknown_role(test_db_session: DbSession) -> None:
    client = _client(test_db_session, github_invites_enabled=True)
    response = client.post(
        "/api/v1/admin/users/invite",
        headers=_ADMIN_HEADERS,
        json=_invite_body(role_names=["viewer"]),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "role-not-found"


def test_invite_returns_503_when_github_invites_disabled(test_db_session: DbSession) -> None:
    _seed_role(test_db_session, role_id=2, name="viewer")
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/users/invite", headers=_ADMIN_HEADERS, json=_invite_body())
    assert response.status_code == 503
    assert response.json()["detail"] == "github-invites-not-configured"


def test_invite_returns_502_when_github_api_fails(test_db_session: DbSession) -> None:
    _seed_role(test_db_session, role_id=2, name="viewer")
    client = _client(test_db_session, github_invites_enabled=True)
    with patch("cctv_api.api.router.create_github_org_invitation") as mock_invite:
        mock_invite.side_effect = GitHubInviteError("github-invite-failed")
        response = client.post("/api/v1/admin/users/invite", headers=_ADMIN_HEADERS, json=_invite_body())
    assert response.status_code == 502
    assert response.json()["detail"] == "github-invite-failed"
    user = test_db_session.execute(select(User).where(User.email == "new-user@example.test")).scalar_one_or_none()
    assert user is None


# GET /api/v1/admin/backups/status


def test_backups_status_requires_auth(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/backups/status")
    assert response.status_code == 401


def test_backups_status_requires_admin_role(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/backups/status", headers=_VIEWER_HEADERS)
    assert response.status_code == 403
