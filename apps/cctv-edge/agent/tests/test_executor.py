from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from panoptix_edge_agent.camera_credentials import CameraCredential, CameraCredentialStore
from panoptix_edge_agent.commands import GatewayCommand
from panoptix_edge_agent.executor import CommandExecutor
from panoptix_edge_agent.media import FailingMediaController, StubMediaController
from panoptix_edge_agent.publish_state import PublishState

NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)


class HealthAwareStubMediaController(StubMediaController):
    def __init__(self) -> None:
        super().__init__()
        self.healthy = True

    def is_publishing_healthy(self, *, camera_id: str, room: str) -> bool:
        return self.healthy


def _start_command(**overrides: object) -> GatewayCommand:
    payload: dict[str, object] = {
        "camera_id": "camera-1",
        "room": "camera_ab12cd34",
        "livekit_url": "wss://livekit.example.test",
        "gateway_publish_token": "test-token",
        "token_expires_at": "2026-05-07T12:01:00Z",
    }
    payload.update(overrides)
    return GatewayCommand(
        command_id="11111111-1111-1111-1111-111111111111",
        kind="gateway.command.start_publish",
        gateway_id="gateway-1",
        issued_at=NOW,
        expires_at=datetime(2999, 5, 7, 12, 0, 30, tzinfo=timezone.utc),
        payload=payload,
    )


def _stop_command(**overrides: object) -> GatewayCommand:
    payload: dict[str, object] = {
        "camera_id": "camera-1",
        "room": "camera_ab12cd34",
    }
    payload.update(overrides)
    return GatewayCommand(
        command_id="22222222-2222-2222-2222-222222222222",
        kind="gateway.command.stop_publish",
        gateway_id="gateway-1",
        issued_at=NOW,
        expires_at=datetime(2999, 5, 7, 12, 0, 30, tzinfo=timezone.utc),
        payload=payload,
    )


def _unknown_command() -> GatewayCommand:
    return GatewayCommand(
        command_id="33333333-3333-3333-3333-333333333333",
        kind="gateway.command.unknown_action",
        gateway_id="gateway-1",
        issued_at=NOW,
        expires_at=datetime(2999, 5, 7, 12, 0, 30, tzinfo=timezone.utc),
        payload={},
    )


def test_start_publish_calls_media_controller_and_tracks_state() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(controller)

    result = asyncio.run(executor.execute(_start_command()))

    assert result.accepted is True
    assert result.error is None
    assert len(controller.start_calls) == 1
    assert controller.start_calls[0]["camera_id"] == "camera-1"
    assert controller.start_calls[0]["room"] == "camera_ab12cd34"
    assert controller.start_calls[0]["livekit_url"] == "wss://livekit.example.test"
    assert controller.start_calls[0]["token"] == "test-token"
    assert executor.publish_state.is_publishing("camera-1")


def test_start_publish_already_publishing_is_idempotent() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(controller)

    first = asyncio.run(executor.execute(_start_command()))
    second = asyncio.run(executor.execute(_start_command()))

    assert first.accepted is True
    assert second.accepted is True
    assert len(controller.start_calls) == 1


def test_start_publish_restarts_when_publish_state_is_stale() -> None:
    controller = HealthAwareStubMediaController()
    executor = CommandExecutor(controller)

    first = asyncio.run(executor.execute(_start_command()))
    controller.healthy = False
    second = asyncio.run(executor.execute(_start_command(gateway_publish_token="fresh-token")))

    assert first.accepted is True
    assert second.accepted is True
    assert len(controller.start_calls) == 2
    assert controller.start_calls[1]["token"] == "fresh-token"
    assert executor.publish_state.is_publishing("camera-1")


def test_stop_publish_calls_media_controller_and_clears_state() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(controller)
    asyncio.run(executor.execute(_start_command()))
    assert executor.publish_state.is_publishing("camera-1")

    result = asyncio.run(executor.execute(_stop_command()))

    assert result.accepted is True
    assert result.error is None
    assert len(controller.stop_calls) == 1
    assert controller.stop_calls[0]["camera_id"] == "camera-1"
    assert controller.stop_calls[0]["room"] == "camera_ab12cd34"
    assert not executor.publish_state.is_publishing("camera-1")


def test_stop_publish_not_publishing_is_idempotent() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(controller)

    result = asyncio.run(executor.execute(_stop_command()))

    assert result.accepted is True
    assert len(controller.stop_calls) == 0


def test_start_publish_missing_camera_id_is_rejected() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(controller)

    result = asyncio.run(executor.execute(_start_command(camera_id="")))

    assert result.accepted is False
    assert result.error == "command-payload-incomplete"
    assert len(controller.start_calls) == 0


def test_start_publish_missing_room_is_rejected() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(controller)

    result = asyncio.run(executor.execute(_start_command(room="")))

    assert result.accepted is False
    assert result.error == "command-payload-incomplete"


def test_start_publish_missing_livekit_url_is_rejected() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(controller)

    result = asyncio.run(executor.execute(_start_command(livekit_url="")))

    assert result.accepted is False
    assert result.error == "command-payload-incomplete"


def test_start_publish_missing_token_is_rejected() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(controller)

    result = asyncio.run(executor.execute(_start_command(gateway_publish_token="")))

    assert result.accepted is False
    assert result.error == "command-payload-incomplete"


def test_start_publish_missing_token_expiry_is_rejected() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(controller)

    result = asyncio.run(executor.execute(_start_command(token_expires_at="")))

    assert result.accepted is False
    assert result.error == "command-payload-incomplete"


def test_stop_publish_missing_camera_id_is_rejected() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(controller)

    result = asyncio.run(executor.execute(_stop_command(camera_id="")))

    assert result.accepted is False
    assert result.error == "command-payload-incomplete"


def test_stop_publish_missing_room_is_rejected() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(controller)

    result = asyncio.run(executor.execute(_stop_command(room="")))

    assert result.accepted is False
    assert result.error == "command-payload-incomplete"


def test_unknown_command_kind_is_rejected() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(controller)

    result = asyncio.run(executor.execute(_unknown_command()))

    assert result.accepted is False
    assert result.error == "command-kind-unsupported"


def test_start_publish_media_controller_failure_is_rejected() -> None:
    controller = FailingMediaController(error="mediamtx-start-failed")
    executor = CommandExecutor(controller)

    result = asyncio.run(executor.execute(_start_command()))

    assert result.accepted is False
    assert result.error == "mediamtx-start-failed"
    assert not executor.publish_state.is_publishing("camera-1")


def test_stop_publish_media_controller_failure_is_rejected() -> None:
    controller_ok = StubMediaController()
    state = PublishState()
    executor_setup = CommandExecutor(controller_ok, publish_state=state)
    asyncio.run(executor_setup.execute(_start_command()))
    assert state.is_publishing("camera-1")

    controller_fail = FailingMediaController(error="mediamtx-stop-failed")
    executor = CommandExecutor(controller_fail, publish_state=state)

    result = asyncio.run(executor.execute(_stop_command()))

    assert result.accepted is False
    assert result.error == "mediamtx-stop-failed"
    assert state.is_publishing("camera-1")


def _make_credential_store() -> CameraCredentialStore:
    cred = CameraCredential(
        camera_id="camera-1",
        rtsp_host="192.168.10.50",
        rtsp_port=554,
        rtsp_path="/stream1",
        rtsp_transport="tcp",
        username="cam-admin",
        password="cam-secret",
    )
    return CameraCredentialStore({"camera-1": cred})


def test_start_publish_with_credential_store_resolves_source_url() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(
        controller,
        credential_store=_make_credential_store(),
    )

    result = asyncio.run(executor.execute(_start_command()))

    assert result.accepted is True
    assert len(controller.start_calls) == 1
    assert controller.start_calls[0]["source_url"] == "rtsp://192.168.10.50/stream1"


def test_start_publish_with_credential_store_missing_camera_rejects() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(
        controller,
        credential_store=_make_credential_store(),
    )

    result = asyncio.run(executor.execute(_start_command(camera_id="unknown-camera")))

    assert result.accepted is False
    assert result.error == "camera-credentials-not-found"
    assert len(controller.start_calls) == 0


def test_start_publish_without_credential_store_uses_default() -> None:
    controller = StubMediaController()
    executor = CommandExecutor(controller)

    result = asyncio.run(executor.execute(_start_command()))

    assert result.accepted is True
    assert len(controller.start_calls) == 1
    assert "source_url" not in controller.start_calls[0]
