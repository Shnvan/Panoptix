from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from panoptix_edge_agent.config import AgentConfig
from panoptix_edge_agent.control import ControlSupervisorResult, GatewayControlClient
from panoptix_edge_agent.control import GatewayControlSupervisor as ControlSupervisor
from panoptix_edge_agent.executor import CommandExecutor
from panoptix_edge_agent.mediamtx_process import (
    MediamtxProcessCommand,
    MediamtxProcessManager,
    MediamtxStartResult,
    MediamtxStopResult,
)
from panoptix_edge_agent.runner import HeartbeatResult, HeartbeatRunner


class HeartbeatLoop(Protocol):
    def run_once(self) -> HeartbeatResult: ...


class ControlLoop(Protocol):
    async def run_once(
        self,
        *,
        cycles: int = 1,
        max_messages: int = 1,
        stop_after_success: bool = False,
    ) -> ControlSupervisorResult: ...


class MediamtxManager(Protocol):
    def start(self) -> MediamtxStartResult: ...

    def stop(self) -> MediamtxStopResult: ...


@dataclass(frozen=True)
class GatewayRuntimeSupervisorResult:
    ok: bool
    heartbeat_ok: bool = False
    control_connected_cycles: int = 0
    control_failed_cycles: int = 0
    control_stopped_reason: str | None = None
    mediamtx_started: bool = False
    mediamtx_stopped: bool = False
    error: str | None = None


class GatewayRuntimeSupervisor:
    def __init__(
        self,
        heartbeat_runner: HeartbeatLoop,
        control_supervisor: ControlLoop,
        *,
        mediamtx_manager: MediamtxManager | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        cycle_delay_seconds: float = 1.0,
    ) -> None:
        if cycle_delay_seconds < 0:
            raise ValueError("cycle_delay_seconds must be greater than or equal to 0")
        self.heartbeat_runner = heartbeat_runner
        self.control_supervisor = control_supervisor
        self.mediamtx_manager = mediamtx_manager
        self.sleep = sleep
        self.cycle_delay_seconds = cycle_delay_seconds

    async def run_once(self, *, max_messages: int = 1) -> GatewayRuntimeSupervisorResult:
        mediamtx_started = False
        if self.mediamtx_manager is not None:
            start_result = self.mediamtx_manager.start()
            if not start_result.ok:
                return GatewayRuntimeSupervisorResult(
                    ok=False,
                    error=start_result.error or "mediamtx-start-failed",
                )
            mediamtx_started = start_result.started

        try:
            heartbeat_result = self.heartbeat_runner.run_once()
            if not heartbeat_result.ok:
                return self._with_mediamtx_stop(
                    GatewayRuntimeSupervisorResult(
                        ok=False,
                        heartbeat_ok=False,
                        mediamtx_started=mediamtx_started,
                        error=heartbeat_result.error or "heartbeat-failed",
                    )
                )

            control_result = await self.control_supervisor.run_once(
                cycles=1,
                max_messages=max_messages,
                stop_after_success=True,
            )
            ok = control_result.connected_cycles > 0
            return self._with_mediamtx_stop(
                GatewayRuntimeSupervisorResult(
                    ok=ok,
                    heartbeat_ok=True,
                    control_connected_cycles=control_result.connected_cycles,
                    control_failed_cycles=control_result.failed_cycles,
                    control_stopped_reason=control_result.stopped_reason,
                    mediamtx_started=mediamtx_started,
                    error=None if ok else "gateway-control-supervision-failed",
                )
            )
        except BaseException:
            self._stop_mediamtx()
            raise

    async def run_forever(self, *, max_messages: int = 1) -> None:
        if self.mediamtx_manager is not None:
            start_result = self.mediamtx_manager.start()
            if not start_result.ok:
                raise RuntimeError(start_result.error or "mediamtx-start-failed")
        try:
            while True:
                self.heartbeat_runner.run_once()
                await self.control_supervisor.run_once(
                    cycles=1,
                    max_messages=max_messages,
                    stop_after_success=False,
                )
                await self.sleep(self.cycle_delay_seconds)
        finally:
            self._stop_mediamtx()

    def _stop_mediamtx(self) -> MediamtxStopResult | None:
        if self.mediamtx_manager is None:
            return None
        return self.mediamtx_manager.stop()

    def _with_mediamtx_stop(
        self,
        result: GatewayRuntimeSupervisorResult,
    ) -> GatewayRuntimeSupervisorResult:
        stop_result = self._stop_mediamtx()
        if stop_result is None:
            return result
        return GatewayRuntimeSupervisorResult(
            ok=result.ok and stop_result.ok,
            heartbeat_ok=result.heartbeat_ok,
            control_connected_cycles=result.control_connected_cycles,
            control_failed_cycles=result.control_failed_cycles,
            control_stopped_reason=result.control_stopped_reason,
            mediamtx_started=result.mediamtx_started,
            mediamtx_stopped=stop_result.stopped or stop_result.already_stopped,
            error=result.error if stop_result.ok else stop_result.error,
        )


def build_gateway_runtime_supervisor(
    config: AgentConfig,
    *,
    executor: CommandExecutor,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> GatewayRuntimeSupervisor:
    mediamtx_manager: MediamtxProcessManager | None = None
    if config.supervise_mediamtx:
        mediamtx_manager = MediamtxProcessManager(
            command=MediamtxProcessCommand(
                binary=config.mediamtx_binary,
                config_path=config.mediamtx_config_path,
            )
        )
    return GatewayRuntimeSupervisor(
        HeartbeatRunner(config, executor=executor),
        ControlSupervisor(GatewayControlClient(config, executor=executor)),
        mediamtx_manager=mediamtx_manager,
        sleep=sleep,
        cycle_delay_seconds=config.heartbeat_interval_seconds,
    )
