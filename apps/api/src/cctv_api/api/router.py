from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.errors import ProblemDetail
from cctv_api.api.gateways import router as gateway_router
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.models.enums import ActorType, StreamKind
from cctv_api.security.dependencies import require_authenticated_user
from cctv_api.security.identity import Principal
from cctv_api.security.audit import AuditLogError, record_audit_event
from cctv_api.security.livekit_tokens import LiveKitTokenConfigError, mint_viewer_subscribe_token
from cctv_api.security.sessions import list_active_sessions, revoke_session
from cctv_api.security.stream_access import (
    get_active_camera,
    record_stream_grant,
    user_has_active_camera_acl,
)
from cctv_api.security.users import get_or_create_user

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(gateway_router)


@v1_router.get("/me")
def get_me(principal: Principal = Depends(require_authenticated_user)) -> dict[str, object]:
    return principal.to_response()


@v1_router.get("/cameras")
def list_cameras(
    _principal: Principal = Depends(require_authenticated_user),
) -> dict[str, object]:
    return {"items": [], "next_cursor": None}


class ViewerTokenResponse(BaseModel):
    camera_id: str
    room: str
    livekit_url: str
    token: str
    expires_at: datetime


@v1_router.get("/cameras/{camera_id}/view-token")
def get_camera_view_token(
    camera_id: str,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> ViewerTokenResponse:
    camera_uuid = _parse_uuid(camera_id, "camera-id-invalid")
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    if user.disabled_at is not None:
        _record_user_audit_safely(
            db,
            request=request,
            actor_id=user.id,
            action="viewer.token.denied.user_disabled",
            resource=f"camera:{camera_uuid}",
            payload={"camera_id": camera_uuid},
        )
        raise ProblemDetail(
            status=403,
            title="Forbidden",
            detail="user-disabled",
            type_uri="https://panoptix.local/problems/forbidden",
        )

    camera = get_active_camera(db, camera_uuid)
    if camera is None:
        _record_user_audit_safely(
            db,
            request=request,
            actor_id=user.id,
            action="viewer.token.denied.camera_not_found",
            resource=f"camera:{camera_uuid}",
            payload={"camera_id": camera_uuid},
        )
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="camera-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )

    if not user_has_active_camera_acl(db, user.id, camera_uuid):
        _record_user_audit_safely(
            db,
            request=request,
            actor_id=user.id,
            action="viewer.token.denied.access",
            resource=f"camera:{camera_uuid}",
            payload={"camera_id": camera_uuid},
        )
        raise ProblemDetail(
            status=403,
            title="Forbidden",
            detail="camera-access-denied",
            type_uri="https://panoptix.local/problems/forbidden",
        )

    try:
        grant = mint_viewer_subscribe_token(
            settings,
            user_id=user.id,
            camera_id=camera_uuid,
            room=camera.livekit_room_name,
        )
    except LiveKitTokenConfigError as exc:
        _record_user_audit_safely(
            db,
            request=request,
            actor_id=user.id,
            action="viewer.token.denied.livekit_config",
            resource=f"camera:{camera_uuid}",
            payload={"camera_id": camera_uuid, "room": camera.livekit_room_name},
        )
        raise ProblemDetail(
            status=503,
            title="Service Unavailable",
            detail=str(exc),
            type_uri="https://panoptix.local/problems/service-unavailable",
        ) from exc

    record_stream_grant(
        db,
        user_id=user.id,
        camera_id=camera_uuid,
        kind=StreamKind.viewer_subscribe,
        jti=grant.jti,
        issued_at=grant.issued_at,
        expires_at=grant.expires_at,
    )
    _record_user_audit_required(
        db,
        request=request,
        actor_id=user.id,
        action="viewer.token.issued",
        resource=f"camera:{camera_uuid}",
        payload={
            "camera_id": camera_uuid,
            "room": camera.livekit_room_name,
            "grant_jti": grant.jti,
            "expires_at": grant.expires_at,
        },
    )
    return ViewerTokenResponse(
        camera_id=str(camera.id),
        room=grant.room,
        livekit_url=grant.livekit_url,
        token=grant.token,
        expires_at=grant.expires_at,
    )


@v1_router.get("/sessions/active")
def get_active_sessions(
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    sessions = list_active_sessions(db, user.id)
    return {
        "items": [
            {
                "id": str(s.id),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "last_seen_at": s.last_seen_at.isoformat() if s.last_seen_at else None,
                "ua_fp": s.ua_fp,
            }
            for s in sessions
        ],
    }


class RevokeSessionRequest(BaseModel):
    session_id: uuid.UUID


@v1_router.post("/sessions/revoke")
def revoke_user_session(
    body: RevokeSessionRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)

    is_admin = "admin" in principal.roles

    if not is_admin:
        own_sessions = list_active_sessions(db, user.id)
        own_ids = {str(s.id) for s in own_sessions}
        if str(body.session_id) not in own_ids:
            _record_user_audit_safely(
                db,
                request=request,
                actor_id=user.id,
                action="session.revoke.denied.not_owned",
                resource=f"session:{body.session_id}",
                payload={"session_id": body.session_id},
            )
            raise ProblemDetail(
                status=403,
                title="Forbidden",
                detail="session-not-owned",
                type_uri="https://panoptix.local/problems/forbidden",
            )

    revoked = revoke_session(db, body.session_id)
    _record_user_audit_required(
        db,
        request=request,
        actor_id=user.id,
        action="session.revoke.succeeded" if revoked else "session.revoke.not_found",
        resource=f"session:{body.session_id}",
        payload={"session_id": body.session_id, "revoked": revoked},
    )
    return {"revoked": revoked, "session_id": str(body.session_id)}


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


def _record_user_audit_safely(
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
            actor_type=ActorType.user,
            actor_id=actor_id,
            action=action,
            resource=resource,
            payload=payload,
            ip=_request_ip(request),
            ua=_request_ua(request),
        )
    except AuditLogError:
        return


def _record_user_audit_required(
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
            actor_type=ActorType.user,
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
