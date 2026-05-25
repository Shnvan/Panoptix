from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.errors import ProblemDetail
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.gateway.command_queue import enqueue_command
from cctv_api.gateway.publish_state import (
    cancel_pending_stop,
    enqueue_immediate_stop_command,
    mark_publish_starting,
    reset_publish_state_for_immediate_stop,
    schedule_publish_stop,
)
from cctv_api.models.enums import ActorType, CameraEventKind, EventSource
from cctv_api.models.enums import GatewayStatus, StreamKind
from cctv_api.models.tables import (
    AuditLog,
    Camera,
    CameraEvent,
    EdgeGateway,
    GatewayCameraAssignment,
    GatewayCommandQueue,
    WebhookReplayCache,
)
from cctv_api.security.audit import AuditLogError, record_audit_event
from cctv_api.security.livekit_tokens import LiveKitTokenConfigError, mint_gateway_publish_token
from cctv_api.security.livekit_webhooks import (
    LiveKitWebhookVerificationError,
    verify_livekit_webhook_authorization,
)
from cctv_api.security.stream_access import record_stream_grant

router = APIRouter()

LIVEKIT_REPLAY_PROVIDER = "livekit"
LIVEKIT_WEBHOOK_REPLAY_TTL_SECONDS = 300
LIVEKIT_WEBHOOK_TIMESTAMP_WINDOW_SECONDS = 60
START_PUBLISH_COMMAND_TTL_SECONDS = 60

_EVENT_KIND_BY_LIVEKIT_EVENT = {
    "track_published": CameraEventKind.online,
    "track_unpublished": CameraEventKind.offline,
    "room_finished": CameraEventKind.offline,
    "participant_connection_aborted": CameraEventKind.degraded,
}


@router.post("/webhooks/livekit")
async def livekit_webhook(
    request: Request,
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    raw_body = await request.body()
    verification = _verify_webhook_auth(request, raw_body, settings)
    payload = _parse_webhook_payload(raw_body)
    event_at = _parse_created_at(payload.get("createdAt"))
    event_name = payload.get("event")
    room_name = _room_name(payload)
    event_id = payload.get("id")
    now = datetime.now(timezone.utc)

    if abs((now - event_at).total_seconds()) > LIVEKIT_WEBHOOK_TIMESTAMP_WINDOW_SECONDS:
        _record_system_audit_required(
            db,
            settings=settings,
            request=request,
            action="livekit.webhook.replay_rejected",
            resource="livekit:webhook",
            payload=_audit_payload(payload, event_at=event_at, reason="stale"),
        )
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="livekit-webhook-stale",
            type_uri="https://panoptix.local/problems/bad-request",
        )

    existing_replay = db.execute(
        select(WebhookReplayCache).where(
            WebhookReplayCache.provider == LIVEKIT_REPLAY_PROVIDER,
            WebhookReplayCache.signature == verification.replay_signature,
        )
    ).scalar_one_or_none()
    if existing_replay is not None:
        _record_system_audit_required(
            db,
            settings=settings,
            request=request,
            action="livekit.webhook.replay_rejected",
            resource="livekit:webhook",
            payload=_audit_payload(payload, event_at=event_at, reason="duplicate"),
        )
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="livekit-webhook-replay",
            type_uri="https://panoptix.local/problems/conflict",
        )

    db.add(
        WebhookReplayCache(
            provider=LIVEKIT_REPLAY_PROVIDER,
            signature=verification.replay_signature,
            ts=event_at,
            expires_at=now + timedelta(seconds=LIVEKIT_WEBHOOK_REPLAY_TTL_SECONDS),
        )
    )

    created_camera_event = _maybe_add_camera_event(
        db,
        event_name=event_name,
        room_name=room_name,
        event_at=event_at,
    )
    queued_publish_command = _maybe_enqueue_publish_command(
        db,
        settings=settings,
        request=request,
        event_name=event_name,
        payload=payload,
        room_name=room_name,
        event_at=event_at,
    )

    _record_system_audit_required(
        db,
        settings=settings,
        request=request,
        action="livekit.webhook.received",
        resource="livekit:webhook",
        payload=_audit_payload(
            payload,
            event_at=event_at,
            camera_event_id=str(created_camera_event.id) if created_camera_event is not None else None,
            command_id=str(queued_publish_command.id) if queued_publish_command is not None else None,
        ),
    )
    return {"accepted": True, "event_id": event_id if isinstance(event_id, str) else None}


def _verify_webhook_auth(
    request: Request,
    raw_body: bytes,
    settings: Settings,
):
    try:
        return verify_livekit_webhook_authorization(
            settings,
            authorization_header=request.headers.get("authorization"),
            raw_body=raw_body,
        )
    except LiveKitWebhookVerificationError as exc:
        if exc.detail == "livekit-webhook-config-invalid":
            raise ProblemDetail(
                status=503,
                title="Service Unavailable",
                detail=exc.detail,
                type_uri="https://panoptix.local/problems/service-unavailable",
            ) from exc
        if exc.detail == "livekit-webhook-authorization-required":
            raise ProblemDetail(
                status=401,
                title="Unauthorized",
                detail=exc.detail,
                type_uri="https://panoptix.local/problems/unauthorized",
            ) from exc
        raise ProblemDetail(
            status=403,
            title="Forbidden",
            detail=exc.detail,
            type_uri="https://panoptix.local/problems/forbidden",
        ) from exc


def _parse_webhook_payload(raw_body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="livekit-webhook-json-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        ) from exc
    if not isinstance(value, dict):
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="livekit-webhook-json-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        )
    return value


def _parse_created_at(value: Any) -> datetime:
    if isinstance(value, bool):
        raise _created_at_invalid()
    if isinstance(value, int | float):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise _created_at_invalid() from exc
    if isinstance(value, str):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except ValueError as exc:
            raise _created_at_invalid() from exc
    raise _created_at_invalid()


def _created_at_invalid() -> ProblemDetail:
    return ProblemDetail(
        status=400,
        title="Bad Request",
        detail="livekit-webhook-created-at-invalid",
        type_uri="https://panoptix.local/problems/bad-request",
    )


def _room_name(payload: dict[str, Any]) -> str | None:
    room = payload.get("room")
    if not isinstance(room, dict):
        return None
    name = room.get("name")
    return name if isinstance(name, str) else None


def _maybe_add_camera_event(
    db: DbSession,
    *,
    event_name: Any,
    room_name: str | None,
    event_at: datetime,
) -> CameraEvent | None:
    if not isinstance(event_name, str) or room_name is None:
        return None
    kind = _EVENT_KIND_BY_LIVEKIT_EVENT.get(event_name)
    if kind is None:
        return None
    camera = db.execute(
        select(Camera)
        .where(Camera.livekit_room_name == room_name)
        .where(Camera.retired_at.is_(None))
    ).scalar_one_or_none()
    if camera is None:
        return None
    event = CameraEvent(
        id=uuid.uuid4(),
        camera_id=camera.id,
        gateway_id=camera.gateway_id,
        kind=kind,
        at=event_at,
        source=EventSource.livekit_webhook,
    )
    db.add(event)
    return event


def _maybe_enqueue_publish_command(
    db: DbSession,
    *,
    settings: Settings,
    request: Request,
    event_name: Any,
    payload: dict[str, Any],
    room_name: str | None,
    event_at: datetime,
) -> GatewayCommandQueue | None:
    if not isinstance(event_name, str) or room_name is None:
        return None
    command_kind = _publish_command_kind(event_name, payload)
    if command_kind is None:
        return None

    camera = _camera_for_room(db, room_name)
    if camera is None:
        return None

    gateway = _assigned_enabled_gateway(db, camera.id)
    if gateway is None:
        _record_system_audit_required(
            db,
            settings=settings,
            request=request,
            action="livekit.publish.command_skipped",
            resource=f"camera:{camera.id}",
            payload={
                "event": event_name,
                "room": room_name,
                "camera_id": camera.id,
                "reason": "gateway-assignment-not-found",
            },
        )
        return None

    if command_kind == "gateway.command.start_publish":
        return _enqueue_start_publish_command(
            db,
            settings=settings,
            request=request,
            camera=camera,
            gateway=gateway,
            room_name=room_name,
            event_name=event_name,
            event_at=event_at,
        )
    if event_name == "participant_left":
        _schedule_stop_publish(
            db,
            settings=settings,
            request=request,
            camera=camera,
            gateway=gateway,
            room_name=room_name,
            event_name=event_name,
            event_at=event_at,
        )
        return None
    return _enqueue_stop_publish_command(
        db,
        settings=settings,
        request=request,
        camera=camera,
        gateway=gateway,
        room_name=room_name,
        event_name=event_name,
        event_at=event_at,
    )


def _publish_command_kind(event_name: str, payload: dict[str, Any]) -> str | None:
    if event_name == "participant_joined":
        return "gateway.command.start_publish"
    if event_name == "room_finished":
        return "gateway.command.stop_publish"
    if event_name == "participant_left" and _participant_count(payload) == 0:
        return "gateway.command.stop_publish"
    return None


def _participant_count(payload: dict[str, Any]) -> int | None:
    raw_count = payload.get("participant_count")
    if raw_count is None:
        room = payload.get("room")
        if isinstance(room, dict):
            raw_count = room.get("participant_count")
    if isinstance(raw_count, bool):
        return None
    if isinstance(raw_count, int):
        return raw_count
    if isinstance(raw_count, str):
        try:
            return int(raw_count)
        except ValueError:
            return None
    return None


def _camera_for_room(db: DbSession, room_name: str) -> Camera | None:
    return db.execute(
        select(Camera)
        .where(Camera.livekit_room_name == room_name)
        .where(Camera.retired_at.is_(None))
    ).scalar_one_or_none()


def _assigned_enabled_gateway(db: DbSession, camera_id: uuid.UUID) -> EdgeGateway | None:
    return db.execute(
        select(EdgeGateway)
        .join(GatewayCameraAssignment, GatewayCameraAssignment.gateway_id == EdgeGateway.id)
        .where(GatewayCameraAssignment.camera_id == str(camera_id))
        .where(GatewayCameraAssignment.revoked_at.is_(None))
        .where(EdgeGateway.status == GatewayStatus.enabled)
        .where(EdgeGateway.disabled_at.is_(None))
        .order_by(GatewayCameraAssignment.granted_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _enqueue_start_publish_command(
    db: DbSession,
    *,
    settings: Settings,
    request: Request,
    camera: Camera,
    gateway: EdgeGateway,
    room_name: str,
    event_name: str,
    event_at: datetime,
) -> GatewayCommandQueue | None:
    cancelled_state = cancel_pending_stop(
        db,
        camera=camera,
        gateway=gateway,
        room=room_name,
        event_at=event_at,
    )
    if cancelled_state is not None:
        _record_system_audit_required(
            db,
            settings=settings,
            request=request,
            action="livekit.publish.stop_cancelled",
            resource=f"camera:{camera.id}",
            payload={
                "gateway_id": gateway.id,
                "camera_id": camera.id,
                "room": room_name,
                "event": event_name,
                "created_at": event_at,
            },
        )
        return None

    _state, should_enqueue = mark_publish_starting(
        db,
        camera=camera,
        gateway=gateway,
        room=room_name,
        event_at=event_at,
    )
    if not should_enqueue:
        return None

    try:
        grant = mint_gateway_publish_token(
            settings,
            gateway_id=gateway.id,
            camera_id=camera.id,
            room=room_name,
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
        gateway_id=gateway.id,
        camera_id=camera.id,
        kind=StreamKind.gateway_publish,
        jti=grant.jti,
        issued_at=grant.issued_at,
        expires_at=grant.expires_at,
    )

    row = enqueue_command(
        db,
        gateway_id=gateway.id,
        kind="gateway.command.start_publish",
        payload={
            "camera_id": str(camera.id),
            "room": room_name,
            "livekit_url": grant.livekit_url,
            "gateway_publish_token": grant.token,
            "token_expires_at": grant.expires_at.isoformat(),
        },
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=START_PUBLISH_COMMAND_TTL_SECONDS),
    )
    _record_system_audit_required(
        db,
        settings=settings,
        request=request,
        action="livekit.publish.start_enqueued",
        resource=f"gateway:{gateway.id}",
        payload={
            "command_id": str(row.id),
            "gateway_id": gateway.id,
            "camera_id": camera.id,
            "room": room_name,
            "event": event_name,
            "grant_jti": grant.jti,
            "token_expires_at": grant.expires_at,
        },
    )
    return row


def _schedule_stop_publish(
    db: DbSession,
    *,
    settings: Settings,
    request: Request,
    camera: Camera,
    gateway: EdgeGateway,
    room_name: str,
    event_name: str,
    event_at: datetime,
) -> None:
    state = schedule_publish_stop(
        db,
        camera=camera,
        gateway=gateway,
        room=room_name,
        event_at=event_at,
    )
    _record_system_audit_required(
        db,
        settings=settings,
        request=request,
        action="livekit.publish.stop_scheduled",
        resource=f"camera:{camera.id}",
        payload={
            "gateway_id": gateway.id,
            "camera_id": camera.id,
            "room": room_name,
            "event": event_name,
            "created_at": event_at,
            "stop_due_at": state.stop_due_at,
        },
    )


def _enqueue_stop_publish_command(
    db: DbSession,
    *,
    settings: Settings,
    request: Request,
    camera: Camera,
    gateway: EdgeGateway,
    room_name: str,
    event_name: str,
    event_at: datetime,
) -> GatewayCommandQueue:
    row = enqueue_immediate_stop_command(
        db,
        gateway_id=gateway.id,
        camera_id=camera.id,
        room=room_name,
        now=datetime.now(timezone.utc),
    )
    reset_publish_state_for_immediate_stop(
        db,
        camera=camera,
        gateway=gateway,
        room=room_name,
        event_at=event_at,
    )
    _record_system_audit_required(
        db,
        settings=settings,
        request=request,
        action="livekit.publish.stop_enqueued",
        resource=f"gateway:{gateway.id}",
        payload={
            "command_id": str(row.id),
            "gateway_id": gateway.id,
            "camera_id": camera.id,
            "room": room_name,
            "event": event_name,
            "created_at": event_at,
        },
    )
    return row


def _record_system_audit_required(
    db: DbSession,
    *,
    settings: Settings,
    request: Request,
    action: str,
    resource: str,
    payload: dict[str, object | None],
) -> AuditLog:
    try:
        return record_audit_event(
            db,
            actor_type=ActorType.system,
            audit_hmac_key_version=settings.AUDIT_HMAC_KEY_VERSION,
            audit_hmac_key=settings.AUDIT_HMAC_KEY,
            actor_id=None,
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


def _audit_payload(
    payload: dict[str, Any],
    *,
    event_at: datetime,
    reason: str | None = None,
    camera_event_id: str | None = None,
    command_id: str | None = None,
) -> dict[str, object | None]:
    return {
        "event_id": payload.get("id") if isinstance(payload.get("id"), str) else None,
        "event": payload.get("event") if isinstance(payload.get("event"), str) else None,
        "room": _room_name(payload),
        "created_at": event_at,
        "reason": reason,
        "camera_event_id": camera_event_id,
        "command_id": command_id,
    }


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


def _request_ua(request: Request) -> str | None:
    return request.headers.get("user-agent")
