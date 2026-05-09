from __future__ import annotations

import pytest

from panoptix_edge_agent.config import ConfigError, load_config_from_env


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
            "PANOPTIX_GATEWAY_COMMAND_SIGNING_KEY": "test-signing-key",
            "PANOPTIX_GATEWAY_CONTROL_WS_PATH": "/custom/ws",
            "PANOPTIX_GATEWAY_CONTROL_RECONNECT_ATTEMPTS": "5",
            "PANOPTIX_GATEWAY_CONTROL_RECONNECT_BACKOFF_SECONDS": "2.5",
        }
    )

    assert config.normalized_api_base_url == "http://api.example.test"
    assert config.gateway_id == "gateway-1"
    assert config.heartbeat_interval_seconds == 15
    assert config.request_timeout_seconds == 2.5
    assert config.agent_version == "0.2.0"
    assert config.camera_ids == ("camera-1", "camera-2")
    assert config.dev_identity_enabled is True
    assert config.command_signing_key == "test-signing-key"
    assert config.control_ws_path == "/custom/ws"
    assert config.control_reconnect_attempts == 5
    assert config.control_reconnect_backoff_seconds == 2.5


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
