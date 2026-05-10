from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.router import CURRENT_PRIVACY_NOTICE_VERSION
from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.tables import AuditLog, PrivacyNoticeAcceptance, Role, User, UserRole


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


def _seed_user(
    db: DbSession,
    *,
    email: str,
    created_at: datetime | None = None,
    disabled_at: datetime | None = None,
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        idp_subject=email,
        created_at=created_at or datetime.now(timezone.utc),
        disabled_at=disabled_at,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_role(db: DbSession, *, role_id: int, name: str) -> Role:
    role = Role(id=role_id, name=name)
    db.add(role)
    db.commit()
    return role


def _grant_role(db: DbSession, *, user_id: uuid.UUID, role_id: int) -> None:
    db.add(UserRole(user_id=user_id, role_id=role_id))
    db.commit()


def test_privacy_notice_requires_authentication(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/privacy/notice")
    assert response.status_code == 401


def test_privacy_notice_returns_current_notice_unaccepted(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/privacy/notice", headers=_VIEWER_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["notice_version"] == CURRENT_PRIVACY_NOTICE_VERSION
    assert data["title"] == "Panoptix CCTV Operator Privacy Notice"
    assert "live-view" in data["body"]
    assert data["accepted"] is False
    assert data["accepted_at"] is None


def test_privacy_notice_accept_records_acceptance_and_audit(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post(
        "/api/v1/privacy/notice/accept",
        headers=_VIEWER_HEADERS,
        json={"notice_version": CURRENT_PRIVACY_NOTICE_VERSION},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["notice_version"] == CURRENT_PRIVACY_NOTICE_VERSION
    assert data["status"] == "accepted"
    assert data["accepted_at"] is not None

    acceptance = test_db_session.execute(select(PrivacyNoticeAcceptance)).scalar_one()
    assert acceptance.notice_version == CURRENT_PRIVACY_NOTICE_VERSION
    audit = test_db_session.execute(select(AuditLog)).scalar_one()
    assert audit.action == "privacy.notice.accepted"

    notice_response = client.get("/api/v1/privacy/notice", headers=_VIEWER_HEADERS)
    assert notice_response.status_code == 200
    assert notice_response.json()["accepted"] is True


def test_privacy_notice_accept_is_idempotent(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    for _ in range(2):
        response = client.post(
            "/api/v1/privacy/notice/accept",
            headers=_VIEWER_HEADERS,
            json={"notice_version": CURRENT_PRIVACY_NOTICE_VERSION},
        )
        assert response.status_code == 200

    acceptances = test_db_session.execute(select(PrivacyNoticeAcceptance)).scalars().all()
    audits = test_db_session.execute(select(AuditLog)).scalars().all()
    assert len(acceptances) == 1
    assert len(audits) == 1


def test_privacy_notice_accept_rejects_wrong_version(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post(
        "/api/v1/privacy/notice/accept",
        headers=_VIEWER_HEADERS,
        json={"notice_version": "old-version"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "privacy-notice-version-mismatch"


def test_admin_users_requires_authentication(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 401


def test_admin_users_requires_admin_role(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/users", headers=_VIEWER_HEADERS)
    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_admin_users_lists_safe_user_fields_and_roles(test_db_session: DbSession) -> None:
    admin_role = _seed_role(test_db_session, role_id=1, name="admin")
    viewer_role = _seed_role(test_db_session, role_id=2, name="viewer")
    user = _seed_user(test_db_session, email="listed@example.test")
    _grant_role(test_db_session, user_id=user.id, role_id=admin_role.id)
    _grant_role(test_db_session, user_id=user.id, role_id=viewer_role.id)

    client = _client(test_db_session)
    response = client.get("/api/v1/admin/users", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["next_cursor"] is None
    assert len(data["items"]) == 1
    listed = next(item for item in data["items"] if item["email"] == "listed@example.test")
    assert listed == {
        "user_id": str(user.id),
        "email": "listed@example.test",
        "roles": ["admin", "viewer"],
        "role_default": "none",
        "disabled_at": None,
        "created_at": user.created_at.isoformat(),
    }
    assert "idp_subject" not in listed


def test_admin_users_supports_email_filter(test_db_session: DbSession) -> None:
    _seed_user(test_db_session, email="first@example.test")
    _seed_user(test_db_session, email="second@example.test")

    client = _client(test_db_session)
    response = client.get(
        "/api/v1/admin/users",
        headers=_ADMIN_HEADERS,
        params={"email": "second@example.test"},
    )
    assert response.status_code == 200
    data = response.json()
    assert [item["email"] for item in data["items"]] == ["second@example.test"]


def test_admin_users_paginates(test_db_session: DbSession) -> None:
    now = datetime.now(timezone.utc)
    _seed_user(test_db_session, email="old@example.test", created_at=now - timedelta(minutes=2))
    middle = _seed_user(test_db_session, email="middle@example.test", created_at=now - timedelta(minutes=1))
    _seed_user(test_db_session, email="new@example.test", created_at=now)

    client = _client(test_db_session)
    response = client.get("/api/v1/admin/users", headers=_ADMIN_HEADERS, params={"limit": 2})
    assert response.status_code == 200
    data = response.json()
    assert [item["email"] for item in data["items"]] == ["new@example.test", "middle@example.test"]
    assert data["next_cursor"] == str(middle.id)

    response2 = client.get(
        "/api/v1/admin/users",
        headers=_ADMIN_HEADERS,
        params={"limit": 2, "cursor": data["next_cursor"]},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert [item["email"] for item in data2["items"]] == ["old@example.test"]
    assert data2["next_cursor"] is None


def test_admin_users_rejects_invalid_cursor(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/users", headers=_ADMIN_HEADERS, params={"cursor": "bad"})
    assert response.status_code == 400
    assert response.json()["detail"] == "cursor-invalid"
