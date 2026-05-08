from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.errors import ProblemDetail
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.gateway.models import (
    GatewayAcceptedResponse,
    GatewayCameraStatusRequest,
    GatewayHeartbeatRequest,
    GatewayHeartbeatResponse,
    GatewayIngestTokenRequest,
    GatewayIngestTokenResponse,
)
from cctv_api.models.enums import StreamKind
from cctv_api.security.dependencies import require_gateway_identity
from cctv_api.security.identity import Principal
from cctv_api.security.livekit_tokens import LiveKitTokenConfigError, mint_gateway_publish_token
from cctv_api.security.stream_access import (
    gateway_has_active_camera_assignment,
    get_active_camera,
    get_enabled_gateway,
    record_stream_grant,
)

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
    payload: GatewayIngestTokenRequest,
    principal: Principal = Depends(require_gateway_identity),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> GatewayIngestTokenResponse:
    _require_matching_gateway(gateway_id, principal)

    gateway_uuid = _parse_uuid(gateway_id, "gateway-id-invalid")
    camera_uuid = _parse_uuid(payload.camera_id, "camera-id-invalid")

    if get_enabled_gateway(db, gateway_uuid) is None:
        raise ProblemDetail(
            status=403,
            title="Forbidden",
            detail="gateway-disabled-or-not-found",
            type_uri="https://panoptix.local/problems/forbidden",
        )

    camera = get_active_camera(db, camera_uuid)
    if camera is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="camera-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )

    if not gateway_has_active_camera_assignment(db, gateway_uuid, camera_uuid):
        raise ProblemDetail(
            status=403,
            title="Forbidden",
            detail="gateway-camera-assignment-denied",
            type_uri="https://panoptix.local/problems/forbidden",
        )

    try:
        grant = mint_gateway_publish_token(
            settings,
            gateway_id=gateway_uuid,
            camera_id=camera_uuid,
            room=camera.livekit_room_name,
        )
    except LiveKitTokenConfigError as exc:
        raise ProblemDetail(
            status=503,
            title="Service Unavailable",
            detail=str(exc),
            type_uri="https://panoptix.local/problems/service-unavailable",
        ) from exc

    record_stream_grant(
        db,
        gateway_id=gateway_uuid,
        camera_id=camera_uuid,
        kind=StreamKind.gateway_publish,
        jti=grant.jti,
        issued_at=grant.issued_at,
        expires_at=grant.expires_at,
    )
    return GatewayIngestTokenResponse(
        camera_id=str(camera.id),
        room=grant.room,
        livekit_url=grant.livekit_url,
        token=grant.token,
        expires_at=grant.expires_at,
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


def _parse_uuid(value: str, detail: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail=detail,
            type_uri="https://panoptix.local/problems/bad-request",
        ) from exc
