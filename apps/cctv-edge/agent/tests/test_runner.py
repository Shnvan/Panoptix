from __future__ import annotations

from typing import Any

from panoptix_edge_agent.client import AgentClientError, CameraStatusReport
from panoptix_edge_agent.config import AgentConfig
from panoptix_edge_agent.runner import HeartbeatRunner

SIGNING_KEY = "test-command-signing-key-with-enough-entropy"
VALID_SIGNATURE = "XtEyJPLXf5z6QvlLFhVRqIhVpwbH0R7H_F_1W4dFzxw"


class FakeClient:
    def __init__(self, response: dict[str, object] | None = None, error: AgentClientError | None = None) -> None:
        self.response = {} if response is None else response
        self.error = error
        self.calls: list[tuple[str, tuple[CameraStatusReport, ...]]] = []

    def send_heartbeat(
        self,
        *,
        status: str = "online",
        cameras: tuple[CameraStatusReport, ...] = (),
    ) -> dict[str, Any]:
        self.calls.append((status, cameras))
        if self.error is not None:
            raise self.error
        return self.response


def _config(**overrides: Any) -> AgentConfig:
    values: dict[str, Any] = {
        "api_base_url": "http://api.example.test",
        "gateway_id": "gateway-1",
        "command_signing_key": SIGNING_KEY,
    }
    values.update(overrides)
    return AgentConfig(**values)


def _command(**overrides: object) -> dict[str, object]:
    command: dict[str, object] = {
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
        "signature": VALID_SIGNATURE,
    }
    command.update(overrides)
    return command


def test_run_once_sends_online_heartbeat_with_configured_cameras() -> None:
    config = _config(camera_ids=("camera-1", "camera-2"))
    client = FakeClient(response={"pending_commands": []})
    runner = HeartbeatRunner(config, client=client)

    result = runner.run_once()

    assert result.ok is True
    assert result.response == {"pending_commands": []}
    assert len(client.calls) == 1
    status, cameras = client.calls[0]
    assert status == "online"
    assert [camera.camera_id for camera in cameras] == ["camera-1", "camera-2"]
    assert [camera.status for camera in cameras] == ["online", "online"]


def test_run_once_returns_error_result_when_client_fails() -> None:
    config = _config()
    runner = HeartbeatRunner(config, client=FakeClient(error=AgentClientError("boom")))

    result = runner.run_once()

    assert result.ok is False
    assert result.error == "boom"


def test_run_once_accepts_verified_pending_heartbeat_command() -> None:
    runner = HeartbeatRunner(
        _config(),
        client=FakeClient(response={"pending_commands": [_command()]}),
    )

    result = runner.run_once()

    assert result.ok is True
    assert result.accepted_commands == 1
    assert result.rejected_commands == 0
    assert result.command_errors == ()


def test_run_once_rejects_tampered_pending_heartbeat_command() -> None:
    runner = HeartbeatRunner(
        _config(),
        client=FakeClient(response={"pending_commands": [_command(signature="invalid-signature")]}),
    )

    result = runner.run_once()

    assert result.ok is True
    assert result.accepted_commands == 0
    assert result.rejected_commands == 1
    assert result.command_errors == ("gateway-command-signature-invalid",)


def test_run_once_rejects_pending_heartbeat_command_without_signing_key() -> None:
    runner = HeartbeatRunner(
        _config(command_signing_key=""),
        client=FakeClient(response={"pending_commands": [_command()]}),
    )

    result = runner.run_once()

    assert result.ok is True
    assert result.accepted_commands == 0
    assert result.rejected_commands == 1
    assert result.command_errors == ("gateway-command-signing-key-invalid",)


def test_run_once_rejects_expired_pending_heartbeat_command() -> None:
    runner = HeartbeatRunner(
        _config(),
        client=FakeClient(
            response={
                "pending_commands": [
                    _command(
                        expires_at="2026-05-07T12:00:30Z",
                        signature="AKRZ_FFmAklMBAkUAWwaxFbZNinYpPjX8LFkz3DKEOk",
                    )
                ]
            }
        ),
    )

    result = runner.run_once()

    assert result.ok is True
    assert result.accepted_commands == 0
    assert result.rejected_commands == 1
    assert result.command_errors == ("gateway-command-expired",)


def test_run_once_rejects_wrong_gateway_pending_heartbeat_command() -> None:
    runner = HeartbeatRunner(
        _config(),
        client=FakeClient(response={"pending_commands": [_command(gateway_id="gateway-2")]}),
    )

    result = runner.run_once()

    assert result.ok is True
    assert result.accepted_commands == 0
    assert result.rejected_commands == 1
    assert result.command_errors == ("gateway-command-target-mismatch",)
