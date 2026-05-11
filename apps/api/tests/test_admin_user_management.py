from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import CameraSourceType
from cctv_api.models.tables import AuditLog, Camera, CameraAcl, Role, Session, User, UserRole
from cctv_api.security.livekit_rooms import ParticipantRemovalResult


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


def _seed_user(db: DbSession, *, email: str) -> User:
    user = User(id=uuid.uuid4(), email=email, idp_subject=email, created_at=datetime.now(timezone.utc))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_role(db: DbSession, *, role_id: int, name: str) -> Role:
    role = Role(id=role_id, name=name)
    db.add(role)
    db.commit()
    return role


def _seed_session(db: DbSession, *, user_id: uuid.UUID) -> Session:
    s = Session(id=uuid.uuid4(), user_id=user_id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _seed_camera(db: DbSession, *, room_name: str, retired: bool = False) -> Camera:
    camera = Camera(
        id=uuid.uuid4(),
        display_name=room_name,
        source_type=CameraSourceType.rtsp,
        livekit_room_name=room_name,
        retired_at=datetime.now(timezone.utc) if retired else None,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


# ── Role assignment tests ──


def test_role_grant_requires_auth(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    resp = client.post("/api/v1/admin/users/00000000-0000-0000-0000-000000000001/role", json={"action": "grant", "role_name": "viewer"})
    assert resp.status_code == 401


def test_role_grant_requires_admin(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    resp = client.post("/api/v1/admin/users/00000000-0000-0000-0000-000000000001/role", json={"action": "grant", "role_name": "viewer"}, headers=_VIEWER_HEADERS)
    assert resp.status_code == 403


def test_role_grant_user_not_found(test_db_session: DbSession) -> None:
    _seed_role(test_db_session, role_id=1, name="viewer")
    client = _client(test_db_session)
    fake_id = str(uuid.uuid4())
    resp = client.post(f"/api/v1/admin/users/{fake_id}/role", json={"action": "grant", "role_name": "viewer"}, headers=_ADMIN_HEADERS)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "user-not-found"


def test_role_grant_role_not_found(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session, email="target@example.test")
    client = _client(test_db_session)
    resp = client.post(f"/api/v1/admin/users/{user.id}/role", json={"action": "grant", "role_name": "nonexistent"}, headers=_ADMIN_HEADERS)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "role-not-found"


def test_role_grant_success_and_audit(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session, email="target@example.test")
    _seed_role(test_db_session, role_id=1, name="viewer")
    client = _client(test_db_session)
    resp = client.post(f"/api/v1/admin/users/{user.id}/role", json={"action": "grant", "role_name": "viewer"}, headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(user.id)
    assert data["role_name"] == "viewer"
    assert data["action"] == "grant"
    assert data["status"] == "ok"

    ur = test_db_session.execute(select(UserRole).where(UserRole.user_id == str(user.id))).scalar_one()
    assert ur.role_id == 1

    audit = test_db_session.execute(select(AuditLog).where(AuditLog.action == "admin.user.role.granted")).scalar_one()
    assert audit.payload["role_name"] == "viewer"


def test_role_grant_duplicate_returns_conflict(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session, email="target@example.test")
    role = _seed_role(test_db_session, role_id=1, name="viewer")
    test_db_session.add(UserRole(user_id=user.id, role_id=role.id))
    test_db_session.commit()

    client = _client(test_db_session)
    resp = client.post(f"/api/v1/admin/users/{user.id}/role", json={"action": "grant", "role_name": "viewer"}, headers=_ADMIN_HEADERS)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "role-already-granted"


def test_role_revoke_success_and_audit(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session, email="target@example.test")
    role = _seed_role(test_db_session, role_id=1, name="viewer")
    test_db_session.add(UserRole(user_id=user.id, role_id=role.id))
    test_db_session.commit()

    client = _client(test_db_session)
    resp = client.post(f"/api/v1/admin/users/{user.id}/role", json={"action": "revoke", "role_name": "viewer"}, headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["action"] == "revoke"

    ur = test_db_session.execute(select(UserRole).where(UserRole.user_id == str(user.id))).scalar_one_or_none()
    assert ur is None

    audit = test_db_session.execute(select(AuditLog).where(AuditLog.action == "admin.user.role.revoked")).scalar_one()
    assert audit.payload["role_name"] == "viewer"


def test_role_revoke_not_granted(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session, email="target@example.test")
    _seed_role(test_db_session, role_id=1, name="viewer")
    client = _client(test_db_session)
    resp = client.post(f"/api/v1/admin/users/{user.id}/role", json={"action": "revoke", "role_name": "viewer"}, headers=_ADMIN_HEADERS)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "role-not-granted"


# ── User disable tests ──


def test_disable_requires_auth(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    resp = client.post("/api/v1/admin/users/00000000-0000-0000-0000-000000000001/disable", json={"reason": "test"})
    assert resp.status_code == 401


def test_disable_requires_admin(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    resp = client.post("/api/v1/admin/users/00000000-0000-0000-0000-000000000001/disable", json={"reason": "test"}, headers=_VIEWER_HEADERS)
    assert resp.status_code == 403


def test_disable_user_not_found(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    fake_id = str(uuid.uuid4())
    resp = client.post(f"/api/v1/admin/users/{fake_id}/disable", json={"reason": "test"}, headers=_ADMIN_HEADERS)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "user-not-found"


def test_disable_user_success_revokes_sessions_and_audits(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session, email="target@example.test")
    _seed_session(test_db_session, user_id=user.id)
    _seed_session(test_db_session, user_id=user.id)

    client = _client(test_db_session)
    resp = client.post(f"/api/v1/admin/users/{user.id}/disable", json={"reason": "policy violation"}, headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(user.id)
    assert data["sessions_revoked"] == 2
    assert data["disabled_at"] is not None
    # LiveKit credentials are placeholders in test settings, so participant
    # removal should be skipped gracefully
    assert data["participants_removed"] == 0
    assert "livekit-credentials-placeholder" in data["participant_errors"]

    test_db_session.refresh(user)
    assert user.disabled_at is not None

    active = test_db_session.execute(
        select(Session).where(Session.user_id == str(user.id), Session.revoked_at.is_(None))
    ).scalars().all()
    assert len(active) == 0

    audit = test_db_session.execute(select(AuditLog).where(AuditLog.action == "admin.user.disabled")).scalar_one()
    assert audit.payload["reason"] == "policy violation"
    assert audit.payload["sessions_revoked"] == 2
    assert audit.payload["participants_removed"] == 0


def test_disable_user_removes_participants_from_active_acl_rooms(
    test_db_session: DbSession,
) -> None:
    user = _seed_user(test_db_session, email="target@example.test")
    active_camera = _seed_camera(test_db_session, room_name="active-room")
    retired_camera = _seed_camera(test_db_session, room_name="retired-room", retired=True)
    revoked_camera = _seed_camera(test_db_session, room_name="revoked-room")
    test_db_session.add_all(
        [
            CameraAcl(user_id=user.id, camera_id=active_camera.id),
            CameraAcl(user_id=user.id, camera_id=retired_camera.id),
            CameraAcl(
                user_id=user.id,
                camera_id=revoked_camera.id,
                revoked_at=datetime.now(timezone.utc),
            ),
        ]
    )
    test_db_session.commit()
    removal = ParticipantRemovalResult(
        rooms_checked=1,
        participants_removed=1,
        errors=["remove-failed:active-room:viewer:500"],
    )

    client = _client(test_db_session)
    with patch("cctv_api.api.router.remove_user_participants", return_value=removal) as remover:
        resp = client.post(
            f"/api/v1/admin/users/{user.id}/disable",
            json={"reason": "policy violation"},
            headers=_ADMIN_HEADERS,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["participants_removed"] == 1
    assert data["participant_errors"] == ["remove-failed:active-room:viewer:500"]
    remover.assert_called_once()
    assert str(remover.call_args.kwargs["user_id"]) == str(user.id)
    assert remover.call_args.kwargs["room_names"] == ["active-room"]

    audit = test_db_session.execute(select(AuditLog).where(AuditLog.action == "admin.user.disabled")).scalar_one()
    assert audit.payload["participants_removed"] == 1
    assert audit.payload["participant_errors"] == ["remove-failed:active-room:viewer:500"]


def test_disable_already_disabled(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session, email="target@example.test")
    user.disabled_at = datetime.now(timezone.utc)
    test_db_session.commit()

    client = _client(test_db_session)
    resp = client.post(f"/api/v1/admin/users/{user.id}/disable", json={"reason": "again"}, headers=_ADMIN_HEADERS)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "user-already-disabled"
