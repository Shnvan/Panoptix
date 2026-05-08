from __future__ import annotations

from fastapi.testclient import TestClient

from cctv_api.core.config import Settings
from cctv_api.main import create_app


def _dev_gateway_client() -> TestClient:
    app = create_app(settings=Settings(APP_ENV="development", ALLOW_DEV_AUTH=True))
    return TestClient(app)


def _gateway_headers(gateway_id: str = "gateway-1") -> dict[str, str]:
    return {"x-panoptix-dev-gateway-id": gateway_id}


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


def test_gateway_id_mismatch_returns_forbidden() -> None:
    client = _dev_gateway_client()

    response = client.post(
        "/api/v1/gateways/gateway-2/heartbeat",
        headers=_gateway_headers("gateway-1"),
        json={"status": "online", "agent_version": "0.1.0", "cameras": []},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gateway-id-mismatch"


def test_gateway_ingest_token_fails_closed_until_livekit_implementation() -> None:
    client = _dev_gateway_client()

    response = client.post(
        "/api/v1/gateways/gateway-1/ingest-token",
        headers=_gateway_headers(),
        json={"camera_id": "camera-1"},
    )

    assert response.status_code == 501
    assert response.json()["detail"] == "gateway-ingest-token-not-implemented"


def test_gateway_camera_status_accepts_valid_dev_gateway_event() -> None:
    client = _dev_gateway_client()

    response = client.post(
        "/api/v1/gateways/gateway-1/cameras/camera-1/status",
        headers=_gateway_headers(),
        json={"status": "online", "detail": "synthetic camera healthy"},
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": True}


def test_gateway_control_ws_requires_gateway_identity(client: TestClient) -> None:
    response = client.get("/api/v1/gateway-control/ws")

    assert response.status_code == 401
    assert response.json()["detail"] == "gateway-identity-required"


def test_gateway_control_ws_placeholder_fails_closed_for_valid_gateway() -> None:
    client = _dev_gateway_client()

    response = client.get("/api/v1/gateway-control/ws", headers=_gateway_headers())

    assert response.status_code == 501
    assert response.json()["detail"] == "gateway-control-websocket-not-implemented"
