from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import patch

import pytest

from panoptix_edge_agent.config import AgentConfig
from panoptix_edge_agent.control import ControlClientError, GatewayControlClient, GatewayControlSupervisor

SIGNING_KEY = "test-command-signing-key-with-enough-entropy"
VALID_SIGNATURE = "XtEyJPLXf5z6QvlLFhVRqIhVpwbH0R7H_F_1W4dFzxw"


class FakeWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        self.sent_messages: list[str | bytes] = []

    async def recv(self) -> str:
        return self.messages.pop(0)

    async def send(self, message: str | bytes) -> None:
        self.sent_messages.append(message)


class FakeWebSocketContext:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket

    async def __aenter__(self) -> FakeWebSocket:
        return self.websocket

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


class RecordingConnector:
    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        self.calls: list[tuple[str, dict[str, str], float]] = []
        self.websockets: list[FakeWebSocket] = []

    def connect(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> FakeWebSocketContext:
        self.calls.append((url, headers, timeout_seconds))
        websocket = FakeWebSocket(self.messages.copy())
        self.websockets.append(websocket)
        return FakeWebSocketContext(websocket)


class FlakyConnector:
    def __init__(self, *, failures_before_success: int, messages: list[str]) -> None:
        self.failures_before_success = failures_before_success
        self.messages = messages
        self.calls = 0

    def connect(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> FakeWebSocketContext:
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise RuntimeError("temporary websocket failure")
        return FakeWebSocketContext(FakeWebSocket(self.messages.copy()))


def _config(**overrides: Any) -> AgentConfig:
    values: dict[str, Any] = {
        "api_base_url": "http://api.example.test/",
        "gateway_id": "gateway-1",
        "request_timeout_seconds": 3.0,
        "dev_identity_enabled": True,
        "command_signing_key": SIGNING_KEY,
    }
    values.update(overrides)
    return AgentConfig(**values)


def _production_config(**overrides: Any) -> AgentConfig:
    values: dict[str, Any] = {
        "api_base_url": "https://api.example.test/",
        "gateway_id": "gateway-1",
        "request_timeout_seconds": 3.0,
        "gateway_service_token": "test-gateway-service-token",
        "command_signing_key": SIGNING_KEY,
    }
    values.update(overrides)
    return AgentConfig(**values)


def _hello(gateway_id: str = "gateway-1") -> str:
    return json.dumps({"type": "connected", "gateway_id": gateway_id})


def _command(signature: str = VALID_SIGNATURE) -> str:
    return json.dumps(
        {
            "command_id": "11111111-1111-1111-1111-111111111111",
            "kind": "gateway.command.start_publish",
            "gateway_id": "gateway-1",
            "issued_at": "2026-05-07T12:00:00Z",
            "expires_at": "2999-05-07T12:00:30Z",
            "payload": {
                "camera_id": "camera-1",
                "room": "camera_ab12cd34",
                "livekit_url": "wss://livekit.example.test",
                "gateway_publish_token": "test-publish-token",
                "token_expires_at": "2026-05-07T12:01:00Z",
            },
            "signature": signature,
        }
    )


def _sleep_recorder(delays: list[float]):
    async def _sleep(delay: float) -> None:
        delays.append(delay)

    return _sleep


def test_websocket_url_uses_ws_for_http_base_url() -> None:
    client = GatewayControlClient(_config())

    assert client.websocket_url == "ws://api.example.test/api/v1/gateway-control/ws"


def test_websocket_url_uses_wss_for_https_base_url() -> None:
    client = GatewayControlClient(_config(api_base_url="https://api.example.test"))

    assert client.websocket_url == "wss://api.example.test/api/v1/gateway-control/ws"


def test_websocket_url_uses_configured_path() -> None:
    client = GatewayControlClient(_config(control_ws_path="/custom/ws"))

    assert client.websocket_url == "ws://api.example.test/custom/ws"


def test_run_once_connects_with_dev_gateway_header() -> None:
    connector = RecordingConnector([_hello()])
    client = GatewayControlClient(_config(), connector=connector)

    result = asyncio.run(client.run_once())

    assert result.connected is True
    assert result.hello_received is True
    assert connector.calls == [
        (
            "ws://api.example.test/api/v1/gateway-control/ws",
            {"Accept": "application/json", "x-panoptix-dev-gateway-id": "gateway-1"},
            3.0,
        )
    ]


def test_run_once_connects_with_production_gateway_auth_headers() -> None:
    connector = RecordingConnector([_hello()])
    client = GatewayControlClient(_production_config(), connector=connector)

    result = asyncio.run(client.run_once())

    assert result.connected is True
    assert result.hello_received is True
    assert connector.calls == [
        (
            "wss://api.example.test/api/v1/gateway-control/ws",
            {
                "Accept": "application/json",
                "x-panoptix-gateway-id": "gateway-1",
                "Authorization": "Bearer test-gateway-service-token",
            },
            3.0,
        )
    ]


def test_run_once_connects_with_cloudflare_access_headers_when_configured() -> None:
    connector = RecordingConnector([_hello()])
    client = GatewayControlClient(
        _production_config(
            cf_access_client_id="test-client-id.access",
            cf_access_client_secret="test-client-secret",
        ),
        connector=connector,
    )

    result = asyncio.run(client.run_once())

    assert result.connected is True
    assert result.hello_received is True
    _url, headers, _timeout_seconds = connector.calls[0]
    assert headers["x-panoptix-gateway-id"] == "gateway-1"
    assert headers["Authorization"] == "Bearer test-gateway-service-token"
    assert headers["CF-Access-Client-Id"] == "test-client-id.access"
    assert headers["CF-Access-Client-Secret"] == "test-client-secret"
    assert "x-panoptix-dev-gateway-id" not in headers


def test_run_once_requires_gateway_service_token_outside_dev_mode() -> None:
    connector = RecordingConnector([_hello()])
    client = GatewayControlClient(
        _production_config(gateway_service_token=""),
        connector=connector,
    )

    with pytest.raises(ControlClientError, match="PANOPTIX_GATEWAY_SERVICE_TOKEN"):
        asyncio.run(client.run_once())

    assert connector.calls == []


def test_run_once_requires_complete_cloudflare_access_pair_when_configured() -> None:
    connector = RecordingConnector([_hello()])
    client = GatewayControlClient(
        _production_config(cf_access_client_id="test-client-id.access"),
        connector=connector,
    )

    with pytest.raises(ControlClientError, match="PANOPTIX_CF_ACCESS_CLIENT_ID"):
        asyncio.run(client.run_once())

    assert connector.calls == []


def test_handle_message_accepts_matching_hello() -> None:
    client = GatewayControlClient(_config())

    result = asyncio.run(client.handle_message(_hello()))

    assert result.kind == "hello"
    assert result.accepted is True
    assert result.error is None


def test_handle_message_rejects_wrong_gateway_hello() -> None:
    client = GatewayControlClient(_config())

    result = asyncio.run(client.handle_message(_hello("gateway-2")))

    assert result.kind == "hello"
    assert result.accepted is False
    assert result.error == "gateway-control-hello-target-mismatch"


def test_handle_message_accepts_valid_command() -> None:
    client = GatewayControlClient(_config())

    result = asyncio.run(client.handle_message(_command()))

    assert result.kind == "command"
    assert result.accepted is True
    assert result.command_id == "11111111-1111-1111-1111-111111111111"
    assert result.error is None


def test_handle_message_rejects_unsigned_command() -> None:
    client = GatewayControlClient(_config(command_signing_key=""))

    result = asyncio.run(client.handle_message(_command()))

    assert result.kind == "command"
    assert result.accepted is False
    assert result.error == "gateway-command-signing-key-invalid"


def test_handle_message_rejects_tampered_command() -> None:
    client = GatewayControlClient(_config())

    result = asyncio.run(client.handle_message(_command("invalid-signature")))

    assert result.kind == "command"
    assert result.accepted is False
    assert result.error == "gateway-command-signature-invalid"


def test_handle_message_rejects_invalid_json() -> None:
    client = GatewayControlClient(_config())

    with pytest.raises(ControlClientError, match="not valid JSON"):
        asyncio.run(client.handle_message("not-json"))


def test_run_once_sends_accepted_ack_for_valid_command() -> None:
    connector = RecordingConnector([_command()])
    client = GatewayControlClient(_config(), connector=connector)

    result = asyncio.run(client.run_once())

    assert result.accepted_commands == 1
    assert result.rejected_commands == 0
    assert [json.loads(message) for message in connector.websockets[0].sent_messages] == [
        {
            "type": "command_ack",
            "command_id": "11111111-1111-1111-1111-111111111111",
            "gateway_id": "gateway-1",
            "status": "accepted",
        }
    ]


def test_run_once_handles_hello_then_command() -> None:
    connector = RecordingConnector([_hello(), _command()])
    client = GatewayControlClient(_config(), connector=connector)

    result = asyncio.run(client.run_once())

    assert result.hello_received is True
    assert result.accepted_commands == 1
    assert [json.loads(message) for message in connector.websockets[0].sent_messages] == [
        {
            "type": "command_ack",
            "command_id": "11111111-1111-1111-1111-111111111111",
            "gateway_id": "gateway-1",
            "status": "accepted",
        }
    ]


def test_run_once_sends_rejected_ack_for_tampered_command() -> None:
    connector = RecordingConnector([_command("invalid-signature")])
    client = GatewayControlClient(_config(), connector=connector)

    result = asyncio.run(client.run_once())

    assert result.accepted_commands == 0
    assert result.rejected_commands == 1
    assert [json.loads(message) for message in connector.websockets[0].sent_messages] == [
        {
            "type": "command_ack",
            "command_id": "11111111-1111-1111-1111-111111111111",
            "gateway_id": "gateway-1",
            "status": "rejected",
            "error": "gateway-command-signature-invalid",
        }
    ]


def test_run_once_sends_rejected_ack_for_wrong_gateway_command() -> None:
    command = json.loads(_command())
    command["gateway_id"] = "gateway-2"
    connector = RecordingConnector([json.dumps(command)])
    client = GatewayControlClient(_config(), connector=connector)

    result = asyncio.run(client.run_once())

    assert result.accepted_commands == 0
    assert result.rejected_commands == 1
    assert [json.loads(message) for message in connector.websockets[0].sent_messages] == [
        {
            "type": "command_ack",
            "command_id": "11111111-1111-1111-1111-111111111111",
            "gateway_id": "gateway-1",
            "status": "rejected",
            "error": "gateway-command-target-mismatch",
        }
    ]


def test_run_with_reconnect_succeeds_on_first_attempt_without_sleeping() -> None:
    connector = RecordingConnector([_hello()])
    sleep_delays: list[float] = []
    client = GatewayControlClient(
        _config(control_reconnect_attempts=3, control_reconnect_backoff_seconds=2.0),
        connector=connector,
        sleep=_sleep_recorder(sleep_delays),
    )

    result = asyncio.run(client.run_with_reconnect())

    assert result.connected is True
    assert result.attempts == 1
    assert result.result is not None
    assert result.result.hello_received is True
    assert result.retryable_failures == 0
    assert result.sleep_delays == ()
    assert result.stopped_reason == "connected"
    assert sleep_delays == []


def test_run_with_reconnect_retries_after_transient_connection_failure() -> None:
    connector = FlakyConnector(failures_before_success=1, messages=[_hello()])
    sleep_delays: list[float] = []
    client = GatewayControlClient(
        _config(control_reconnect_attempts=3, control_reconnect_backoff_seconds=2.0),
        connector=connector,
        sleep=_sleep_recorder(sleep_delays),
    )

    with patch("random.uniform", return_value=0):
        result = asyncio.run(client.run_with_reconnect())

    assert result.connected is True
    assert result.attempts == 2
    assert result.retryable_failures == 1
    assert result.sleep_delays == (2.0,)
    assert result.stopped_reason == "connected"
    assert connector.calls == 2
    assert sleep_delays == [2.0]


def test_run_with_reconnect_stops_after_configured_attempts() -> None:
    connector = FlakyConnector(failures_before_success=99, messages=[_hello()])
    sleep_delays: list[float] = []
    client = GatewayControlClient(
        _config(control_reconnect_attempts=2, control_reconnect_backoff_seconds=0.5),
        connector=connector,
        sleep=_sleep_recorder(sleep_delays),
    )

    with patch("random.uniform", return_value=0):
        result = asyncio.run(client.run_with_reconnect())

    assert result.connected is False
    assert result.attempts == 2
    assert result.error == "gateway control websocket failed: temporary websocket failure"
    assert result.retryable_failures == 2
    assert result.sleep_delays == (0.5,)
    assert result.stopped_reason == "exhausted-retries"
    assert connector.calls == 2
    assert sleep_delays == [0.5]


def test_run_with_reconnect_does_not_retry_invalid_control_message() -> None:
    connector = RecordingConnector(["not-json"])
    sleep_delays: list[float] = []
    client = GatewayControlClient(
        _config(control_reconnect_attempts=3),
        connector=connector,
        sleep=_sleep_recorder(sleep_delays),
    )

    result = asyncio.run(client.run_with_reconnect())

    assert result.connected is False
    assert result.attempts == 1
    assert result.error == "gateway control message was not valid JSON"
    assert result.retryable_failures == 0
    assert result.sleep_delays == ()
    assert result.stopped_reason == "non-retryable-error"
    assert len(connector.calls) == 1
    assert sleep_delays == []


def test_control_supervisor_runs_repeated_successful_cycles() -> None:
    connector = RecordingConnector([_hello()])
    sleep_delays: list[float] = []
    client = GatewayControlClient(
        _config(control_reconnect_attempts=2, control_reconnect_backoff_seconds=0.25),
        connector=connector,
        sleep=_sleep_recorder(sleep_delays),
    )
    supervisor = GatewayControlSupervisor(client)

    result = asyncio.run(supervisor.run_once(cycles=3))

    assert result.cycles == 3
    assert result.connected_cycles == 3
    assert result.failed_cycles == 0
    assert result.consecutive_failures == 0
    assert result.stopped_reason == "cycle-limit"
    assert result.last_result is not None
    assert result.last_result.connected is True
    assert connector.calls == [
        ("ws://api.example.test/api/v1/gateway-control/ws", {"Accept": "application/json", "x-panoptix-dev-gateway-id": "gateway-1"}, 3.0),
        ("ws://api.example.test/api/v1/gateway-control/ws", {"Accept": "application/json", "x-panoptix-dev-gateway-id": "gateway-1"}, 3.0),
        ("ws://api.example.test/api/v1/gateway-control/ws", {"Accept": "application/json", "x-panoptix-dev-gateway-id": "gateway-1"}, 3.0),
    ]
    assert sleep_delays == [0.25, 0.25]


def test_control_supervisor_can_stop_after_first_success() -> None:
    connector = RecordingConnector([_hello()])
    sleep_delays: list[float] = []
    client = GatewayControlClient(
        _config(control_reconnect_attempts=2, control_reconnect_backoff_seconds=0.25),
        connector=connector,
        sleep=_sleep_recorder(sleep_delays),
    )
    supervisor = GatewayControlSupervisor(client)

    result = asyncio.run(supervisor.run_once(cycles=3, stop_after_success=True))

    assert result.cycles == 1
    assert result.connected_cycles == 1
    assert result.failed_cycles == 0
    assert result.stopped_reason == "connected"
    assert len(connector.calls) == 1
    assert sleep_delays == []


def test_control_supervisor_stops_on_non_retryable_error() -> None:
    connector = RecordingConnector(["not-json"])
    sleep_delays: list[float] = []
    client = GatewayControlClient(
        _config(control_reconnect_attempts=3, control_reconnect_backoff_seconds=0.25),
        connector=connector,
        sleep=_sleep_recorder(sleep_delays),
    )
    supervisor = GatewayControlSupervisor(client)

    result = asyncio.run(supervisor.run_once(cycles=3))

    assert result.cycles == 1
    assert result.connected_cycles == 0
    assert result.failed_cycles == 1
    assert result.consecutive_failures == 1
    assert result.stopped_reason == "non-retryable-error"
    assert result.last_result is not None
    assert result.last_result.error == "gateway control message was not valid JSON"
    assert len(connector.calls) == 1
    assert sleep_delays == []


def test_control_supervisor_tracks_consecutive_failures() -> None:
    connector = FlakyConnector(failures_before_success=99, messages=[_hello()])
    sleep_delays: list[float] = []
    client = GatewayControlClient(
        _config(control_reconnect_attempts=1, control_reconnect_backoff_seconds=0.25),
        connector=connector,
        sleep=_sleep_recorder(sleep_delays),
    )
    supervisor = GatewayControlSupervisor(client)

    result = asyncio.run(supervisor.run_once(cycles=2))

    assert result.cycles == 2
    assert result.connected_cycles == 0
    assert result.failed_cycles == 2
    assert result.consecutive_failures == 2
    assert result.stopped_reason == "cycle-limit"
    assert connector.calls == 2
    assert sleep_delays == [0.25]


def test_control_supervisor_rejects_invalid_cycle_count() -> None:
    supervisor = GatewayControlSupervisor(GatewayControlClient(_config()))

    with pytest.raises(ControlClientError, match="cycles must be at least 1"):
        asyncio.run(supervisor.run_once(cycles=0))


def test_control_supervisor_propagates_cancellation() -> None:
    connector = FlakyConnector(failures_before_success=99, messages=[_hello()])

    async def _cancel_sleep(_delay: float) -> None:
        raise asyncio.CancelledError

    client = GatewayControlClient(
        _config(control_reconnect_attempts=2, control_reconnect_backoff_seconds=0.25),
        connector=connector,
        sleep=_cancel_sleep,
    )
    supervisor = GatewayControlSupervisor(client)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(supervisor.run_once(cycles=1))


def test_reconnect_uses_exponential_backoff() -> None:
    base = 1.0
    max_delay = 60.0

    with patch("random.uniform", return_value=0):
        for attempt_index, expected_delay in [(0, 1.0), (1, 2.0), (2, 4.0)]:
            connector = FlakyConnector(failures_before_success=attempt_index + 1, messages=[_hello()])
            sleep_delays: list[float] = []
            client = GatewayControlClient(
                _config(
                    control_reconnect_attempts=attempt_index + 2,
                    control_reconnect_backoff_seconds=base,
                ),
                connector=connector,
                sleep=_sleep_recorder(sleep_delays),
            )
            asyncio.run(client.run_with_reconnect())
            assert sleep_delays[attempt_index] == min(base * (2 ** attempt_index), max_delay), (
                f"attempt_index={attempt_index}: expected {expected_delay}, got {sleep_delays[attempt_index]}"
            )


def test_reconnect_backoff_capped_at_max() -> None:
    base = 1.0
    max_delay = 60.0
    large_attempt_index = 10  # base * 2^10 = 1024.0, well above max_delay

    connector = FlakyConnector(failures_before_success=large_attempt_index + 1, messages=[_hello()])
    sleep_delays: list[float] = []
    client = GatewayControlClient(
        _config(
            control_reconnect_attempts=large_attempt_index + 2,
            control_reconnect_backoff_seconds=base,
        ),
        connector=connector,
        sleep=_sleep_recorder(sleep_delays),
    )

    with patch("random.uniform", return_value=0):
        asyncio.run(client.run_with_reconnect())

    for delay in sleep_delays:
        assert delay <= max_delay + base, f"delay {delay} exceeds max_delay + base ({max_delay + base})"
    assert sleep_delays[large_attempt_index] == max_delay


def test_reconnect_backoff_has_jitter() -> None:
    base = 1.0

    observed_delays: list[float] = []

    async def _capture_first_sleep(delay: float) -> None:
        observed_delays.append(delay)
        raise asyncio.CancelledError

    for _ in range(10):
        client = GatewayControlClient(
            _config(control_reconnect_attempts=3, control_reconnect_backoff_seconds=base),
            connector=FlakyConnector(failures_before_success=1, messages=[_hello()]),
            sleep=_capture_first_sleep,
        )
        try:
            asyncio.run(client.run_with_reconnect())
        except asyncio.CancelledError:
            pass

    assert len(observed_delays) == 10
    assert len(set(observed_delays)) > 1, "all backoff delays were identical — jitter not applied"
