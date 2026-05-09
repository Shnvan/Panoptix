from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterable
from typing import Any

from fastapi import APIRouter, Depends, Request, WebSocket
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.errors import ProblemDetail
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.gateway.command_signing import CommandSigningError, sign_command_envelope
from cctv_api.gateway.models import (
    GatewayAcceptedResponse,
    GatewayCameraStatusRequest,
    GatewayCommandAck,
    GatewayCommandEnvelope,
    GatewayHeartbeatRequest,
    GatewayHeartbeatResponse,
    GatewayIngestTokenRequest,
    GatewayIngestTokenResponse,
)
from cctv_api.models.enums import ActorType, StreamKind
from cctv_api.security.audit import AuditLogError, record_audit_event
from cctv_api.security.dependencies import require_gateway_identity, verify_gateway_identity_ws
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
    request: Request,
    principal: Principal = Depends(require_gateway_identity),
    settings: Settings = Depends(get_settings),
) -> GatewayHeartbeatResponse:
    _require_matching_gateway(gateway_id, principal)
    try:
        pending_commands = _signed_gateway_commands(
            request.app.state,
            gateway_id,
            settings.GATEWAY_COMMAND_SIGNING_KEY,
        )
    except CommandSigningError as exc:
        raise ProblemDetail(
            status=503,
            title="Service Unavailable",
            detail="gateway-command-signing-failed",
            type_uri="https://panoptix.local/problems/service-unavailable",
        ) from exc
    return GatewayHeartbeatResponse(pending_commands=pending_commands)


@router.post("/gateways/{gateway_id}/ingest-token")
def gateway_ingest_token(
    gateway_id: str,
    payload: GatewayIngestTokenRequest,
    request: Request,
    principal: Principal = Depends(require_gateway_identity),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> GatewayIngestTokenResponse:
    if principal.gateway_id != gateway_id:
        _record_gateway_audit_safely(
            db,
            request=request,
            actor_id=_parse_uuid_or_none(principal.gateway_id),
            action="gateway.ingest.denied.gateway_mismatch",
            resource=f"gateway:{gateway_id}",
            payload={"route_gateway_id": gateway_id, "principal_gateway_id": principal.gateway_id},
        )
    _require_matching_gateway(gateway_id, principal)

    gateway_uuid = _parse_uuid(gateway_id, "gateway-id-invalid")
    camera_uuid = _parse_uuid(payload.camera_id, "camera-id-invalid")

    if get_enabled_gateway(db, gateway_uuid) is None:
        _record_gateway_audit_safely(
            db,
            request=request,
            actor_id=gateway_uuid,
            action="gateway.ingest.denied.disabled",
            resource=f"camera:{camera_uuid}",
            payload={"gateway_id": gateway_uuid, "camera_id": camera_uuid},
        )
        raise ProblemDetail(
            status=403,
            title="Forbidden",
            detail="gateway-disabled-or-not-found",
            type_uri="https://panoptix.local/problems/forbidden",
        )

    camera = get_active_camera(db, camera_uuid)
    if camera is None:
        _record_gateway_audit_safely(
            db,
            request=request,
            actor_id=gateway_uuid,
            action="gateway.ingest.denied.camera_not_found",
            resource=f"camera:{camera_uuid}",
            payload={"gateway_id": gateway_uuid, "camera_id": camera_uuid},
        )
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="camera-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )

    if not gateway_has_active_camera_assignment(db, gateway_uuid, camera_uuid):
        _record_gateway_audit_safely(
            db,
            request=request,
            actor_id=gateway_uuid,
            action="gateway.ingest.denied.unassigned",
            resource=f"camera:{camera_uuid}",
            payload={"gateway_id": gateway_uuid, "camera_id": camera_uuid},
        )
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
        _record_gateway_audit_safely(
            db,
            request=request,
            actor_id=gateway_uuid,
            action="gateway.ingest.denied.livekit_config",
            resource=f"camera:{camera_uuid}",
            payload={"gateway_id": gateway_uuid, "camera_id": camera_uuid, "room": camera.livekit_room_name},
        )
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
    _record_gateway_audit_required(
        db,
        request=request,
        actor_id=gateway_uuid,
        action="gateway.ingest.token.issued",
        resource=f"camera:{camera_uuid}",
        payload={
            "gateway_id": gateway_uuid,
            "camera_id": camera_uuid,
            "room": camera.livekit_room_name,
            "grant_jti": grant.jti,
            "expires_at": grant.expires_at,
        },
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


@router.websocket("/gateway-control/ws")
async def gateway_control_ws(
    websocket: WebSocket,
    principal: Principal | None = Depends(verify_gateway_identity_ws),
    settings: Settings = Depends(get_settings),
) -> None:
    if principal is None or principal.gateway_id is None:
        await websocket.close(code=1008, reason="gateway-identity-required")
        return

    await websocket.accept()
    await websocket.send_json({"type": "connected", "gateway_id": principal.gateway_id})

    try:
        for signed_command in _signed_gateway_commands(
            websocket.app.state,
            principal.gateway_id,
            settings.GATEWAY_COMMAND_SIGNING_KEY,
        ):
            await websocket.send_json(signed_command.model_dump(mode="json"))
    except CommandSigningError:
        await websocket.close(code=1011, reason="gateway-command-signing-failed")
        return

    try:
        while True:
            raw_message = await websocket.receive_text()
            ack = _parse_gateway_command_ack(raw_message)
            if ack is None or ack.gateway_id != principal.gateway_id:
                await websocket.close(code=1008, reason="gateway-command-ack-invalid")
                return
            _record_gateway_command_ack(websocket, principal.gateway_id, ack)
    except WebSocketDisconnect:
        pass


def _signed_gateway_commands(
    app_state: Any,
    gateway_id: str,
    signing_key: str,
) -> list[GatewayCommandEnvelope]:
    return [
        sign_command_envelope(command, signing_key)
        for command in _gateway_control_commands(app_state, gateway_id)
    ]


def _gateway_control_commands(app_state: Any, gateway_id: str) -> Iterable[GatewayCommandEnvelope]:
    provider = getattr(app_state, "gateway_control_command_provider", None)
    if not callable(provider):
        return ()
    commands = provider(gateway_id)
    if commands is None:
        return ()
    return commands


def _parse_gateway_command_ack(raw_message: str) -> GatewayCommandAck | None:
    try:
        decoded = json.loads(raw_message)
    except json.JSONDecodeError:
        return None
    try:
        return GatewayCommandAck.model_validate(decoded)
    except ValidationError:
        return None


def _record_gateway_command_ack(
    websocket: WebSocket,
    gateway_id: str,
    ack: GatewayCommandAck,
) -> None:
    sink: Callable[[str, GatewayCommandAck], Any] | None = getattr(
        websocket.app.state,
        "gateway_control_ack_sink",
        None,
    )
    if not callable(sink):
        return
    sink(gateway_id, ack)


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


def _parse_uuid_or_none(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _record_gateway_audit_safely(
    db: DbSession,
    *,
    request: Request,
    actor_id: uuid.UUID | None,
    action: str,
    resource: str,
    payload: dict[str, object] | None = None,
) -> None:
    try:
        record_audit_event(
            db,
            actor_type=ActorType.gateway,
            actor_id=actor_id,
            action=action,
            resource=resource,
            payload=payload,
            ip=_request_ip(request),
            ua=_request_ua(request),
        )
    except AuditLogError:
        return


def _record_gateway_audit_required(
    db: DbSession,
    *,
    request: Request,
    actor_id: uuid.UUID,
    action: str,
    resource: str,
    payload: dict[str, object] | None = None,
) -> None:
    try:
        record_audit_event(
            db,
            actor_type=ActorType.gateway,
            actor_id=actor_id,
            action=action,
            resource=resource,
            payload=payload,
            ip=_request_ip(request),
            ua=_request_ua(request),
        )
    except AuditLogError as exc:
        raise ProblemDetail(
            status=503,
            title="Service Unavailable",
            detail="audit-log-write-failed",
            type_uri="https://panoptix.local/problems/service-unavailable",
        ) from exc


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


def _request_ua(request: Request) -> str | None:
    return request.headers.get("user-agent")
