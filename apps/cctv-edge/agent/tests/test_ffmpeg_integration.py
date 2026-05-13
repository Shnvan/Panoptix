from __future__ import annotations

import asyncio
import shutil
import subprocess

import pytest

from panoptix_edge_agent.ffmpeg_rtsp_frame_source import FfmpegRtspFrameSourceConfig

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="ffmpeg not installed"
)

_WIDTH = 320
_HEIGHT = 240
_RATE = 5
_FRAME_SIZE = _WIDTH * _HEIGHT * 4  # 307200 bytes for RGBA


def _testsrc2_args() -> list[str]:
    """Build FFmpeg args that generate synthetic RGBA frames from testsrc2."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={_WIDTH}x{_HEIGHT}:rate={_RATE}",
        "-an",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgba",
        "pipe:1",
    ]


def test_ffmpeg_generates_rgba_frames() -> None:
    """FFmpeg with testsrc2 source produces correctly-sized raw RGBA frames."""

    async def run() -> bytes:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *_testsrc2_args(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            ),
            timeout=10.0,
        )
        try:
            assert proc.stdout is not None
            frame_data = await asyncio.wait_for(
                proc.stdout.readexactly(_FRAME_SIZE),
                timeout=10.0,
            )
            return frame_data
        finally:
            proc.kill()
            await asyncio.wait_for(proc.wait(), timeout=10.0)

    frame = asyncio.run(run())

    assert len(frame) == _FRAME_SIZE, (
        f"Expected {_FRAME_SIZE} bytes for one {_WIDTH}x{_HEIGHT} RGBA frame, got {len(frame)}"
    )
    assert frame != bytes(_FRAME_SIZE), "Frame data should not be all-zero (testsrc2 is colourful)"


def test_ffmpeg_process_cleanup() -> None:
    """FFmpeg subprocess terminates cleanly after being signalled."""

    async def run() -> int:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *_testsrc2_args(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            ),
            timeout=10.0,
        )
        assert proc.stdout is not None

        # Read one frame so the process is actively producing output.
        await asyncio.wait_for(proc.stdout.readexactly(_FRAME_SIZE), timeout=10.0)

        proc.terminate()
        returncode = await asyncio.wait_for(proc.wait(), timeout=10.0)
        return returncode

    returncode = asyncio.run(run())

    # On Unix terminate() sends SIGTERM → negative return code.
    # On Windows it's equivalent to kill() and returns a non-zero code.
    # Either way the process must have exited (returncode is not None).
    assert returncode is not None, "Process should have exited after terminate()"


def test_ffmpeg_build_args_produce_valid_command() -> None:
    """Args built by FfmpegRtspFrameSourceConfig have the correct structure and the ffmpeg binary is usable."""
    config = FfmpegRtspFrameSourceConfig(
        rtsp_url="rtsp://192.0.2.1:8554/cam",
        width=_WIDTH,
        height=_HEIGHT,
        frame_rate=_RATE,
    )
    args = config.args()

    # Structural checks — the builder must produce a well-formed command.
    assert args[0] == "ffmpeg", "First arg must be the ffmpeg binary name"
    assert "-rtsp_transport" in args
    rtsp_transport_idx = args.index("-rtsp_transport")
    assert args[rtsp_transport_idx + 1] == "tcp"
    assert "-i" in args
    input_idx = args.index("-i")
    assert args[input_idx + 1] == "rtsp://192.0.2.1:8554/cam"
    assert "-f" in args
    assert "rawvideo" in args
    assert "-pix_fmt" in args
    assert "rgba" in args
    assert f"scale={_WIDTH}:{_HEIGHT}" in args
    assert args[-1] == "pipe:1"

    # Confirm the ffmpeg binary is actually executable by asking for its help text.
    result = subprocess.run(
        ["ffmpeg", "-h"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10.0,
    )
    assert result.returncode == 0, "ffmpeg -h must exit 0, confirming the binary is usable"
