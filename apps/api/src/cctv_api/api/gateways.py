from __future__ import annotations

from fastapi import APIRouter, Depends

from cctv_api.api.errors import ProblemDetail
from cctv_api.gateway.models import (
    GatewayAcceptedResponse,
    GatewayCameraStatusRequest,
    GatewayHeartbeatRequest,
    GatewayHeartbeatResponse,
    GatewayIngestTokenRequest,
)
from cctv_api.security.dependencies import require_gateway_identity
from cctv_api.security.identity import Principal

router = APIRouter()


def _require_matching_gateway(gateway_id: str, principal: Principal) -> None:
    if principal.gateway_id != gateway_id:
        raise ProblemDetail(
            status=403,
            title="Forbidden",
            detail="gateway-id-mismatch",
            type_uri="https://panoptix.local/problems/forbidden",
        )


@router.post("/gateways/{gateway_id}/heartbeat")
def gateway_heartbeat(
    gateway_id: str,
    _payload: GatewayHeartbeatRequest,
    principal: Principal = Depends(require_gateway_identity),
) -> GatewayHeartbeatResponse:
    _require_matching_gateway(gateway_id, principal)
    return GatewayHeartbeatResponse()


@router.post("/gateways/{gateway_id}/ingest-token")
def gateway_ingest_token(
    gateway_id: str,
    _payload: GatewayIngestTokenRequest,
    principal: Principal = Depends(require_gateway_identity),
) -> None:
    _require_matching_gateway(gateway_id, principal)
    raise ProblemDetail(
        status=501,
        title="Not Implemented",
        detail="gateway-ingest-token-not-implemented",
        type_uri="https://panoptix.local/problems/not-implemented",
    )


@router.post("/gateways/{gateway_id}/cameras/{camera_id}/status")
def gateway_camera_status(
    gateway_id: str,
    camera_id: str,
    _payload: GatewayCameraStatusRequest,
    principal: Principal = Depends(require_gateway_identity),
) -> GatewayAcceptedResponse:
    _require_matching_gateway(gateway_id, principal)
    if not camera_id:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="camera-id-required",
            type_uri="https://panoptix.local/problems/bad-request",
        )
    return GatewayAcceptedResponse()


@router.get("/gateway-control/ws")
def gateway_control_ws(
    principal: Principal = Depends(require_gateway_identity),
) -> None:
    if principal.gateway_id is None:
        raise ProblemDetail(
            status=403,
            title="Forbidden",
            detail="gateway-id-required",
            type_uri="https://panoptix.local/problems/forbidden",
        )
    raise ProblemDetail(
        status=501,
        title="Not Implemented",
        detail="gateway-control-websocket-not-implemented",
        type_uri="https://panoptix.local/problems/not-implemented",
    )
