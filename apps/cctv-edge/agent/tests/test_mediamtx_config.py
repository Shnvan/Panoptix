from __future__ import annotations

from pathlib import Path

import pytest

from panoptix_edge_agent.mediamtx_config import (
    MediamtxConfigError,
    MediamtxLocalConfig,
    build_mediamtx_local_yaml,
    default_mediamtx_local_config,
)


def test_default_mediamtx_local_config_matches_synthetic_source() -> None:
    config = default_mediamtx_local_config()

    assert config.synthetic_path == "synthetic-camera-1"
    assert config.synthetic_rtsp_url == "rtsp://127.0.0.1:8554/synthetic-camera-1"


def test_build_mediamtx_local_yaml_includes_safe_defaults() -> None:
    yaml = build_mediamtx_local_yaml()

    assert "api: no" in yaml
    assert "apiAddress: 127.0.0.1:9997" in yaml
    assert "rtsp: yes" in yaml
    assert "rtspAddress: 127.0.0.1:8554" in yaml
    assert "  synthetic-camera-1:" in yaml
    assert "    source: publisher" in yaml
    assert "rtsp://" not in yaml
    assert "@" not in yaml


def test_checked_in_mediamtx_local_yaml_matches_generated_defaults() -> None:
    mediamtx_config = Path(__file__).resolve().parents[2] / "mediamtx" / "mediamtx.local.yml"

    assert mediamtx_config.read_text(encoding="utf-8") == build_mediamtx_local_yaml()


def test_build_mediamtx_local_yaml_allows_loopback_api_when_enabled() -> None:
    yaml = build_mediamtx_local_yaml(
        MediamtxLocalConfig(
            api_enabled=True,
            api_address="127.0.0.1:9997",
        )
    )

    assert "api: yes" in yaml
    assert "apiAddress: 127.0.0.1:9997" in yaml


def test_build_mediamtx_local_yaml_allows_localhost_api_when_enabled() -> None:
    yaml = build_mediamtx_local_yaml(
        MediamtxLocalConfig(
            api_enabled=True,
            api_address="localhost:9997",
        )
    )

    assert "api: yes" in yaml
    assert "apiAddress: localhost:9997" in yaml


def test_build_mediamtx_local_yaml_rejects_wildcard_api_binding() -> None:
    with pytest.raises(MediamtxConfigError, match="loopback"):
        build_mediamtx_local_yaml(
            MediamtxLocalConfig(
                api_enabled=True,
                api_address="0.0.0.0:9997",
            )
        )


def test_build_mediamtx_local_yaml_rejects_camera_vlan_api_binding() -> None:
    with pytest.raises(MediamtxConfigError, match="loopback"):
        build_mediamtx_local_yaml(
            MediamtxLocalConfig(
                api_enabled=True,
                api_address="192.168.10.2:9997",
            )
        )


def test_build_mediamtx_local_yaml_rejects_wan_api_binding_when_api_disabled() -> None:
    with pytest.raises(MediamtxConfigError, match="loopback"):
        build_mediamtx_local_yaml(
            MediamtxLocalConfig(
                api_enabled=False,
                api_address="203.0.113.10:9997",
            )
        )


def test_build_mediamtx_local_yaml_rejects_invalid_rtsp_binding() -> None:
    with pytest.raises(MediamtxConfigError, match="rtsp_address"):
        build_mediamtx_local_yaml(MediamtxLocalConfig(rtsp_address="0.0.0.0:8554"))


def test_build_mediamtx_local_yaml_rejects_invalid_port() -> None:
    with pytest.raises(MediamtxConfigError, match="port"):
        build_mediamtx_local_yaml(MediamtxLocalConfig(rtsp_address="127.0.0.1:0"))


def test_build_mediamtx_local_yaml_rejects_invalid_path_characters() -> None:
    with pytest.raises(MediamtxConfigError, match="synthetic_path"):
        build_mediamtx_local_yaml(MediamtxLocalConfig(synthetic_path="synthetic/camera/1"))


def test_build_mediamtx_local_yaml_reflects_custom_safe_path() -> None:
    yaml = build_mediamtx_local_yaml(MediamtxLocalConfig(synthetic_path="synthetic_camera_01"))

    assert "  synthetic_camera_01:" in yaml
