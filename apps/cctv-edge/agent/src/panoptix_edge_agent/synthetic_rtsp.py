from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from panoptix_edge_agent.config import AgentConfig


class SyntheticRtspError(ValueError):
    pass


@dataclass(frozen=True)
class SyntheticRtspSource:
    rtsp_url: str
    video_size: str = "1280x720"
    frame_rate: int = 30
    audio_frequency: int = 1000
    ffmpeg_binary: str = "ffmpeg"

    @classmethod
    def from_config(cls, config: AgentConfig) -> SyntheticRtspSource:
        return cls(
            rtsp_url=config.synthetic_rtsp_url,
            video_size=config.synthetic_video_size,
            frame_rate=config.synthetic_frame_rate,
            audio_frequency=config.synthetic_audio_frequency,
        )

    def ffmpeg_args(self) -> list[str]:
        _validate_source(self)
        return [
            self.ffmpeg_binary,
            "-re",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={self.video_size}:rate={self.frame_rate}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={self.audio_frequency}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-c:a",
            "aac",
            "-f",
            "rtsp",
            self.rtsp_url,
        ]


def build_synthetic_rtsp_ffmpeg_args(config: AgentConfig) -> list[str]:
    return SyntheticRtspSource.from_config(config).ffmpeg_args()


def _validate_source(source: SyntheticRtspSource) -> None:
    _validate_rtsp_url(source.rtsp_url)
    _validate_video_size(source.video_size)
    if source.frame_rate < 1:
        raise SyntheticRtspError("frame_rate must be at least 1")
    if source.audio_frequency < 1:
        raise SyntheticRtspError("audio_frequency must be at least 1")
    if not source.ffmpeg_binary:
        raise SyntheticRtspError("ffmpeg_binary is required")


def _validate_rtsp_url(raw: str) -> None:
    parsed = urlsplit(raw)
    if parsed.scheme not in {"rtsp", "rtsps"} or not parsed.netloc:
        raise SyntheticRtspError("rtsp_url must be an rtsp:// or rtsps:// URL")
    if parsed.username is not None or parsed.password is not None:
        raise SyntheticRtspError("rtsp_url must not include credentials")


def _validate_video_size(raw: str) -> None:
    width, separator, height = raw.partition("x")
    if separator != "x":
        raise SyntheticRtspError("video_size must use WIDTHxHEIGHT format")
    try:
        width_value = int(width)
        height_value = int(height)
    except ValueError as exc:
        raise SyntheticRtspError("video_size must use integer WIDTHxHEIGHT values") from exc
    if width_value < 1 or height_value < 1:
        raise SyntheticRtspError("video_size dimensions must be at least 1")
