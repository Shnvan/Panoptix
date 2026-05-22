from __future__ import annotations

from ua_parser import parse


def device_detail_payload(user_agent: str | None) -> dict[str, dict[str, object | None]]:
    parsed = parse(user_agent or "")
    parsed_browser = parsed.user_agent
    parsed_os = parsed.os
    parsed_device = parsed.device
    return {
        "browser": {
            "family": parsed_browser.family if parsed_browser else None,
            "version": _parsed_version(parsed_browser),
        },
        "os": {
            "family": parsed_os.family if parsed_os else None,
            "version": _parsed_version(parsed_os),
        },
        "device": {
            "family": parsed_device.family if parsed_device else None,
            "brand": parsed_device.brand if parsed_device else None,
            "model": parsed_device.model if parsed_device else None,
            "device_class": _device_class(user_agent, parsed_os.family if parsed_os else None),
        },
    }


def _parsed_version(parsed: object | None) -> str | None:
    if parsed is None:
        return None
    parts = [
        getattr(parsed, "major", None),
        getattr(parsed, "minor", None),
        getattr(parsed, "patch", None),
        getattr(parsed, "patch_minor", None),
    ]
    version = ".".join(str(part) for part in parts if part is not None)
    return version or None


def _device_class(user_agent: str | None, os_family: str | None) -> str:
    if not user_agent:
        return "unknown"
    lowered = user_agent.lower()
    if "ipad" in lowered or "tablet" in lowered:
        return "tablet"
    if "mobile" in lowered or "iphone" in lowered:
        return "mobile"
    if os_family in {"Windows", "Mac OS X", "Linux", "Ubuntu", "Chrome OS"}:
        return "desktop"
    return "unknown"
