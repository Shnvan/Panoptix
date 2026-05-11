from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from panoptix_edge_agent import __version__


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AgentConfig:
    api_base_url: str
    gateway_id: str
    heartbeat_interval_seconds: int = 10
    agent_version: str = __version__
    request_timeout_seconds: float = 5.0
    camera_ids: tuple[str, ...] = ()
    dev_identity_enabled: bool = False
    command_signing_key: str = ""
    control_ws_path: str = "/api/v1/gateway-control/ws"
    control_reconnect_attempts: int = 3
    control_reconnect_backoff_seconds: float = 1.0
    synthetic_rtsp_url: str = "rtsp://127.0.0.1:8554/synthetic-camera-1"
    synthetic_video_size: str = "1280x720"
    synthetic_frame_rate: int = 30
    synthetic_audio_frequency: int = 1000
    media_publisher_mode: str = "stub"
    media_source_url: str = "rtsp://127.0.0.1:8554/synthetic-camera-1"
    media_width: int = 640
    media_height: int = 480
    media_frame_rate: int = 15
    media_ffmpeg_binary: str = "ffmpeg"

    @property
    def normalized_api_base_url(self) -> str:
        return self.api_base_url.rstrip("/")


def load_config_from_env(environ: Mapping[str, str] | None = None) -> AgentConfig:
    env = os.environ if environ is None else environ
    api_base_url = _required(env, "PANOPTIX_API_BASE_URL")
    gateway_id = _required(env, "PANOPTIX_GATEWAY_ID")
    heartbeat_interval_seconds = _int_value(env, "PANOPTIX_HEARTBEAT_INTERVAL_SECONDS", 10)
    request_timeout_seconds = _float_value(env, "PANOPTIX_REQUEST_TIMEOUT_SECONDS", 5.0)
    agent_version = env.get("PANOPTIX_AGENT_VERSION", __version__).strip() or __version__
    camera_ids = _csv_value(env.get("PANOPTIX_CAMERA_IDS", ""))
    dev_identity_enabled = _bool_value(env.get("PANOPTIX_DEV_GATEWAY_IDENTITY", "false"))
    command_signing_key = env.get("PANOPTIX_GATEWAY_COMMAND_SIGNING_KEY", "").strip()
    control_ws_path = env.get("PANOPTIX_GATEWAY_CONTROL_WS_PATH", "/api/v1/gateway-control/ws").strip()
    control_reconnect_attempts = _int_value(env, "PANOPTIX_GATEWAY_CONTROL_RECONNECT_ATTEMPTS", 3)
    control_reconnect_backoff_seconds = _float_value(
        env,
        "PANOPTIX_GATEWAY_CONTROL_RECONNECT_BACKOFF_SECONDS",
        1.0,
    )
    synthetic_rtsp_url = env.get(
        "PANOPTIX_SYNTHETIC_RTSP_URL",
        "rtsp://127.0.0.1:8554/synthetic-camera-1",
    ).strip()
    synthetic_video_size = env.get("PANOPTIX_SYNTHETIC_VIDEO_SIZE", "1280x720").strip()
    synthetic_frame_rate = _int_value(env, "PANOPTIX_SYNTHETIC_FRAME_RATE", 30)
    synthetic_audio_frequency = _int_value(env, "PANOPTIX_SYNTHETIC_AUDIO_FREQUENCY", 1000)
    media_publisher_mode = env.get("PANOPTIX_MEDIA_PUBLISHER_MODE", "stub").strip().lower()
    media_source_url = env.get(
        "PANOPTIX_MEDIA_SOURCE_URL",
        "rtsp://127.0.0.1:8554/synthetic-camera-1",
    ).strip()
    media_width = _int_value(env, "PANOPTIX_MEDIA_WIDTH", 640)
    media_height = _int_value(env, "PANOPTIX_MEDIA_HEIGHT", 480)
    media_frame_rate = _int_value(env, "PANOPTIX_MEDIA_FRAME_RATE", 15)
    media_ffmpeg_binary = env.get("PANOPTIX_MEDIA_FFMPEG_BINARY", "ffmpeg").strip() or "ffmpeg"

    if heartbeat_interval_seconds < 5:
        raise ConfigError("PANOPTIX_HEARTBEAT_INTERVAL_SECONDS must be at least 5")
    if request_timeout_seconds <= 0:
        raise ConfigError("PANOPTIX_REQUEST_TIMEOUT_SECONDS must be greater than 0")
    if not control_ws_path.startswith("/"):
        raise ConfigError("PANOPTIX_GATEWAY_CONTROL_WS_PATH must start with /")
    if control_reconnect_attempts < 1:
        raise ConfigError("PANOPTIX_GATEWAY_CONTROL_RECONNECT_ATTEMPTS must be at least 1")
    if control_reconnect_backoff_seconds < 0:
        raise ConfigError(
            "PANOPTIX_GATEWAY_CONTROL_RECONNECT_BACKOFF_SECONDS must be greater than or equal to 0"
        )
    _validate_rtsp_url(synthetic_rtsp_url, "PANOPTIX_SYNTHETIC_RTSP_URL")
    _validate_video_size(synthetic_video_size, "PANOPTIX_SYNTHETIC_VIDEO_SIZE")
    if synthetic_frame_rate < 1:
        raise ConfigError("PANOPTIX_SYNTHETIC_FRAME_RATE must be at least 1")
    if synthetic_audio_frequency < 1:
        raise ConfigError("PANOPTIX_SYNTHETIC_AUDIO_FREQUENCY must be at least 1")
    if media_publisher_mode not in {"stub", "livekit-ffmpeg"}:
        raise ConfigError("PANOPTIX_MEDIA_PUBLISHER_MODE must be 'stub' or 'livekit-ffmpeg'")
    if media_publisher_mode == "livekit-ffmpeg":
        _validate_rtsp_url(media_source_url, "PANOPTIX_MEDIA_SOURCE_URL")
        if media_width < 1:
            raise ConfigError("PANOPTIX_MEDIA_WIDTH must be at least 1")
        if media_height < 1:
            raise ConfigError("PANOPTIX_MEDIA_HEIGHT must be at least 1")
        if media_frame_rate < 1:
            raise ConfigError("PANOPTIX_MEDIA_FRAME_RATE must be at least 1")
        if not media_ffmpeg_binary:
            raise ConfigError("PANOPTIX_MEDIA_FFMPEG_BINARY is required")

    return AgentConfig(
        api_base_url=api_base_url,
        gateway_id=gateway_id,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        agent_version=agent_version,
        request_timeout_seconds=request_timeout_seconds,
        camera_ids=camera_ids,
        dev_identity_enabled=dev_identity_enabled,
        command_signing_key=command_signing_key,
        control_ws_path=control_ws_path,
        control_reconnect_attempts=control_reconnect_attempts,
        control_reconnect_backoff_seconds=control_reconnect_backoff_seconds,
        synthetic_rtsp_url=synthetic_rtsp_url,
        synthetic_video_size=synthetic_video_size,
        synthetic_frame_rate=synthetic_frame_rate,
        synthetic_audio_frequency=synthetic_audio_frequency,
        media_publisher_mode=media_publisher_mode,
        media_source_url=media_source_url,
        media_width=media_width,
        media_height=media_height,
        media_frame_rate=media_frame_rate,
        media_ffmpeg_binary=media_ffmpeg_binary,
    )


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required")
    return value


def _int_value(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _float_value(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc


def _csv_value(raw: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _bool_value(raw: str) -> bool:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off", ""}:
        return False
    raise ConfigError("PANOPTIX_DEV_GATEWAY_IDENTITY must be a boolean")


def _validate_rtsp_url(raw: str, name: str) -> None:
    parsed = urlsplit(raw)
    if parsed.scheme not in {"rtsp", "rtsps"} or not parsed.netloc:
        raise ConfigError(f"{name} must be an rtsp:// or rtsps:// URL")
    if parsed.username is not None or parsed.password is not None:
        raise ConfigError(f"{name} must not include credentials")


def _validate_video_size(raw: str, name: str) -> None:
    width, separator, height = raw.partition("x")
    if separator != "x":
        raise ConfigError(f"{name} must use WIDTHxHEIGHT format")
    try:
        width_value = int(width)
        height_value = int(height)
    except ValueError as exc:
        raise ConfigError(f"{name} must use integer WIDTHxHEIGHT values") from exc
    if width_value < 1 or height_value < 1:
        raise ConfigError(f"{name} dimensions must be at least 1")
