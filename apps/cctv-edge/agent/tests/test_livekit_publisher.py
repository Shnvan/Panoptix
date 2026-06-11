from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone

from panoptix_edge_agent.commands import GatewayCommand
from panoptix_edge_agent.executor import CommandExecutor
from panoptix_edge_agent.livekit_publisher import (
    LiveKitMediaController,
    LiveKitPublishRequest,
    LiveKitPublisherResult,
    LiveKitSdkPublisherClient,
    LiveKitVideoFrame,
    LiveKitVideoTrackMediaSession,
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
        self.healthy = True

    async def start_publish(self, request: LiveKitPublishRequest) -> LiveKitPublisherResult:
        self.start_calls.append(request)
        return self.start_result

    async def stop_publish(self, *, camera_id: str, room: str) -> LiveKitPublisherResult:
        self.stop_calls.append({"camera_id": camera_id, "room": room})
        return self.stop_result

    def is_publishing_healthy(self, *, camera_id: str, room: str) -> bool:
        return self.healthy


class FakePublication:
    def __init__(self, sid: str = "track-sid-1") -> None:
        self.sid = sid


class FakeLocalParticipant:
    def __init__(self, *, publish_error: Exception | None = None) -> None:
        self.publish_error = publish_error
        self.publish_calls: list[dict[str, object]] = []
        self.unpublish_calls: list[str] = []
        self.publication = FakePublication()

    async def publish_track(self, track: object, options: object) -> FakePublication:
        self.publish_calls.append({"track": track, "options": options})
        if self.publish_error is not None:
            raise self.publish_error
        return self.publication

    async def unpublish_track(self, track_sid: str) -> None:
        self.unpublish_calls.append(track_sid)


class FakeSdkRoom:
    def __init__(
        self,
        *,
        connect_error: Exception | None = None,
        disconnect_error: Exception | None = None,
        local_participant: FakeLocalParticipant | None = None,
    ) -> None:
        self.connect_error = connect_error
        self.disconnect_error = disconnect_error
        self.local_participant = (
            FakeLocalParticipant() if local_participant is None else local_participant
        )
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


class FakeVideoSource:
    def __init__(self, width: int, height: int, *, is_screencast: bool = False) -> None:
        self.width = width
        self.height = height
        self.is_screencast = is_screencast
        self.capture_calls: list[dict[str, object]] = []
        self.closed = False

    def capture_frame(self, frame: object) -> None:
        self.capture_calls.append({"frame": frame})

    async def aclose(self) -> None:
        self.closed = True


class AsyncFailingVideoSource(FakeVideoSource):
    def __init__(
        self,
        width: int,
        height: int,
        *,
        fail_on_capture: int,
        is_screencast: bool = False,
    ) -> None:
        super().__init__(width, height, is_screencast=is_screencast)
        self.fail_on_capture = fail_on_capture

    async def _raise_capture_error(self) -> None:
        raise RuntimeError("Event loop is closed")

    def capture_frame(self, frame: object) -> object:
        self.capture_calls.append({"frame": frame})
        if len(self.capture_calls) == self.fail_on_capture:
            return self._raise_capture_error()
        return None


class FakeLocalVideoTrackFactory:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, object]] = []
        self.created_track = object()

    def create_video_track(self, name: str, source: FakeVideoSource) -> object:
        self.create_calls.append({"name": name, "source": source})
        return self.created_track


class FakeRtcModule:
    def __init__(
        self,
        room: FakeSdkRoom,
        video_source_factory: Callable[..., FakeVideoSource] | None = None,
    ) -> None:
        self.room = room
        self.video_source_factory = video_source_factory
        self.room_options_calls: list[dict[str, bool]] = []
        self.video_sources: list[FakeVideoSource] = []
        self.video_frame_calls: list[dict[str, object]] = []
        self.track_publish_options_calls: list[dict[str, object]] = []
        self.LocalVideoTrack = FakeLocalVideoTrackFactory()
        self.TrackSource = type("FakeTrackSource", (), {"SOURCE_CAMERA": "camera-source"})()
        self.VideoBufferType = type("FakeVideoBufferType", (), {"RGBA": "rgba-buffer"})()

    def Room(self) -> FakeSdkRoom:
        return self.room

    def RoomOptions(self, *, auto_subscribe: bool) -> dict[str, bool]:
        options = {"auto_subscribe": auto_subscribe}
        self.room_options_calls.append(options)
        return options

    def VideoSource(
        self,
        width: int,
        height: int,
        *,
        is_screencast: bool = False,
    ) -> FakeVideoSource:
        if self.video_source_factory is None:
            source = FakeVideoSource(width, height, is_screencast=is_screencast)
        else:
            source = self.video_source_factory(width, height, is_screencast=is_screencast)
        self.video_sources.append(source)
        return source

    def VideoFrame(self, *, width: int, height: int, type: object, data: bytes) -> dict[str, object]:
        frame = {"width": width, "height": height, "type": type, "data": data}
        self.video_frame_calls.append(frame)
        return frame

    def TrackPublishOptions(self, *, source: object) -> dict[str, object]:
        options = {"source": source}
        self.track_publish_options_calls.append(options)
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
        self.healthy = True

    async def start(self) -> None:
        self.start_calls += 1
        if self.start_error is not None:
            raise self.start_error

    async def stop(self) -> None:
        self.stop_calls += 1
        if self.stop_error is not None:
            raise self.stop_error

    def is_healthy(self) -> bool:
        return self.healthy


class FakeVideoFrameSource:
    def __init__(
        self,
        frames: list[LiveKitVideoFrame],
        *,
        error_after_frames: Exception | None = None,
    ) -> None:
        self.frames = frames
        self.error_after_frames = error_after_frames
        self.index = 0
        self.closed = False

    def __aiter__(self) -> FakeVideoFrameSource:
        return self

    async def __anext__(self) -> LiveKitVideoFrame:
        await asyncio.sleep(0)
        if self.index < len(self.frames):
            frame = self.frames[self.index]
            self.index += 1
            return frame
        if self.error_after_frames is not None:
            error = self.error_after_frames
            self.error_after_frames = None
            raise error
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self.closed = True


class RecordingFrameSourceFactory:
    def __init__(self, frame_source: FakeVideoFrameSource) -> None:
        self.frame_source = frame_source
        self.calls: list[LiveKitPublishRequest] = []

    def __call__(self, request: LiveKitPublishRequest) -> FakeVideoFrameSource:
        self.calls.append(request)
        return self.frame_source


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


class QueuedMediaSessionFactory:
    def __init__(self, sessions: list[FakeMediaSession]) -> None:
        self.sessions = sessions
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        *,
        request: LiveKitPublishRequest,
        room: FakeSdkRoom,
    ) -> FakeMediaSession:
        self.calls.append({"request": request, "room": room})
        return self.sessions[len(self.calls) - 1]


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


def _video_frame(*, timestamp_us: int = 0) -> LiveKitVideoFrame:
    return LiveKitVideoFrame(
        data=bytes([255, 0, 0, 255] * 4),
        width=2,
        height=2,
        timestamp_us=timestamp_us,
    )


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


def test_livekit_media_controller_restarts_unhealthy_active_session() -> None:
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
    publisher.healthy = False
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
    assert len(publisher.start_calls) == 2
    assert publisher.stop_calls == [{"camera_id": "camera-1", "room": "camera_ab12cd34"}]
    assert controller.active_sessions["camera-1"].token == "gateway-token-2"


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


def test_livekit_sdk_publisher_restarts_unhealthy_active_session() -> None:
    room = FakeSdkRoom()
    first_session = FakeMediaSession()
    second_session = FakeMediaSession()
    session_factory = QueuedMediaSessionFactory([first_session, second_session])
    client = LiveKitSdkPublisherClient(
        rtc_module=FakeRtcModule(room),
        media_session_factory=session_factory,
    )

    first = asyncio.run(client.start_publish(_publish_request(token="gateway-token-secret")))
    first_session.healthy = False
    second = asyncio.run(client.start_publish(_publish_request(token="gateway-token-secret-2")))

    assert first.ok is True
    assert second.ok is True
    assert first_session.stop_calls == 1
    assert second_session.start_calls == 1
    assert room.disconnect_calls == 1
    assert len(room.connect_calls) == 2
    assert len(session_factory.calls) == 2
    assert client.active_sessions["camera-1"].media_session is second_session
    assert client.active_sessions["camera-1"].request.token == "gateway-token-secret-2"


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


def test_video_track_media_session_publishes_track_and_pumps_frames() -> None:
    room = FakeSdkRoom()
    rtc_module = FakeRtcModule(room)
    frame_source = FakeVideoFrameSource([_video_frame(timestamp_us=100), _video_frame(timestamp_us=200)])
    session = LiveKitVideoTrackMediaSession(
        request=_publish_request(),
        room=room,
        rtc_module=rtc_module,
        frame_source=frame_source,
    )

    async def run_session() -> None:
        await session.start()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await session.stop()

    asyncio.run(run_session())

    assert len(rtc_module.video_sources) == 1
    video_source = rtc_module.video_sources[0]
    assert video_source.width == 2
    assert video_source.height == 2
    assert rtc_module.LocalVideoTrack.create_calls == [
        {"name": "camera-camera-1-video", "source": video_source}
    ]
    assert rtc_module.track_publish_options_calls == [{"source": "camera-source"}]
    assert room.local_participant.publish_calls == [
        {
            "track": rtc_module.LocalVideoTrack.created_track,
            "options": {"source": "camera-source"},
        }
    ]
    assert len(video_source.capture_calls) == 2
    assert room.local_participant.unpublish_calls == ["track-sid-1"]
    assert video_source.closed is True
    assert frame_source.closed is True


def test_video_track_media_session_factory_receives_source_url_from_publish_request() -> None:
    room = FakeSdkRoom()
    rtc_module = FakeRtcModule(room)
    frame_source = FakeVideoFrameSource([_video_frame()])
    frame_source_factory = RecordingFrameSourceFactory(frame_source)
    factory_client = LiveKitSdkPublisherClient(rtc_module=rtc_module)
    client = LiveKitSdkPublisherClient(
        rtc_module=rtc_module,
        media_session_factory=factory_client.build_video_track_media_session_factory(
            frame_source_factory
        ),
    )

    start = asyncio.run(client.start_publish(_publish_request()))
    stop = asyncio.run(client.stop_publish(camera_id="camera-1", room="camera_ab12cd34"))

    assert start.ok is True
    assert stop.ok is True
    assert len(frame_source_factory.calls) == 1
    assert frame_source_factory.calls[0].source_url == "rtsp://127.0.0.1:8554/synthetic-camera-1"
    assert frame_source_factory.calls[0].token == "gateway-token-secret"


def test_video_track_media_session_start_failure_cleans_up_and_does_not_store_session() -> None:
    room = FakeSdkRoom(local_participant=FakeLocalParticipant(publish_error=RuntimeError("publish failed")))
    rtc_module = FakeRtcModule(room)
    frame_source = FakeVideoFrameSource([_video_frame()])
    frame_source_factory = RecordingFrameSourceFactory(frame_source)
    factory_client = LiveKitSdkPublisherClient(rtc_module=rtc_module)
    client = LiveKitSdkPublisherClient(
        rtc_module=rtc_module,
        media_session_factory=factory_client.build_video_track_media_session_factory(
            frame_source_factory
        ),
    )

    result = asyncio.run(client.start_publish(_publish_request()))

    assert result.ok is False
    assert result.error == "livekit-sdk-start-failed"
    assert "gateway-token-secret" not in repr(result)
    assert "camera-1" not in client.active_sessions
    assert rtc_module.video_sources[0].closed is True
    assert frame_source.closed is True


def test_video_track_media_session_frame_pump_failure_is_contained() -> None:
    room = FakeSdkRoom()
    rtc_module = FakeRtcModule(room)
    frame_source = FakeVideoFrameSource(
        [_video_frame()],
        error_after_frames=RuntimeError("gateway-token-secret leaked from frame source"),
    )
    session = LiveKitVideoTrackMediaSession(
        request=_publish_request(),
        room=room,
        rtc_module=rtc_module,
        frame_source=frame_source,
    )

    async def run_session() -> None:
        await session.start()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert session.is_healthy() is False
        await session.stop()

    asyncio.run(run_session())

    assert session.frame_pump_error == "livekit-frame-pump-failed"
    assert "gateway-token-secret" not in repr(session.frame_pump_error)
    assert room.local_participant.unpublish_calls == ["track-sid-1"]
    assert room.disconnect_calls == 1
    assert rtc_module.video_sources[0].closed is True
    assert frame_source.closed is True


def test_video_track_media_session_capture_failure_disconnects_room() -> None:
    room = FakeSdkRoom()
    rtc_module = FakeRtcModule(
        room,
        video_source_factory=lambda width, height, is_screencast=False: AsyncFailingVideoSource(
            width,
            height,
            fail_on_capture=2,
            is_screencast=is_screencast,
        ),
    )
    frame_source = FakeVideoFrameSource(
        [_video_frame(timestamp_us=100), _video_frame(timestamp_us=200)]
    )
    session = LiveKitVideoTrackMediaSession(
        request=_publish_request(),
        room=room,
        rtc_module=rtc_module,
        frame_source=frame_source,
    )

    async def run_session() -> None:
        await session.start()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert session.is_healthy() is False
        await session.stop()

    asyncio.run(run_session())

    assert session.frame_pump_error == "livekit-frame-pump-failed"
    assert room.local_participant.unpublish_calls == ["track-sid-1"]
    assert room.disconnect_calls == 1
    assert rtc_module.video_sources[0].closed is True
    assert frame_source.closed is True


def test_video_track_media_session_source_end_disconnects_room() -> None:
    room = FakeSdkRoom()
    rtc_module = FakeRtcModule(room)
    frame_source = FakeVideoFrameSource([_video_frame()])
    session = LiveKitVideoTrackMediaSession(
        request=_publish_request(),
        room=room,
        rtc_module=rtc_module,
        frame_source=frame_source,
    )

    async def run_session() -> None:
        await session.start()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert session.is_healthy() is False
        await session.stop()

    asyncio.run(run_session())

    assert session.frame_pump_error == "livekit-frame-source-ended"
    assert room.local_participant.unpublish_calls == ["track-sid-1"]
    assert room.disconnect_calls == 1
    assert rtc_module.video_sources[0].closed is True
    assert frame_source.closed is True


def test_video_track_media_session_rejects_invalid_frame_before_publish() -> None:
    room = FakeSdkRoom()
    rtc_module = FakeRtcModule(room)
    frame_source = FakeVideoFrameSource(
        [
            LiveKitVideoFrame(
                data=b"too-short",
                width=2,
                height=2,
                timestamp_us=0,
            )
        ]
    )
    factory_client = LiveKitSdkPublisherClient(rtc_module=rtc_module)
    client = LiveKitSdkPublisherClient(
        rtc_module=rtc_module,
        media_session_factory=factory_client.build_video_track_media_session_factory(
            RecordingFrameSourceFactory(frame_source)
        ),
    )

    result = asyncio.run(client.start_publish(_publish_request()))

    assert result.ok is False
    assert result.error == "livekit-sdk-start-failed"
    assert room.local_participant.publish_calls == []
    assert frame_source.closed is True
    assert "camera-1" not in client.active_sessions


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


class HangingVideoFrameSource:
    def __init__(self, start_frame: LiveKitVideoFrame) -> None:
        self.start_frame = start_frame
        self.closed = False

    def __aiter__(self) -> HangingVideoFrameSource:
        return self

    async def __anext__(self) -> LiveKitVideoFrame:
        if self.start_frame is not None:
            frame = self.start_frame
            self.start_frame = None
            return frame
        await asyncio.sleep(5.0)
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self.closed = True


def test_video_track_media_session_frame_stall_timeout() -> None:
    room = FakeSdkRoom()
    rtc_module = FakeRtcModule(room)
    frame = _video_frame()
    frame_source = HangingVideoFrameSource(frame)
    session = LiveKitVideoTrackMediaSession(
        request=_publish_request(),
        room=room,
        rtc_module=rtc_module,
        frame_source=frame_source,
        frame_stall_timeout=0.1,
    )

    async def run_session() -> None:
        await session.start()
        await asyncio.sleep(0.2)
        assert session.is_healthy() is False
        assert session.frame_pump_error == "livekit-frame-stall-timeout"
        await session.stop()

    asyncio.run(run_session())
    assert room.local_participant.unpublish_calls == ["track-sid-1"]
    assert room.disconnect_calls == 1
    assert rtc_module.video_sources[0].closed is True
    assert frame_source.closed is True


def test_video_track_media_session_continuous_frames_remains_healthy() -> None:
    room = FakeSdkRoom()
    rtc_module = FakeRtcModule(room)
    frame_source = HangingVideoFrameSource(_video_frame())
    session = LiveKitVideoTrackMediaSession(
        request=_publish_request(),
        room=room,
        rtc_module=rtc_module,
        frame_source=frame_source,
        frame_stall_timeout=1.0,
    )

    async def run_session() -> None:
        await session.start()
        await asyncio.sleep(0.1)
        assert session.is_healthy() is True
        await session.stop()

    asyncio.run(run_session())
    assert session.frame_pump_error is None


def test_publisher_errors_do_not_leak_secrets() -> None:
    # Ensure credentials and tokens do not leak in errors
    req = _publish_request(
        rtsp_username="secret_user",
        rtsp_password="secret_password",
        token="secret_token",
    )
    rep = repr(req)
    assert "secret_user" not in rep
    assert "secret_password" not in rep
    assert "secret_token" not in rep

