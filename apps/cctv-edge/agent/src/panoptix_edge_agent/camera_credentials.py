from __future__ import annotations

import json
import os
import platform
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from panoptix_edge_agent.config import ConfigError


class CredentialFileError(ConfigError):
    pass


@dataclass(frozen=True)
class CameraCredential:
    camera_id: str
    rtsp_host: str
    rtsp_port: int
    rtsp_path: str
    rtsp_transport: str
    username: str
    password: str
    tls: bool = False

    def __repr__(self) -> str:
        return (
            f"CameraCredential(camera_id={self.camera_id!r}, "
            f"rtsp_host={self.rtsp_host!r}, "
            f"rtsp_port={self.rtsp_port}, "
            f"rtsp_path={self.rtsp_path!r}, "
            f"rtsp_transport={self.rtsp_transport!r}, "
            f"username='***', password='***', "
            f"tls={self.tls})"
        )


class CameraCredentialStore:
    def __init__(self, credentials: dict[str, CameraCredential]) -> None:
        self._credentials = credentials

    def resolve(self, camera_id: str) -> CameraCredential | None:
        return self._credentials.get(camera_id)

    def camera_ids(self) -> frozenset[str]:
        return frozenset(self._credentials.keys())


def load_camera_credentials(path: str | Path) -> CameraCredentialStore:
    file_path = Path(path)
    if not file_path.is_file():
        raise CredentialFileError(f"credential file not found: {file_path}")

    try:
        raw = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CredentialFileError(f"cannot read credential file: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CredentialFileError(f"invalid JSON in credential file: {exc}") from exc

    if not isinstance(data, dict):
        raise CredentialFileError("credential file must contain a JSON object")

    version = data.get("version")
    if version != 1:
        raise CredentialFileError(f"unsupported credential file version: {version}")

    cameras_raw = data.get("cameras")
    if not isinstance(cameras_raw, dict):
        raise CredentialFileError("credential file must contain a 'cameras' object")

    credentials: dict[str, CameraCredential] = {}
    for camera_id, entry in cameras_raw.items():
        if not isinstance(camera_id, str) or not camera_id.strip():
            raise CredentialFileError("camera id must be a non-empty string")
        if not isinstance(entry, dict):
            raise CredentialFileError(f"camera entry for '{camera_id}' must be an object")
        credentials[camera_id] = _parse_camera_entry(camera_id, entry)

    return CameraCredentialStore(credentials)


def build_rtsp_url(credential: CameraCredential) -> str:
    scheme = "rtsps" if credential.tls else "rtsp"
    port_suffix = f":{credential.rtsp_port}" if credential.rtsp_port != 554 else ""
    return f"{scheme}://{credential.rtsp_host}{port_suffix}{credential.rtsp_path}"


def build_authenticated_rtsp_url(credential: CameraCredential) -> str:
    scheme = "rtsps" if credential.tls else "rtsp"
    port_suffix = f":{credential.rtsp_port}" if credential.rtsp_port != 554 else ""
    user = quote(credential.username, safe="")
    pwd = quote(credential.password, safe="")
    return f"{scheme}://{user}:{pwd}@{credential.rtsp_host}{port_suffix}{credential.rtsp_path}"


def check_credential_file_permissions(path: str | Path) -> None:
    if platform.system() == "Windows":
        return
    file_path = Path(path)
    try:
        mode = os.stat(file_path).st_mode
    except OSError as exc:
        raise CredentialFileError(f"cannot stat credential file: {exc}") from exc
    file_perms = stat.S_IMODE(mode)
    if file_perms & (stat.S_IRWXG | stat.S_IRWXO):
        raise CredentialFileError(
            f"credential file permissions too open ({oct(file_perms)}), "
            f"expected 0o600 or stricter"
        )


def _parse_camera_entry(camera_id: str, entry: dict[str, object]) -> CameraCredential:
    rtsp_host = _str_field(entry, "rtsp_host", camera_id)
    rtsp_port = _int_field(entry, "rtsp_port", camera_id)
    rtsp_path = _str_field(entry, "rtsp_path", camera_id)
    rtsp_transport = _str_field(entry, "rtsp_transport", camera_id)
    username = _str_field(entry, "username", camera_id)
    password = _str_field(entry, "password", camera_id)
    tls = entry.get("tls", False)

    if not isinstance(tls, bool):
        raise CredentialFileError(f"camera '{camera_id}': tls must be a boolean")
    if rtsp_port < 1 or rtsp_port > 65535:
        raise CredentialFileError(f"camera '{camera_id}': rtsp_port must be 1-65535")
    if not rtsp_path.startswith("/"):
        raise CredentialFileError(f"camera '{camera_id}': rtsp_path must start with /")
    if rtsp_transport not in {"tcp", "udp"}:
        raise CredentialFileError(f"camera '{camera_id}': rtsp_transport must be 'tcp' or 'udp'")

    return CameraCredential(
        camera_id=camera_id,
        rtsp_host=rtsp_host,
        rtsp_port=rtsp_port,
        rtsp_path=rtsp_path,
        rtsp_transport=rtsp_transport,
        username=username,
        password=password,
        tls=tls,
    )


def _str_field(entry: dict[str, object], field: str, camera_id: str) -> str:
    value = entry.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CredentialFileError(f"camera '{camera_id}': {field} must be a non-empty string")
    return value


def _int_field(entry: dict[str, object], field: str, camera_id: str) -> int:
    value = entry.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise CredentialFileError(f"camera '{camera_id}': {field} must be an integer")
    return value
