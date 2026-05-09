from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from panoptix_edge_agent.config import AgentConfig
from panoptix_edge_agent.control import ControlClientError, GatewayControlClient

SIGNING_KEY = "test-command-signing-key-with-enough-entropy"
VALID_SIGNATURE = "l-71KAAPUCsG-WaaroJwgexPNKsOB-9l37K232jAgOA"


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
            "payload": {"camera_id": "camera-1", "room": "camera_ab12cd34"},
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


def test_handle_message_accepts_matching_hello() -> None:
    client = GatewayControlClient(_config())

    result = client.handle_message(_hello())

    assert result.kind == "hello"
    assert result.accepted is True
    assert result.error is None


def test_handle_message_rejects_wrong_gateway_hello() -> None:
    client = GatewayControlClient(_config())

    result = client.handle_message(_hello("gateway-2"))

    assert result.kind == "hello"
    assert result.accepted is False
    assert result.error == "gateway-control-hello-target-mismatch"


def test_handle_message_accepts_valid_command() -> None:
    client = GatewayControlClient(_config())

    result = client.handle_message(_command())

    assert result.kind == "command"
    assert result.accepted is True
    assert result.command_id == "11111111-1111-1111-1111-111111111111"
    assert result.error is None


def test_handle_message_rejects_unsigned_command() -> None:
    client = GatewayControlClient(_config(command_signing_key=""))

    result = client.handle_message(_command())

    assert result.kind == "command"
    assert result.accepted is False
    assert result.error == "gateway-command-signing-key-invalid"


def test_handle_message_rejects_tampered_command() -> None:
    client = GatewayControlClient(_config())

    result = client.handle_message(_command("invalid-signature"))

    assert result.kind == "command"
    assert result.accepted is False
    assert result.error == "gateway-command-signature-invalid"


def test_handle_message_rejects_invalid_json() -> None:
    client = GatewayControlClient(_config())

    with pytest.raises(ControlClientError, match="not valid JSON"):
        client.handle_message("not-json")


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

    result = asyncio.run(client.run_once(max_messages=2))

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
    assert sleep_delays == []


def test_run_with_reconnect_retries_after_transient_connection_failure() -> None:
    connector = FlakyConnector(failures_before_success=1, messages=[_hello()])
    sleep_delays: list[float] = []
    client = GatewayControlClient(
        _config(control_reconnect_attempts=3, control_reconnect_backoff_seconds=2.0),
        connector=connector,
        sleep=_sleep_recorder(sleep_delays),
    )

    result = asyncio.run(client.run_with_reconnect())

    assert result.connected is True
    assert result.attempts == 2
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

    result = asyncio.run(client.run_with_reconnect())

    assert result.connected is False
    assert result.attempts == 2
    assert result.error == "gateway control websocket failed: temporary websocket failure"
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
    assert len(connector.calls) == 1
    assert sleep_delays == []
