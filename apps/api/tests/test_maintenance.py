from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import CameraPublishStatus, CameraSourceType, CommandStatus, GatewayStatus
from cctv_api.models.tables import (
    AuditLog,
    Camera,
    CameraPublishState,
    EdgeGateway,
    GatewayCameraAssignment,
    GatewayCommandQueue,
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


def _seed_gateway(db: DbSession, *, name: str = "gw") -> EdgeGateway:
    gw = EdgeGateway(id=uuid.uuid4(), name=name, status=GatewayStatus.enabled)
    db.add(gw)
    db.commit()
    db.refresh(gw)
    return gw


def _seed_camera(db: DbSession, *, display_name: str = "cam", room: str = "room-cam") -> Camera:
    cam = Camera(
        id=uuid.uuid4(),
        display_name=display_name,
        source_type=CameraSourceType.synthetic_rtsp_test_source,
        livekit_room_name=room,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def _assign_camera(db: DbSession, *, gateway_id: uuid.UUID, camera_id: uuid.UUID) -> None:
    db.add(GatewayCameraAssignment(
        gateway_id=gateway_id,
        camera_id=camera_id,
        granted_at=datetime.now(timezone.utc),
    ))
    db.commit()


def test_maintenance_requires_authentication(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/jobs/run-maintenance")
    assert response.status_code == 401


def test_maintenance_requires_admin_role(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/jobs/run-maintenance", headers=_VIEWER_HEADERS)
    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_maintenance_empty_returns_zeros(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/jobs/run-maintenance", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data == {"expired_commands": 0, "stops_enqueued": 0}


def test_maintenance_expires_stale_commands(test_db_session: DbSession) -> None:
    gw = _seed_gateway(test_db_session)
    now = datetime.now(timezone.utc)
    for i in range(3):
        test_db_session.add(GatewayCommandQueue(
            id=uuid.uuid4(),
            gateway_id=gw.id,
            kind="test.command",
            payload={},
            status=CommandStatus.pending,
            issued_at=now - timedelta(hours=1),
            expires_at=now - timedelta(minutes=i + 1),
        ))
    test_db_session.commit()

    client = _client(test_db_session)
    response = client.post("/api/v1/admin/jobs/run-maintenance", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["expired_commands"] == 3
    assert data["stops_enqueued"] == 0

    expired = test_db_session.execute(
        select(GatewayCommandQueue).where(GatewayCommandQueue.status == CommandStatus.expired)
    ).scalars().all()
    assert len(expired) == 3


def test_maintenance_enqueues_due_publish_stops(test_db_session: DbSession) -> None:
    gw = _seed_gateway(test_db_session)
    cam = _seed_camera(test_db_session)
    _assign_camera(test_db_session, gateway_id=gw.id, camera_id=cam.id)

    now = datetime.now(timezone.utc)
    state = CameraPublishState(
        camera_id=cam.id,
        gateway_id=gw.id,
        room=cam.livekit_room_name,
        status=CameraPublishStatus.stop_pending,
        last_viewer_count=0,
        started_at=now - timedelta(minutes=1),
        stop_requested_at=now - timedelta(seconds=15),
        stop_due_at=now - timedelta(seconds=5),
        updated_at=now - timedelta(seconds=15),
    )
    test_db_session.add(state)
    test_db_session.commit()

    client = _client(test_db_session)
    response = client.post("/api/v1/admin/jobs/run-maintenance", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["expired_commands"] == 0
    assert data["stops_enqueued"] == 1

    stop_cmd = test_db_session.execute(
        select(GatewayCommandQueue).where(GatewayCommandQueue.kind == "gateway.command.stop_publish")
    ).scalar_one()
    assert str(stop_cmd.gateway_id) == str(gw.id)


def test_maintenance_writes_audit(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    client.post("/api/v1/admin/jobs/run-maintenance", headers=_ADMIN_HEADERS)

    audit = test_db_session.execute(
        select(AuditLog).where(AuditLog.action == "admin.maintenance.run")
    ).scalar_one()
    assert audit.payload["expired_commands"] == 0
    assert audit.payload["stops_enqueued"] == 0
