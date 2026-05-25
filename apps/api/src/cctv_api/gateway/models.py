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


class GatewayCommandAck(BaseModel):
    type: Literal["command_ack"] = "command_ack"
    command_id: str | None = None
    gateway_id: str
    status: Literal["accepted", "rejected"]
    error: str | None = None


class GatewayHeartbeatResponse(BaseModel):
    server_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pending_commands: list[GatewayCommandEnvelope] = Field(default_factory=list)


class GatewayIngestTokenRequest(BaseModel):
    camera_id: str


class GatewayIngestTokenResponse(BaseModel):
    camera_id: str
    room: str
    livekit_url: str
    token: str
    expires_at: datetime


class GatewayCameraStatusRequest(BaseModel):
    status: Literal["online", "offline", "degraded"]
    detail: str | None = None
    observed_at: datetime | None = None


class GatewayDiscoveryFinding(BaseModel):
    ip: str = Field(max_length=45)
    hostname: str | None = Field(default=None, max_length=255)
    open_ports: list[int] = Field(default_factory=list, max_length=32)
    status: Literal["open"] = "open"
    candidate_kind: Literal["possible_camera", "possible_nvr", "unknown_device"]
    confidence: Literal["low", "medium", "high"]


class GatewayDiscoveryRunRequest(BaseModel):
    started_at: datetime
    finished_at: datetime
    status: Literal["completed", "partial", "failed"]
    approved_ranges: list[str] = Field(default_factory=list, max_length=64)
    ports: list[int] = Field(default_factory=list, max_length=64)
    scanned_host_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    findings: list[GatewayDiscoveryFinding] = Field(default_factory=list, max_length=512)
    agent_version: str | None = Field(default=None, max_length=64)
    error: str | None = Field(default=None, max_length=512)


class GatewayDiscoveryRunAcceptedResponse(BaseModel):
    accepted: bool = True
    discovery_run_id: str
    status: str


class GatewayDiscoveryRunResponse(BaseModel):
    discovery_run_id: str
    gateway_id: str
    started_at: datetime
    finished_at: datetime
    status: str
    approved_ranges: list[str]
    ports: list[int]
    scanned_host_count: int
    candidate_count: int
    findings: list[GatewayDiscoveryFinding]
    agent_version: str | None = None
    error: str | None = None
    created_at: datetime


class GatewayAcceptedResponse(BaseModel):
    accepted: bool = True
