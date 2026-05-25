from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import CameraSourceType, GatewayStatus
from cctv_api.models.tables import Camera, CameraAcl, EdgeGateway, GatewayCameraAssignment


_ADMIN_HEADERS = {
    "x-panoptix-dev-auth": "1",
    "x-panoptix-dev-email": "admin@example.test",
    "x-panoptix-dev-subject": "admin@example.test",
    "x-panoptix-dev-roles": "admin",
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


def _seed_gateway(
    db: DbSession,
    *,
    name: str = "Test Gateway",
    status: GatewayStatus = GatewayStatus.enabled,
    minutes_ago: int = 0,
) -> EdgeGateway:
    now = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    gw = EdgeGateway(
        id=uuid.uuid4(),
        name=name,
        status=status,
        created_at=now,
    )
    db.add(gw)
    db.commit()
    db.refresh(gw)
    return gw


def _seed_camera(
    db: DbSession,
    *,
    display_name: str = "Front Gate",
    gateway_id: uuid.UUID | None = None,
    minutes_ago: int = 0,
) -> Camera:
    now = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    cam = Camera(
        id=uuid.uuid4(),
        display_name=display_name,
        source_type=CameraSourceType.rtsp,
        room_uuid=uuid.uuid4(),
        livekit_room_name=f"room-{uuid.uuid4().hex[:8]}",
        gateway_id=str(gateway_id) if gateway_id else None,
        created_at=now,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def _seed_acl(db: DbSession, *, camera_id: uuid.UUID, user_email: str = "viewer@test") -> None:
    from cctv_api.security.users import get_or_create_user

    user = get_or_create_user(db, email=user_email, idp_subject=user_email)
    acl = CameraAcl(
        user_id=user.id,
        camera_id=str(camera_id),
        granted_at=datetime.now(timezone.utc),
    )
    db.add(acl)
    db.commit()


def _seed_assignment(db: DbSession, *, gateway_id: uuid.UUID, camera_id: uuid.UUID) -> None:
    asgn = GatewayCameraAssignment(
        gateway_id=str(gateway_id),
        camera_id=str(camera_id),
        granted_at=datetime.now(timezone.utc),
    )
    db.add(asgn)
    db.commit()


# ── Gateway search ──


def test_gateway_search_by_name(test_db_session: DbSession) -> None:
    _seed_gateway(test_db_session, name="Warehouse Alpha")
    _seed_gateway(test_db_session, name="Office Beta", minutes_ago=1)
    c = _client(test_db_session)
    resp = c.get("/api/v1/admin/gateways?search=warehouse", headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Warehouse Alpha"


def test_gateway_search_with_status_filter(test_db_session: DbSession) -> None:
    _seed_gateway(test_db_session, name="Warehouse Alpha", status=GatewayStatus.enabled)
    _seed_gateway(test_db_session, name="Warehouse Beta", status=GatewayStatus.disabled, minutes_ago=1)
    c = _client(test_db_session)
    resp = c.get("/api/v1/admin/gateways?search=warehouse&status=enabled", headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Warehouse Alpha"


def test_gateway_empty_search_returns_all(test_db_session: DbSession) -> None:
    _seed_gateway(test_db_session, name="GW1")
    _seed_gateway(test_db_session, name="GW2", minutes_ago=1)
    c = _client(test_db_session)
    resp = c.get("/api/v1/admin/gateways", headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


# ── Gateway list enrichment ──


def test_gateway_list_includes_camera_count(test_db_session: DbSession) -> None:
    gw = _seed_gateway(test_db_session, name="Rich GW")
    cam = _seed_camera(test_db_session, gateway_id=gw.id)
    _seed_assignment(test_db_session, gateway_id=gw.id, camera_id=cam.id)
    c = _client(test_db_session)
    resp = c.get("/api/v1/admin/gateways", headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["camera_count"] == 1


def test_gateway_list_camera_count_zero(test_db_session: DbSession) -> None:
    _seed_gateway(test_db_session, name="Empty GW")
    c = _client(test_db_session)
    resp = c.get("/api/v1/admin/gateways", headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["items"][0]["camera_count"] == 0


# ── Camera search ──


def test_camera_search_by_display_name(test_db_session: DbSession) -> None:
    _seed_camera(test_db_session, display_name="Front Gate Camera")
    _seed_camera(test_db_session, display_name="Rear Parking Lot", minutes_ago=1)
    c = _client(test_db_session)
    resp = c.get("/api/v1/admin/cameras?search=front", headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["display_name"] == "Front Gate Camera"


def test_camera_filter_by_source_type(test_db_session: DbSession) -> None:
    _seed_camera(test_db_session, display_name="CCTV Cam")
    c = _client(test_db_session)
    resp = c.get("/api/v1/admin/cameras?source_type=rtsp", headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


def test_camera_filter_invalid_source_type(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.get("/api/v1/admin/cameras?source_type=invalid_type", headers=_ADMIN_HEADERS)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "source-type-invalid"


def test_camera_filter_by_gateway_id(test_db_session: DbSession) -> None:
    gw = _seed_gateway(test_db_session, name="GW-A")
    _seed_camera(test_db_session, display_name="Cam on GW-A", gateway_id=gw.id)
    _seed_camera(test_db_session, display_name="Unassigned Cam", minutes_ago=1)
    c = _client(test_db_session)
    resp = c.get(f"/api/v1/admin/cameras?gateway_id={gw.id}", headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["display_name"] == "Cam on GW-A"


def test_camera_search_and_filter_combined(test_db_session: DbSession) -> None:
    gw = _seed_gateway(test_db_session, name="GW-Combo")
    _seed_camera(test_db_session, display_name="Front Gate", gateway_id=gw.id)
    _seed_camera(test_db_session, display_name="Front Lobby", minutes_ago=1)
    c = _client(test_db_session)
    resp = c.get(f"/api/v1/admin/cameras?search=front&gateway_id={gw.id}", headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["display_name"] == "Front Gate"


# ── Camera list enrichment ──


def test_camera_list_includes_gateway_id_and_acl_count(test_db_session: DbSession) -> None:
    gw = _seed_gateway(test_db_session, name="Enrich GW")
    cam = _seed_camera(test_db_session, display_name="Enriched Cam", gateway_id=gw.id)
    _seed_acl(test_db_session, camera_id=cam.id, user_email="v1@test")
    _seed_acl(test_db_session, camera_id=cam.id, user_email="v2@test")
    c = _client(test_db_session)
    resp = c.get("/api/v1/admin/cameras", headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["gateway_id"] == str(gw.id)
    assert items[0]["acl_count"] == 2


def test_camera_list_acl_count_zero_no_gateway(test_db_session: DbSession) -> None:
    _seed_camera(test_db_session, display_name="Bare Cam")
    c = _client(test_db_session)
    resp = c.get("/api/v1/admin/cameras", headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["gateway_id"] is None
    assert items[0]["acl_count"] == 0
