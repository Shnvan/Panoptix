from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from panoptix_edge_agent.commands import GatewayCommand
from panoptix_edge_agent.executor import CommandExecutor
from panoptix_edge_agent.livekit_publisher import (
    LiveKitMediaController,
    LiveKitPublishRequest,
    LiveKitPublisherResult,
    LiveKitSdkPublisherClient,
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


class FakeSdkRoom:
    def __init__(
        self,
        *,
        connect_error: Exception | None = None,
        disconnect_error: Exception | None = None,
    ) -> None:
        self.connect_error = connect_error
        self.disconnect_error = disconnect_error
        self.connect_calls: list[dict[str, object]] = []
        self.disconnect_calls = 0

    async def connect(self, url: str, token: str, options: object) -> None:
        self.connect_calls.append({"url": url, "token": token, "options": options})
        if self.connect_error is not None:
            raise self.connect_error

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        if self.disconnect_error is not None:
            raise self.disconnect_error


class FakeRtcModule:
    def __init__(self, room: FakeSdkRoom) -> None:
        self.room = room
        self.room_options_calls: list[dict[str, bool]] = []

    def Room(self) -> FakeSdkRoom:
        return self.room

    def RoomOptions(self, *, auto_subscribe: bool) -> dict[str, bool]:
        options = {"auto_subscribe": auto_subscribe}
        self.room_options_calls.append(options)
        return options


class FakeMediaSession:
    def __init__(
        self,
        *,
        start_error: Exception | None = None,
        stop_error: Exception | None = None,
    ) -> None:
        self.start_error = start_error
        self.stop_error = stop_error
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        self.start_calls += 1
        if self.start_error is not None:
            raise self.start_error

    async def stop(self) -> None:
        self.stop_calls += 1
        if self.stop_error is not None:
            raise self.stop_error


class RecordingMediaSessionFactory:
    def __init__(self, session: FakeMediaSession | None = None) -> None:
        self.session = FakeMediaSession() if session is None else session
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        *,
        request: LiveKitPublishRequest,
        room: FakeSdkRoom,
    ) -> FakeMediaSession:
        self.calls.append({"request": request, "room": room})
        return self.session


def _publish_request(**overrides: str) -> LiveKitPublishRequest:
    values = {
        "camera_id": "camera-1",
        "room": "camera_ab12cd34",
        "livekit_url": "wss://livekit.example.test",
        "token": "gateway-token-secret",
        "source_url": "rtsp://127.0.0.1:8554/synthetic-camera-1",
    }
    values.update(overrides)
    return LiveKitPublishRequest(**values)


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


def test_livekit_sdk_publisher_missing_sdk_fails_clearly() -> None:
    def missing_sdk() -> FakeRtcModule:
        raise ModuleNotFoundError("No module named 'livekit'")

    client = LiveKitSdkPublisherClient(rtc_module_resolver=missing_sdk)

    result = asyncio.run(client.start_publish(_publish_request()))

    assert result.ok is False
    assert result.error == "livekit-sdk-unavailable"
    assert "gateway-token-secret" not in repr(result)


def test_livekit_sdk_publisher_start_connects_room_and_starts_media_session() -> None:
    room = FakeSdkRoom()
    rtc_module = FakeRtcModule(room)
    session_factory = RecordingMediaSessionFactory()
    client = LiveKitSdkPublisherClient(
        rtc_module=rtc_module,
        media_session_factory=session_factory,
    )

    result = asyncio.run(client.start_publish(_publish_request()))

    assert result.ok is True
    assert room.connect_calls == [
        {
            "url": "wss://livekit.example.test",
            "token": "gateway-token-secret",
            "options": {"auto_subscribe": False},
        }
    ]
    assert rtc_module.room_options_calls == [{"auto_subscribe": False}]
    assert len(session_factory.calls) == 1
    assert session_factory.calls[0]["room"] is room
    request = session_factory.calls[0]["request"]
    assert isinstance(request, LiveKitPublishRequest)
    assert request.camera_id == "camera-1"
    assert request.room == "camera_ab12cd34"
    assert request.source_url == "rtsp://127.0.0.1:8554/synthetic-camera-1"
    assert session_factory.session.start_calls == 1
    assert "camera-1" in client.active_sessions


def test_livekit_sdk_publisher_stop_disconnects_room_and_stops_media_session() -> None:
    room = FakeSdkRoom()
    session_factory = RecordingMediaSessionFactory()
    client = LiveKitSdkPublisherClient(
        rtc_module=FakeRtcModule(room),
        media_session_factory=session_factory,
    )
    asyncio.run(client.start_publish(_publish_request()))

    result = asyncio.run(client.stop_publish(camera_id="camera-1", room="camera_ab12cd34"))

    assert result.ok is True
    assert session_factory.session.stop_calls == 1
    assert room.disconnect_calls == 1
    assert "camera-1" not in client.active_sessions


def test_livekit_sdk_publisher_start_failure_does_not_store_session() -> None:
    room = FakeSdkRoom(connect_error=RuntimeError("gateway-token-secret leaked from sdk"))
    session_factory = RecordingMediaSessionFactory()
    client = LiveKitSdkPublisherClient(
        rtc_module=FakeRtcModule(room),
        media_session_factory=session_factory,
    )

    result = asyncio.run(client.start_publish(_publish_request()))

    assert result.ok is False
    assert result.error == "livekit-sdk-start-failed"
    assert "gateway-token-secret" not in repr(result)
    assert "camera-1" not in client.active_sessions
    assert room.disconnect_calls == 1
    assert session_factory.calls == []


def test_livekit_sdk_publisher_media_session_start_failure_cleans_up_room() -> None:
    room = FakeSdkRoom()
    session = FakeMediaSession(start_error=RuntimeError("media start failed"))
    session_factory = RecordingMediaSessionFactory(session)
    client = LiveKitSdkPublisherClient(
        rtc_module=FakeRtcModule(room),
        media_session_factory=session_factory,
    )

    result = asyncio.run(client.start_publish(_publish_request()))

    assert result.ok is False
    assert result.error == "livekit-sdk-start-failed"
    assert session.start_calls == 1
    assert session.stop_calls == 1
    assert room.disconnect_calls == 1
    assert "camera-1" not in client.active_sessions


def test_livekit_sdk_publisher_stop_failure_keeps_session() -> None:
    room = FakeSdkRoom(disconnect_error=RuntimeError("gateway-token-secret leaked from sdk"))
    session_factory = RecordingMediaSessionFactory()
    client = LiveKitSdkPublisherClient(
        rtc_module=FakeRtcModule(room),
        media_session_factory=session_factory,
    )
    asyncio.run(client.start_publish(_publish_request()))

    result = asyncio.run(client.stop_publish(camera_id="camera-1", room="camera_ab12cd34"))

    assert result.ok is False
    assert result.error == "livekit-sdk-stop-failed"
    assert "gateway-token-secret" not in repr(result)
    assert "camera-1" in client.active_sessions
    assert session_factory.session.stop_calls == 1
    assert room.disconnect_calls == 1


def test_livekit_sdk_publisher_stop_unknown_session_is_idempotent() -> None:
    client = LiveKitSdkPublisherClient(rtc_module=FakeRtcModule(FakeSdkRoom()))

    result = asyncio.run(client.stop_publish(camera_id="camera-1", room="camera_ab12cd34"))

    assert result.ok is True


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
