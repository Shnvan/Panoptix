from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, cast
from urllib.parse import quote, urlsplit

from panoptix_edge_agent.livekit_publisher import LiveKitVideoFrame


class FfmpegRtspFrameSourceError(ValueError):
    pass


class FfmpegStdout(Protocol):
    def read(self, size: int) -> bytes: ...


class FfmpegFrameProcess(Protocol):
    stdout: FfmpegStdout | None

    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def kill(self) -> None: ...


FfmpegProcessFactory = Callable[[Sequence[str]], FfmpegFrameProcess]


@dataclass(frozen=True)
class FfmpegRtspFrameSourceConfig:
    rtsp_url: str
    width: int
    height: int
    frame_rate: int
    ffmpeg_binary: str = "ffmpeg"
    stop_timeout_seconds: float = 5.0
    rtsp_username: str | None = None
    rtsp_password: str | None = None
    rtsp_transport: str = "tcp"

    def __repr__(self) -> str:
        cred = ""
        if self.rtsp_username is not None:
            cred = ", rtsp_username='***', rtsp_password='***'"
        return (
            f"FfmpegRtspFrameSourceConfig(rtsp_url={self.rtsp_url!r}, "
            f"width={self.width}, height={self.height}, "
            f"frame_rate={self.frame_rate}, "
            f"ffmpeg_binary={self.ffmpeg_binary!r}, "
            f"stop_timeout_seconds={self.stop_timeout_seconds}, "
            f"rtsp_transport={self.rtsp_transport!r}{cred})"
        )

    @property
    def frame_size_bytes(self) -> int:
        return self.width * self.height * 4

    @property
    def frame_interval_us(self) -> int:
        return 1_000_000 // self.frame_rate

    def args(self) -> list[str]:
        _validate_config(self)
        input_url = self.rtsp_url
        if self.rtsp_username is not None and self.rtsp_password is not None:
            parsed = urlsplit(self.rtsp_url)
            user = quote(self.rtsp_username, safe="")
            pwd = quote(self.rtsp_password, safe="")
            input_url = parsed._replace(netloc=f"{user}:{pwd}@{parsed.hostname or ''}" + (f":{parsed.port}" if parsed.port else "")).geturl()
        return [
            self.ffmpeg_binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-rtsp_transport",
            self.rtsp_transport,
            "-i",
            input_url,
            "-an",
            "-vf",
            f"scale={self.width}:{self.height}",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "pipe:1",
        ]


class FfmpegRtspFrameSource:
    def __init__(
        self,
        config: FfmpegRtspFrameSourceConfig,
        process_factory: FfmpegProcessFactory | None = None,
    ) -> None:
        self.config = config
        self.process_factory = _default_process_factory if process_factory is None else process_factory
        self.process: FfmpegFrameProcess | None = None
        self.frame_index = 0
        self.closed = False

    def __aiter__(self) -> FfmpegRtspFrameSource:
        return self

    async def __anext__(self) -> LiveKitVideoFrame:
        if self.closed:
            raise StopAsyncIteration
        try:
            process = self._ensure_process()
        except FfmpegRtspFrameSourceError:
            await self.aclose()
            raise
        stdout = process.stdout
        if stdout is None:
            await self.aclose()
            raise FfmpegRtspFrameSourceError("ffmpeg-stdout-unavailable")

        data = await asyncio.to_thread(stdout.read, self.config.frame_size_bytes)
        if len(data) == self.config.frame_size_bytes:
            frame = LiveKitVideoFrame(
                data=data,
                width=self.config.width,
                height=self.config.height,
                timestamp_us=self.frame_index * self.config.frame_interval_us,
            )
            self.frame_index += 1
            return frame

        await self.aclose()
        if not data:
            raise StopAsyncIteration
        raise FfmpegRtspFrameSourceError("ffmpeg-frame-short-read")

    async def aclose(self) -> None:
        if self.closed:
            return
        self.closed = True
        process = self.process
        self.process = None
        if process is None:
            return

        stdout = process.stdout
        close = getattr(stdout, "close", None)
        if close is not None:
            close()

        if process.poll() is not None:
            return
        try:
            process.terminate()
            await asyncio.to_thread(process.wait, self.config.stop_timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            await asyncio.to_thread(process.wait, self.config.stop_timeout_seconds)

    def _ensure_process(self) -> FfmpegFrameProcess:
        if self.process is not None:
            return self.process
        try:
            process = self.process_factory(self.config.args())
        except (FfmpegRtspFrameSourceError, OSError) as exc:
            raise FfmpegRtspFrameSourceError(str(exc)) from exc
        self.process = process
        if process.stdout is None:
            raise FfmpegRtspFrameSourceError("ffmpeg-stdout-unavailable")
        return process


def build_ffmpeg_rtsp_frame_source_args(config: FfmpegRtspFrameSourceConfig) -> list[str]:
    return config.args()


def _default_process_factory(args: Sequence[str]) -> FfmpegFrameProcess:
    return cast(
        FfmpegFrameProcess,
        subprocess.Popen(
            list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ),
    )


def _validate_config(config: FfmpegRtspFrameSourceConfig) -> None:
    _validate_binary(config.ffmpeg_binary)
    _validate_rtsp_url(config.rtsp_url)
    if config.width < 1:
        raise FfmpegRtspFrameSourceError("width must be at least 1")
    if config.height < 1:
        raise FfmpegRtspFrameSourceError("height must be at least 1")
    if config.frame_rate < 1:
        raise FfmpegRtspFrameSourceError("frame_rate must be at least 1")
    if config.stop_timeout_seconds <= 0:
        raise FfmpegRtspFrameSourceError("stop_timeout_seconds must be positive")


def _validate_binary(raw: str) -> None:
    value = raw.strip()
    if not value:
        raise FfmpegRtspFrameSourceError("ffmpeg_binary is required")
    if value.startswith("-"):
        raise FfmpegRtspFrameSourceError("ffmpeg_binary must not start with -")
    if any(character in value for character in {"\x00", "\n", "\r"}):
        raise FfmpegRtspFrameSourceError("ffmpeg_binary contains an invalid character")


def _validate_rtsp_url(raw: str) -> None:
    parsed = urlsplit(raw)
    if parsed.scheme not in {"rtsp", "rtsps"} or not parsed.netloc:
        raise FfmpegRtspFrameSourceError("rtsp_url must be an rtsp:// or rtsps:// URL")
    if parsed.username is not None or parsed.password is not None:
        raise FfmpegRtspFrameSourceError("rtsp_url must not include credentials")
