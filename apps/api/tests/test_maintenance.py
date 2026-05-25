from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, sessionmaker

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.jobs.maintenance import (
    maintenance_scheduler_loop,
    run_scheduled_maintenance_job,
    should_start_maintenance_scheduler,
)
from cctv_api.main import create_app
from cctv_api.models.enums import CameraPublishStatus, CameraSourceType, CommandStatus, GatewayStatus
from cctv_api.models.tables import (
    AuditLog,
    Camera,
    CameraPublishState,
    EdgeGateway,
    GatewayCameraAssignment,
    GatewayCommandQueue,
    VisitorVisit,
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
    assert data == {"expired_commands": 0, "stops_enqueued": 0, "purged_visitor_visits": 0}


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


def test_maintenance_purges_expired_visitor_visits(test_db_session: DbSession) -> None:
    now = datetime.now(timezone.utc)
    test_db_session.add_all([
        VisitorVisit(
            id=uuid.uuid4(),
            collected_at=now - timedelta(days=31),
            page_path="/old",
            notice_version="2026-05-22",
            ip_enrichment_status="not_configured",
            ip_enrichment={},
        ),
        VisitorVisit(
            id=uuid.uuid4(),
            collected_at=now - timedelta(days=1),
            page_path="/recent",
            notice_version="2026-05-22",
            ip_enrichment_status="not_configured",
            ip_enrichment={},
        ),
    ])
    test_db_session.commit()

    client = _client(test_db_session)
    response = client.post("/api/v1/admin/jobs/run-maintenance", headers=_ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["purged_visitor_visits"] == 1
    remaining = test_db_session.execute(select(VisitorVisit)).scalar_one()
    assert remaining.page_path == "/recent"


def test_scheduled_maintenance_expires_stale_commands(test_db_session: DbSession) -> None:
    gw = _seed_gateway(test_db_session)
    now = datetime.now(timezone.utc)
    test_db_session.add(GatewayCommandQueue(
        id=uuid.uuid4(),
        gateway_id=gw.id,
        kind="scheduled.expire",
        payload={},
        status=CommandStatus.pending,
        issued_at=now - timedelta(hours=1),
        expires_at=now - timedelta(minutes=1),
    ))
    test_db_session.commit()

    result = run_scheduled_maintenance_job(test_db_session, settings=_scheduler_settings())

    assert result.expired_commands == 1
    assert result.stops_enqueued == 0
    expired = test_db_session.execute(
        select(GatewayCommandQueue).where(GatewayCommandQueue.status == CommandStatus.expired)
    ).scalar_one()
    assert expired.kind == "scheduled.expire"


def test_scheduled_maintenance_enqueues_due_publish_stop_and_system_audit(test_db_session: DbSession) -> None:
    gw = _seed_gateway(test_db_session)
    cam = _seed_camera(test_db_session, room="scheduled-room")
    _assign_camera(test_db_session, gateway_id=gw.id, camera_id=cam.id)
    now = datetime.now(timezone.utc)
    test_db_session.add(CameraPublishState(
        camera_id=cam.id,
        gateway_id=gw.id,
        room=cam.livekit_room_name,
        status=CameraPublishStatus.stop_pending,
        last_viewer_count=0,
        started_at=now - timedelta(minutes=1),
        stop_requested_at=now - timedelta(seconds=15),
        stop_due_at=now - timedelta(seconds=5),
        updated_at=now - timedelta(seconds=15),
    ))
    test_db_session.commit()

    result = run_scheduled_maintenance_job(test_db_session, settings=_scheduler_settings())

    assert result.error is None
    assert result.expired_commands == 0
    assert result.stops_enqueued == 1
    actions = [
        row.action
        for row in test_db_session.execute(select(AuditLog).order_by(AuditLog.id)).scalars().all()
    ]
    assert actions == ["livekit.publish.stop_enqueued", "system.maintenance.run"]


def test_scheduler_is_disabled_by_default() -> None:
    assert should_start_maintenance_scheduler(Settings()) is False


def test_scheduler_does_not_start_with_placeholder_database_url() -> None:
    settings = _scheduler_settings(ENABLE_MAINTENANCE_SCHEDULER=True)
    assert should_start_maintenance_scheduler(settings) is False


def test_scheduler_starts_when_enabled_with_real_database_url() -> None:
    settings = _scheduler_settings(
        ENABLE_MAINTENANCE_SCHEDULER=True,
        DATABASE_URL="sqlite:///scheduler-test.db",
    )
    assert should_start_maintenance_scheduler(settings) is True


def test_scheduler_loop_handles_cancellation(_test_db: sessionmaker[DbSession]) -> None:
    sleep_calls = 0

    async def _sleep(_seconds: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        raise asyncio.CancelledError

    async def _run() -> None:
        await maintenance_scheduler_loop(_test_db, settings=_scheduler_settings(), sleep=_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_run())
    assert sleep_calls == 1


def _scheduler_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "APP_ENV": "development",
        "ALLOW_DEV_AUTH": True,
        "AUDIT_HMAC_KEY_VERSION": 1,
        "AUDIT_HMAC_KEY": "test-audit-key-with-enough-entropy",
        "MAINTENANCE_INTERVAL_SECONDS": 5,
    }
    values.update(overrides)
    return Settings(**values)
