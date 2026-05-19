from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class MediamtxProcessError(ValueError):
    pass


class ManagedProcess(Protocol):
    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def kill(self) -> None: ...


DEFAULT_MEDIAMTX_CONFIG_PATH = Path(__file__).resolve().parents[3] / "mediamtx" / "mediamtx.local.yml"


@dataclass(frozen=True)
class MediamtxProcessCommand:
    binary: str = "mediamtx"
    config_path: str | Path = DEFAULT_MEDIAMTX_CONFIG_PATH

    def args(self) -> list[str]:
        binary = _validate_arg(self.binary, "binary")
        config_path = _validate_config_path(self.config_path)
        return [binary, config_path]


@dataclass(frozen=True)
class MediamtxStartResult:
    ok: bool
    started: bool = False
    already_running: bool = False
    command: tuple[str, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class MediamtxStopResult:
    ok: bool
    stopped: bool = False
    already_stopped: bool = False
    killed: bool = False
    error: str | None = None


ProcessFactory = Callable[[Sequence[str]], ManagedProcess]


class MediamtxProcessManager:
    def __init__(
        self,
        command: MediamtxProcessCommand | None = None,
        process_factory: ProcessFactory | None = None,
        stop_timeout_seconds: float = 5.0,
    ) -> None:
        self.command = MediamtxProcessCommand() if command is None else command
        self.process_factory = _default_process_factory if process_factory is None else process_factory
        self.stop_timeout_seconds = stop_timeout_seconds
        self.process: ManagedProcess | None = None

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> MediamtxStartResult:
        if self.is_running():
            return MediamtxStartResult(
                ok=False,
                already_running=True,
                error="mediamtx-already-running",
            )
        self.process = None
        try:
            args = self.command.args()
            process = self.process_factory(args)
        except (MediamtxProcessError, OSError) as exc:
            return MediamtxStartResult(ok=False, error=str(exc))
        if process.poll() is not None:
            return MediamtxStartResult(
                ok=False,
                command=tuple(args),
                error="mediamtx-exited-immediately",
            )
        self.process = process
        return MediamtxStartResult(ok=True, started=True, command=tuple(args))

    def stop(self) -> MediamtxStopResult:
        if not self.is_running():
            self.process = None
            return MediamtxStopResult(ok=True, already_stopped=True)
        process = self.process
        if process is None:
            return MediamtxStopResult(ok=True, already_stopped=True)
        try:
            process.terminate()
            process.wait(timeout=self.stop_timeout_seconds)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=self.stop_timeout_seconds)
            except OSError as exc:
                return MediamtxStopResult(ok=False, error=str(exc))
            self.process = None
            return MediamtxStopResult(ok=True, stopped=True, killed=True)
        except OSError as exc:
            return MediamtxStopResult(ok=False, error=str(exc))
        self.process = None
        return MediamtxStopResult(ok=True, stopped=True)


def build_mediamtx_process_args(command: MediamtxProcessCommand | None = None) -> list[str]:
    selected = MediamtxProcessCommand() if command is None else command
    return selected.args()


def _default_process_factory(args: Sequence[str]) -> ManagedProcess:
    return subprocess.Popen(list(args))


def _validate_config_path(raw: str | Path) -> str:
    value = _validate_arg(str(raw), "config_path")
    path = Path(value)
    if path.name != "mediamtx.local.yml" and path.suffix not in {".yml", ".yaml"}:
        raise MediamtxProcessError("config_path must reference a YAML config file")
    if path.is_dir():
        raise MediamtxProcessError("config_path must reference a file")
    if not path.exists():
        raise MediamtxProcessError("config_path does not exist")
    return str(path)


def _validate_arg(raw: str, name: str) -> str:
    value = raw.strip()
    if not value:
        raise MediamtxProcessError(f"{name} is required")
    if value.startswith("-"):
        raise MediamtxProcessError(f"{name} must not start with -")
    if any(character in value for character in {"\x00", "\n", "\r"}):
        raise MediamtxProcessError(f"{name} contains an invalid character")
    return value
