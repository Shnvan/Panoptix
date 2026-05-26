from __future__ import annotations

from pathlib import Path

import pytest

from panoptix_edge_agent.config import ConfigError, load_config_from_env


MEDIAMTX_CONFIG_PATH = Path(__file__).resolve().parents[2] / "mediamtx" / "mediamtx.local.yml"


def test_load_config_from_env_requires_api_base_url() -> None:
    with pytest.raises(ConfigError, match="PANOPTIX_API_BASE_URL is required"):
        load_config_from_env({"PANOPTIX_GATEWAY_ID": "gateway-1"})


def test_load_config_from_env_requires_gateway_id() -> None:
    with pytest.raises(ConfigError, match="PANOPTIX_GATEWAY_ID is required"):
        load_config_from_env({"PANOPTIX_API_BASE_URL": "http://api.example.test"})


def test_load_config_from_env_parses_values() -> None:
    config = load_config_from_env(
        {
            "PANOPTIX_API_BASE_URL": "http://api.example.test/",
            "PANOPTIX_GATEWAY_ID": "gateway-1",
            "PANOPTIX_HEARTBEAT_INTERVAL_SECONDS": "15",
            "PANOPTIX_REQUEST_TIMEOUT_SECONDS": "2.5",
            "PANOPTIX_AGENT_VERSION": "0.2.0",
            "PANOPTIX_CAMERA_IDS": "camera-1, camera-2,,",
            "PANOPTIX_DEV_GATEWAY_IDENTITY": "true",
            "PANOPTIX_GATEWAY_SERVICE_TOKEN": "test-gateway-service-token",
            "PANOPTIX_CF_ACCESS_CLIENT_ID": "test-client-id.access",
            "PANOPTIX_CF_ACCESS_CLIENT_SECRET": "test-client-secret",
            "PANOPTIX_GATEWAY_COMMAND_SIGNING_KEY": "test-signing-key",
            "PANOPTIX_GATEWAY_CONTROL_WS_PATH": "/custom/ws",
            "PANOPTIX_GATEWAY_CONTROL_RECONNECT_ATTEMPTS": "5",
            "PANOPTIX_GATEWAY_CONTROL_RECONNECT_BACKOFF_SECONDS": "2.5",
            "PANOPTIX_SYNTHETIC_RTSP_URL": "rtsp://127.0.0.1:8554/custom-source",
            "PANOPTIX_SYNTHETIC_VIDEO_SIZE": "640x360",
            "PANOPTIX_SYNTHETIC_FRAME_RATE": "15",
            "PANOPTIX_SYNTHETIC_AUDIO_FREQUENCY": "440",
            "PANOPTIX_SUPERVISE_MEDIAMTX": "true",
            "PANOPTIX_MEDIAMTX_BINARY": "mediamtx.exe",
            "PANOPTIX_MEDIAMTX_CONFIG_PATH": str(MEDIAMTX_CONFIG_PATH),
            "PANOPTIX_DISCOVERY_APPROVED_RANGES": "192.168.50.0/24,10.10.0.0/24",
            "PANOPTIX_DISCOVERY_PORTS": "554,80,80,8080",
            "PANOPTIX_DISCOVERY_TIMEOUT_SECONDS": "0.75",
            "PANOPTIX_DISCOVERY_MAX_HOSTS": "512",
        }
    )

    assert config.normalized_api_base_url == "http://api.example.test"
    assert config.gateway_id == "gateway-1"
    assert config.heartbeat_interval_seconds == 15
    assert config.request_timeout_seconds == 2.5
    assert config.agent_version == "0.2.0"
    assert config.camera_ids == ("camera-1", "camera-2")
    assert config.dev_identity_enabled is True
    assert config.gateway_service_token == "test-gateway-service-token"
    assert config.cf_access_client_id == "test-client-id.access"
    assert config.cf_access_client_secret == "test-client-secret"
    assert config.command_signing_key == "test-signing-key"
    assert config.control_ws_path == "/custom/ws"
    assert config.control_reconnect_attempts == 5
    assert config.control_reconnect_backoff_seconds == 2.5
    assert config.synthetic_rtsp_url == "rtsp://127.0.0.1:8554/custom-source"
    assert config.synthetic_video_size == "640x360"
    assert config.synthetic_frame_rate == 15
    assert config.synthetic_audio_frequency == 440
    assert config.supervise_mediamtx is True
    assert config.mediamtx_binary == "mediamtx.exe"
    assert config.mediamtx_config_path == str(MEDIAMTX_CONFIG_PATH)
    assert config.discovery_approved_ranges == ("192.168.50.0/24", "10.10.0.0/24")
    assert config.discovery_ports == (554, 80, 8080)
    assert config.discovery_timeout_seconds == 0.75
    assert config.discovery_max_hosts == 512


def test_load_config_from_env_rejects_short_heartbeat_interval() -> None:
    with pytest.raises(ConfigError, match="at least 5"):
        load_config_from_env(
            {
                "PANOPTIX_API_BASE_URL": "http://api.example.test",
                "PANOPTIX_GATEWAY_ID": "gateway-1",
                "PANOPTIX_HEARTBEAT_INTERVAL_SECONDS": "4",
            }
        )


def test_load_config_from_env_rejects_control_ws_path_without_leading_slash() -> None:
    with pytest.raises(ConfigError, match="must start with /"):
        load_config_from_env(
            {
                "PANOPTIX_API_BASE_URL": "http://api.example.test",
                "PANOPTIX_GATEWAY_ID": "gateway-1",
                "PANOPTIX_GATEWAY_CONTROL_WS_PATH": "api/v1/gateway-control/ws",
            }
        )


def test_load_config_from_env_rejects_control_reconnect_attempts_below_one() -> None:
    with pytest.raises(ConfigError, match="RECONNECT_ATTEMPTS must be at least 1"):
        load_config_from_env(
            {
                "PANOPTIX_API_BASE_URL": "http://api.example.test",
                "PANOPTIX_GATEWAY_ID": "gateway-1",
                "PANOPTIX_GATEWAY_CONTROL_RECONNECT_ATTEMPTS": "0",
            }
        )


def test_load_config_from_env_rejects_negative_control_reconnect_backoff() -> None:
    with pytest.raises(ConfigError, match="RECONNECT_BACKOFF_SECONDS"):
        load_config_from_env(
            {
                "PANOPTIX_API_BASE_URL": "http://api.example.test",
                "PANOPTIX_GATEWAY_ID": "gateway-1",
                "PANOPTIX_GATEWAY_CONTROL_RECONNECT_BACKOFF_SECONDS": "-0.1",
            }
        )


def test_load_config_from_env_rejects_invalid_synthetic_rtsp_url() -> None:
    with pytest.raises(ConfigError, match="PANOPTIX_SYNTHETIC_RTSP_URL"):
        load_config_from_env(
            {
                "PANOPTIX_API_BASE_URL": "http://api.example.test",
                "PANOPTIX_GATEWAY_ID": "gateway-1",
                "PANOPTIX_SYNTHETIC_RTSP_URL": "http://127.0.0.1:8554/source",
            }
        )


def test_load_config_from_env_rejects_synthetic_rtsp_url_credentials() -> None:
    with pytest.raises(ConfigError, match="must not include credentials"):
        load_config_from_env(
            {
                "PANOPTIX_API_BASE_URL": "http://api.example.test",
                "PANOPTIX_GATEWAY_ID": "gateway-1",
                "PANOPTIX_SYNTHETIC_RTSP_URL": "rtsp://user:pass@127.0.0.1:8554/source",
            }
        )


def test_load_config_from_env_rejects_invalid_synthetic_video_size() -> None:
    with pytest.raises(ConfigError, match="PANOPTIX_SYNTHETIC_VIDEO_SIZE"):
        load_config_from_env(
            {
                "PANOPTIX_API_BASE_URL": "http://api.example.test",
                "PANOPTIX_GATEWAY_ID": "gateway-1",
                "PANOPTIX_SYNTHETIC_VIDEO_SIZE": "640/360",
            }
        )


def test_load_config_from_env_rejects_invalid_synthetic_frame_rate() -> None:
    with pytest.raises(ConfigError, match="PANOPTIX_SYNTHETIC_FRAME_RATE"):
        load_config_from_env(
            {
                "PANOPTIX_API_BASE_URL": "http://api.example.test",
                "PANOPTIX_GATEWAY_ID": "gateway-1",
                "PANOPTIX_SYNTHETIC_FRAME_RATE": "0",
            }
        )


def test_load_config_from_env_rejects_invalid_synthetic_audio_frequency() -> None:
    with pytest.raises(ConfigError, match="PANOPTIX_SYNTHETIC_AUDIO_FREQUENCY"):
        load_config_from_env(
            {
                "PANOPTIX_API_BASE_URL": "http://api.example.test",
                "PANOPTIX_GATEWAY_ID": "gateway-1",
                "PANOPTIX_SYNTHETIC_AUDIO_FREQUENCY": "0",
            }
        )


def test_load_config_from_env_defaults_supervisor_settings_to_safe_values() -> None:
    config = load_config_from_env({
        "PANOPTIX_API_BASE_URL": "http://api.example.test",
        "PANOPTIX_GATEWAY_ID": "gateway-1",
    })

    assert config.supervise_mediamtx is False
    assert config.mediamtx_binary == "mediamtx"
    assert config.mediamtx_config_path.endswith("mediamtx.local.yml")


def test_load_config_from_env_rejects_bad_mediamtx_config_when_supervised() -> None:
    with pytest.raises(ConfigError, match="PANOPTIX_MEDIAMTX_CONFIG"):
        load_config_from_env({
            "PANOPTIX_API_BASE_URL": "http://api.example.test",
            "PANOPTIX_GATEWAY_ID": "gateway-1",
            "PANOPTIX_SUPERVISE_MEDIAMTX": "true",
            "PANOPTIX_MEDIAMTX_BINARY": "--mediamtx",
        })


def test_load_config_from_env_rejects_invalid_discovery_ports() -> None:
    with pytest.raises(ConfigError, match="PANOPTIX_DISCOVERY_PORTS"):
        load_config_from_env({
            "PANOPTIX_API_BASE_URL": "http://api.example.test",
            "PANOPTIX_GATEWAY_ID": "gateway-1",
            "PANOPTIX_DISCOVERY_PORTS": "554,70000",
        })


def test_load_config_from_env_rejects_invalid_discovery_limits() -> None:
    with pytest.raises(ConfigError, match="PANOPTIX_DISCOVERY_TIMEOUT_SECONDS"):
        load_config_from_env({
            "PANOPTIX_API_BASE_URL": "http://api.example.test",
            "PANOPTIX_GATEWAY_ID": "gateway-1",
            "PANOPTIX_DISCOVERY_TIMEOUT_SECONDS": "0",
        })
    with pytest.raises(ConfigError, match="PANOPTIX_DISCOVERY_MAX_HOSTS"):
        load_config_from_env({
            "PANOPTIX_API_BASE_URL": "http://api.example.test",
            "PANOPTIX_GATEWAY_ID": "gateway-1",
            "PANOPTIX_DISCOVERY_MAX_HOSTS": "0",
        })
