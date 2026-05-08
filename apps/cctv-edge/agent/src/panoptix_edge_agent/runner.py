from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from panoptix_edge_agent.client import AgentClientError, CameraStatusReport, GatewayApiClient
from panoptix_edge_agent.config import AgentConfig


@dataclass(frozen=True)
class HeartbeatResult:
    ok: bool
    response: dict[str, object] | None = None
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
        return HeartbeatResult(ok=True, response=response)

    def run_forever(self) -> None:
        while True:
            self.run_once()
            self.sleep(self.config.heartbeat_interval_seconds)
