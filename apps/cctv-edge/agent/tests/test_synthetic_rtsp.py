from __future__ import annotations

import pytest

from panoptix_edge_agent.config import AgentConfig
from panoptix_edge_agent.synthetic_rtsp import (
    SyntheticRtspError,
    SyntheticRtspSource,
    build_synthetic_rtsp_ffmpeg_args,
)


def _config(**overrides: object) -> AgentConfig:
    values: dict[str, object] = {
        "api_base_url": "http://api.example.test",
        "gateway_id": "gateway-1",
    }
    values.update(overrides)
    return AgentConfig(**values)


def test_build_synthetic_rtsp_ffmpeg_args_uses_safe_argument_list() -> None:
    args = build_synthetic_rtsp_ffmpeg_args(_config())

    assert isinstance(args, list)
    assert args[0] == "ffmpeg"
    assert "testsrc=size=1280x720:rate=30" in args
    assert "sine=frequency=1000" in args
    assert "rtsp://127.0.0.1:8554/synthetic-camera-1" in args
    assert "-tune" in args
    assert "zerolatency" in args
    assert "-f" in args
    assert "rtsp" in args


def test_build_synthetic_rtsp_ffmpeg_args_reflects_custom_config() -> None:
    args = build_synthetic_rtsp_ffmpeg_args(
        _config(
            synthetic_rtsp_url="rtsp://127.0.0.1:8554/custom-source",
            synthetic_video_size="640x360",
            synthetic_frame_rate=15,
            synthetic_audio_frequency=440,
        )
    )

    assert "testsrc=size=640x360:rate=15" in args
    assert "sine=frequency=440" in args
    assert args[-1] == "rtsp://127.0.0.1:8554/custom-source"


def test_synthetic_rtsp_source_allows_custom_ffmpeg_binary() -> None:
    args = SyntheticRtspSource(
        rtsp_url="rtsp://127.0.0.1:8554/synthetic-camera-1",
        ffmpeg_binary="ffmpeg.exe",
    ).ffmpeg_args()

    assert args[0] == "ffmpeg.exe"


def test_synthetic_rtsp_source_rejects_invalid_url_scheme() -> None:
    source = SyntheticRtspSource(rtsp_url="http://127.0.0.1:8554/synthetic-camera-1")

    with pytest.raises(SyntheticRtspError, match="rtsp:// or rtsps://"):
        source.ffmpeg_args()


def test_synthetic_rtsp_source_rejects_url_credentials() -> None:
    source = SyntheticRtspSource(rtsp_url="rtsp://user:pass@127.0.0.1:8554/synthetic-camera-1")

    with pytest.raises(SyntheticRtspError, match="must not include credentials"):
        source.ffmpeg_args()


def test_synthetic_rtsp_source_rejects_invalid_video_size() -> None:
    source = SyntheticRtspSource(
        rtsp_url="rtsp://127.0.0.1:8554/synthetic-camera-1",
        video_size="1280/720",
    )

    with pytest.raises(SyntheticRtspError, match="WIDTHxHEIGHT"):
        source.ffmpeg_args()


def test_synthetic_rtsp_source_rejects_invalid_frame_rate() -> None:
    source = SyntheticRtspSource(
        rtsp_url="rtsp://127.0.0.1:8554/synthetic-camera-1",
        frame_rate=0,
    )

    with pytest.raises(SyntheticRtspError, match="frame_rate"):
        source.ffmpeg_args()


def test_synthetic_rtsp_source_rejects_invalid_audio_frequency() -> None:
    source = SyntheticRtspSource(
        rtsp_url="rtsp://127.0.0.1:8554/synthetic-camera-1",
        audio_frequency=0,
    )

    with pytest.raises(SyntheticRtspError, match="audio_frequency"):
        source.ffmpeg_args()
