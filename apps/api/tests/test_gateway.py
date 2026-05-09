from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from starlette.websockets import WebSocketDisconnect

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.gateway.command_signing import verify_command_envelope
from cctv_api.gateway.models import GatewayCommandAck, GatewayCommandEnvelope
from cctv_api.main import create_app
from cctv_api.models.enums import CameraEventKind, CameraSourceType, EventSource, GatewayStatus
from cctv_api.models.tables import Camera, CameraAcl, CameraEvent, EdgeGateway, GatewayCameraAssignment, User


SIGNING_KEY = "test-command-signing-key-with-enough-entropy"


def _dev_gateway_client(*, signing_key: str = "replace-me") -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            GATEWAY_COMMAND_SIGNING_KEY=signing_key,
        )
    )
    return TestClient(app)


def _dev_gateway_client_with_db(test_db_session: DbSession, *, signing_key: str = "replace-me") -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            GATEWAY_COMMAND_SIGNING_KEY=signing_key,
        )
    )

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


def _gateway_headers(gateway_id: str = "gateway-1") -> dict[str, str]:
    return {"x-panoptix-dev-gateway-id": gateway_id}


def _viewer_headers() -> dict[str, str]:
    return {
        "x-panoptix-dev-auth": "1",
        "x-panoptix-dev-email": "viewer@example.test",
        "x-panoptix-dev-subject": "viewer@example.test",
        "x-panoptix-dev-roles": "viewer",
    }


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


def _assign_gateway_camera(
    db: DbSession,
    *,
    gateway_id: uuid.UUID,
    camera_id: uuid.UUID,
    revoked: bool = False,
) -> GatewayCameraAssignment:
    assignment = GatewayCameraAssignment(
        gateway_id=gateway_id,
        camera_id=camera_id,
        granted_at=datetime.now(timezone.utc),
        revoked_at=datetime.now(timezone.utc) if revoked else None,
    )
    db.add(assignment)
    db.commit()
    return assignment


def _seed_user(db: DbSession, *, email: str = "viewer@example.test") -> User:
    user = User(id=uuid.uuid4(), email=email, idp_subject=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _grant_camera_acl(db: DbSession, *, user_id: uuid.UUID, camera_id: uuid.UUID) -> CameraAcl:
    acl = CameraAcl(user_id=user_id, camera_id=camera_id, granted_at=datetime.now(timezone.utc))
    db.add(acl)
    db.commit()
    return acl


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


def _command(gateway_id: str = "gateway-1") -> GatewayCommandEnvelope:
    now = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)
    return GatewayCommandEnvelope(
        command_id="11111111-1111-1111-1111-111111111111",
        kind="gateway.command.start_publish",
        gateway_id=gateway_id,
        issued_at=now,
        expires_at=now + timedelta(seconds=30),
        payload={"camera_id": "camera-1", "room": "camera_ab12cd34"},
        signature="",
    )


def test_gateway_heartbeat_requires_gateway_identity(client: TestClient) -> None:
    response = client.post(
        "/api/v1/gateways/gateway-1/heartbeat",
        json={"status": "online", "agent_version": "0.1.0", "cameras": []},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "gateway-identity-required"


def test_gateway_heartbeat_accepts_dev_gateway_identity() -> None:
    client = _dev_gateway_client()

    response = client.post(
        "/api/v1/gateways/gateway-1/heartbeat",
        headers=_gateway_headers(),
        json={"status": "online", "agent_version": "0.1.0", "cameras": []},
    )

    assert response.status_code == 200
    data = response.json()
    assert "server_time" in data
    assert data["pending_commands"] == []


def test_gateway_heartbeat_returns_signed_pending_commands_from_app_state_provider() -> None:
    client = _dev_gateway_client(signing_key=SIGNING_KEY)
    client.app.state.gateway_control_command_provider = lambda gateway_id: [_command(gateway_id)]

    response = client.post(
        "/api/v1/gateways/gateway-1/heartbeat",
        headers=_gateway_headers(),
        json={"status": "online", "agent_version": "0.1.0", "cameras": []},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["pending_commands"]) == 1
    command = GatewayCommandEnvelope.model_validate(data["pending_commands"][0])
    assert command.gateway_id == "gateway-1"
    assert command.signature
    verify_command_envelope(
        command,
        SIGNING_KEY,
        expected_gateway_id="gateway-1",
        now=datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_gateway_heartbeat_fails_closed_when_pending_command_signing_fails() -> None:
    client = _dev_gateway_client(signing_key="replace-me")
    client.app.state.gateway_control_command_provider = lambda gateway_id: [_command(gateway_id)]

    response = client.post(
        "/api/v1/gateways/gateway-1/heartbeat",
        headers=_gateway_headers(),
        json={"status": "online", "agent_version": "0.1.0", "cameras": []},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "gateway-command-signing-failed"


def test_gateway_id_mismatch_returns_forbidden() -> None:
    client = _dev_gateway_client()

    response = client.post(
        "/api/v1/gateways/gateway-2/heartbeat",
        headers=_gateway_headers("gateway-1"),
        json={"status": "online", "agent_version": "0.1.0", "cameras": []},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gateway-id-mismatch"


def test_gateway_ingest_token_requires_uuid_gateway_id() -> None:
    client = _dev_gateway_client()

    response = client.post(
        "/api/v1/gateways/gateway-1/ingest-token",
        headers=_gateway_headers(),
        json={"camera_id": "camera-1"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "gateway-id-invalid"


def test_gateway_camera_status_requires_authentication(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/gateways/{uuid.uuid4()}/cameras/{uuid.uuid4()}/status",
        json={"status": "online", "detail": "synthetic camera healthy"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "gateway-identity-required"


def test_gateway_camera_status_rejects_gateway_id_mismatch() -> None:
    gateway_id = uuid.uuid4()
    other_gateway_id = uuid.uuid4()
    client = _dev_gateway_client()

    response = client.post(
        f"/api/v1/gateways/{gateway_id}/cameras/{uuid.uuid4()}/status",
        headers=_gateway_headers(str(other_gateway_id)),
        json={"status": "online", "detail": "synthetic camera healthy"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gateway-id-mismatch"


def test_gateway_camera_status_rejects_invalid_gateway_id() -> None:
    client = _dev_gateway_client()

    response = client.post(
        f"/api/v1/gateways/not-a-uuid/cameras/{uuid.uuid4()}/status",
        headers=_gateway_headers("not-a-uuid"),
        json={"status": "online", "detail": "synthetic camera healthy"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "gateway-id-invalid"


def test_gateway_camera_status_rejects_invalid_camera_id() -> None:
    gateway_id = uuid.uuid4()
    client = _dev_gateway_client()

    response = client.post(
        f"/api/v1/gateways/{gateway_id}/cameras/not-a-uuid/status",
        headers=_gateway_headers(str(gateway_id)),
        json={"status": "online", "detail": "synthetic camera healthy"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "camera-id-invalid"


def test_gateway_camera_status_rejects_missing_gateway(test_db_session: DbSession) -> None:
    gateway_id = uuid.uuid4()
    camera = _seed_camera(test_db_session)
    client = _dev_gateway_client_with_db(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway_id}/cameras/{camera.id}/status",
        headers=_gateway_headers(str(gateway_id)),
        json={"status": "online", "detail": "synthetic camera healthy"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gateway-disabled-or-not-found"


def test_gateway_camera_status_rejects_disabled_gateway(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session, status=GatewayStatus.disabled)
    camera = _seed_camera(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _dev_gateway_client_with_db(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/cameras/{camera.id}/status",
        headers=_gateway_headers(str(gateway.id)),
        json={"status": "online", "detail": "synthetic camera healthy"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gateway-disabled-or-not-found"


def test_gateway_camera_status_rejects_missing_camera(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    client = _dev_gateway_client_with_db(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/cameras/{uuid.uuid4()}/status",
        headers=_gateway_headers(str(gateway.id)),
        json={"status": "online", "detail": "synthetic camera healthy"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "camera-not-found"


def test_gateway_camera_status_rejects_retired_camera(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session, retired=True)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _dev_gateway_client_with_db(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/cameras/{camera.id}/status",
        headers=_gateway_headers(str(gateway.id)),
        json={"status": "online", "detail": "synthetic camera healthy"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "camera-not-found"


def test_gateway_camera_status_rejects_missing_assignment(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    client = _dev_gateway_client_with_db(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/cameras/{camera.id}/status",
        headers=_gateway_headers(str(gateway.id)),
        json={"status": "online", "detail": "synthetic camera healthy"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gateway-camera-assignment-denied"


def test_gateway_camera_status_rejects_revoked_assignment(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id, revoked=True)
    client = _dev_gateway_client_with_db(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/cameras/{camera.id}/status",
        headers=_gateway_headers(str(gateway.id)),
        json={"status": "online", "detail": "synthetic camera healthy"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gateway-camera-assignment-denied"


def test_gateway_camera_status_persists_camera_event(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _dev_gateway_client_with_db(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/cameras/{camera.id}/status",
        headers=_gateway_headers(str(gateway.id)),
        json={"status": "degraded", "detail": "packet loss"},
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": True}
    event = test_db_session.execute(select(CameraEvent)).scalar_one()
    assert event.camera_id == camera.id
    assert event.gateway_id == gateway.id
    assert event.kind == CameraEventKind.degraded
    assert event.source == EventSource.heartbeat
    assert event.at is not None


def test_gateway_camera_status_uses_observed_at(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    observed_at = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)
    client = _dev_gateway_client_with_db(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/cameras/{camera.id}/status",
        headers=_gateway_headers(str(gateway.id)),
        json={"status": "offline", "observed_at": observed_at.isoformat()},
    )

    assert response.status_code == 200
    event = test_db_session.execute(select(CameraEvent)).scalar_one()
    assert event.kind == CameraEventKind.offline
    assert event.at.replace(tzinfo=timezone.utc) == observed_at


def test_gateway_camera_status_event_is_visible_to_acl_viewer(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    _grant_camera_acl(test_db_session, user_id=user.id, camera_id=camera.id)
    client = _dev_gateway_client_with_db(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/cameras/{camera.id}/status",
        headers=_gateway_headers(str(gateway.id)),
        json={"status": "online", "detail": "synthetic camera healthy"},
    )
    assert response.status_code == 200

    events_response = client.get("/api/v1/cameras/events", headers=_viewer_headers())
    assert events_response.status_code == 200
    events = _parse_sse_events(events_response.text)
    assert len(events) == 1
    assert events[0]["camera_id"] == str(camera.id)
    assert events[0]["gateway_id"] == str(gateway.id)
    assert events[0]["kind"] == "online"
    assert events[0]["source"] == "heartbeat"


def test_gateway_control_ws_rejects_unauthenticated() -> None:
    client = _dev_gateway_client()

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/gateway-control/ws"):
            pass

    assert exc_info.value.code == 1008


def test_gateway_control_ws_rejects_browser_dev_auth() -> None:
    client = _dev_gateway_client()

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/v1/gateway-control/ws",
            headers={"x-panoptix-dev-auth": "1"},
        ):
            pass

    assert exc_info.value.code == 1008


def test_gateway_control_ws_accepts_valid_gateway_and_sends_hello() -> None:
    client = _dev_gateway_client()

    with client.websocket_connect(
        "/api/v1/gateway-control/ws",
        headers=_gateway_headers("gateway-1"),
    ) as ws:
        hello = ws.receive_json()
        assert hello == {"type": "connected", "gateway_id": "gateway-1"}


def test_gateway_control_ws_sends_signed_command_from_app_state_provider() -> None:
    client = _dev_gateway_client(signing_key=SIGNING_KEY)
    client.app.state.gateway_control_command_provider = lambda gateway_id: [_command(gateway_id)]

    with client.websocket_connect(
        "/api/v1/gateway-control/ws",
        headers=_gateway_headers("gateway-1"),
    ) as ws:
        assert ws.receive_json() == {"type": "connected", "gateway_id": "gateway-1"}
        command_data = ws.receive_json()

    command = GatewayCommandEnvelope.model_validate(command_data)
    assert command.gateway_id == "gateway-1"
    assert command.signature
    verify_command_envelope(
        command,
        SIGNING_KEY,
        expected_gateway_id="gateway-1",
        now=datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_gateway_control_ws_records_accepted_ack_from_gateway() -> None:
    client = _dev_gateway_client(signing_key=SIGNING_KEY)
    received: list[tuple[str, GatewayCommandAck]] = []
    client.app.state.gateway_control_command_provider = lambda gateway_id: [_command(gateway_id)]
    client.app.state.gateway_control_ack_sink = lambda gateway_id, ack: received.append(
        (gateway_id, ack)
    )

    with client.websocket_connect(
        "/api/v1/gateway-control/ws",
        headers=_gateway_headers("gateway-1"),
    ) as ws:
        ws.receive_json()
        command = ws.receive_json()
        ws.send_json(
            {
                "type": "command_ack",
                "command_id": command["command_id"],
                "gateway_id": "gateway-1",
                "status": "accepted",
            }
        )

    assert [(gateway_id, ack.model_dump()) for gateway_id, ack in received] == [
        (
            "gateway-1",
            {
                "type": "command_ack",
                "command_id": "11111111-1111-1111-1111-111111111111",
                "gateway_id": "gateway-1",
                "status": "accepted",
                "error": None,
            },
        )
    ]


def test_gateway_control_ws_records_rejected_ack_from_gateway() -> None:
    client = _dev_gateway_client(signing_key=SIGNING_KEY)
    received: list[tuple[str, GatewayCommandAck]] = []
    client.app.state.gateway_control_command_provider = lambda gateway_id: [_command(gateway_id)]
    client.app.state.gateway_control_ack_sink = lambda gateway_id, ack: received.append(
        (gateway_id, ack)
    )

    with client.websocket_connect(
        "/api/v1/gateway-control/ws",
        headers=_gateway_headers("gateway-1"),
    ) as ws:
        ws.receive_json()
        command = ws.receive_json()
        ws.send_json(
            {
                "type": "command_ack",
                "command_id": command["command_id"],
                "gateway_id": "gateway-1",
                "status": "rejected",
                "error": "gateway-command-signature-invalid",
            }
        )

    assert [(gateway_id, ack.status, ack.error) for gateway_id, ack in received] == [
        ("gateway-1", "rejected", "gateway-command-signature-invalid")
    ]


def test_gateway_control_ws_closes_without_sending_unsigned_command_when_signing_fails() -> None:
    client = _dev_gateway_client(signing_key="replace-me")
    client.app.state.gateway_control_command_provider = lambda gateway_id: [_command(gateway_id)]

    with client.websocket_connect(
        "/api/v1/gateway-control/ws",
        headers=_gateway_headers("gateway-1"),
    ) as ws:
        assert ws.receive_json() == {"type": "connected", "gateway_id": "gateway-1"}
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()

    assert exc_info.value.code == 1011
