from __future__ import annotations

import argparse
import sys

from panoptix_edge_agent.config import ConfigError, load_config_from_env
from panoptix_edge_agent.runner import HeartbeatRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="panoptix-edge-agent")
    parser.add_argument(
        "--once",
        action="store_true",
        help="send one heartbeat and exit instead of running continuously",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config_from_env()
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    runner = HeartbeatRunner(config)
    if args.once:
        result = runner.run_once()
        if not result.ok:
            print(f"heartbeat failed: {result.error}", file=sys.stderr)
            return 1
        print("heartbeat accepted")
        return 0

    runner.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
