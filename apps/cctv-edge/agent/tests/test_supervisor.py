from __future__ import annotations

import asyncio

import pytest

from panoptix_edge_agent.config import AgentConfig
from panoptix_edge_agent.control import ControlSupervisorResult
from panoptix_edge_agent.mediamtx_process import MediamtxStartResult, MediamtxStopResult
from panoptix_edge_agent.runner import HeartbeatResult
from panoptix_edge_agent.supervisor import GatewayRuntimeSupervisor


class FakeHeartbeatRunner:
    def __init__(self, result: HeartbeatResult | None = None) -> None:
        self.result = HeartbeatResult(ok=True) if result is None else result
        self.calls = 0

    def run_once(self) -> HeartbeatResult:
        self.calls += 1
        return self.result


class FakeControlSupervisor:
    def __init__(self, result: ControlSupervisorResult | None = None) -> None:
        self.result = (
            ControlSupervisorResult(cycles=1, connected_cycles=1, stopped_reason="connected")
            if result is None
            else result
        )
        self.calls: list[dict[str, object]] = []

    async def run_once(
        self,
        *,
        cycles: int = 1,
        max_messages: int = 1,
        stop_after_success: bool = False,
    ) -> ControlSupervisorResult:
        self.calls.append({
            "cycles": cycles,
            "max_messages": max_messages,
            "stop_after_success": stop_after_success,
        })
        return self.result


class FakeMediamtxManager:
    def __init__(
        self,
        start_result: MediamtxStartResult | None = None,
        stop_result: MediamtxStopResult | None = None,
    ) -> None:
        self.start_result = (
            MediamtxStartResult(ok=True, started=True)
            if start_result is None
            else start_result
        )
        self.stop_result = (
            MediamtxStopResult(ok=True, stopped=True)
            if stop_result is None
            else stop_result
        )
        self.start_calls = 0
        self.stop_calls = 0

    def start(self) -> MediamtxStartResult:
        self.start_calls += 1
        return self.start_result

    def stop(self) -> MediamtxStopResult:
        self.stop_calls += 1
        return self.stop_result


async def _cancel_sleep(_delay: float) -> None:
    raise asyncio.CancelledError


def _config(**overrides: object) -> AgentConfig:
    values: dict[str, object] = {
        "api_base_url": "http://api.example.test",
        "gateway_id": "gateway-1",
        "command_signing_key": "test-signing-key",
    }
    values.update(overrides)
    return AgentConfig(**values)


def test_runtime_supervisor_run_once_starts_and_stops_mediamtx() -> None:
    heartbeat = FakeHeartbeatRunner()
    control = FakeControlSupervisor()
    mediamtx = FakeMediamtxManager()
    supervisor = GatewayRuntimeSupervisor(
        heartbeat,
        control,
        mediamtx_manager=mediamtx,
    )

    result = asyncio.run(supervisor.run_once(max_messages=2))

    assert result.ok is True
    assert result.heartbeat_ok is True
    assert result.control_connected_cycles == 1
    assert result.control_stopped_reason == "connected"
    assert result.mediamtx_started is True
    assert result.mediamtx_stopped is True
    assert heartbeat.calls == 1
    assert control.calls == [{"cycles": 1, "max_messages": 2, "stop_after_success": True}]
    assert mediamtx.start_calls == 1
    assert mediamtx.stop_calls == 1


def test_runtime_supervisor_can_run_without_mediamtx() -> None:
    supervisor = GatewayRuntimeSupervisor(
        FakeHeartbeatRunner(),
        FakeControlSupervisor(),
    )

    result = asyncio.run(supervisor.run_once())

    assert result.ok is True
    assert result.mediamtx_started is False
    assert result.mediamtx_stopped is False


def test_runtime_supervisor_reports_mediamtx_start_failure() -> None:
    mediamtx = FakeMediamtxManager(MediamtxStartResult(ok=False, error="spawn failed"))
    heartbeat = FakeHeartbeatRunner()
    control = FakeControlSupervisor()
    supervisor = GatewayRuntimeSupervisor(
        heartbeat,
        control,
        mediamtx_manager=mediamtx,
    )

    result = asyncio.run(supervisor.run_once())

    assert result.ok is False
    assert result.error == "spawn failed"
    assert heartbeat.calls == 0
    assert control.calls == []
    assert mediamtx.start_calls == 1
    assert mediamtx.stop_calls == 0


def test_runtime_supervisor_stops_mediamtx_when_heartbeat_fails() -> None:
    mediamtx = FakeMediamtxManager()
    supervisor = GatewayRuntimeSupervisor(
        FakeHeartbeatRunner(HeartbeatResult(ok=False, error="heartbeat failed")),
        FakeControlSupervisor(),
        mediamtx_manager=mediamtx,
    )

    result = asyncio.run(supervisor.run_once())

    assert result.ok is False
    assert result.error == "heartbeat failed"
    assert result.mediamtx_stopped is True
    assert mediamtx.stop_calls == 1


def test_runtime_supervisor_reports_control_failure() -> None:
    supervisor = GatewayRuntimeSupervisor(
        FakeHeartbeatRunner(),
        FakeControlSupervisor(ControlSupervisorResult(cycles=1, failed_cycles=1)),
    )

    result = asyncio.run(supervisor.run_once())

    assert result.ok is False
    assert result.heartbeat_ok is True
    assert result.control_failed_cycles == 1
    assert result.error == "gateway-control-supervision-failed"


def test_runtime_supervisor_run_forever_stops_mediamtx_on_cancellation() -> None:
    mediamtx = FakeMediamtxManager()
    supervisor = GatewayRuntimeSupervisor(
        FakeHeartbeatRunner(),
        FakeControlSupervisor(),
        mediamtx_manager=mediamtx,
        sleep=_cancel_sleep,
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(supervisor.run_forever())

    assert mediamtx.start_calls == 1
    assert mediamtx.stop_calls == 1


def test_runtime_supervisor_rejects_negative_cycle_delay() -> None:
    with pytest.raises(ValueError, match="cycle_delay_seconds"):
        GatewayRuntimeSupervisor(
            FakeHeartbeatRunner(),
            FakeControlSupervisor(),
            cycle_delay_seconds=-0.1,
        )
