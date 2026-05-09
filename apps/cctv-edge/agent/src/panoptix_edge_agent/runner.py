from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from panoptix_edge_agent.client import AgentClientError, CameraStatusReport, GatewayApiClient
from panoptix_edge_agent.commands import (
    CommandVerificationError,
    GatewayCommand,
    verify_gateway_command,
)
from panoptix_edge_agent.config import AgentConfig


@dataclass(frozen=True)
class HeartbeatResult:
    ok: bool
    response: dict[str, object] | None = None
    accepted_commands: int = 0
    rejected_commands: int = 0
    command_errors: tuple[str, ...] = ()
    error: str | None = None


class HeartbeatRunner:
    def __init__(
        self,
        config: AgentConfig,
        client: GatewayApiClient | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.client = GatewayApiClient(config) if client is None else client
        self.sleep = sleep

    def run_once(self) -> HeartbeatResult:
        cameras = tuple(
            CameraStatusReport(
                camera_id=camera_id,
                status="online",
                last_seen_at=datetime.now(timezone.utc),
            )
            for camera_id in self.config.camera_ids
        )
        try:
            response = self.client.send_heartbeat(status="online", cameras=cameras)
        except AgentClientError as exc:
            return HeartbeatResult(ok=False, error=str(exc))
        accepted_commands, rejected_commands, command_errors = self._verify_pending_commands(response)
        return HeartbeatResult(
            ok=True,
            response=response,
            accepted_commands=accepted_commands,
            rejected_commands=rejected_commands,
            command_errors=command_errors,
        )

    def run_forever(self) -> None:
        while True:
            self.run_once()
            self.sleep(self.config.heartbeat_interval_seconds)

    def _verify_pending_commands(self, response: dict[str, Any]) -> tuple[int, int, tuple[str, ...]]:
        pending_commands = response.get("pending_commands", [])
        if not isinstance(pending_commands, list):
            return (0, 1, ("gateway-heartbeat-pending-commands-invalid",))

        accepted_commands = 0
        rejected_commands = 0
        errors: list[str] = []
        for raw_command in pending_commands:
            if not isinstance(raw_command, dict):
                rejected_commands += 1
                errors.append("gateway-command-invalid")
                continue
            try:
                command = GatewayCommand.from_dict(raw_command)
                verify_gateway_command(
                    command,
                    self.config.command_signing_key,
                    expected_gateway_id=self.config.gateway_id,
                )
            except (KeyError, CommandVerificationError) as exc:
                rejected_commands += 1
                errors.append(str(exc))
                continue
            accepted_commands += 1
        return (accepted_commands, rejected_commands, tuple(errors))
