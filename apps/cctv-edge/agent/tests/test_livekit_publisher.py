from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from panoptix_edge_agent.commands import GatewayCommand
from panoptix_edge_agent.executor import CommandExecutor
from panoptix_edge_agent.livekit_publisher import (
    LiveKitMediaController,
    LiveKitPublishRequest,
    LiveKitPublisherResult,
    SdkUnavailableLiveKitPublisherClient,
)

NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)


class FakeLiveKitPublisherClient:
    def __init__(
        self,
        start_result: LiveKitPublisherResult | None = None,
        stop_result: LiveKitPublisherResult | None = None,
    ) -> None:
        self.start_result = LiveKitPublisherResult(ok=True) if start_result is None else start_result
        self.stop_result = LiveKitPublisherResult(ok=True) if stop_result is None else stop_result
        self.start_calls: list[LiveKitPublishRequest] = []
        self.stop_calls: list[dict[str, str]] = []

    async def start_publish(self, request: LiveKitPublishRequest) -> LiveKitPublisherResult:
        self.start_calls.append(request)
        return self.start_result

    async def stop_publish(self, *, camera_id: str, room: str) -> LiveKitPublisherResult:
        self.stop_calls.append({"camera_id": camera_id, "room": room})
        return self.stop_result


def _start_command(**overrides: object) -> GatewayCommand:
    payload: dict[str, object] = {
        "camera_id": "camera-1",
        "room": "camera_ab12cd34",
        "livekit_url": "wss://livekit.example.test",
        "gateway_publish_token": "gateway-token",
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


def test_livekit_media_controller_start_calls_publisher() -> None:
    publisher = FakeLiveKitPublisherClient()
    controller = LiveKitMediaController(
        publisher=publisher,
        source_url="rtsp://127.0.0.1:8554/synthetic-camera-1",
    )

    result = asyncio.run(
        controller.start_publish(
            camera_id="camera-1",
            room="camera_ab12cd34",
            livekit_url="wss://livekit.example.test",
            token="gateway-token",
        )
    )

    assert result.ok is True
    assert len(publisher.start_calls) == 1
    assert publisher.start_calls[0].camera_id == "camera-1"
    assert publisher.start_calls[0].room == "camera_ab12cd34"
    assert publisher.start_calls[0].livekit_url == "wss://livekit.example.test"
    assert publisher.start_calls[0].token == "gateway-token"
    assert publisher.start_calls[0].source_url == "rtsp://127.0.0.1:8554/synthetic-camera-1"


def test_livekit_media_controller_start_is_idempotent_for_same_camera_and_room() -> None:
    publisher = FakeLiveKitPublisherClient()
    controller = LiveKitMediaController(publisher=publisher)

    first = asyncio.run(
        controller.start_publish(
            camera_id="camera-1",
            room="camera_ab12cd34",
            livekit_url="wss://livekit.example.test",
            token="gateway-token",
        )
    )
    second = asyncio.run(
        controller.start_publish(
            camera_id="camera-1",
            room="camera_ab12cd34",
            livekit_url="wss://livekit.example.test",
            token="gateway-token-2",
        )
    )

    assert first.ok is True
    assert second.ok is True
    assert len(publisher.start_calls) == 1


def test_livekit_media_controller_start_rejects_room_mismatch_for_active_camera() -> None:
    publisher = FakeLiveKitPublisherClient()
    controller = LiveKitMediaController(publisher=publisher)
    asyncio.run(
        controller.start_publish(
            camera_id="camera-1",
            room="camera_ab12cd34",
            livekit_url="wss://livekit.example.test",
            token="gateway-token",
        )
    )

    result = asyncio.run(
        controller.start_publish(
            camera_id="camera-1",
            room="camera_other",
            livekit_url="wss://livekit.example.test",
            token="gateway-token",
        )
    )

    assert result.ok is False
    assert result.error == "livekit-publish-room-mismatch"
    assert len(publisher.start_calls) == 1


def test_livekit_media_controller_stop_calls_publisher_and_clears_session() -> None:
    publisher = FakeLiveKitPublisherClient()
    controller = LiveKitMediaController(publisher=publisher)
    asyncio.run(
        controller.start_publish(
            camera_id="camera-1",
            room="camera_ab12cd34",
            livekit_url="wss://livekit.example.test",
            token="gateway-token",
        )
    )

    result = asyncio.run(controller.stop_publish(camera_id="camera-1", room="camera_ab12cd34"))

    assert result.ok is True
    assert publisher.stop_calls == [{"camera_id": "camera-1", "room": "camera_ab12cd34"}]
    assert "camera-1" not in controller.active_sessions


def test_livekit_media_controller_stop_is_idempotent_when_no_session_exists() -> None:
    publisher = FakeLiveKitPublisherClient()
    controller = LiveKitMediaController(publisher=publisher)

    result = asyncio.run(controller.stop_publish(camera_id="camera-1", room="camera_ab12cd34"))

    assert result.ok is True
    assert publisher.stop_calls == []


def test_livekit_media_controller_rejects_invalid_livekit_url() -> None:
    publisher = FakeLiveKitPublisherClient()
    controller = LiveKitMediaController(publisher=publisher)

    result = asyncio.run(
        controller.start_publish(
            camera_id="camera-1",
            room="camera_ab12cd34",
            livekit_url="https://livekit.example.test",
            token="gateway-token",
        )
    )

    assert result.ok is False
    assert result.error == "livekit_url must be a ws:// or wss:// URL"
    assert publisher.start_calls == []


def test_livekit_media_controller_rejects_livekit_url_credentials() -> None:
    publisher = FakeLiveKitPublisherClient()
    controller = LiveKitMediaController(publisher=publisher)

    result = asyncio.run(
        controller.start_publish(
            camera_id="camera-1",
            room="camera_ab12cd34",
            livekit_url="wss://user:pass@livekit.example.test",
            token="gateway-token",
        )
    )

    assert result.ok is False
    assert result.error == "livekit_url must not include credentials"
    assert publisher.start_calls == []


def test_livekit_media_controller_rejects_missing_token() -> None:
    publisher = FakeLiveKitPublisherClient()
    controller = LiveKitMediaController(publisher=publisher)

    result = asyncio.run(
        controller.start_publish(
            camera_id="camera-1",
            room="camera_ab12cd34",
            livekit_url="wss://livekit.example.test",
            token="",
        )
    )

    assert result.ok is False
    assert result.error == "token is required"
    assert publisher.start_calls == []


def test_livekit_media_controller_rejects_invalid_source_url() -> None:
    publisher = FakeLiveKitPublisherClient()
    controller = LiveKitMediaController(
        publisher=publisher,
        source_url="https://camera.example.test/stream",
    )

    result = asyncio.run(
        controller.start_publish(
            camera_id="camera-1",
            room="camera_ab12cd34",
            livekit_url="wss://livekit.example.test",
            token="gateway-token",
        )
    )

    assert result.ok is False
    assert result.error == "source_url must be an rtsp:// or rtsps:// URL"
    assert publisher.start_calls == []


def test_livekit_media_controller_surfaces_start_failure() -> None:
    publisher = FakeLiveKitPublisherClient(
        start_result=LiveKitPublisherResult(ok=False, error="publish-start-failed")
    )
    controller = LiveKitMediaController(publisher=publisher)

    result = asyncio.run(
        controller.start_publish(
            camera_id="camera-1",
            room="camera_ab12cd34",
            livekit_url="wss://livekit.example.test",
            token="gateway-token",
        )
    )

    assert result.ok is False
    assert result.error == "publish-start-failed"
    assert "camera-1" not in controller.active_sessions


def test_livekit_media_controller_surfaces_stop_failure_and_keeps_session() -> None:
    publisher = FakeLiveKitPublisherClient(
        stop_result=LiveKitPublisherResult(ok=False, error="publish-stop-failed")
    )
    controller = LiveKitMediaController(publisher=publisher)
    asyncio.run(
        controller.start_publish(
            camera_id="camera-1",
            room="camera_ab12cd34",
            livekit_url="wss://livekit.example.test",
            token="gateway-token",
        )
    )

    result = asyncio.run(controller.stop_publish(camera_id="camera-1", room="camera_ab12cd34"))

    assert result.ok is False
    assert result.error == "publish-stop-failed"
    assert "camera-1" in controller.active_sessions


def test_sdk_unavailable_client_fails_clearly() -> None:
    controller = LiveKitMediaController(publisher=SdkUnavailableLiveKitPublisherClient())

    result = asyncio.run(
        controller.start_publish(
            camera_id="camera-1",
            room="camera_ab12cd34",
            livekit_url="wss://livekit.example.test",
            token="gateway-token",
        )
    )

    assert result.ok is False
    assert result.error == "livekit-sdk-unavailable"


def test_command_executor_works_with_livekit_media_controller() -> None:
    publisher = FakeLiveKitPublisherClient()
    controller = LiveKitMediaController(publisher=publisher)
    executor = CommandExecutor(controller)

    start = asyncio.run(executor.execute(_start_command()))
    stop = asyncio.run(executor.execute(_stop_command()))

    assert start.accepted is True
    assert stop.accepted is True
    assert len(publisher.start_calls) == 1
    assert publisher.stop_calls == [{"camera_id": "camera-1", "room": "camera_ab12cd34"}]
    assert not executor.publish_state.is_publishing("camera-1")


def test_command_executor_rejects_livekit_controller_start_failure() -> None:
    publisher = FakeLiveKitPublisherClient(
        start_result=LiveKitPublisherResult(ok=False, error="publish-start-failed")
    )
    controller = LiveKitMediaController(publisher=publisher)
    executor = CommandExecutor(controller)

    result = asyncio.run(executor.execute(_start_command()))

    assert result.accepted is False
    assert result.error == "publish-start-failed"
    assert not executor.publish_state.is_publishing("camera-1")
