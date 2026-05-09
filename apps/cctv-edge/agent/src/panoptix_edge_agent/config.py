from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

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

    if heartbeat_interval_seconds < 5:
        raise ConfigError("PANOPTIX_HEARTBEAT_INTERVAL_SECONDS must be at least 5")
    if request_timeout_seconds <= 0:
        raise ConfigError("PANOPTIX_REQUEST_TIMEOUT_SECONDS must be greater than 0")
    if not control_ws_path.startswith("/"):
        raise ConfigError("PANOPTIX_GATEWAY_CONTROL_WS_PATH must start with /")

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
