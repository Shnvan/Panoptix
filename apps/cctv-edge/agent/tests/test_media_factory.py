from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from panoptix_edge_agent.config import AgentConfig, ConfigError, load_config_from_env
from panoptix_edge_agent.livekit_publisher import LiveKitMediaController
from panoptix_edge_agent.media import StubMediaController
from panoptix_edge_agent.media_factory import MediaFactoryResult, build_media_controller


def _config(**overrides: object) -> AgentConfig:
    values: dict[str, object] = {
        "api_base_url": "http://api.example.test",
        "gateway_id": "gateway-1",
    }
    values.update(overrides)
    return AgentConfig(**values)


class FakeStdout:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.closed = False

    def read(self, size: int) -> bytes:
        if not self.chunks:
            return b""
        return self.chunks.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeProcess:
    def __init__(self, stdout: FakeStdout) -> None:
        self.stdout = stdout
        self.returncode: int | None = None
        self.terminated = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        self.returncode = 0
        return 0

    def kill(self) -> None:
        self.returncode = -9


class RecordingProcessFactory:
    def __init__(self) -> None:
        self.process = FakeProcess(FakeStdout([bytes([1, 0, 0, 255] * 4)]))
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args: Sequence[str]) -> FakeProcess:
        self.calls.append(tuple(args))
        return self.process


class FakePublication:
    sid = "track-sid-1"


class FakeLocalParticipant:
    def __init__(self) -> None:
        self.publish_calls: list[dict[str, object]] = []
        self.unpublish_calls: list[str] = []

    async def publish_track(self, track: object, options: object) -> FakePublication:
        self.publish_calls.append({"track": track, "options": options})
        return FakePublication()

    async def unpublish_track(self, track_sid: str) -> None:
        self.unpublish_calls.append(track_sid)


class FakeRoom:
    def __init__(self) -> None:
        self.local_participant = FakeLocalParticipant()
        self.connect_calls: list[dict[str, object]] = []
        self.disconnect_calls = 0

    async def connect(self, url: str, token: str, options: object) -> None:
        self.connect_calls.append({"url": url, "token": token, "options": options})

    async def disconnect(self) -> None:
        self.disconnect_calls += 1


class FakeVideoSource:
    def __init__(self, width: int, height: int, *, is_screencast: bool = False) -> None:
        self.width = width
        self.height = height
        self.is_screencast = is_screencast
        self.capture_calls: list[dict[str, object]] = []
        self.closed = False

    def capture_frame(self, frame: object, *, timestamp_us: int = 0) -> None:
        self.capture_calls.append({"frame": frame, "timestamp_us": timestamp_us})

    async def aclose(self) -> None:
        self.closed = True


class FakeLocalVideoTrackFactory:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, object]] = []
        self.created_track = object()

    def create_video_track(self, name: str, source: FakeVideoSource) -> object:
        self.create_calls.append({"name": name, "source": source})
        return self.created_track


class FakeRtcModule:
    def __init__(self, room: FakeRoom) -> None:
        self.room = room
        self.room_options_calls: list[dict[str, bool]] = []
        self.video_sources: list[FakeVideoSource] = []
        self.video_frame_calls: list[dict[str, object]] = []
        self.track_publish_options_calls: list[dict[str, object]] = []
        self.LocalVideoTrack = FakeLocalVideoTrackFactory()
        self.TrackSource = type("FakeTrackSource", (), {"SOURCE_CAMERA": "camera-source"})()
        self.VideoBufferType = type("FakeVideoBufferType", (), {"RGBA": "rgba-buffer"})()

    def Room(self) -> FakeRoom:
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
        source = FakeVideoSource(width, height, is_screencast=is_screencast)
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


def test_build_media_controller_stub_mode_returns_stub() -> None:
    config = _config(media_publisher_mode="stub")

    result = build_media_controller(config)

    assert isinstance(result, MediaFactoryResult)
    assert result.mode == "stub"
    assert result.error is None
    assert isinstance(result.controller, StubMediaController)


def test_build_media_controller_defaults_to_stub() -> None:
    config = _config()

    result = build_media_controller(config)

    assert result.mode == "stub"
    assert isinstance(result.controller, StubMediaController)


def test_build_media_controller_livekit_ffmpeg_with_fake_rtc() -> None:
    room = FakeRoom()
    rtc_module = FakeRtcModule(room)
    config = _config(
        media_publisher_mode="livekit-ffmpeg",
        media_source_url="rtsp://127.0.0.1:8554/synthetic-camera-1",
        media_width=640,
        media_height=480,
        media_frame_rate=15,
    )

    result = build_media_controller(
        config,
        rtc_module=rtc_module,
        process_factory=RecordingProcessFactory(),
    )

    assert result.mode == "livekit-ffmpeg"
    assert result.error is None
    assert isinstance(result.controller, LiveKitMediaController)


def test_build_media_controller_livekit_ffmpeg_without_sdk_falls_back_to_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_import(name: str) -> Any:
        raise ImportError(name)

    monkeypatch.setattr("panoptix_edge_agent.media_factory.importlib.import_module", unavailable_import)
    config = _config(media_publisher_mode="livekit-ffmpeg")

    result = build_media_controller(config)

    assert result.mode == "livekit-ffmpeg"
    assert result.error == "livekit-sdk-unavailable"
    assert isinstance(result.controller, StubMediaController)


def test_build_media_controller_invalid_mode_raises() -> None:
    config = _config(media_publisher_mode="invalid")

    with pytest.raises(ConfigError, match="'stub' or 'livekit-ffmpeg'"):
        build_media_controller(config)


def test_build_media_controller_livekit_ffmpeg_uses_config_source_url() -> None:
    room = FakeRoom()
    rtc_module = FakeRtcModule(room)
    config = _config(
        media_publisher_mode="livekit-ffmpeg",
        media_source_url="rtsp://192.168.1.100:554/live",
    )

    result = build_media_controller(
        config,
        rtc_module=rtc_module,
        process_factory=RecordingProcessFactory(),
    )

    assert isinstance(result.controller, LiveKitMediaController)
    assert result.controller.source_url == "rtsp://192.168.1.100:554/live"


def test_build_media_controller_livekit_ffmpeg_uses_config_dimensions() -> None:
    room = FakeRoom()
    rtc_module = FakeRtcModule(room)
    config = _config(
        media_publisher_mode="livekit-ffmpeg",
        media_width=1280,
        media_height=720,
        media_frame_rate=30,
    )

    result = build_media_controller(
        config,
        rtc_module=rtc_module,
        process_factory=RecordingProcessFactory(),
    )

    assert result.mode == "livekit-ffmpeg"
    assert result.error is None


def test_config_rejects_invalid_media_publisher_mode() -> None:
    with pytest.raises(ConfigError, match="PANOPTIX_MEDIA_PUBLISHER_MODE"):
        load_config_from_env({
            "PANOPTIX_API_BASE_URL": "http://api.example.test",
            "PANOPTIX_GATEWAY_ID": "gateway-1",
            "PANOPTIX_MEDIA_PUBLISHER_MODE": "invalid",
        })


def test_config_accepts_stub_media_publisher_mode() -> None:
    config = load_config_from_env({
        "PANOPTIX_API_BASE_URL": "http://api.example.test",
        "PANOPTIX_GATEWAY_ID": "gateway-1",
        "PANOPTIX_MEDIA_PUBLISHER_MODE": "stub",
    })

    assert config.media_publisher_mode == "stub"


def test_config_accepts_livekit_ffmpeg_media_publisher_mode() -> None:
    config = load_config_from_env({
        "PANOPTIX_API_BASE_URL": "http://api.example.test",
        "PANOPTIX_GATEWAY_ID": "gateway-1",
        "PANOPTIX_MEDIA_PUBLISHER_MODE": "livekit-ffmpeg",
    })

    assert config.media_publisher_mode == "livekit-ffmpeg"
    assert config.media_source_url == "rtsp://127.0.0.1:8554/synthetic-camera-1"
    assert config.media_width == 640
    assert config.media_height == 480
    assert config.media_frame_rate == 15
    assert config.media_ffmpeg_binary == "ffmpeg"


def test_config_rejects_invalid_media_source_url_in_livekit_ffmpeg_mode() -> None:
    with pytest.raises(ConfigError, match="PANOPTIX_MEDIA_SOURCE_URL"):
        load_config_from_env({
            "PANOPTIX_API_BASE_URL": "http://api.example.test",
            "PANOPTIX_GATEWAY_ID": "gateway-1",
            "PANOPTIX_MEDIA_PUBLISHER_MODE": "livekit-ffmpeg",
            "PANOPTIX_MEDIA_SOURCE_URL": "https://camera.test/stream",
        })


def test_config_does_not_validate_media_source_url_in_stub_mode() -> None:
    config = load_config_from_env({
        "PANOPTIX_API_BASE_URL": "http://api.example.test",
        "PANOPTIX_GATEWAY_ID": "gateway-1",
        "PANOPTIX_MEDIA_PUBLISHER_MODE": "stub",
        "PANOPTIX_MEDIA_SOURCE_URL": "https://anything.test",
    })

    assert config.media_source_url == "https://anything.test"
