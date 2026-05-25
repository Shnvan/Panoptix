from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import CameraEventKind, CameraSourceType, EventSource
from cctv_api.models.tables import AuditLog, Camera, CameraAcl, CameraEvent, User


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


def _seed_user(db: DbSession, *, email: str = "viewer@example.test") -> User:
    user = User(id=uuid.uuid4(), email=email, idp_subject=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_camera(
    db: DbSession,
    *,
    display_name: str = "Test Camera",
    created_at: datetime | None = None,
    retired: bool = False,
) -> Camera:
    camera = Camera(
        id=uuid.uuid4(),
        display_name=display_name,
        source_type=CameraSourceType.rtsp,
        livekit_room_name=f"room-{uuid.uuid4().hex[:8]}",
        created_at=created_at or datetime.now(timezone.utc),
        retired_at=datetime.now(timezone.utc) if retired else None,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


def _grant_acl(db: DbSession, *, user_id: uuid.UUID, camera_id: uuid.UUID) -> CameraAcl:
    acl = CameraAcl(user_id=user_id, camera_id=camera_id, granted_at=datetime.now(timezone.utc))
    db.add(acl)
    db.commit()
    return acl


def _seed_camera_event(
    db: DbSession,
    *,
    camera_id: uuid.UUID,
    at: datetime | None = None,
    kind: CameraEventKind = CameraEventKind.online,
    source: EventSource = EventSource.heartbeat,
) -> CameraEvent:
    event = CameraEvent(
        id=uuid.uuid4(),
        camera_id=camera_id,
        kind=kind,
        at=at or datetime.now(timezone.utc),
        source=source,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _parse_sse_events(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for frame in body.strip().split("\n\n"):
        if not frame:
            continue
        lines = frame.splitlines()
        assert lines[0] == "event: camera_event"
        assert lines[1].startswith("data: ")
        events.append(json.loads(lines[1].removeprefix("data: ")))
    return events


def test_cameras_requires_authentication(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/cameras")
    assert response.status_code == 401


def test_cameras_returns_empty_for_user_with_no_acls(test_db_session: DbSession) -> None:
    _seed_camera(test_db_session, display_name="Unrelated Camera")
    client = _client(test_db_session)
    response = client.get("/api/v1/cameras", headers=_VIEWER_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["next_cursor"] is None


def test_cameras_returns_accessible_cameras(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    camera = _seed_camera(test_db_session, display_name="Front Door")
    _grant_acl(test_db_session, user_id=user.id, camera_id=camera.id)

    client = _client(test_db_session)
    response = client.get("/api/v1/cameras", headers=_VIEWER_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["camera_id"] == str(camera.id)
    assert item["display_name"] == "Front Door"
    assert item["source_type"] == "rtsp"
    assert item["livekit_room_name"] == camera.livekit_room_name


def test_cameras_excludes_retired_cameras(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    camera = _seed_camera(test_db_session, display_name="Retired Camera", retired=True)
    _grant_acl(test_db_session, user_id=user.id, camera_id=camera.id)

    client = _client(test_db_session)
    response = client.get("/api/v1/cameras", headers=_VIEWER_HEADERS)
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_cameras_excludes_revoked_acl_cameras(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    camera = _seed_camera(test_db_session, display_name="Revoked Camera")
    acl = _grant_acl(test_db_session, user_id=user.id, camera_id=camera.id)
    acl.revoked_at = datetime.now(timezone.utc)
    test_db_session.commit()

    client = _client(test_db_session)
    response = client.get("/api/v1/cameras", headers=_VIEWER_HEADERS)
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_cameras_pagination(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)

    now = datetime.now(timezone.utc)
    for i in range(3):
        camera = _seed_camera(
            test_db_session,
            display_name=f"Camera {i}",
            created_at=now - timedelta(minutes=10 - i),
        )
        _grant_acl(test_db_session, user_id=user.id, camera_id=camera.id)

    client = _client(test_db_session)

    response = client.get("/api/v1/cameras?limit=2", headers=_VIEWER_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["next_cursor"] is not None

    response2 = client.get(f"/api/v1/cameras?limit=2&cursor={data['next_cursor']}", headers=_VIEWER_HEADERS)
    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2["items"]) == 1
    assert data2["next_cursor"] is None


def test_cameras_does_not_show_other_users_cameras(test_db_session: DbSession) -> None:
    user_a = _seed_user(test_db_session, email="usera@example.test")
    user_b = _seed_user(test_db_session, email="viewer@example.test")

    camera_a = _seed_camera(test_db_session, display_name="User A Camera")
    _grant_acl(test_db_session, user_id=user_a.id, camera_id=camera_a.id)

    camera_b = _seed_camera(test_db_session, display_name="User B Camera")
    _grant_acl(test_db_session, user_id=user_b.id, camera_id=camera_b.id)

    client = _client(test_db_session)
    response = client.get("/api/v1/cameras", headers=_VIEWER_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["display_name"] == "User B Camera"


# -- Camera Event SSE Tests --


def test_camera_events_requires_authentication(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/cameras/events")
    assert response.status_code == 401


def test_camera_events_empty_for_user_with_no_acls(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    _seed_camera_event(test_db_session, camera_id=camera.id)

    client = _client(test_db_session)
    response = client.get("/api/v1/cameras/events", headers=_VIEWER_HEADERS)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text == ""


def test_camera_events_returns_accessible_events(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    camera = _seed_camera(test_db_session)
    _grant_acl(test_db_session, user_id=user.id, camera_id=camera.id)
    event = _seed_camera_event(
        test_db_session,
        camera_id=camera.id,
        kind=CameraEventKind.degraded,
        source=EventSource.mediamtx_callback,
    )

    client = _client(test_db_session)
    response = client.get("/api/v1/cameras/events", headers=_VIEWER_HEADERS)
    assert response.status_code == 200

    events = _parse_sse_events(response.text)
    assert events == [
        {
            "event_id": str(event.id),
            "camera_id": str(camera.id),
            "gateway_id": None,
            "kind": "degraded",
            "source": "mediamtx_callback",
            "at": event.at.isoformat(),
        }
    ]


def test_camera_events_excludes_other_users_events(test_db_session: DbSession) -> None:
    user_a = _seed_user(test_db_session, email="usera@example.test")
    user_b = _seed_user(test_db_session, email="viewer@example.test")

    camera_a = _seed_camera(test_db_session, display_name="User A Camera")
    _grant_acl(test_db_session, user_id=user_a.id, camera_id=camera_a.id)
    _seed_camera_event(test_db_session, camera_id=camera_a.id, kind=CameraEventKind.offline)

    camera_b = _seed_camera(test_db_session, display_name="User B Camera")
    _grant_acl(test_db_session, user_id=user_b.id, camera_id=camera_b.id)
    visible_event = _seed_camera_event(test_db_session, camera_id=camera_b.id, kind=CameraEventKind.online)

    client = _client(test_db_session)
    response = client.get("/api/v1/cameras/events", headers=_VIEWER_HEADERS)
    assert response.status_code == 200

    events = _parse_sse_events(response.text)
    assert len(events) == 1
    assert events[0]["event_id"] == str(visible_event.id)
    assert events[0]["camera_id"] == str(camera_b.id)


def test_camera_events_excludes_revoked_acl_and_retired_camera_events(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)

    revoked_camera = _seed_camera(test_db_session, display_name="Revoked Camera")
    revoked_acl = _grant_acl(test_db_session, user_id=user.id, camera_id=revoked_camera.id)
    revoked_acl.revoked_at = datetime.now(timezone.utc)
    test_db_session.commit()
    _seed_camera_event(test_db_session, camera_id=revoked_camera.id, kind=CameraEventKind.offline)

    retired_camera = _seed_camera(test_db_session, display_name="Retired Camera", retired=True)
    _grant_acl(test_db_session, user_id=user.id, camera_id=retired_camera.id)
    _seed_camera_event(test_db_session, camera_id=retired_camera.id, kind=CameraEventKind.retired)

    client = _client(test_db_session)
    response = client.get("/api/v1/cameras/events", headers=_VIEWER_HEADERS)
    assert response.status_code == 200
    assert response.text == ""


def test_camera_events_since_filters_older_events(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    camera = _seed_camera(test_db_session)
    _grant_acl(test_db_session, user_id=user.id, camera_id=camera.id)

    now = datetime.now(timezone.utc)
    _seed_camera_event(test_db_session, camera_id=camera.id, at=now - timedelta(minutes=10))
    new_event = _seed_camera_event(test_db_session, camera_id=camera.id, at=now, kind=CameraEventKind.reconnecting)

    client = _client(test_db_session)
    response = client.get(
        "/api/v1/cameras/events",
        headers=_VIEWER_HEADERS,
        params={"since": (now - timedelta(minutes=1)).isoformat()},
    )
    assert response.status_code == 200

    events = _parse_sse_events(response.text)
    assert len(events) == 1
    assert events[0]["event_id"] == str(new_event.id)
    assert events[0]["kind"] == "reconnecting"


def test_camera_events_invalid_since_returns_400(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/cameras/events?since=not-a-date", headers=_VIEWER_HEADERS)
    assert response.status_code == 400
    assert response.json()["detail"] == "since-invalid"


# ── Admin Camera Create Tests ──


def test_create_camera_requires_authentication(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/cameras", json={
        "display_name": "New Camera", "source_type": "rtsp", "livekit_room_name": "room-new",
    })
    assert response.status_code == 401


def test_create_camera_requires_admin_role(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/cameras", headers=_VIEWER_HEADERS, json={
        "display_name": "New Camera", "source_type": "rtsp", "livekit_room_name": "room-new",
    })
    assert response.status_code == 403


def test_create_camera_rejects_invalid_source_type(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/cameras", headers=_ADMIN_HEADERS, json={
        "display_name": "New Camera", "source_type": "invalid_type", "livekit_room_name": "room-new",
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "source-type-invalid"


def test_create_camera_rejects_duplicate_room_name(test_db_session: DbSession) -> None:
    _seed_camera(test_db_session, display_name="Existing")
    existing_room = test_db_session.query(Camera).first().livekit_room_name  # type: ignore[union-attr]

    client = _client(test_db_session)
    response = client.post("/api/v1/admin/cameras", headers=_ADMIN_HEADERS, json={
        "display_name": "New Camera", "source_type": "rtsp", "livekit_room_name": existing_room,
    })
    assert response.status_code == 409
    assert response.json()["detail"] == "room-name-taken"


def test_create_camera_succeeds(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/cameras", headers=_ADMIN_HEADERS, json={
        "display_name": "Front Gate", "source_type": "rtsp", "livekit_room_name": "room-front-gate",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["display_name"] == "Front Gate"
    assert data["source_type"] == "rtsp"
    assert data["livekit_room_name"] == "room-front-gate"
    assert "camera_id" in data


# ── Admin Camera Update Tests ──


def test_update_camera_requires_authentication(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.patch(
        f"/api/v1/admin/cameras/{camera.id}",
        json={"display_name": "Updated Camera"},
    )
    assert response.status_code == 401


def test_update_camera_requires_admin_role(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.patch(
        f"/api/v1/admin/cameras/{camera.id}",
        headers=_VIEWER_HEADERS,
        json={"display_name": "Updated Camera"},
    )
    assert response.status_code == 403


def test_update_camera_succeeds_and_writes_audit(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.patch(
        f"/api/v1/admin/cameras/{camera.id}",
        headers=_ADMIN_HEADERS,
        json={
            "display_name": "Updated Camera",
            "source_type": "synthetic_rtsp_test_source",
            "livekit_room_name": "room-updated-camera",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == str(camera.id)
    assert data["display_name"] == "Updated Camera"
    assert data["source_type"] == "synthetic_rtsp_test_source"
    assert data["livekit_room_name"] == "room-updated-camera"

    test_db_session.refresh(camera)
    assert camera.display_name == "Updated Camera"
    assert camera.source_type == CameraSourceType.synthetic_rtsp_test_source
    assert camera.livekit_room_name == "room-updated-camera"

    audit = test_db_session.execute(select(AuditLog).where(AuditLog.action == "camera.update")).scalar_one()
    assert audit.payload["camera_id"] == str(camera.id)
    assert audit.payload["before"]["display_name"] == "Test Camera"
    assert audit.payload["after"]["display_name"] == "Updated Camera"


def test_update_camera_rejects_duplicate_room_name(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    other = _seed_camera(test_db_session, display_name="Other")
    client = _client(test_db_session)
    response = client.patch(
        f"/api/v1/admin/cameras/{camera.id}",
        headers=_ADMIN_HEADERS,
        json={"livekit_room_name": other.livekit_room_name},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "room-name-taken"


def test_update_camera_not_found_returns_404(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.patch(
        f"/api/v1/admin/cameras/{uuid.uuid4()}",
        headers=_ADMIN_HEADERS,
        json={"display_name": "Missing"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "camera-not-found"


# ── Admin Camera ACL Tests ──


def test_camera_acl_requires_admin(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{camera.id}/acl",
        headers=_VIEWER_HEADERS,
        json={"action": "grant", "user_email": "newuser@example.test"},
    )
    assert response.status_code == 403


def test_camera_acl_grant_succeeds(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{camera.id}/acl",
        headers=_ADMIN_HEADERS,
        json={"action": "grant", "user_email": "newviewer@example.test"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "grant"
    assert data["user_email"] == "newviewer@example.test"
    assert data["status"] == "applied"


def test_camera_acl_grant_duplicate_returns_409(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    user = _seed_user(test_db_session, email="grantee@example.test")
    _grant_acl(test_db_session, user_id=user.id, camera_id=camera.id)

    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{camera.id}/acl",
        headers=_ADMIN_HEADERS,
        json={"action": "grant", "user_email": "grantee@example.test"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "acl-already-active"


def test_camera_acl_revoke_succeeds(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    user = _seed_user(test_db_session, email="revokee@example.test")
    _grant_acl(test_db_session, user_id=user.id, camera_id=camera.id)

    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{camera.id}/acl",
        headers=_ADMIN_HEADERS,
        json={"action": "revoke", "user_email": "revokee@example.test"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "revoke"
    assert data["status"] == "applied"


def test_camera_acl_revoke_not_found_returns_404(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{camera.id}/acl",
        headers=_ADMIN_HEADERS,
        json={"action": "revoke", "user_email": "nobody@example.test"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "acl-not-found"


def test_camera_acl_rejects_invalid_action(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{camera.id}/acl",
        headers=_ADMIN_HEADERS,
        json={"action": "delete", "user_email": "user@example.test"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "action-invalid"


# ── Admin Camera Disable Tests ──


def test_disable_camera_requires_admin(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{camera.id}/disable",
        headers=_VIEWER_HEADERS,
        json={"reason": "No longer needed"},
    )
    assert response.status_code == 403


def test_disable_camera_succeeds(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{camera.id}/disable",
        headers=_ADMIN_HEADERS,
        json={"reason": "Decommissioned"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == str(camera.id)
    assert data["display_name"] == camera.display_name
    assert "retired_at" in data
    assert data["participants_removed"] == 0
    assert isinstance(data["participant_errors"], list)


def test_disable_camera_already_retired_returns_409(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session, retired=True)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{camera.id}/disable",
        headers=_ADMIN_HEADERS,
        json={"reason": "Try again"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "camera-already-retired"


def test_disable_camera_not_found_returns_404(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{uuid.uuid4()}/disable",
        headers=_ADMIN_HEADERS,
        json={"reason": "Does not exist"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "camera-not-found"


# ── Admin Camera Enable Tests ──


def test_enable_camera_requires_admin(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session, retired=True)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{camera.id}/enable",
        headers=_VIEWER_HEADERS,
    )
    assert response.status_code == 403


def test_enable_camera_requires_authentication(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session, retired=True)
    client = _client(test_db_session)
    response = client.post(f"/api/v1/admin/cameras/{camera.id}/enable")
    assert response.status_code == 401


def test_enable_camera_succeeds_and_writes_audit(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session, retired=True)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{camera.id}/enable",
        headers=_ADMIN_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == str(camera.id)
    assert data["retired_at"] is None

    test_db_session.refresh(camera)
    assert camera.retired_at is None

    audit = test_db_session.execute(select(AuditLog).where(AuditLog.action == "camera.enable")).scalar_one()
    assert audit.payload["camera_id"] == str(camera.id)
    assert audit.payload["before"]["retired_at"] is not None
    assert audit.payload["after"]["retired_at"] is None


def test_enable_camera_already_active_returns_409(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{camera.id}/enable",
        headers=_ADMIN_HEADERS,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "camera-already-active"


def test_enable_camera_not_found_returns_404(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{uuid.uuid4()}/enable",
        headers=_ADMIN_HEADERS,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "camera-not-found"


# ── Camera disable → kill viewer participants ──

LIVEKIT_SECRET = "test-livekit-secret-with-at-least-32-bytes"


def _client_with_livekit(test_db_session: DbSession) -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            LIVEKIT_CLOUD_URL="wss://livekit.example.test",
            LIVEKIT_CLOUD_API_KEY="test-livekit-key",
            LIVEKIT_CLOUD_API_SECRET=LIVEKIT_SECRET,
            AUDIT_HMAC_KEY_VERSION=1,
            AUDIT_HMAC_KEY="test-audit-key-with-enough-entropy",
        )
    )

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


def test_disable_camera_with_placeholder_creds_returns_placeholder_error(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/cameras/{camera.id}/disable",
        headers=_ADMIN_HEADERS,
        json={"reason": "placeholder test"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["participants_removed"] == 0
    assert "livekit-credentials-placeholder" in body["participant_errors"]


def test_disable_camera_removes_viewer_participants(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    viewer_id = uuid.uuid4()

    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = {
        "participants": [
            {"identity": f"viewer:{viewer_id}:{camera.id}", "sid": "PA_v1"},
        ]
    }
    remove_response = MagicMock()
    remove_response.status_code = 200

    client = _client_with_livekit(test_db_session)
    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.side_effect = [list_response, remove_response]
        response = client.post(
            f"/api/v1/admin/cameras/{camera.id}/disable",
            headers=_ADMIN_HEADERS,
            json={"reason": "decommissioned"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["participants_removed"] == 1
    assert body["participant_errors"] == []

    audit = test_db_session.execute(select(AuditLog)).scalars().all()
    disable_audit = [a for a in audit if a.action == "camera.disable"][0]
    assert disable_audit.payload["participants_removed"] == 1


def test_disable_camera_no_viewers_removes_zero(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)

    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = {"participants": []}

    client = _client_with_livekit(test_db_session)
    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.return_value = list_response
        response = client.post(
            f"/api/v1/admin/cameras/{camera.id}/disable",
            headers=_ADMIN_HEADERS,
            json={"reason": "no viewers"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["participants_removed"] == 0
    assert body["participant_errors"] == []


# ── Admin camera listing tests ──


def test_list_admin_cameras_requires_admin(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/cameras", headers=_VIEWER_HEADERS)
    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_list_admin_cameras_returns_empty(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/cameras", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["next_cursor"] is None


def test_list_admin_cameras_returns_active_only_by_default(test_db_session: DbSession) -> None:
    now = datetime.now(timezone.utc)
    _seed_camera(test_db_session, display_name="Active Cam", created_at=now)
    _seed_camera(test_db_session, display_name="Retired Cam", created_at=now - timedelta(seconds=1), retired=True)
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/cameras", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["display_name"] == "Active Cam"


def test_list_admin_cameras_includes_retired_when_requested(test_db_session: DbSession) -> None:
    now = datetime.now(timezone.utc)
    _seed_camera(test_db_session, display_name="Active Cam", created_at=now)
    _seed_camera(test_db_session, display_name="Retired Cam", created_at=now - timedelta(seconds=1), retired=True)
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/cameras?include_retired=true", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    names = [item["display_name"] for item in data["items"]]
    assert "Active Cam" in names
    assert "Retired Cam" in names


def test_list_admin_cameras_paginates(test_db_session: DbSession) -> None:
    now = datetime.now(timezone.utc)
    for i in range(3):
        _seed_camera(test_db_session, display_name=f"Cam {i}", created_at=now - timedelta(seconds=i))
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/cameras?limit=2", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["next_cursor"] is not None

    response2 = client.get(f"/api/v1/admin/cameras?limit=2&cursor={data['next_cursor']}", headers=_ADMIN_HEADERS)
    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2["items"]) == 1
    assert data2["next_cursor"] is None


def test_get_admin_camera_detail_requires_admin(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.get(f"/api/v1/admin/cameras/{camera.id}", headers=_VIEWER_HEADERS)
    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_get_admin_camera_detail_returns_fields(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session, display_name="Detail Cam")
    user = _seed_user(test_db_session)
    _grant_acl(test_db_session, user_id=user.id, camera_id=camera.id)
    client = _client(test_db_session)
    response = client.get(f"/api/v1/admin/cameras/{camera.id}", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == str(camera.id)
    assert data["display_name"] == "Detail Cam"
    assert data["source_type"] == "rtsp"
    assert data["livekit_room_name"] == camera.livekit_room_name
    assert data["acl_count"] == 1
    assert "room_uuid" in data
    assert "gateway_id" in data
    assert "site_id" in data


def test_get_admin_camera_detail_not_found(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get(f"/api/v1/admin/cameras/{uuid.uuid4()}", headers=_ADMIN_HEADERS)
    assert response.status_code == 404
    assert response.json()["detail"] == "camera-not-found"
