from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from panoptix_edge_agent import __version__
from panoptix_edge_agent.mediamtx_process import (
    DEFAULT_MEDIAMTX_CONFIG_PATH,
    MediamtxProcessCommand,
    MediamtxProcessError,
)


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
    gateway_service_token: str = ""
    cf_access_client_id: str = ""
    cf_access_client_secret: str = ""
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
    media_frame_stall_timeout_seconds: float = 10.0
    supervise_mediamtx: bool = False
    mediamtx_binary: str = "mediamtx"
    mediamtx_config_path: str = str(DEFAULT_MEDIAMTX_CONFIG_PATH)
    camera_credentials_path: str = ""
    discovery_approved_ranges: tuple[str, ...] = ()
    discovery_ports: tuple[int, ...] = (554, 80, 443, 8000, 8080, 8899)
    discovery_timeout_seconds: float = 1.0
    discovery_max_hosts: int = 256

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
    gateway_service_token = env.get("PANOPTIX_GATEWAY_SERVICE_TOKEN", "").strip()
    cf_access_client_id = env.get("PANOPTIX_CF_ACCESS_CLIENT_ID", "").strip()
    cf_access_client_secret = env.get("PANOPTIX_CF_ACCESS_CLIENT_SECRET", "").strip()
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
    media_frame_stall_timeout_seconds = _float_value(
        env,
        "PANOPTIX_MEDIA_FRAME_STALL_TIMEOUT_SECONDS",
        10.0,
    )
    supervise_mediamtx = _bool_value(env.get("PANOPTIX_SUPERVISE_MEDIAMTX", "false"))
    mediamtx_binary = env.get("PANOPTIX_MEDIAMTX_BINARY", "mediamtx").strip() or "mediamtx"
    mediamtx_config_path = env.get(
        "PANOPTIX_MEDIAMTX_CONFIG_PATH",
        str(DEFAULT_MEDIAMTX_CONFIG_PATH),
    ).strip() or str(DEFAULT_MEDIAMTX_CONFIG_PATH)
    camera_credentials_path = env.get("PANOPTIX_CAMERA_CREDENTIALS_PATH", "").strip()
    discovery_approved_ranges = _csv_value(env.get("PANOPTIX_DISCOVERY_APPROVED_RANGES", ""))
    discovery_ports = _ports_value(env.get("PANOPTIX_DISCOVERY_PORTS", "554,80,443,8000,8080,8899"))
    discovery_timeout_seconds = _float_value(env, "PANOPTIX_DISCOVERY_TIMEOUT_SECONDS", 1.0)
    discovery_max_hosts = _int_value(env, "PANOPTIX_DISCOVERY_MAX_HOSTS", 256)

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
        if media_frame_stall_timeout_seconds <= 0:
            raise ConfigError("PANOPTIX_MEDIA_FRAME_STALL_TIMEOUT_SECONDS must be greater than 0")
    if supervise_mediamtx:
        try:
            MediamtxProcessCommand(
                binary=mediamtx_binary,
                config_path=mediamtx_config_path,
            ).args()
        except MediamtxProcessError as exc:
            raise ConfigError(f"PANOPTIX_MEDIAMTX_CONFIG invalid: {exc}") from exc
    if discovery_timeout_seconds <= 0:
        raise ConfigError("PANOPTIX_DISCOVERY_TIMEOUT_SECONDS must be greater than 0")
    if discovery_max_hosts < 1:
        raise ConfigError("PANOPTIX_DISCOVERY_MAX_HOSTS must be at least 1")

    return AgentConfig(
        api_base_url=api_base_url,
        gateway_id=gateway_id,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        agent_version=agent_version,
        request_timeout_seconds=request_timeout_seconds,
        camera_ids=camera_ids,
        dev_identity_enabled=dev_identity_enabled,
        gateway_service_token=gateway_service_token,
        cf_access_client_id=cf_access_client_id,
        cf_access_client_secret=cf_access_client_secret,
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
        media_frame_stall_timeout_seconds=media_frame_stall_timeout_seconds,
        supervise_mediamtx=supervise_mediamtx,
        mediamtx_binary=mediamtx_binary,
        mediamtx_config_path=mediamtx_config_path,
        camera_credentials_path=camera_credentials_path,
        discovery_approved_ranges=discovery_approved_ranges,
        discovery_ports=discovery_ports,
        discovery_timeout_seconds=discovery_timeout_seconds,
        discovery_max_hosts=discovery_max_hosts,
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


def _ports_value(raw: str) -> tuple[int, ...]:
    values = _csv_value(raw)
    ports: list[int] = []
    for value in values:
        try:
            port = int(value)
        except ValueError as exc:
            raise ConfigError("PANOPTIX_DISCOVERY_PORTS must contain integer ports") from exc
        if port < 1 or port > 65535:
            raise ConfigError("PANOPTIX_DISCOVERY_PORTS must contain ports from 1 to 65535")
        if port not in ports:
            ports.append(port)
    if not ports:
        raise ConfigError("PANOPTIX_DISCOVERY_PORTS must contain at least one port")
    return tuple(ports)


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
