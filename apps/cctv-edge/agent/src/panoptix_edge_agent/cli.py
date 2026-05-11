from __future__ import annotations

import argparse
import asyncio
import sys

from panoptix_edge_agent.config import ConfigError, load_config_from_env
from panoptix_edge_agent.control import (
    ControlClientError,
    GatewayControlClient,
    GatewayControlSupervisor,
)
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
    parser.add_argument(
        "--control-loop-once",
        action="store_true",
        help="run one bounded gateway control WebSocket reconnect loop and exit",
    )
    parser.add_argument(
        "--smoke-ffmpeg-livekit",
        action="store_true",
        help="run a real FFmpeg-to-LiveKit smoke test (requires PANOPTIX_SMOKE_* env vars, FFmpeg, and LiveKit SDK)",
    )
    parser.add_argument(
        "--supervise",
        action="store_true",
        help="run the edge gateway runtime supervisor",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.smoke_ffmpeg_livekit:
        return _run_smoke_ffmpeg_livekit()

    try:
        config = load_config_from_env()
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    from panoptix_edge_agent.executor import CommandExecutor
    from panoptix_edge_agent.media_factory import build_media_controller

    factory_result = build_media_controller(config)
    if factory_result.error is not None:
        print(
            f"media controller warning: {factory_result.error} "
            f"(falling back to stub)",
            file=sys.stderr,
        )
    executor = CommandExecutor(factory_result.controller)

    if args.supervise:
        return _run_supervisor(config, executor)

    if args.control_once:
        try:
            control_result = asyncio.run(
                GatewayControlClient(config, executor=executor).run_once()
            )
        except ControlClientError as exc:
            print(f"gateway control failed: {exc}", file=sys.stderr)
            return 1
        if not control_result.hello_received and control_result.accepted_commands == 0:
            print("gateway control connected without accepted messages", file=sys.stderr)
            return 1
        print("gateway control accepted")
        return 0

    if args.control_loop_once:
        supervisor_result = asyncio.run(
            GatewayControlSupervisor(
                GatewayControlClient(config, executor=executor)
            ).run_once(stop_after_success=True)
        )
        reconnect_result = supervisor_result.last_result
        if reconnect_result is None or not reconnect_result.connected:
            error = reconnect_result.error if reconnect_result is not None else "no reconnect result"
            print(f"gateway control reconnect failed: {error}", file=sys.stderr)
            return 1
        print(
            "gateway control reconnect accepted "
            f"after {reconnect_result.attempts} attempt(s); "
            f"supervisor stopped: {supervisor_result.stopped_reason}"
        )
        return 0

    runner = HeartbeatRunner(config, executor=executor)
    if args.once:
        heartbeat_result = runner.run_once()
        if not heartbeat_result.ok:
            print(f"heartbeat failed: {heartbeat_result.error}", file=sys.stderr)
            return 1
        print("heartbeat accepted")
        return 0

    runner.run_forever()
    return 0


def _run_smoke_ffmpeg_livekit() -> int:
    from panoptix_edge_agent.smoke_config import SmokeConfigError, load_smoke_config
    from panoptix_edge_agent.smoke_ffmpeg_livekit import run_smoke

    try:
        smoke_config = load_smoke_config()
    except SmokeConfigError as exc:
        print(f"smoke config error: {exc}", file=sys.stderr)
        return 2

    print(
        f"smoke: starting FFmpeg-to-LiveKit smoke test\n"
        f"  livekit_url: {smoke_config.livekit_url}\n"
        f"  rtsp_url:    {smoke_config.rtsp_url}\n"
        f"  room:        {smoke_config.room}\n"
        f"  camera_id:   {smoke_config.camera_id}\n"
        f"  duration:    {smoke_config.duration_seconds}s\n"
        f"  resolution:  {smoke_config.width}x{smoke_config.height}@{smoke_config.frame_rate}fps"
    )

    result = asyncio.run(run_smoke(smoke_config))

    if result.ok:
        print(
            f"smoke: PASSED\n"
            f"  frames_published: {result.frames_published}\n"
            f"  duration:         {result.duration_seconds}s\n"
            f"  cleanup_ok:       {result.cleanup_ok}"
        )
        if not result.cleanup_ok:
            print(f"  cleanup_error:    {result.cleanup_error}", file=sys.stderr)
            return 1
        return 0

    print(f"smoke: FAILED — {result.error}", file=sys.stderr)
    return 1


def _run_supervisor(config: object, executor: object) -> int:
    from typing import cast

    from panoptix_edge_agent.config import AgentConfig
    from panoptix_edge_agent.executor import CommandExecutor
    from panoptix_edge_agent.supervisor import build_gateway_runtime_supervisor

    typed_config = cast(AgentConfig, config)
    typed_executor = cast(CommandExecutor, executor)
    try:
        asyncio.run(
            build_gateway_runtime_supervisor(
                typed_config,
                executor=typed_executor,
            ).run_forever()
        )
    except KeyboardInterrupt:
        print("gateway supervisor stopped")
        return 0
    except RuntimeError as exc:
        print(f"gateway supervisor failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
