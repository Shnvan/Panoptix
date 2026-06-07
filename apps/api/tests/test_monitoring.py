from __future__ import annotations

import json
from pathlib import Path

from cctv_api.monitoring import validate_health_file, validate_health_payload


def test_shallow_health_requires_ok() -> None:
    assert validate_health_payload("shallow", {"status": "ok"})[0] is True
    assert validate_health_payload("shallow", {"status": "degraded"}) == (
        False,
        "status=degraded",
    )


def test_deep_health_accepts_only_production_healthy_dependencies() -> None:
    healthy = {
        "status": "ok",
        "db": "connected",
        "livekit": "connected",
        "gateway": "connected",
        "assistant": "enabled",
    }
    assert validate_health_payload("deep", healthy)[0] is True


def test_deep_health_rejects_degraded_status() -> None:
    payload = {
        "status": "degraded",
        "db": "connected",
        "livekit": "connected",
        "gateway": "connected",
        "assistant": "enabled",
    }
    assert validate_health_payload("deep", payload) == (False, "status=degraded")


def test_deep_health_rejects_stale_gateway() -> None:
    payload = {
        "status": "degraded",
        "db": "connected",
        "livekit": "connected",
        "gateway": "stale",
        "assistant": "enabled",
    }
    assert validate_health_payload("deep", payload) == (
        False,
        "status=degraded, gateway=stale",
    )


def test_deep_health_rejects_not_configured_livekit_and_no_gateways() -> None:
    payload = {
        "status": "ok",
        "db": "connected",
        "livekit": "not_configured",
        "gateway": "no_gateways",
        "assistant": "enabled",
    }
    assert validate_health_payload("deep", payload) == (
        False,
        "livekit=not_configured, gateway=no_gateways",
    )


def test_health_file_rejects_malformed_json_without_echoing_content(tmp_path: Path) -> None:
    path = tmp_path / "health.json"
    path.write_text('{"token":"sensitive"', encoding="utf-8")
    assert validate_health_file("deep", path) == (
        False,
        "response body was not valid JSON",
    )


def test_health_file_reads_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "health.json"
    path.write_text(
        json.dumps(
            {
                "status": "ok",
                "db": "connected",
                "livekit": "connected",
                "gateway": "connected",
                "assistant": "enabled",
            }
        ),
        encoding="utf-8",
    )
    assert validate_health_file("deep", path)[0] is True


def test_deep_health_rejects_disabled_assistant_in_production() -> None:
    payload = {
        "status": "ok",
        "db": "connected",
        "livekit": "connected",
        "gateway": "connected",
        "assistant": "disabled",
    }
    assert validate_health_payload("deep", payload) == (
        False,
        "assistant=disabled",
    )
