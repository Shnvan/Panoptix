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


def _production_config() -> AgentConfig:
    return AgentConfig(
        api_base_url="http://api.example.test/",
        gateway_id="gateway-1",
        agent_version="0.1.0",
        request_timeout_seconds=3.0,
        gateway_service_token="test-gateway-service-token",
    )


def _production_cloudflare_config() -> AgentConfig:
    return AgentConfig(
        api_base_url="http://api.example.test/",
        gateway_id="gateway-1",
        agent_version="0.1.0",
        request_timeout_seconds=3.0,
        gateway_service_token="test-gateway-service-token",
        cf_access_client_id="test-client-id.access",
        cf_access_client_secret="test-client-secret",
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
    assert headers["User-Agent"] == "Panoptix-Edge-Agent/0.1.0"
    assert headers["x-panoptix-dev-gateway-id"] == "gateway-1"
    assert "x-panoptix-gateway-id" not in headers
    assert "Authorization" not in headers
    assert "CF-Access-Client-Id" not in headers
    assert "CF-Access-Client-Secret" not in headers
    assert timeout_seconds == 3.0


def test_send_heartbeat_posts_production_gateway_auth_headers() -> None:
    transport = RecordingTransport(HttpResponse(status_code=200, body='{"pending_commands": []}'))
    client = GatewayApiClient(_production_config(), transport=transport)

    client.send_heartbeat()

    _url, _payload, headers, _timeout_seconds = transport.calls[0]
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
    assert headers["User-Agent"] == "Panoptix-Edge-Agent/0.1.0"
    assert headers["x-panoptix-gateway-id"] == "gateway-1"
    assert headers["Authorization"] == "Bearer test-gateway-service-token"
    assert "x-panoptix-dev-gateway-id" not in headers
    assert "CF-Access-Client-Id" not in headers
    assert "CF-Access-Client-Secret" not in headers


def test_send_heartbeat_posts_cloudflare_access_headers_when_configured() -> None:
    transport = RecordingTransport(HttpResponse(status_code=200, body='{"pending_commands": []}'))
    client = GatewayApiClient(_production_cloudflare_config(), transport=transport)

    client.send_heartbeat()

    _url, _payload, headers, _timeout_seconds = transport.calls[0]
    assert headers["User-Agent"] == "Panoptix-Edge-Agent/0.1.0"
    assert headers["x-panoptix-gateway-id"] == "gateway-1"
    assert headers["Authorization"] == "Bearer test-gateway-service-token"
    assert headers["CF-Access-Client-Id"] == "test-client-id.access"
    assert headers["CF-Access-Client-Secret"] == "test-client-secret"
    assert "x-panoptix-dev-gateway-id" not in headers


def test_dev_config_does_not_send_cloudflare_access_headers() -> None:
    transport = RecordingTransport(HttpResponse(status_code=200, body='{"pending_commands": []}'))
    client = GatewayApiClient(
        AgentConfig(
            api_base_url="http://api.example.test/",
            gateway_id="gateway-1",
            agent_version="0.1.0",
            request_timeout_seconds=3.0,
            dev_identity_enabled=True,
            gateway_service_token="test-gateway-service-token",
            cf_access_client_id="test-client-id.access",
            cf_access_client_secret="test-client-secret",
        ),
        transport=transport,
    )

    client.send_heartbeat()

    _url, _payload, headers, _timeout_seconds = transport.calls[0]
    assert headers["User-Agent"] == "Panoptix-Edge-Agent/0.1.0"
    assert headers["x-panoptix-dev-gateway-id"] == "gateway-1"
    assert "x-panoptix-gateway-id" not in headers
    assert "Authorization" not in headers
    assert "CF-Access-Client-Id" not in headers
    assert "CF-Access-Client-Secret" not in headers


def test_post_requires_gateway_service_token_outside_dev_mode() -> None:
    transport = RecordingTransport(HttpResponse(status_code=200, body='{"pending_commands": []}'))
    client = GatewayApiClient(
        AgentConfig(
            api_base_url="http://api.example.test/",
            gateway_id="gateway-1",
            dev_identity_enabled=False,
        ),
        transport=transport,
    )

    with pytest.raises(AgentClientError, match="PANOPTIX_GATEWAY_SERVICE_TOKEN"):
        client.send_heartbeat()

    assert transport.calls == []


def test_post_requires_complete_cloudflare_access_pair_when_configured() -> None:
    transport = RecordingTransport(HttpResponse(status_code=200, body='{"pending_commands": []}'))
    client = GatewayApiClient(
        AgentConfig(
            api_base_url="http://api.example.test/",
            gateway_id="gateway-1",
            dev_identity_enabled=False,
            gateway_service_token="test-gateway-service-token",
            cf_access_client_id="test-client-id.access",
        ),
        transport=transport,
    )

    with pytest.raises(AgentClientError, match="PANOPTIX_CF_ACCESS_CLIENT_ID"):
        client.send_heartbeat()

    assert transport.calls == []


def test_send_camera_status_posts_expected_payload() -> None:
    transport = RecordingTransport(HttpResponse(status_code=200, body='{"accepted": true}'))
    client = GatewayApiClient(_config(), transport=transport)

    response = client.send_camera_status(camera_id="camera-1", status="degraded", detail="packet loss")

    assert response == {"accepted": True}
    url, payload, _headers, _timeout_seconds = transport.calls[0]
    assert url == "http://api.example.test/api/v1/gateways/gateway-1/cameras/camera-1/status"
    assert payload == {"status": "degraded", "detail": "packet loss"}


def test_send_discovery_run_posts_expected_payload() -> None:
    transport = RecordingTransport(HttpResponse(status_code=200, body='{"accepted": true}'))
    client = GatewayApiClient(_config(), transport=transport)
    report = {
        "started_at": "2026-05-25T10:00:00+00:00",
        "finished_at": "2026-05-25T10:00:01+00:00",
        "status": "completed",
        "approved_ranges": ["192.168.50.0/30"],
        "ports": [554, 80],
        "scanned_host_count": 2,
        "candidate_count": 1,
        "findings": [],
        "agent_version": "0.1.0",
    }

    response = client.send_discovery_run(report)

    assert response == {"accepted": True}
    url, payload, _headers, _timeout_seconds = transport.calls[0]
    assert url == "http://api.example.test/api/v1/gateways/gateway-1/discovery-runs"
    assert payload == report


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
