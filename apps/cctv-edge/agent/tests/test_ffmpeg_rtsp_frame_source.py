from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Sequence

import pytest

from panoptix_edge_agent.ffmpeg_rtsp_frame_source import (
    FfmpegRtspFrameSource,
    FfmpegRtspFrameSourceConfig,
    FfmpegRtspFrameSourceError,
    build_ffmpeg_rtsp_frame_source_args,
)


class FakeStdout:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.read_calls: list[int] = []
        self.closed = False

    def read(self, size: int) -> bytes:
        self.read_calls.append(size)
        if not self.chunks:
            return b""
        return self.chunks.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeProcess:
    def __init__(
        self,
        stdout: FakeStdout | None,
        *,
        returncode: int | None = None,
        wait_error: BaseException | None = None,
    ) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.wait_error = wait_error
        self.terminated = False
        self.killed = False
        self.wait_calls = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.wait_error is not None:
            error = self.wait_error
            self.wait_error = None
            raise error
        self.returncode = 0
        return 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


class RecordingProcessFactory:
    def __init__(self, process: FakeProcess) -> None:
        self.process = process
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args: Sequence[str]) -> FakeProcess:
        self.calls.append(tuple(args))
        return self.process


def _config(**overrides: object) -> FfmpegRtspFrameSourceConfig:
    values: dict[str, object] = {
        "rtsp_url": "rtsp://127.0.0.1:8554/synthetic-camera-1",
        "width": 2,
        "height": 2,
        "frame_rate": 25,
    }
    values.update(overrides)
    return FfmpegRtspFrameSourceConfig(**values)


def _frame_bytes(value: int = 1) -> bytes:
    return bytes([value, 0, 0, 255] * 4)


def test_build_ffmpeg_rtsp_frame_source_args_uses_safe_rawvideo_stdout() -> None:
    args = build_ffmpeg_rtsp_frame_source_args(_config())

    assert isinstance(args, list)
    assert args[0] == "ffmpeg"
    assert "-rtsp_transport" in args
    assert "tcp" in args
    assert "-f" in args
    assert "rawvideo" in args
    assert "-pix_fmt" in args
    assert "rgba" in args
    assert "pipe:1" == args[-1]
    assert "rtsp://127.0.0.1:8554/synthetic-camera-1" in args


def test_build_ffmpeg_rtsp_frame_source_args_reflects_custom_values() -> None:
    args = build_ffmpeg_rtsp_frame_source_args(
        _config(
            rtsp_url="rtsps://camera.local.test/live",
            width=640,
            height=360,
            frame_rate=15,
            ffmpeg_binary="ffmpeg.exe",
        )
    )

    assert args[0] == "ffmpeg.exe"
    assert "rtsps://camera.local.test/live" in args
    assert "scale=640:360" in args


def test_build_ffmpeg_rtsp_frame_source_args_rejects_invalid_url_scheme() -> None:
    with pytest.raises(FfmpegRtspFrameSourceError, match="rtsp:// or rtsps://"):
        build_ffmpeg_rtsp_frame_source_args(_config(rtsp_url="https://camera.local.test/live"))


def test_build_ffmpeg_rtsp_frame_source_args_rejects_url_credentials() -> None:
    with pytest.raises(FfmpegRtspFrameSourceError, match="must not include credentials"):
        build_ffmpeg_rtsp_frame_source_args(
            _config(rtsp_url="rtsp://user:pass@camera.local.test/live")
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("width", 0, "width"),
        ("height", 0, "height"),
        ("frame_rate", 0, "frame_rate"),
        ("ffmpeg_binary", "", "ffmpeg_binary is required"),
        ("ffmpeg_binary", "--ffmpeg", "must not start"),
        ("stop_timeout_seconds", 0, "stop_timeout_seconds"),
    ],
)
def test_build_ffmpeg_rtsp_frame_source_args_rejects_invalid_config(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(FfmpegRtspFrameSourceError, match=message):
        build_ffmpeg_rtsp_frame_source_args(_config(**{field: value}))


def test_ffmpeg_rtsp_frame_source_yields_frames_from_fake_stdout() -> None:
    stdout = FakeStdout([_frame_bytes(1), _frame_bytes(2)])
    process = FakeProcess(stdout)
    factory = RecordingProcessFactory(process)
    source = FfmpegRtspFrameSource(_config(), process_factory=factory)

    async def read_frames() -> tuple[object, object]:
        first = await anext(source)
        second = await anext(source)
        await source.aclose()
        return first, second

    first, second = asyncio.run(read_frames())

    assert len(factory.calls) == 1
    assert stdout.read_calls == [16, 16]
    assert first.data == _frame_bytes(1)
    assert first.width == 2
    assert first.height == 2
    assert first.timestamp_us == 0
    assert second.data == _frame_bytes(2)
    assert second.timestamp_us == 40_000
    assert process.terminated is True
    assert stdout.closed is True


def test_ffmpeg_rtsp_frame_source_stops_on_clean_eof() -> None:
    stdout = FakeStdout([])
    source = FfmpegRtspFrameSource(
        _config(),
        process_factory=RecordingProcessFactory(FakeProcess(stdout)),
    )

    async def read_empty() -> None:
        with pytest.raises(StopAsyncIteration):
            await anext(source)

    asyncio.run(read_empty())

    assert source.closed is True


def test_ffmpeg_rtsp_frame_source_rejects_short_read_without_partial_frame() -> None:
    stdout = FakeStdout([b"short"])
    source = FfmpegRtspFrameSource(
        _config(),
        process_factory=RecordingProcessFactory(FakeProcess(stdout)),
    )

    async def read_short() -> None:
        with pytest.raises(FfmpegRtspFrameSourceError, match="short-read"):
            await anext(source)

    asyncio.run(read_short())

    assert source.frame_index == 0
    assert source.closed is True


def test_ffmpeg_rtsp_frame_source_close_is_idempotent() -> None:
    process = FakeProcess(FakeStdout([_frame_bytes()]))
    source = FfmpegRtspFrameSource(
        _config(),
        process_factory=RecordingProcessFactory(process),
    )

    async def close_twice() -> None:
        await anext(source)
        await source.aclose()
        await source.aclose()

    asyncio.run(close_twice())

    assert process.terminated is True
    assert process.wait_calls == 1


def test_ffmpeg_rtsp_frame_source_close_kills_after_timeout() -> None:
    process = FakeProcess(
        FakeStdout([_frame_bytes()]),
        wait_error=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=0.1),
    )
    source = FfmpegRtspFrameSource(
        _config(stop_timeout_seconds=0.1),
        process_factory=RecordingProcessFactory(process),
    )

    async def close_after_timeout() -> None:
        await anext(source)
        await source.aclose()

    asyncio.run(close_after_timeout())

    assert process.terminated is True
    assert process.killed is True
    assert process.wait_calls == 2


def test_ffmpeg_rtsp_frame_source_rejects_missing_stdout() -> None:
    process = FakeProcess(stdout=None)
    source = FfmpegRtspFrameSource(
        _config(),
        process_factory=RecordingProcessFactory(process),
    )

    async def read_missing_stdout() -> None:
        with pytest.raises(FfmpegRtspFrameSourceError, match="stdout"):
            await anext(source)

    asyncio.run(read_missing_stdout())

    assert process.terminated is True
    assert source.closed is True
