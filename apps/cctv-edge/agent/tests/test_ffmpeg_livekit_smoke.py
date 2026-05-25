from __future__ import annotations

from collections.abc import Sequence

from panoptix_edge_agent.ffmpeg_livekit_smoke import (
    FfmpegVideoTrackSettings,
    build_ffmpeg_livekit_publisher,
    build_ffmpeg_video_track_media_session_factory,
    run_synthetic_ffmpeg_to_livekit_smoke,
)
from panoptix_edge_agent.ffmpeg_rtsp_frame_source import FfmpegRtspFrameSourceConfig
from panoptix_edge_agent.livekit_publisher import (
    LiveKitPublishRequest,
    LiveKitVideoTrackMediaSession,
)
from panoptix_edge_agent.publish_dry_run import SyntheticPublishDryRunConfig


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
        self.killed = False
        self.wait_calls = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        self.returncode = 0
        return 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


class RecordingProcessFactory:
    def __init__(self, process: FakeProcess | None = None) -> None:
        self.process = FakeProcess(FakeStdout([_frame_bytes()])) if process is None else process
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


def _frame_bytes(value: int = 1) -> bytes:
    return bytes([value, 0, 0, 255] * 4)


def _request(**overrides: str) -> LiveKitPublishRequest:
    values = {
        "camera_id": "camera-1",
        "room": "camera_ab12cd34",
        "livekit_url": "wss://livekit.example.test",
        "token": "gateway-token-secret",
        "source_url": "rtsp://127.0.0.1:8554/synthetic-camera-1",
    }
    values.update(overrides)
    return LiveKitPublishRequest(**values)


def test_ffmpeg_video_track_factory_builds_config_from_publish_request() -> None:
    room = FakeRoom()
    rtc_module = FakeRtcModule(room)
    factory = build_ffmpeg_video_track_media_session_factory(
        rtc_module=rtc_module,
        settings=FfmpegVideoTrackSettings(width=2, height=2, frame_rate=25),
        process_factory=RecordingProcessFactory(),
    )

    session = factory(request=_request(), room=room)

    assert isinstance(session, LiveKitVideoTrackMediaSession)
    assert factory.created_configs == [
        FfmpegRtspFrameSourceConfig(
            rtsp_url="rtsp://127.0.0.1:8554/synthetic-camera-1",
            width=2,
            height=2,
            frame_rate=25,
        )
    ]


def test_build_ffmpeg_livekit_publisher_returns_opt_in_sdk_publisher() -> None:
    room = FakeRoom()
    rtc_module = FakeRtcModule(room)

    publisher = build_ffmpeg_livekit_publisher(
        rtc_module=rtc_module,
        settings=FfmpegVideoTrackSettings(width=2, height=2, frame_rate=25),
        process_factory=RecordingProcessFactory(),
    )

    assert publisher.active_sessions == {}


def test_synthetic_ffmpeg_to_livekit_smoke_publishes_fake_stdout_frames() -> None:
    room = FakeRoom()
    rtc_module = FakeRtcModule(room)
    stdout = FakeStdout([_frame_bytes(1), _frame_bytes(2)])
    process = FakeProcess(stdout)
    process_factory = RecordingProcessFactory(process)

    result = run_synthetic_ffmpeg_to_livekit_smoke(
        rtc_module=rtc_module,
        process_factory=process_factory,
        settings=FfmpegVideoTrackSettings(width=2, height=2, frame_rate=25),
    )

    assert result.ok is True
    assert result.dry_run_result.accepted_commands == 2
    assert result.dry_run_result.rejected_commands == 0
    assert result.frame_source_configs[0].rtsp_url == "rtsp://127.0.0.1:8554/synthetic-camera-1"
    assert process_factory.calls
    assert "rtsp://127.0.0.1:8554/synthetic-camera-1" in process_factory.calls[0]
    assert room.connect_calls[0]["url"] == "wss://livekit.example.test"
    assert room.disconnect_calls == 1
    assert room.local_participant.publish_calls
    assert room.local_participant.unpublish_calls == ["track-sid-1"]
    assert rtc_module.video_sources[0].capture_calls[0]["timestamp_us"] == 0
    assert stdout.closed is True
    assert process.terminated is True


def test_synthetic_ffmpeg_to_livekit_smoke_start_failure_is_token_safe() -> None:
    room = FakeRoom()
    rtc_module = FakeRtcModule(room)
    stdout = FakeStdout([b"short"])
    process = FakeProcess(stdout)

    result = run_synthetic_ffmpeg_to_livekit_smoke(
        rtc_module=rtc_module,
        process_factory=RecordingProcessFactory(process),
        settings=FfmpegVideoTrackSettings(width=2, height=2, frame_rate=25),
        config=SyntheticPublishDryRunConfig(gateway_publish_token="gateway-token-secret"),
    )

    assert result.ok is False
    assert result.dry_run_result.rejected_commands == 1
    assert result.dry_run_result.errors == ("livekit-sdk-start-failed",)
    assert "gateway-token-secret" not in repr(result)
    assert room.local_participant.publish_calls == []
    assert process.terminated is True
    assert stdout.closed is True
