from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import CameraSourceType, GatewayStatus
from cctv_api.models.tables import AuditLog, Camera, EdgeGateway, GatewayCameraAssignment
from cctv_api.security.stream_access import get_enabled_gateway


LIVEKIT_SECRET = "test-livekit-secret-with-at-least-32-bytes"


def _client(test_db_session: DbSession) -> TestClient:
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


def _admin_headers() -> dict[str, str]:
    return {
        "x-panoptix-dev-auth": "1",
        "x-panoptix-dev-email": "admin@example.test",
        "x-panoptix-dev-subject": "admin@example.test",
        "x-panoptix-dev-roles": "admin",
    }


def _viewer_headers() -> dict[str, str]:
    return {
        "x-panoptix-dev-auth": "1",
        "x-panoptix-dev-email": "viewer@example.test",
        "x-panoptix-dev-subject": "viewer@example.test",
        "x-panoptix-dev-roles": "viewer",
    }


def _gateway_headers(gateway_id: uuid.UUID) -> dict[str, str]:
    return {"x-panoptix-dev-gateway-id": str(gateway_id)}


def _seed_gateway(db: DbSession, *, status: GatewayStatus = GatewayStatus.enabled) -> EdgeGateway:
    gateway = EdgeGateway(id=uuid.uuid4(), name="Test Gateway", status=status)
    db.add(gateway)
    db.commit()
    db.refresh(gateway)
    return gateway


def _seed_camera(db: DbSession, *, retired: bool = False) -> Camera:
    camera = Camera(
        id=uuid.uuid4(),
        display_name="Front Gate",
        source_type=CameraSourceType.rtsp,
        livekit_room_name=f"camera_{uuid.uuid4().hex[:8]}",
        retired_at=datetime.now(timezone.utc) if retired else None,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


def _seed_assignment(db: DbSession, *, gateway_id: uuid.UUID, camera_id: uuid.UUID) -> GatewayCameraAssignment:
    assignment = GatewayCameraAssignment(
        gateway_id=gateway_id,
        camera_id=camera_id,
        granted_at=datetime.now(timezone.utc),
    )
    db.add(assignment)
    db.commit()
    return assignment


def _audit_actions(db: DbSession) -> list[str]:
    return [row.action for row in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars().all()]


def test_create_gateway_requires_authentication(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/gateways", json={"name": "Gateway A"})
    assert response.status_code == 401


def test_create_gateway_requires_admin_role(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post("/api/v1/admin/gateways", headers=_viewer_headers(), json={"name": "Gateway A"})
    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_create_gateway_succeeds_and_writes_audit(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post(
        "/api/v1/admin/gateways",
        headers=_admin_headers(),
        json={"name": "East Wing Gateway", "mtls_fingerprint": "sha256:test"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["gateway_id"]
    assert body["name"] == "East Wing Gateway"
    assert body["status"] == "enabled"
    assert body["created_at"] is not None

    gateway = test_db_session.execute(select(EdgeGateway)).scalar_one()
    assert str(gateway.id) == body["gateway_id"]
    assert gateway.name == "East Wing Gateway"
    assert gateway.status == GatewayStatus.enabled
    assert gateway.mtls_fingerprint == "sha256:test"
    assert _audit_actions(test_db_session) == ["gateway.create"]


def test_disable_gateway_requires_admin(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/disable",
        headers=_viewer_headers(),
        json={"reason": "maintenance"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_disable_gateway_rejects_invalid_gateway_id(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post(
        "/api/v1/admin/gateways/not-a-uuid/disable",
        headers=_admin_headers(),
        json={"reason": "bad id"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "gateway-id-invalid"


def test_disable_gateway_rejects_missing_gateway(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{uuid.uuid4()}/disable",
        headers=_admin_headers(),
        json={"reason": "missing"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "gateway-not-found"


def test_disable_gateway_succeeds_and_prevents_enabled_lookup(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/disable",
        headers=_admin_headers(),
        json={"reason": "compromised"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["gateway_id"] == str(gateway.id)
    assert body["status"] == "disabled"
    assert body["disabled_at"] is not None

    test_db_session.refresh(gateway)
    assert gateway.status == GatewayStatus.disabled
    assert gateway.disabled_at is not None
    assert get_enabled_gateway(test_db_session, gateway.id) is None
    assert _audit_actions(test_db_session) == ["gateway.disable"]


def test_disable_gateway_rejects_already_disabled(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session, status=GatewayStatus.disabled)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/disable",
        headers=_admin_headers(),
        json={"reason": "again"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "gateway-already-disabled"


def test_gateway_assignment_requires_admin(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/cameras",
        headers=_viewer_headers(),
        json={"action": "grant", "camera_id": str(camera.id)},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_gateway_assignment_rejects_invalid_gateway_id(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        "/api/v1/admin/gateways/not-a-uuid/cameras",
        headers=_admin_headers(),
        json={"action": "grant", "camera_id": str(camera.id)},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "gateway-id-invalid"


def test_gateway_assignment_rejects_invalid_camera_id(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/cameras",
        headers=_admin_headers(),
        json={"action": "grant", "camera_id": "not-a-uuid"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "camera-id-invalid"


def test_gateway_assignment_rejects_missing_gateway(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{uuid.uuid4()}/cameras",
        headers=_admin_headers(),
        json={"action": "grant", "camera_id": str(camera.id)},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "gateway-not-found"


def test_gateway_assignment_rejects_missing_camera(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/cameras",
        headers=_admin_headers(),
        json={"action": "grant", "camera_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "camera-not-found"


def test_gateway_assignment_rejects_retired_camera(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session, retired=True)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/cameras",
        headers=_admin_headers(),
        json={"action": "grant", "camera_id": str(camera.id)},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "camera-not-found"


def test_gateway_assignment_rejects_invalid_action(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/cameras",
        headers=_admin_headers(),
        json={"action": "delete", "camera_id": str(camera.id)},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "action-invalid"


def test_gateway_assignment_grant_succeeds_and_enables_gateway_status(
    test_db_session: DbSession,
) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/cameras",
        headers=_admin_headers(),
        json={"action": "grant", "camera_id": str(camera.id)},
    )
    assert response.status_code == 200
    assert response.json() == {
        "gateway_id": str(gateway.id),
        "camera_id": str(camera.id),
        "action": "grant",
        "status": "applied",
    }

    assignment = test_db_session.execute(select(GatewayCameraAssignment)).scalar_one()
    assert assignment.gateway_id == gateway.id
    assert assignment.camera_id == camera.id
    assert assignment.revoked_at is None
    assert _audit_actions(test_db_session) == ["gateway.camera.grant"]

    status_response = client.post(
        f"/api/v1/gateways/{gateway.id}/cameras/{camera.id}/status",
        headers=_gateway_headers(gateway.id),
        json={"status": "online"},
    )
    assert status_response.status_code == 200


def test_gateway_assignment_grant_enables_ingest_token(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    grant_response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/cameras",
        headers=_admin_headers(),
        json={"action": "grant", "camera_id": str(camera.id)},
    )
    assert grant_response.status_code == 200

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/ingest-token",
        headers=_gateway_headers(gateway.id),
        json={"camera_id": str(camera.id)},
    )
    assert response.status_code == 200
    assert response.json()["camera_id"] == str(camera.id)


def test_gateway_assignment_duplicate_grant_returns_409(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    _seed_assignment(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/cameras",
        headers=_admin_headers(),
        json={"action": "grant", "camera_id": str(camera.id)},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "gateway-camera-assignment-already-active"


def test_gateway_assignment_revoke_succeeds_and_writes_audit(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    assignment = _seed_assignment(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/cameras",
        headers=_admin_headers(),
        json={"action": "revoke", "camera_id": str(camera.id)},
    )
    assert response.status_code == 200
    assert response.json()["action"] == "revoke"
    test_db_session.refresh(assignment)
    assert assignment.revoked_at is not None
    assert _audit_actions(test_db_session) == ["gateway.camera.revoke"]


def test_gateway_assignment_revoke_missing_assignment_returns_404(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gateway.id}/cameras",
        headers=_admin_headers(),
        json={"action": "revoke", "camera_id": str(camera.id)},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "gateway-camera-assignment-not-found"
