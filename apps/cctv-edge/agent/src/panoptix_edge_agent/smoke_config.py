from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit


class SmokeConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SmokeConfig:
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    rtsp_url: str
    room: str
    camera_id: str
    duration_seconds: int
    width: int
    height: int
    frame_rate: int
    ffmpeg_binary: str


_MIN_API_SECRET_LENGTH = 32
_MIN_DURATION = 3
_MAX_DURATION = 120


def load_smoke_config(
    environ: Mapping[str, str] | None = None,
    *,
    skip_ffmpeg_check: bool = False,
) -> SmokeConfig:
    import os

    env: Mapping[str, str] = os.environ if environ is None else environ

    livekit_url = _required(env, "PANOPTIX_SMOKE_LIVEKIT_URL")
    livekit_api_key = _required(env, "PANOPTIX_SMOKE_LIVEKIT_API_KEY")
    livekit_api_secret = _required(env, "PANOPTIX_SMOKE_LIVEKIT_API_SECRET")
    rtsp_url = env.get("PANOPTIX_SMOKE_RTSP_URL", "rtsp://127.0.0.1:8554/synthetic-camera-1").strip()
    room = env.get("PANOPTIX_SMOKE_ROOM", "smoke-test-room").strip() or "smoke-test-room"
    camera_id = env.get("PANOPTIX_SMOKE_CAMERA_ID", "smoke-test-camera").strip() or "smoke-test-camera"
    duration_seconds = _int_value(env, "PANOPTIX_SMOKE_DURATION_SECONDS", 10)
    width = _int_value(env, "PANOPTIX_SMOKE_WIDTH", 640)
    height = _int_value(env, "PANOPTIX_SMOKE_HEIGHT", 480)
    frame_rate = _int_value(env, "PANOPTIX_SMOKE_FRAME_RATE", 15)
    ffmpeg_binary = env.get("PANOPTIX_SMOKE_FFMPEG_BINARY", "ffmpeg").strip() or "ffmpeg"

    _validate_livekit_url(livekit_url)
    _validate_api_secret(livekit_api_secret)
    _validate_rtsp_url(rtsp_url)
    _validate_duration(duration_seconds)
    _validate_positive_int(width, "PANOPTIX_SMOKE_WIDTH")
    _validate_positive_int(height, "PANOPTIX_SMOKE_HEIGHT")
    _validate_positive_int(frame_rate, "PANOPTIX_SMOKE_FRAME_RATE")
    _validate_ffmpeg_binary(ffmpeg_binary, skip_check=skip_ffmpeg_check)

    return SmokeConfig(
        livekit_url=livekit_url,
        livekit_api_key=livekit_api_key,
        livekit_api_secret=livekit_api_secret,
        rtsp_url=rtsp_url,
        room=room,
        camera_id=camera_id,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        frame_rate=frame_rate,
        ffmpeg_binary=ffmpeg_binary,
    )


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise SmokeConfigError(f"{name} is required")
    if value in {"replace-me", "placeholder", "changeme", "CHANGEME"}:
        raise SmokeConfigError(f"{name} must not be a placeholder value")
    return value


def _int_value(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise SmokeConfigError(f"{name} must be an integer") from exc


def _validate_livekit_url(raw: str) -> None:
    parsed = urlsplit(raw)
    if parsed.scheme not in {"ws", "wss"} or not parsed.netloc:
        raise SmokeConfigError(
            "PANOPTIX_SMOKE_LIVEKIT_URL must be a ws:// or wss:// URL"
        )
    if parsed.username is not None or parsed.password is not None:
        raise SmokeConfigError(
            "PANOPTIX_SMOKE_LIVEKIT_URL must not include credentials"
        )


def _validate_api_secret(raw: str) -> None:
    if len(raw) < _MIN_API_SECRET_LENGTH:
        raise SmokeConfigError(
            f"PANOPTIX_SMOKE_LIVEKIT_API_SECRET must be at least {_MIN_API_SECRET_LENGTH} characters"
        )


def _validate_rtsp_url(raw: str) -> None:
    parsed = urlsplit(raw)
    if parsed.scheme not in {"rtsp", "rtsps"} or not parsed.netloc:
        raise SmokeConfigError(
            "PANOPTIX_SMOKE_RTSP_URL must be an rtsp:// or rtsps:// URL"
        )
    if parsed.username is not None or parsed.password is not None:
        raise SmokeConfigError(
            "PANOPTIX_SMOKE_RTSP_URL must not include credentials"
        )


def _validate_duration(value: int) -> None:
    if value < _MIN_DURATION:
        raise SmokeConfigError(
            f"PANOPTIX_SMOKE_DURATION_SECONDS must be at least {_MIN_DURATION}"
        )
    if value > _MAX_DURATION:
        raise SmokeConfigError(
            f"PANOPTIX_SMOKE_DURATION_SECONDS must be at most {_MAX_DURATION}"
        )


def _validate_positive_int(value: int, name: str) -> None:
    if value < 1:
        raise SmokeConfigError(f"{name} must be at least 1")


def _validate_ffmpeg_binary(raw: str, *, skip_check: bool = False) -> None:
    if not raw:
        raise SmokeConfigError("PANOPTIX_SMOKE_FFMPEG_BINARY is required")
    if raw.startswith("-"):
        raise SmokeConfigError("PANOPTIX_SMOKE_FFMPEG_BINARY must not start with -")
    if skip_check:
        return
    if shutil.which(raw) is None:
        raise SmokeConfigError(
            f"PANOPTIX_SMOKE_FFMPEG_BINARY '{raw}' was not found on PATH"
        )
