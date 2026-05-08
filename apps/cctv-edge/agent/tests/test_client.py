from __future__ import annotations

from typing import Any

import pytest

from panoptix_edge_agent.client import AgentClientError, CameraStatusReport, GatewayApiClient, HttpResponse
from panoptix_edge_agent.config import AgentConfig


class RecordingTransport:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any], dict[str, str], float]] = []

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        self.calls.append((url, payload, headers, timeout_seconds))
        return self.response


def _config() -> AgentConfig:
    return AgentConfig(
        api_base_url="http://api.example.test/",
        gateway_id="gateway-1",
        agent_version="0.1.0",
        request_timeout_seconds=3.0,
        dev_identity_enabled=True,
    )


def test_send_heartbeat_posts_expected_payload_and_headers() -> None:
    transport = RecordingTransport(HttpResponse(status_code=200, body='{"pending_commands": []}'))
    client = GatewayApiClient(_config(), transport=transport)

    response = client.send_heartbeat(
        cameras=(CameraStatusReport(camera_id="camera-1", status="online", detail="healthy"),)
    )

    assert response == {"pending_commands": []}
    assert len(transport.calls) == 1
    url, payload, headers, timeout_seconds = transport.calls[0]
    assert url == "http://api.example.test/api/v1/gateways/gateway-1/heartbeat"
    assert payload == {
        "status": "online",
        "agent_version": "0.1.0",
        "cameras": [{"camera_id": "camera-1", "status": "online", "detail": "healthy"}],
    }
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
    assert headers["x-panoptix-dev-gateway-id"] == "gateway-1"
    assert timeout_seconds == 3.0


def test_send_camera_status_posts_expected_payload() -> None:
    transport = RecordingTransport(HttpResponse(status_code=200, body='{"accepted": true}'))
    client = GatewayApiClient(_config(), transport=transport)

    response = client.send_camera_status(camera_id="camera-1", status="degraded", detail="packet loss")

    assert response == {"accepted": True}
    url, payload, _headers, _timeout_seconds = transport.calls[0]
    assert url == "http://api.example.test/api/v1/gateways/gateway-1/cameras/camera-1/status"
    assert payload == {"status": "degraded", "detail": "packet loss"}


def test_post_raises_on_error_status() -> None:
    transport = RecordingTransport(HttpResponse(status_code=403, body='{"detail": "forbidden"}'))
    client = GatewayApiClient(_config(), transport=transport)

    with pytest.raises(AgentClientError) as exc_info:
        client.send_heartbeat()

    assert exc_info.value.status_code == 403
    assert exc_info.value.body == '{"detail": "forbidden"}'


def test_post_raises_on_invalid_json_response() -> None:
    transport = RecordingTransport(HttpResponse(status_code=200, body="not-json"))
    client = GatewayApiClient(_config(), transport=transport)

    with pytest.raises(AgentClientError, match="not valid JSON"):
        client.send_heartbeat()
