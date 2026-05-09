from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from cctv_api.core.config import Settings
from cctv_api.gateway.command_signing import verify_command_envelope
from cctv_api.gateway.models import GatewayCommandAck, GatewayCommandEnvelope
from cctv_api.main import create_app


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


def _gateway_headers(gateway_id: str = "gateway-1") -> dict[str, str]:
    return {"x-panoptix-dev-gateway-id": gateway_id}


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


def test_gateway_camera_status_accepts_valid_dev_gateway_event() -> None:
    client = _dev_gateway_client()

    response = client.post(
        "/api/v1/gateways/gateway-1/cameras/camera-1/status",
        headers=_gateway_headers(),
        json={"status": "online", "detail": "synthetic camera healthy"},
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": True}


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
