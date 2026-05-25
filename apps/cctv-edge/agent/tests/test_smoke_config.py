from __future__ import annotations

from unittest.mock import patch

import pytest

from panoptix_edge_agent.smoke_config import SmokeConfig, SmokeConfigError, load_smoke_config


_VALID_ENV = {
    "PANOPTIX_SMOKE_LIVEKIT_URL": "ws://127.0.0.1:7880",
    "PANOPTIX_SMOKE_LIVEKIT_API_KEY": "devkey",
    "PANOPTIX_SMOKE_LIVEKIT_API_SECRET": "secret-with-at-least-thirty-two-bytes",
}


def test_load_smoke_config_accepts_valid_env() -> None:
    config = load_smoke_config(_VALID_ENV, skip_ffmpeg_check=True)

    assert isinstance(config, SmokeConfig)
    assert config.livekit_url == "ws://127.0.0.1:7880"
    assert config.livekit_api_key == "devkey"
    assert config.livekit_api_secret == "secret-with-at-least-thirty-two-bytes"
    assert config.rtsp_url == "rtsp://127.0.0.1:8554/synthetic-camera-1"
    assert config.room == "smoke-test-room"
    assert config.camera_id == "smoke-test-camera"
    assert config.duration_seconds == 10
    assert config.width == 640
    assert config.height == 480
    assert config.frame_rate == 15
    assert config.ffmpeg_binary == "ffmpeg"


def test_load_smoke_config_accepts_custom_values() -> None:
    env = {
        **_VALID_ENV,
        "PANOPTIX_SMOKE_LIVEKIT_URL": "wss://livekit.example.test",
        "PANOPTIX_SMOKE_RTSP_URL": "rtsps://camera.local.test/live",
        "PANOPTIX_SMOKE_ROOM": "custom-room",
        "PANOPTIX_SMOKE_CAMERA_ID": "custom-camera",
        "PANOPTIX_SMOKE_DURATION_SECONDS": "30",
        "PANOPTIX_SMOKE_WIDTH": "1280",
        "PANOPTIX_SMOKE_HEIGHT": "720",
        "PANOPTIX_SMOKE_FRAME_RATE": "30",
        "PANOPTIX_SMOKE_FFMPEG_BINARY": "ffmpeg.exe",
    }

    config = load_smoke_config(env, skip_ffmpeg_check=True)

    assert config.livekit_url == "wss://livekit.example.test"
    assert config.rtsp_url == "rtsps://camera.local.test/live"
    assert config.room == "custom-room"
    assert config.camera_id == "custom-camera"
    assert config.duration_seconds == 30
    assert config.width == 1280
    assert config.height == 720
    assert config.frame_rate == 30
    assert config.ffmpeg_binary == "ffmpeg.exe"


def test_load_smoke_config_rejects_missing_livekit_url() -> None:
    env = {k: v for k, v in _VALID_ENV.items() if k != "PANOPTIX_SMOKE_LIVEKIT_URL"}

    with pytest.raises(SmokeConfigError, match="PANOPTIX_SMOKE_LIVEKIT_URL is required"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_missing_api_key() -> None:
    env = {k: v for k, v in _VALID_ENV.items() if k != "PANOPTIX_SMOKE_LIVEKIT_API_KEY"}

    with pytest.raises(SmokeConfigError, match="PANOPTIX_SMOKE_LIVEKIT_API_KEY is required"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_missing_api_secret() -> None:
    env = {k: v for k, v in _VALID_ENV.items() if k != "PANOPTIX_SMOKE_LIVEKIT_API_SECRET"}

    with pytest.raises(SmokeConfigError, match="PANOPTIX_SMOKE_LIVEKIT_API_SECRET is required"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_placeholder_api_key() -> None:
    env = {**_VALID_ENV, "PANOPTIX_SMOKE_LIVEKIT_API_KEY": "replace-me"}

    with pytest.raises(SmokeConfigError, match="must not be a placeholder"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_short_api_secret() -> None:
    env = {**_VALID_ENV, "PANOPTIX_SMOKE_LIVEKIT_API_SECRET": "too-short"}

    with pytest.raises(SmokeConfigError, match="at least 32 characters"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_invalid_livekit_url_scheme() -> None:
    env = {**_VALID_ENV, "PANOPTIX_SMOKE_LIVEKIT_URL": "https://livekit.example.test"}

    with pytest.raises(SmokeConfigError, match="ws:// or wss://"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_livekit_url_credentials() -> None:
    env = {**_VALID_ENV, "PANOPTIX_SMOKE_LIVEKIT_URL": "ws://user:pass@livekit.example.test"}

    with pytest.raises(SmokeConfigError, match="must not include credentials"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_invalid_rtsp_url_scheme() -> None:
    env = {**_VALID_ENV, "PANOPTIX_SMOKE_RTSP_URL": "https://camera.test/stream"}

    with pytest.raises(SmokeConfigError, match="rtsp:// or rtsps://"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_rtsp_url_credentials() -> None:
    env = {**_VALID_ENV, "PANOPTIX_SMOKE_RTSP_URL": "rtsp://user:pass@camera.test/live"}

    with pytest.raises(SmokeConfigError, match="must not include credentials"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_duration_below_minimum() -> None:
    env = {**_VALID_ENV, "PANOPTIX_SMOKE_DURATION_SECONDS": "1"}

    with pytest.raises(SmokeConfigError, match="at least 3"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_duration_above_maximum() -> None:
    env = {**_VALID_ENV, "PANOPTIX_SMOKE_DURATION_SECONDS": "999"}

    with pytest.raises(SmokeConfigError, match="at most 120"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_non_integer_dimension() -> None:
    env = {**_VALID_ENV, "PANOPTIX_SMOKE_WIDTH": "abc"}

    with pytest.raises(SmokeConfigError, match="must be an integer"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_zero_width() -> None:
    env = {**_VALID_ENV, "PANOPTIX_SMOKE_WIDTH": "0"}

    with pytest.raises(SmokeConfigError, match="at least 1"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_zero_frame_rate() -> None:
    env = {**_VALID_ENV, "PANOPTIX_SMOKE_FRAME_RATE": "0"}

    with pytest.raises(SmokeConfigError, match="at least 1"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_rejects_ffmpeg_not_found() -> None:
    with patch("panoptix_edge_agent.smoke_config.shutil") as mock_shutil:
        mock_shutil.which.return_value = None

        with pytest.raises(SmokeConfigError, match="not found on PATH"):
            load_smoke_config(_VALID_ENV, skip_ffmpeg_check=False)


def test_load_smoke_config_rejects_ffmpeg_binary_starting_with_dash() -> None:
    env = {**_VALID_ENV, "PANOPTIX_SMOKE_FFMPEG_BINARY": "--evil"}

    with pytest.raises(SmokeConfigError, match="must not start with"):
        load_smoke_config(env, skip_ffmpeg_check=True)


def test_load_smoke_config_frozen() -> None:
    config = load_smoke_config(_VALID_ENV, skip_ffmpeg_check=True)

    with pytest.raises(AttributeError):
        config.room = "mutated"  # type: ignore[misc]
