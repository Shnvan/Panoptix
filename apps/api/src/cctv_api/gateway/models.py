from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class CameraStatus(BaseModel):
    camera_id: str
    status: Literal["online", "offline", "degraded"]
    last_seen_at: datetime | None = None
    detail: str | None = None


class GatewayHeartbeatRequest(BaseModel):
    status: Literal["online", "degraded", "offline"]
    agent_version: str
    cameras: list[CameraStatus] = Field(default_factory=list)


class GatewayCommandEnvelope(BaseModel):
    command_id: str
    kind: str
    gateway_id: str
    issued_at: datetime
    expires_at: datetime
    payload: dict[str, object] = Field(default_factory=dict)
    signature: str


class GatewayHeartbeatResponse(BaseModel):
    server_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pending_commands: list[GatewayCommandEnvelope] = Field(default_factory=list)


class GatewayIngestTokenRequest(BaseModel):
    camera_id: str


class GatewayCameraStatusRequest(BaseModel):
    status: Literal["online", "offline", "degraded"]
    detail: str | None = None
    observed_at: datetime | None = None


class GatewayAcceptedResponse(BaseModel):
    accepted: bool = True
