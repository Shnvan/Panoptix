from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass


class MediamtxConfigError(ValueError):
    pass


_PATH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass(frozen=True)
class MediamtxLocalConfig:
    rtsp_address: str = "127.0.0.1:8554"
    api_enabled: bool = False
    api_address: str = "127.0.0.1:9997"
    synthetic_path: str = "synthetic-camera-1"

    @property
    def synthetic_rtsp_url(self) -> str:
        return f"rtsp://{self.rtsp_address}/{self.synthetic_path}"

    def validate(self) -> None:
        _validate_loopback_address(self.rtsp_address, "rtsp_address")
        if self.api_enabled:
            _validate_loopback_address(self.api_address, "api_address")
        else:
            _validate_disabled_api_address(self.api_address)
        _validate_path(self.synthetic_path)

    def to_yaml(self) -> str:
        self.validate()
        api_value = "yes" if self.api_enabled else "no"
        return "\n".join(
            [
                f"api: {api_value}",
                f"apiAddress: {self.api_address}",
                "rtsp: yes",
                f"rtspAddress: {self.rtsp_address}",
                "rtmp: no",
                "hls: no",
                "webrtc: no",
                "srt: no",
                "paths:",
                f"  {self.synthetic_path}:",
                "    source: publisher",
                "",
            ]
        )


def default_mediamtx_local_config() -> MediamtxLocalConfig:
    return MediamtxLocalConfig()


def build_mediamtx_local_yaml(config: MediamtxLocalConfig | None = None) -> str:
    selected = default_mediamtx_local_config() if config is None else config
    return selected.to_yaml()


def _validate_disabled_api_address(raw: str) -> None:
    if raw:
        _validate_loopback_address(raw, "api_address")


def _validate_loopback_address(raw: str, name: str) -> None:
    host, port = _split_host_port(raw, name)
    if not (1 <= port <= 65535):
        raise MediamtxConfigError(f"{name} port must be between 1 and 65535")
    if host.lower() == "localhost":
        return
    try:
        ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise MediamtxConfigError(f"{name} host must be localhost or a loopback IP") from exc
    if not ip.is_loopback:
        raise MediamtxConfigError(f"{name} must be bound to loopback only")


def _split_host_port(raw: str, name: str) -> tuple[str, int]:
    if not raw:
        raise MediamtxConfigError(f"{name} is required")
    if raw.startswith("["):
        host, separator, port_raw = raw[1:].partition("]:")
    else:
        host, separator, port_raw = raw.rpartition(":")
    if not host or not separator or not port_raw:
        raise MediamtxConfigError(f"{name} must use HOST:PORT format")
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise MediamtxConfigError(f"{name} port must be an integer") from exc
    return host, port


def _validate_path(raw: str) -> None:
    if not _PATH_PATTERN.fullmatch(raw):
        raise MediamtxConfigError("synthetic_path must contain only letters, numbers, dot, underscore, or dash")
    if ":" in raw or "@" in raw:
        raise MediamtxConfigError("synthetic_path must not contain credentials")
