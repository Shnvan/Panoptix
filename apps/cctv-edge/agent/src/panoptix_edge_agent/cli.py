from __future__ import annotations

import argparse
import asyncio
import sys

from panoptix_edge_agent.config import ConfigError, load_config_from_env
from panoptix_edge_agent.control import ControlClientError, GatewayControlClient
from panoptix_edge_agent.runner import HeartbeatRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="panoptix-edge-agent")
    parser.add_argument(
        "--once",
        action="store_true",
        help="send one heartbeat and exit instead of running continuously",
    )
    parser.add_argument(
        "--control-once",
        action="store_true",
        help="connect to gateway control WebSocket, read one message, and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config_from_env()
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    if args.control_once:
        try:
            control_result = asyncio.run(GatewayControlClient(config).run_once())
        except ControlClientError as exc:
            print(f"gateway control failed: {exc}", file=sys.stderr)
            return 1
        if not control_result.hello_received and control_result.accepted_commands == 0:
            print("gateway control connected without accepted messages", file=sys.stderr)
            return 1
        print("gateway control accepted")
        return 0

    runner = HeartbeatRunner(config)
    if args.once:
        heartbeat_result = runner.run_once()
        if not heartbeat_result.ok:
            print(f"heartbeat failed: {heartbeat_result.error}", file=sys.stderr)
            return 1
        print("heartbeat accepted")
        return 0

    runner.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
