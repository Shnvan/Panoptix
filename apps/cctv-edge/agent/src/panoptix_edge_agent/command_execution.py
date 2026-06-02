from __future__ import annotations

import asyncio
import threading
from typing import Protocol

from panoptix_edge_agent.commands import GatewayCommand
from panoptix_edge_agent.executor import CommandExecutionResult, CommandExecutor


class AsyncCommandExecutor(Protocol):
    async def execute(self, command: GatewayCommand) -> CommandExecutionResult: ...


class LoopBoundCommandExecutor:
    """Run command execution on one persistent event loop.

    LiveKit publisher sessions keep asyncio tasks alive between commands. Running each
    command with a new asyncio.run() closes the task-owning loop and breaks cleanup.
    """

    def __init__(self, executor: AsyncCommandExecutor) -> None:
        self._executor = executor
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    async def execute(self, command: GatewayCommand) -> CommandExecutionResult:
        return await asyncio.to_thread(self.execute_blocking, command)

    def execute_blocking(self, command: GatewayCommand) -> CommandExecutionResult:
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(self._executor.execute(command), loop)
        return future.result()

    def close(self) -> None:
        with self._lock:
            loop = self._loop
            thread = self._thread
            if loop is None:
                return
            loop.call_soon_threadsafe(loop.stop)
            self._loop = None
            self._thread = None
            self._ready.clear()
        if thread is not None:
            thread.join(timeout=5)

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is not None and self._loop.is_running():
                return self._loop
            self._ready.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="panoptix-command-executor-loop",
                daemon=True,
            )
            self._thread.start()
        self._ready.wait(timeout=5)
        with self._lock:
            if self._loop is None:
                raise RuntimeError("command executor event loop did not start")
            return self._loop

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._lock:
            self._loop = loop
            self._ready.set()
        try:
            loop.run_forever()
        finally:
            loop.close()


def loop_bound_executor(executor: CommandExecutor | LoopBoundCommandExecutor) -> LoopBoundCommandExecutor:
    if isinstance(executor, LoopBoundCommandExecutor):
        return executor
    return LoopBoundCommandExecutor(executor)
