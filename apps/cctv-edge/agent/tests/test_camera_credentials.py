from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from unittest.mock import patch

import pytest

from panoptix_edge_agent.camera_credentials import (
    CameraCredential,
    CameraCredentialStore,
    CredentialFileError,
    build_authenticated_rtsp_url,
    build_rtsp_url,
    check_credential_file_permissions,
    load_camera_credentials,
)


VALID_CAMERAS_JSON = {
    "version": 1,
    "cameras": {
        "camera-abc-123": {
            "rtsp_host": "192.168.10.50",
            "rtsp_port": 554,
            "rtsp_path": "/stream1",
            "rtsp_transport": "tcp",
            "username": "admin",
            "password": "s3cret",
            "tls": False,
        },
        "camera-def-456": {
            "rtsp_host": "192.168.10.51",
            "rtsp_port": 8554,
            "rtsp_path": "/live/main",
            "rtsp_transport": "udp",
            "username": "cam-user",
            "password": "p@ssw0rd!",
            "tls": True,
        },
    },
}


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_load_valid_credentials(tmp_path: Path) -> None:
    path = tmp_path / "cameras.json"
    _write_json(path, VALID_CAMERAS_JSON)

    store = load_camera_credentials(path)

    assert store.camera_ids() == frozenset({"camera-abc-123", "camera-def-456"})


def test_resolve_existing_camera(tmp_path: Path) -> None:
    path = tmp_path / "cameras.json"
    _write_json(path, VALID_CAMERAS_JSON)
    store = load_camera_credentials(path)

    cred = store.resolve("camera-abc-123")

    assert cred is not None
    assert cred.camera_id == "camera-abc-123"
    assert cred.rtsp_host == "192.168.10.50"
    assert cred.rtsp_port == 554
    assert cred.rtsp_path == "/stream1"
    assert cred.rtsp_transport == "tcp"
    assert cred.username == "admin"
    assert cred.password == "s3cret"
    assert cred.tls is False


def test_resolve_missing_camera(tmp_path: Path) -> None:
    path = tmp_path / "cameras.json"
    _write_json(path, VALID_CAMERAS_JSON)
    store = load_camera_credentials(path)

    assert store.resolve("nonexistent-camera") is None


def test_build_rtsp_url_default_port() -> None:
    cred = CameraCredential(
        camera_id="cam-1",
        rtsp_host="10.0.0.1",
        rtsp_port=554,
        rtsp_path="/stream",
        rtsp_transport="tcp",
        username="user",
        password="pass",
    )
    assert build_rtsp_url(cred) == "rtsp://10.0.0.1/stream"


def test_build_rtsp_url_custom_port() -> None:
    cred = CameraCredential(
        camera_id="cam-1",
        rtsp_host="10.0.0.1",
        rtsp_port=8554,
        rtsp_path="/live",
        rtsp_transport="tcp",
        username="user",
        password="pass",
    )
    assert build_rtsp_url(cred) == "rtsp://10.0.0.1:8554/live"


def test_build_rtsp_url_tls() -> None:
    cred = CameraCredential(
        camera_id="cam-1",
        rtsp_host="10.0.0.1",
        rtsp_port=554,
        rtsp_path="/stream",
        rtsp_transport="tcp",
        username="user",
        password="pass",
        tls=True,
    )
    assert build_rtsp_url(cred) == "rtsps://10.0.0.1/stream"


def test_build_authenticated_rtsp_url() -> None:
    cred = CameraCredential(
        camera_id="cam-1",
        rtsp_host="10.0.0.1",
        rtsp_port=554,
        rtsp_path="/stream",
        rtsp_transport="tcp",
        username="admin",
        password="s3cret",
    )
    assert build_authenticated_rtsp_url(cred) == "rtsp://admin:s3cret@10.0.0.1/stream"


def test_build_authenticated_rtsp_url_special_chars() -> None:
    cred = CameraCredential(
        camera_id="cam-1",
        rtsp_host="10.0.0.1",
        rtsp_port=8554,
        rtsp_path="/live",
        rtsp_transport="tcp",
        username="user@domain",
        password="p@ss:word/!",
        tls=True,
    )
    url = build_authenticated_rtsp_url(cred)
    assert url.startswith("rtsps://")
    assert "user%40domain" in url
    assert "p%40ss%3Aword%2F%21" in url
    assert ":8554" in url


def test_credential_repr_redacts_password() -> None:
    cred = CameraCredential(
        camera_id="cam-1",
        rtsp_host="10.0.0.1",
        rtsp_port=554,
        rtsp_path="/stream",
        rtsp_transport="tcp",
        username="admin",
        password="super-secret-password",
    )
    text = repr(cred)
    assert "super-secret-password" not in text
    assert "admin" not in text
    assert "***" in text
    assert "cam-1" in text


def test_load_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    with pytest.raises(CredentialFileError, match="not found"):
        load_camera_credentials(path)


def test_load_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(CredentialFileError, match="invalid JSON"):
        load_camera_credentials(path)


def test_load_wrong_version(tmp_path: Path) -> None:
    path = tmp_path / "cameras.json"
    _write_json(path, {"version": 99, "cameras": {}})
    with pytest.raises(CredentialFileError, match="unsupported.*version"):
        load_camera_credentials(path)


def test_load_missing_version(tmp_path: Path) -> None:
    path = tmp_path / "cameras.json"
    _write_json(path, {"cameras": {}})
    with pytest.raises(CredentialFileError, match="unsupported.*version"):
        load_camera_credentials(path)


def test_load_cameras_not_object(tmp_path: Path) -> None:
    path = tmp_path / "cameras.json"
    _write_json(path, {"version": 1, "cameras": "not-a-dict"})
    with pytest.raises(CredentialFileError, match="'cameras' object"):
        load_camera_credentials(path)


def test_load_invalid_port_too_high(tmp_path: Path) -> None:
    data = {
        "version": 1,
        "cameras": {
            "cam-1": {
                "rtsp_host": "10.0.0.1",
                "rtsp_port": 70000,
                "rtsp_path": "/stream",
                "rtsp_transport": "tcp",
                "username": "u",
                "password": "p",
            }
        },
    }
    path = tmp_path / "cameras.json"
    _write_json(path, data)
    with pytest.raises(CredentialFileError, match="rtsp_port must be 1-65535"):
        load_camera_credentials(path)


def test_load_invalid_port_zero(tmp_path: Path) -> None:
    data = {
        "version": 1,
        "cameras": {
            "cam-1": {
                "rtsp_host": "10.0.0.1",
                "rtsp_port": 0,
                "rtsp_path": "/stream",
                "rtsp_transport": "tcp",
                "username": "u",
                "password": "p",
            }
        },
    }
    path = tmp_path / "cameras.json"
    _write_json(path, data)
    with pytest.raises(CredentialFileError, match="rtsp_port must be 1-65535"):
        load_camera_credentials(path)


def test_load_invalid_path_no_slash(tmp_path: Path) -> None:
    data = {
        "version": 1,
        "cameras": {
            "cam-1": {
                "rtsp_host": "10.0.0.1",
                "rtsp_port": 554,
                "rtsp_path": "stream",
                "rtsp_transport": "tcp",
                "username": "u",
                "password": "p",
            }
        },
    }
    path = tmp_path / "cameras.json"
    _write_json(path, data)
    with pytest.raises(CredentialFileError, match="rtsp_path must start with /"):
        load_camera_credentials(path)


def test_load_invalid_transport(tmp_path: Path) -> None:
    data = {
        "version": 1,
        "cameras": {
            "cam-1": {
                "rtsp_host": "10.0.0.1",
                "rtsp_port": 554,
                "rtsp_path": "/stream",
                "rtsp_transport": "http",
                "username": "u",
                "password": "p",
            }
        },
    }
    path = tmp_path / "cameras.json"
    _write_json(path, data)
    with pytest.raises(CredentialFileError, match="rtsp_transport must be"):
        load_camera_credentials(path)


def test_load_empty_username(tmp_path: Path) -> None:
    data = {
        "version": 1,
        "cameras": {
            "cam-1": {
                "rtsp_host": "10.0.0.1",
                "rtsp_port": 554,
                "rtsp_path": "/stream",
                "rtsp_transport": "tcp",
                "username": "",
                "password": "p",
            }
        },
    }
    path = tmp_path / "cameras.json"
    _write_json(path, data)
    with pytest.raises(CredentialFileError, match="username must be a non-empty"):
        load_camera_credentials(path)


def test_load_empty_password(tmp_path: Path) -> None:
    data = {
        "version": 1,
        "cameras": {
            "cam-1": {
                "rtsp_host": "10.0.0.1",
                "rtsp_port": 554,
                "rtsp_path": "/stream",
                "rtsp_transport": "tcp",
                "username": "u",
                "password": "",
            }
        },
    }
    path = tmp_path / "cameras.json"
    _write_json(path, data)
    with pytest.raises(CredentialFileError, match="password must be a non-empty"):
        load_camera_credentials(path)


def test_load_tls_not_boolean(tmp_path: Path) -> None:
    data = {
        "version": 1,
        "cameras": {
            "cam-1": {
                "rtsp_host": "10.0.0.1",
                "rtsp_port": 554,
                "rtsp_path": "/stream",
                "rtsp_transport": "tcp",
                "username": "u",
                "password": "p",
                "tls": "yes",
            }
        },
    }
    path = tmp_path / "cameras.json"
    _write_json(path, data)
    with pytest.raises(CredentialFileError, match="tls must be a boolean"):
        load_camera_credentials(path)


def test_load_empty_cameras_is_valid(tmp_path: Path) -> None:
    path = tmp_path / "cameras.json"
    _write_json(path, {"version": 1, "cameras": {}})
    store = load_camera_credentials(path)
    assert store.camera_ids() == frozenset()


@pytest.mark.skipif(platform.system() == "Windows", reason="POSIX permissions")
def test_check_permissions_rejects_group_readable(tmp_path: Path) -> None:
    path = tmp_path / "cameras.json"
    _write_json(path, VALID_CAMERAS_JSON)
    os.chmod(path, 0o640)
    with pytest.raises(CredentialFileError, match="permissions too open"):
        check_credential_file_permissions(path)


@pytest.mark.skipif(platform.system() == "Windows", reason="POSIX permissions")
def test_check_permissions_accepts_0600(tmp_path: Path) -> None:
    path = tmp_path / "cameras.json"
    _write_json(path, VALID_CAMERAS_JSON)
    os.chmod(path, 0o600)
    check_credential_file_permissions(path)


def test_check_permissions_skips_on_windows() -> None:
    with patch("panoptix_edge_agent.camera_credentials.platform.system", return_value="Windows"):
        check_credential_file_permissions("/nonexistent/file")


def test_credential_store_direct_construction() -> None:
    cred = CameraCredential(
        camera_id="cam-1",
        rtsp_host="10.0.0.1",
        rtsp_port=554,
        rtsp_path="/stream",
        rtsp_transport="tcp",
        username="u",
        password="p",
    )
    store = CameraCredentialStore({"cam-1": cred})
    assert store.resolve("cam-1") is cred
    assert store.resolve("cam-2") is None


def test_config_camera_credentials_path_defaults_empty() -> None:
    from panoptix_edge_agent.config import load_config_from_env

    config = load_config_from_env({
        "PANOPTIX_API_BASE_URL": "http://api.example.test",
        "PANOPTIX_GATEWAY_ID": "gateway-1",
    })
    assert config.camera_credentials_path == ""


def test_config_camera_credentials_path_from_env() -> None:
    from panoptix_edge_agent.config import load_config_from_env

    config = load_config_from_env({
        "PANOPTIX_API_BASE_URL": "http://api.example.test",
        "PANOPTIX_GATEWAY_ID": "gateway-1",
        "PANOPTIX_CAMERA_CREDENTIALS_PATH": "/etc/panoptix/cameras.json",
    })
    assert config.camera_credentials_path == "/etc/panoptix/cameras.json"
