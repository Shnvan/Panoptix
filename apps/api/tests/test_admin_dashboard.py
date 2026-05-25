from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import CameraPublishStatus, CameraSourceType, CommandStatus, GatewayStatus
from cctv_api.models.tables import Camera, CameraPublishState, EdgeGateway, GatewayCommandQueue, User


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


def test_dashboard_requires_admin(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/dashboard", headers=_VIEWER_HEADERS)
    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_dashboard_returns_empty_counts(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/dashboard", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["cameras"] == {"total": 0, "active": 0, "retired": 0}
    assert data["gateways"] == {"total": 0, "enabled": 0, "disabled": 0}
    assert data["users"] == {"total": 0, "active": 0, "disabled": 0}
    assert data["commands"] == {"pending": 0}
    assert data["publishing"] == {"active": 0}


def test_dashboard_counts_cameras(test_db_session: DbSession) -> None:
    for i in range(2):
        test_db_session.add(Camera(
            id=uuid.uuid4(),
            display_name=f"Active Camera {i}",
            source_type=CameraSourceType.rtsp,
            livekit_room_name=f"room-active-{i}",
        ))
        test_db_session.commit()
    test_db_session.add(Camera(
        id=uuid.uuid4(),
        display_name="Retired Camera",
        source_type=CameraSourceType.rtsp,
        livekit_room_name="room-retired",
        retired_at=datetime.now(timezone.utc),
    ))
    test_db_session.commit()

    client = _client(test_db_session)
    response = client.get("/api/v1/admin/dashboard", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["cameras"] == {"total": 3, "active": 2, "retired": 1}


def test_dashboard_counts_gateways(test_db_session: DbSession) -> None:
    for i in range(2):
        test_db_session.add(EdgeGateway(id=uuid.uuid4(), name=f"Enabled GW {i}", status=GatewayStatus.enabled))
        test_db_session.commit()
    test_db_session.add(EdgeGateway(id=uuid.uuid4(), name="Disabled GW", status=GatewayStatus.disabled))
    test_db_session.commit()

    client = _client(test_db_session)
    response = client.get("/api/v1/admin/dashboard", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["gateways"] == {"total": 3, "enabled": 2, "disabled": 1}


def test_dashboard_counts_users(test_db_session: DbSession) -> None:
    for i in range(2):
        test_db_session.add(User(id=uuid.uuid4(), email=f"active{i}@example.test", idp_subject=f"active{i}"))
        test_db_session.commit()
    test_db_session.add(User(
        id=uuid.uuid4(),
        email="disabled@example.test",
        idp_subject="disabled",
        disabled_at=datetime.now(timezone.utc),
    ))
    test_db_session.commit()

    client = _client(test_db_session)
    response = client.get("/api/v1/admin/dashboard", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    # Dev auth creates the admin user implicitly, so total is seeded + 1
    assert data["users"]["total"] >= 3
    assert data["users"]["disabled"] >= 1
    assert data["users"]["active"] == data["users"]["total"] - data["users"]["disabled"]


def test_dashboard_counts_pending_commands_and_publishing(test_db_session: DbSession) -> None:
    gateway = EdgeGateway(id=uuid.uuid4(), name="GW", status=GatewayStatus.enabled)
    test_db_session.add(gateway)
    test_db_session.commit()

    now = datetime.now(timezone.utc)
    for i in range(2):
        test_db_session.add(GatewayCommandQueue(
            id=uuid.uuid4(),
            gateway_id=gateway.id,
            kind="test",
            status=CommandStatus.pending,
            expires_at=now + timedelta(hours=1),
        ))
        test_db_session.commit()
    test_db_session.add(GatewayCommandQueue(
        id=uuid.uuid4(),
        gateway_id=gateway.id,
        kind="test",
        status=CommandStatus.accepted,
        expires_at=now + timedelta(hours=1),
    ))
    test_db_session.commit()

    camera = Camera(
        id=uuid.uuid4(),
        display_name="Publishing Camera",
        source_type=CameraSourceType.rtsp,
        livekit_room_name="room-pub",
    )
    test_db_session.add(camera)
    test_db_session.commit()

    test_db_session.add(CameraPublishState(
        camera_id=camera.id,
        gateway_id=gateway.id,
        room="room-pub",
        status=CameraPublishStatus.publishing,
    ))
    test_db_session.commit()

    client = _client(test_db_session)
    response = client.get("/api/v1/admin/dashboard", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["commands"]["pending"] == 2
    assert data["publishing"]["active"] == 1
