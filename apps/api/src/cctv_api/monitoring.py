from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Literal

HealthKind = Literal["shallow", "deep"]


def validate_health_payload(kind: HealthKind, payload: object) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "response JSON must be an object"

    if kind == "shallow":
        status = _safe_status(payload.get("status"))
        if status != "ok":
            return False, f"status={status}"
        return True, "status=ok"

    expected = {
        "status": "ok",
        "db": "connected",
        "livekit": "connected",
        "gateway": "connected",
        "assistant": "disabled",
    }
    observed = {field: _safe_status(payload.get(field)) for field in expected}
    failures = [
        f"{field}={observed[field]}"
        for field, required in expected.items()
        if observed[field] != required
    ]
    if failures:
        return False, ", ".join(failures)
    return True, "status=ok, db=connected, livekit=connected, gateway=connected"


def validate_health_file(kind: HealthKind, path: Path) -> tuple[bool, str]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "response body was not valid JSON"
    return validate_health_payload(kind, payload)


def _safe_status(value: object) -> str:
    if not isinstance(value, str):
        return "missing"
    normalized = value.strip().lower()
    if normalized in {
        "connected",
        "degraded",
        "disabled",
        "enabled",
        "error",
        "no_gateways",
        "not_configured",
        "not_connected",
        "ok",
        "stale",
    }:
        return normalized
    return "unexpected"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("shallow", "deep"))
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    healthy, summary = validate_health_file(args.kind, args.path)
    print(summary)
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
