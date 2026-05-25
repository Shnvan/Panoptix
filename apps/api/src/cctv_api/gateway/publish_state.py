from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.gateway.command_queue import enqueue_command
from cctv_api.models.enums import CameraPublishStatus, GatewayStatus
from cctv_api.models.tables import Camera, CameraPublishState, EdgeGateway, GatewayCameraAssignment, GatewayCommandQueue

STOP_GRACE_SECONDS = 10
STOP_PUBLISH_COMMAND_TTL_SECONDS = 30


@dataclass(frozen=True)
class StopCommandResult:
    command: GatewayCommandQueue | None
    camera: Camera
    gateway: EdgeGateway
    state: CameraPublishState


AuditRecorder = Callable[[str, str, dict[str, object | None]], None]


def mark_publish_starting(
    db: DbSession,
    *,
    camera: Camera,
    gateway: EdgeGateway,
    room: str,
    event_at: datetime,
) -> tuple[CameraPublishState, bool]:
    state = _get_or_create_state(db, camera=camera, gateway=gateway, room=room, now=event_at)
    state.gateway_id = gateway.id
    state.room = room
    state.last_viewer_count = max(state.last_viewer_count, 1)
    state.updated_at = event_at
    if state.status in {CameraPublishStatus.starting, CameraPublishStatus.publishing}:
        return state, False
    state.status = CameraPublishStatus.starting
    state.started_at = event_at
    state.stop_requested_at = None
    state.stop_due_at = None
    db.flush()
    return state, True


def schedule_publish_stop(
    db: DbSession,
    *,
    camera: Camera,
    gateway: EdgeGateway,
    room: str,
    event_at: datetime,
    grace_seconds: int = STOP_GRACE_SECONDS,
) -> CameraPublishState:
    state = _get_or_create_state(db, camera=camera, gateway=gateway, room=room, now=event_at)
    state.gateway_id = gateway.id
    state.room = room
    state.status = CameraPublishStatus.stop_pending
    state.last_viewer_count = 0
    state.stop_requested_at = event_at
    state.stop_due_at = event_at + timedelta(seconds=grace_seconds)
    state.updated_at = event_at
    db.flush()
    return state


def cancel_pending_stop(
    db: DbSession,
    *,
    camera: Camera,
    gateway: EdgeGateway,
    room: str,
    event_at: datetime,
) -> CameraPublishState | None:
    state = db.get(CameraPublishState, camera.id)
    if state is None or state.status != CameraPublishStatus.stop_pending:
        return None
    state.gateway_id = gateway.id
    state.room = room
    state.status = CameraPublishStatus.publishing if state.started_at is not None else CameraPublishStatus.starting
    state.last_viewer_count = max(state.last_viewer_count, 1)
    state.stop_requested_at = None
    state.stop_due_at = None
    state.updated_at = event_at
    db.flush()
    return state


def reset_publish_state_for_immediate_stop(
    db: DbSession,
    *,
    camera: Camera,
    gateway: EdgeGateway,
    room: str,
    event_at: datetime,
) -> CameraPublishState:
    state = _get_or_create_state(db, camera=camera, gateway=gateway, room=room, now=event_at)
    state.gateway_id = gateway.id
    state.room = room
    state.status = CameraPublishStatus.idle
    state.last_viewer_count = 0
    state.started_at = None
    state.stop_requested_at = event_at
    state.stop_due_at = None
    state.updated_at = event_at
    db.flush()
    return state


def enqueue_due_publish_stops(
    db: DbSession,
    *,
    now: datetime | None = None,
    audit: AuditRecorder | None = None,
) -> list[StopCommandResult]:
    current_time = _now() if now is None else _normalize_datetime(now)
    states = list(
        db.execute(
            select(CameraPublishState)
            .where(CameraPublishState.status == CameraPublishStatus.stop_pending)
            .where(CameraPublishState.stop_due_at.is_not(None))
            .where(CameraPublishState.stop_due_at <= current_time)
            .order_by(CameraPublishState.stop_due_at.asc())
        )
        .scalars()
        .all()
    )
    results: list[StopCommandResult] = []
    for state in states:
        camera = db.get(Camera, state.camera_id)
        if camera is None or camera.retired_at is not None:
            state.status = CameraPublishStatus.idle
            state.updated_at = current_time
            state.stop_due_at = None
            continue
        gateway = _enabled_gateway_for_state(db, state)
        if gateway is None:
            state.status = CameraPublishStatus.idle
            state.updated_at = current_time
            state.stop_due_at = None
            continue
        command = _enqueue_stop_command(
            db,
            gateway_id=gateway.id,
            camera_id=camera.id,
            room=state.room,
            now=current_time,
        )
        state.gateway_id = gateway.id
        state.status = CameraPublishStatus.idle
        state.last_viewer_count = 0
        state.started_at = None
        state.stop_due_at = None
        state.updated_at = current_time
        if audit is not None:
            audit(
                "livekit.publish.stop_enqueued",
                f"gateway:{gateway.id}",
                {
                    "command_id": str(command.id),
                    "gateway_id": gateway.id,
                    "camera_id": camera.id,
                    "room": state.room,
                    "event": "stop_grace_elapsed",
                    "created_at": current_time,
                },
            )
        results.append(StopCommandResult(command=command, camera=camera, gateway=gateway, state=state))
    db.flush()
    return results


def enqueue_immediate_stop_command(
    db: DbSession,
    *,
    gateway_id: uuid.UUID,
    camera_id: uuid.UUID,
    room: str,
    now: datetime | None = None,
) -> GatewayCommandQueue:
    return _enqueue_stop_command(
        db,
        gateway_id=gateway_id,
        camera_id=camera_id,
        room=room,
        now=_now() if now is None else _normalize_datetime(now),
    )


def _get_or_create_state(
    db: DbSession,
    *,
    camera: Camera,
    gateway: EdgeGateway,
    room: str,
    now: datetime,
) -> CameraPublishState:
    state = db.get(CameraPublishState, camera.id)
    if state is not None:
        return state
    state = CameraPublishState(
        camera_id=camera.id,
        gateway_id=gateway.id,
        room=room,
        status=CameraPublishStatus.idle,
        last_viewer_count=0,
        updated_at=now,
    )
    db.add(state)
    db.flush()
    return state


def _enabled_gateway_for_state(db: DbSession, state: CameraPublishState) -> EdgeGateway | None:
    if state.gateway_id is None:
        return None
    return db.execute(
        select(EdgeGateway)
        .join(GatewayCameraAssignment, GatewayCameraAssignment.gateway_id == EdgeGateway.id)
        .where(EdgeGateway.id == state.gateway_id)
        .where(EdgeGateway.status == GatewayStatus.enabled)
        .where(EdgeGateway.disabled_at.is_(None))
        .where(GatewayCameraAssignment.camera_id == str(state.camera_id))
        .where(GatewayCameraAssignment.revoked_at.is_(None))
        .limit(1)
    ).scalar_one_or_none()


def _enqueue_stop_command(
    db: DbSession,
    *,
    gateway_id: uuid.UUID,
    camera_id: uuid.UUID,
    room: str,
    now: datetime,
) -> GatewayCommandQueue:
    return enqueue_command(
        db,
        gateway_id=gateway_id,
        kind="gateway.command.stop_publish",
        payload={"camera_id": str(camera_id), "room": room},
        expires_at=now + timedelta(seconds=STOP_PUBLISH_COMMAND_TTL_SECONDS),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
