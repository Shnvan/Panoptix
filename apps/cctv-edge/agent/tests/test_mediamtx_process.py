from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from panoptix_edge_agent.mediamtx_process import (
    DEFAULT_MEDIAMTX_CONFIG_PATH,
    MediamtxProcessCommand,
    MediamtxProcessError,
    MediamtxProcessManager,
    build_mediamtx_process_args,
)


class FakeProcess:
    def __init__(self, returncode: int | None = None, wait_error: BaseException | None = None) -> None:
        self.returncode = returncode
        self.wait_error = wait_error
        self.terminated = False
        self.killed = False
        self.wait_calls = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.wait_error is not None:
            error = self.wait_error
            self.wait_error = None
            raise error
        self.returncode = 0
        return 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


class RecordingProcessFactory:
    def __init__(self, process: FakeProcess | None = None) -> None:
        self.process = FakeProcess() if process is None else process
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args: Sequence[str]) -> FakeProcess:
        self.calls.append(tuple(args))
        return self.process


def test_build_mediamtx_process_args_returns_argument_list() -> None:
    args = build_mediamtx_process_args()

    assert isinstance(args, list)
    assert args[0] == "mediamtx"
    assert args[1] == str(DEFAULT_MEDIAMTX_CONFIG_PATH)
    assert args[1].endswith("mediamtx.local.yml")


def test_build_mediamtx_process_args_reflects_custom_values(tmp_path: Path) -> None:
    config_path = tmp_path / "custom.yml"
    config_path.write_text("api: no\n", encoding="utf-8")

    args = build_mediamtx_process_args(
        MediamtxProcessCommand(
            binary="mediamtx.exe",
            config_path=config_path,
        )
    )

    assert args == ["mediamtx.exe", str(config_path)]


def test_build_mediamtx_process_args_rejects_empty_binary() -> None:
    with pytest.raises(MediamtxProcessError, match="binary is required"):
        build_mediamtx_process_args(MediamtxProcessCommand(binary=""))


def test_build_mediamtx_process_args_rejects_binary_that_starts_with_dash() -> None:
    with pytest.raises(MediamtxProcessError, match="binary must not start"):
        build_mediamtx_process_args(MediamtxProcessCommand(binary="--mediamtx"))


def test_build_mediamtx_process_args_rejects_missing_config(tmp_path: Path) -> None:
    with pytest.raises(MediamtxProcessError, match="config_path does not exist"):
        build_mediamtx_process_args(MediamtxProcessCommand(config_path=tmp_path / "missing.yml"))


def test_build_mediamtx_process_args_rejects_non_yaml_config(tmp_path: Path) -> None:
    config_path = tmp_path / "mediamtx.txt"
    config_path.write_text("api: no\n", encoding="utf-8")

    with pytest.raises(MediamtxProcessError, match="YAML"):
        build_mediamtx_process_args(MediamtxProcessCommand(config_path=config_path))


def test_process_manager_starts_process_once() -> None:
    factory = RecordingProcessFactory()
    manager = MediamtxProcessManager(process_factory=factory)

    result = manager.start()

    assert result.ok is True
    assert result.started is True
    assert result.command == tuple(build_mediamtx_process_args())
    assert manager.is_running()
    assert factory.calls == [tuple(build_mediamtx_process_args())]


def test_process_manager_rejects_double_start() -> None:
    factory = RecordingProcessFactory()
    manager = MediamtxProcessManager(process_factory=factory)

    first = manager.start()
    second = manager.start()

    assert first.ok is True
    assert second.ok is False
    assert second.already_running is True
    assert second.error == "mediamtx-already-running"
    assert len(factory.calls) == 1


def test_process_manager_reports_immediate_exit() -> None:
    factory = RecordingProcessFactory(FakeProcess(returncode=1))
    manager = MediamtxProcessManager(process_factory=factory)

    result = manager.start()

    assert result.ok is False
    assert result.error == "mediamtx-exited-immediately"
    assert not manager.is_running()


def test_process_manager_reports_factory_failure() -> None:
    def factory(args: Sequence[str]) -> FakeProcess:
        raise OSError("spawn failed")

    manager = MediamtxProcessManager(process_factory=factory)

    result = manager.start()

    assert result.ok is False
    assert result.error == "spawn failed"


def test_process_manager_stops_gracefully() -> None:
    process = FakeProcess()
    manager = MediamtxProcessManager(process_factory=RecordingProcessFactory(process))
    manager.start()

    result = manager.stop()

    assert result.ok is True
    assert result.stopped is True
    assert result.killed is False
    assert process.terminated is True
    assert process.killed is False
    assert not manager.is_running()


def test_process_manager_stop_is_idempotent() -> None:
    manager = MediamtxProcessManager(process_factory=RecordingProcessFactory())

    result = manager.stop()

    assert result.ok is True
    assert result.already_stopped is True


def test_process_manager_kills_after_timeout() -> None:
    process = FakeProcess(wait_error=subprocess.TimeoutExpired(cmd="mediamtx", timeout=0.1))
    manager = MediamtxProcessManager(
        process_factory=RecordingProcessFactory(process),
        stop_timeout_seconds=0.1,
    )
    manager.start()

    result = manager.stop()

    assert result.ok is True
    assert result.stopped is True
    assert result.killed is True
    assert process.terminated is True
    assert process.killed is True
    assert process.wait_calls == 2
    assert not manager.is_running()


def test_process_manager_reports_stop_failure() -> None:
    process = FakeProcess(wait_error=OSError("wait failed"))
    manager = MediamtxProcessManager(process_factory=RecordingProcessFactory(process))
    manager.start()

    result = manager.stop()

    assert result.ok is False
    assert result.error == "wait failed"
