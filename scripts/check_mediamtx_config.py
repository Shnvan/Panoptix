"""
check_mediamtx_config.py — validate a mediamtx YAML config for insecure settings.

Usage:
    python scripts/check_mediamtx_config.py path/to/mediamtx.yml

Exit codes:
    0 — no WARNs found
    1 — one or more WARNs found
"""

import sys
import yaml


def check_config(path: str) -> list[tuple[str, str]]:
    """Return a list of (level, message) findings for the given config file."""
    with open(path, "r") as fh:
        cfg = yaml.safe_load(fh) or {}

    findings: list[tuple[str, str]] = []

    # 1. Admin API enabled
    if cfg.get("api") in (True, "yes"):
        findings.append(
            ("WARN", "api is enabled — disable in production (set `api: no`)")
        )

    # 2. RTSP bound to all interfaces
    rtsp_addr = cfg.get("rtspAddress", "")
    if rtsp_addr.startswith("0.0.0.0") or rtsp_addr == "":
        findings.append(
            (
                "WARN",
                f"rtspAddress '{rtsp_addr or '(default 0.0.0.0:8554)'}' listens on all "
                "interfaces — bind to the camera VLAN interface IP instead",
            )
        )

    # 3. Paths without publish credentials
    paths = cfg.get("paths", {}) or {}
    for name, path_cfg in paths.items():
        path_cfg = path_cfg or {}
        has_user = bool(path_cfg.get("publishUser"))
        has_pass = bool(path_cfg.get("publishPass"))
        has_ip_filter = bool(path_cfg.get("publishIPs"))
        if not (has_user and has_pass) and not has_ip_filter:
            findings.append(
                (
                    "WARN",
                    f"path '{name}': no publishUser/publishPass or publishIPs — "
                    "unauthenticated publish is allowed",
                )
            )

        # 4. SRTP encryption not strict
        if path_cfg.get("encryption", "") != "strict":
            findings.append(
                (
                    "INFO",
                    f"path '{name}': encryption is not 'strict' — "
                    "consider enabling SRTP (`encryption: strict`)",
                )
            )

    return findings


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <mediamtx-config.yml>", file=sys.stderr)
        sys.exit(2)

    findings = check_config(sys.argv[1])
    for level, msg in findings:
        print(f"[{level}] {msg}")

    has_warns = any(level == "WARN" for level, _ in findings)
    sys.exit(1 if has_warns else 0)


if __name__ == "__main__":
    main()
