from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.models.enums import GatewayStatus, StreamKind
from cctv_api.models.tables import (
    Camera,
    CameraAcl,
    EdgeGateway,
    GatewayCameraAssignment,
    StreamGrant,
)


def get_active_camera(db: DbSession, camera_id: uuid.UUID) -> Camera | None:
    stmt = select(Camera).where(Camera.id == str(camera_id), Camera.retired_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def user_has_active_camera_acl(db: DbSession, user_id: uuid.UUID, camera_id: uuid.UUID) -> bool:
    stmt = select(CameraAcl).where(
        CameraAcl.user_id == str(user_id),
        CameraAcl.camera_id == str(camera_id),
        CameraAcl.revoked_at.is_(None),
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def get_enabled_gateway(db: DbSession, gateway_id: uuid.UUID) -> EdgeGateway | None:
    stmt = select(EdgeGateway).where(
        EdgeGateway.id == str(gateway_id),
        EdgeGateway.status == GatewayStatus.enabled,
        EdgeGateway.disabled_at.is_(None),
    )
    return db.execute(stmt).scalar_one_or_none()


def gateway_has_active_camera_assignment(
    db: DbSession,
    gateway_id: uuid.UUID,
    camera_id: uuid.UUID,
) -> bool:
    stmt = select(GatewayCameraAssignment).where(
        GatewayCameraAssignment.gateway_id == str(gateway_id),
        GatewayCameraAssignment.camera_id == str(camera_id),
        GatewayCameraAssignment.revoked_at.is_(None),
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def record_stream_grant(
    db: DbSession,
    *,
    camera_id: uuid.UUID,
    kind: StreamKind,
    jti: str,
    issued_at: datetime,
    expires_at: datetime,
    user_id: uuid.UUID | None = None,
    gateway_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
) -> StreamGrant:
    grant = StreamGrant(
        id=uuid.uuid4(),
        user_id=user_id,
        gateway_id=gateway_id,
        session_id=session_id,
        camera_id=camera_id,
        jti=jti,
        kind=kind,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)
    return grant
