from __future__ import annotations

import asyncio
import json
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, AsyncContextManager, Protocol
from urllib.parse import urlsplit, urlunsplit

from panoptix_edge_agent.command_execution import LoopBoundCommandExecutor, loop_bound_executor
from panoptix_edge_agent.commands import (
    CommandVerificationError,
    GatewayCommand,
    verify_gateway_command,
)
from panoptix_edge_agent.config import AgentConfig
from panoptix_edge_agent.executor import CommandExecutor
from panoptix_edge_agent.media import StubMediaController


class ControlClientError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True) -> None:
        self.retryable = retryable
        super().__init__(message)


class WebSocketConnection(Protocol):
    async def recv(self) -> str | bytes:
        raise NotImplementedError

    async def send(self, message: str | bytes) -> None:
        raise NotImplementedError


class WebSocketConnector(Protocol):
    def connect(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> AsyncContextManager[WebSocketConnection]:
        raise NotImplementedError


class WebSocketsConnector:
    def connect(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> AsyncContextManager[WebSocketConnection]:
        try:
            import websockets
        except ImportError as exc:
            raise ControlClientError(
                "websockets package is required for gateway control",
                retryable=False,
            ) from exc
        return websockets.connect(
            url,
            additional_headers=headers,
            open_timeout=timeout_seconds,
            close_timeout=timeout_seconds,
        )


@dataclass(frozen=True)
class ControlMessageResult:
    kind: str
    accepted: bool
    command_id: str | None = None
    error: str | None = None

    def ack_payload(self, gateway_id: str) -> dict[str, object] | None:
        if self.kind != "command":
            return None
        payload: dict[str, object] = {
            "type": "command_ack",
            "command_id": self.command_id,
            "gateway_id": gateway_id,
            "status": "accepted" if self.accepted else "rejected",
        }
        if self.error is not None:
            payload["error"] = self.error
        return payload


@dataclass(frozen=True)
class ControlRunResult:
    connected: bool
    hello_received: bool = False
    accepted_commands: int = 0
    rejected_commands: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ControlReconnectResult:
    connected: bool
    attempts: int
    result: ControlRunResult | None = None
    error: str | None = None
    retryable_failures: int = 0
    sleep_delays: tuple[float, ...] = field(default_factory=tuple)
    stopped_reason: str = "connected"


@dataclass(frozen=True)
class ControlSupervisorResult:
    cycles: int
    connected_cycles: int = 0
    failed_cycles: int = 0
    consecutive_failures: int = 0
    last_result: ControlReconnectResult | None = None
    stopped_reason: str = "cycle-limit"


class GatewayControlClient:
    def __init__(
        self,
        config: AgentConfig,
        connector: WebSocketConnector | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        executor: CommandExecutor | LoopBoundCommandExecutor | None = None,
    ) -> None:
        self.config = config
        self.connector = WebSocketsConnector() if connector is None else connector
        self.sleep = sleep
        raw_executor = executor if executor is not None else CommandExecutor(StubMediaController())
        self.executor = loop_bound_executor(raw_executor)

    @property
    def websocket_url(self) -> str:
        parsed = urlsplit(self.config.normalized_api_base_url)
        if parsed.scheme == "http":
            scheme = "ws"
        elif parsed.scheme == "https":
            scheme = "wss"
        else:
            raise ControlClientError(
                "PANOPTIX_API_BASE_URL must use http or https",
                retryable=False,
            )
        return urlunsplit((scheme, parsed.netloc, self.config.control_ws_path, "", ""))

    _RECONNECT_MAX_DELAY: float = 60.0

    async def run_with_reconnect(self, *, max_messages: int = 1) -> ControlReconnectResult:
        final_error: str | None = None
        retryable_failures = 0
        sleep_delays: list[float] = []
        for attempt in range(1, self.config.control_reconnect_attempts + 1):
            try:
                result = await self.run_once(max_messages=max_messages)
            except ControlClientError as exc:
                final_error = str(exc)
                if exc.retryable:
                    retryable_failures += 1
                if not exc.retryable or attempt >= self.config.control_reconnect_attempts:
                    return ControlReconnectResult(
                        connected=False,
                        attempts=attempt,
                        error=final_error,
                        retryable_failures=retryable_failures,
                        sleep_delays=tuple(sleep_delays),
                        stopped_reason="exhausted-retries" if exc.retryable else "non-retryable-error",
                    )
                base = self.config.control_reconnect_backoff_seconds
                attempt_index = attempt - 1
                delay = min(base * (2 ** attempt_index), self._RECONNECT_MAX_DELAY) + random.uniform(0, base)
                sleep_delays.append(delay)
                await self.sleep(delay)
                continue
            return ControlReconnectResult(
                connected=True,
                attempts=attempt,
                result=result,
                retryable_failures=retryable_failures,
                sleep_delays=tuple(sleep_delays),
                stopped_reason="connected",
            )
        return ControlReconnectResult(
            connected=False,
            attempts=self.config.control_reconnect_attempts,
            error=final_error,
            retryable_failures=retryable_failures,
            sleep_delays=tuple(sleep_delays),
            stopped_reason="exhausted-retries",
        )

    async def run_once(self, *, max_messages: int = 1) -> ControlRunResult:
        if max_messages < 1:
            raise ControlClientError("max_messages must be at least 1", retryable=False)

        errors: list[str] = []
        hello_received = False
        accepted_commands = 0
        rejected_commands = 0
        received_messages = 0

        try:
            async with self.connector.connect(
                self.websocket_url,
                self._headers(),
                self.config.request_timeout_seconds,
            ) as websocket:
                while accepted_commands + rejected_commands < max_messages:
                    timeout_seconds = (
                        self.config.request_timeout_seconds
                        if received_messages == 0
                        else min(self.config.request_timeout_seconds, 1.0)
                    )
                    try:
                        raw_message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=timeout_seconds,
                        )
                    except (asyncio.TimeoutError, IndexError):
                        if received_messages > 0:
                            break
                        raise

                    received_messages += 1
                    result = await self.handle_message(raw_message)
                    if result.kind == "hello" and result.accepted:
                        hello_received = True
                    elif result.kind == "command" and result.accepted:
                        accepted_commands += 1
                    elif result.kind == "command":
                        rejected_commands += 1
                    ack_payload = result.ack_payload(self.config.gateway_id)
                    if ack_payload is not None:
                        await websocket.send(json.dumps(ack_payload))
                    if result.error is not None:
                        errors.append(result.error)
        except ControlClientError:
            raise
        except Exception as exc:
            raise ControlClientError(f"gateway control websocket failed: {exc}") from exc

        return ControlRunResult(
            connected=True,
            hello_received=hello_received,
            accepted_commands=accepted_commands,
            rejected_commands=rejected_commands,
            errors=tuple(errors),
        )

    async def handle_message(self, raw_message: str | bytes) -> ControlMessageResult:
        data = _decode_message(raw_message)
        if data.get("type") == "connected":
            return self._handle_hello(data)
        return await self._handle_command(data)

    def _handle_hello(self, data: dict[str, Any]) -> ControlMessageResult:
        if data.get("gateway_id") != self.config.gateway_id:
            return ControlMessageResult(
                kind="hello",
                accepted=False,
                error="gateway-control-hello-target-mismatch",
            )
        return ControlMessageResult(kind="hello", accepted=True)

    async def _handle_command(self, data: dict[str, Any]) -> ControlMessageResult:
        command_id = str(data["command_id"]) if "command_id" in data else None
        try:
            command = GatewayCommand.from_dict(data)
            verify_gateway_command(
                command,
                self.config.command_signing_key,
                expected_gateway_id=self.config.gateway_id,
            )
        except (KeyError, CommandVerificationError) as exc:
            return ControlMessageResult(
                kind="command",
                accepted=False,
                command_id=command_id,
                error=str(exc),
            )
        exec_result = await self.executor.execute(command)
        if not exec_result.accepted:
            return ControlMessageResult(
                kind="command",
                accepted=False,
                command_id=command.command_id,
                error=exec_result.error,
            )
        return ControlMessageResult(kind="command", accepted=True, command_id=command.command_id)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.config.dev_identity_enabled:
            headers["x-panoptix-dev-gateway-id"] = self.config.gateway_id
            return headers

        service_token = self.config.gateway_service_token.strip()
        if not service_token:
            raise ControlClientError(
                "PANOPTIX_GATEWAY_SERVICE_TOKEN is required when dev gateway identity is disabled",
                retryable=False,
            )
        headers["x-panoptix-gateway-id"] = self.config.gateway_id
        headers["Authorization"] = f"Bearer {service_token}"

        cf_access_client_id = self.config.cf_access_client_id.strip()
        cf_access_client_secret = self.config.cf_access_client_secret.strip()
        if bool(cf_access_client_id) != bool(cf_access_client_secret):
            raise ControlClientError(
                "PANOPTIX_CF_ACCESS_CLIENT_ID and PANOPTIX_CF_ACCESS_CLIENT_SECRET must be configured together",
                retryable=False,
            )
        if cf_access_client_id and cf_access_client_secret:
            headers["CF-Access-Client-Id"] = cf_access_client_id
            headers["CF-Access-Client-Secret"] = cf_access_client_secret
        return headers


class GatewayControlSupervisor:
    def __init__(
        self,
        client: GatewayControlClient,
        *,
        cycle_delay_seconds: float | None = None,
    ) -> None:
        if cycle_delay_seconds is not None and cycle_delay_seconds < 0:
            raise ControlClientError("cycle_delay_seconds must be greater than or equal to 0", retryable=False)
        self.client = client
        self.cycle_delay_seconds = (
            client.config.control_reconnect_backoff_seconds
            if cycle_delay_seconds is None
            else cycle_delay_seconds
        )

    async def run_once(
        self,
        *,
        cycles: int = 1,
        max_messages: int = 1,
        stop_after_success: bool = False,
    ) -> ControlSupervisorResult:
        if cycles < 1:
            raise ControlClientError("cycles must be at least 1", retryable=False)

        connected_cycles = 0
        failed_cycles = 0
        consecutive_failures = 0
        last_result: ControlReconnectResult | None = None
        stopped_reason = "cycle-limit"

        for cycle in range(1, cycles + 1):
            result = await self.client.run_with_reconnect(max_messages=max_messages)
            last_result = result
            if result.connected:
                connected_cycles += 1
                consecutive_failures = 0
                if stop_after_success:
                    stopped_reason = "connected"
                    break
            else:
                failed_cycles += 1
                consecutive_failures += 1
                if result.stopped_reason == "non-retryable-error":
                    stopped_reason = "non-retryable-error"
                    break
            if cycle < cycles:
                await self.client.sleep(self.cycle_delay_seconds)

        return ControlSupervisorResult(
            cycles=connected_cycles + failed_cycles,
            connected_cycles=connected_cycles,
            failed_cycles=failed_cycles,
            consecutive_failures=consecutive_failures,
            last_result=last_result,
            stopped_reason=stopped_reason,
        )

    async def run_forever(self, *, max_messages: int = 1) -> None:
        while True:
            await self.run_once(cycles=1, max_messages=max_messages)
            await self.client.sleep(self.cycle_delay_seconds)


def _decode_message(raw_message: str | bytes) -> dict[str, Any]:
    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode("utf-8")
    try:
        decoded = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        raise ControlClientError(
            "gateway control message was not valid JSON",
            retryable=False,
        ) from exc
    if not isinstance(decoded, dict):
        raise ControlClientError(
            "gateway control message JSON must be an object",
            retryable=False,
        )
    return decoded
