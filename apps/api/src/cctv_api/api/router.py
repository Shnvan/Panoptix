from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Generator, Sequence
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from starlette.responses import StreamingResponse

from cctv_api.api.errors import ProblemDetail
from cctv_api.api.gateways import router as gateway_router
from cctv_api.api.livekit_webhooks import router as livekit_webhook_router
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.gateway.command_queue import enqueue_command, expire_stale_commands
from cctv_api.jobs.maintenance import run_admin_maintenance_job
from cctv_api.models.enums import ActorType, CameraSourceType, CommandStatus, GatewayStatus, StreamKind
from cctv_api.models.tables import (
    AuditHmacKey,
    AuditLog,
    Camera,
    CameraAcl,
    CameraEvent,
    EdgeGateway,
    GatewayCameraAssignment,
    GatewayCommandQueue,
    PrivacyNoticeAcceptance,
    Role,
    User,
    UserRole,
)
from cctv_api.security.audit import (
    AuditLogError,
    record_audit_event,
    verify_audit_chain_by_key_version,
)
from cctv_api.security.dependencies import require_authenticated_user
from cctv_api.security.identity import Principal
from cctv_api.security.livekit_tokens import LiveKitTokenConfigError, mint_viewer_subscribe_token
from cctv_api.security.policy import require_role
from cctv_api.security.service_tokens import generate_service_token, hash_service_token
from cctv_api.security.sessions import list_active_sessions, revoke_all_user_sessions, revoke_session
from cctv_api.security.stream_access import (
    get_active_camera,
    record_stream_grant,
    user_has_active_camera_acl,
)
from cctv_api.security.users import get_or_create_user, get_user_roles

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(gateway_router)
v1_router.include_router(livekit_webhook_router)

CURRENT_PRIVACY_NOTICE_VERSION = "2026-05-10"
CURRENT_PRIVACY_NOTICE_TITLE = "Panoptix CCTV Operator Privacy Notice"
CURRENT_PRIVACY_NOTICE_BODY = (
    "Panoptix provides live-view access to assigned CCTV cameras only. "
    "Use is audited. Do not record, publish, or share camera views outside approved operations."
)


@v1_router.get("/me")
def get_me(principal: Principal = Depends(require_authenticated_user)) -> dict[str, object]:
    return principal.to_response()


@v1_router.get("/cameras")
def list_cameras(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)

    query = (
        select(Camera)
        .join(CameraAcl, CameraAcl.camera_id == Camera.id)
        .where(Camera.retired_at.is_(None))
        .where(CameraAcl.user_id == str(user.id))
        .where(CameraAcl.revoked_at.is_(None))
        .order_by(Camera.created_at.desc())
    )

    if cursor:
        cursor_uuid = _parse_uuid(cursor, "invalid cursor")
        cursor_row = db.execute(select(Camera).where(Camera.id == str(cursor_uuid))).scalar_one_or_none()
        if cursor_row:
            query = query.where(Camera.created_at < cursor_row.created_at)

    rows = db.execute(query.limit(limit + 1)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    items = [
        {
            "camera_id": str(row.id),
            "display_name": row.display_name,
            "source_type": row.source_type.value if row.source_type else None,
            "livekit_room_name": row.livekit_room_name,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]

    next_cursor = str(rows[-1].id) if has_more and rows else None
    return {"items": items, "next_cursor": next_cursor}


@v1_router.get("/cameras/events")
def stream_camera_events(
    since: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> StreamingResponse:
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    since_at = _parse_datetime(since, "since-invalid") if since is not None else None

    query = (
        select(CameraEvent)
        .join(Camera, Camera.id == CameraEvent.camera_id)
        .join(CameraAcl, CameraAcl.camera_id == Camera.id)
        .where(Camera.retired_at.is_(None))
        .where(CameraAcl.user_id == str(user.id))
        .where(CameraAcl.revoked_at.is_(None))
        .order_by(CameraEvent.at.asc(), CameraEvent.id.asc())
        .limit(limit)
    )
    if since_at is not None:
        query = query.where(CameraEvent.at > since_at)

    rows = db.execute(query).scalars().all()
    return StreamingResponse(_iter_camera_event_sse(rows), media_type="text/event-stream")


class ViewerTokenResponse(BaseModel):
    camera_id: str
    room: str
    livekit_url: str
    token: str
    expires_at: datetime


class AuditVerificationResponse(BaseModel):
    valid: bool
    checked: int
    error: str | None = None


class PrivacyNoticeResponse(BaseModel):
    notice_version: str
    title: str
    body: str
    accepted: bool
    accepted_at: datetime | None = None


class PrivacyNoticeAcceptRequest(BaseModel):
    notice_version: str = Field(min_length=1, max_length=64)


class PrivacyNoticeAcceptResponse(BaseModel):
    notice_version: str
    accepted_at: datetime
    status: str


@v1_router.get("/admin/users")
def list_admin_users(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    email: str | None = Query(default=None, max_length=320),
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    require_role(principal, "admin")
    query = select(User).order_by(User.created_at.desc(), User.id.desc())
    if email is not None:
        query = query.where(User.email == email)
    if cursor is not None:
        cursor_uuid = _parse_uuid(cursor, "cursor-invalid")
        cursor_row = db.execute(select(User).where(User.id == str(cursor_uuid))).scalar_one_or_none()
        if cursor_row is not None:
            query = query.where(User.created_at < cursor_row.created_at)
    rows = list(db.execute(query.limit(limit + 1)).scalars().all())
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    next_cursor: str | None = str(rows[-1].id) if has_more and rows else None
    items = [
        {
            "user_id": str(row.id),
            "email": row.email,
            "roles": sorted(get_user_roles(db, row.id)),
            "role_default": row.role_default,
            "disabled_at": row.disabled_at.isoformat() if row.disabled_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
    return {"items": items, "next_cursor": next_cursor}


class RoleActionRequest(BaseModel):
    action: str = Field(pattern="^(grant|revoke)$")
    role_name: str = Field(min_length=1, max_length=64)


class RoleActionResponse(BaseModel):
    user_id: str
    role_name: str
    action: str
    status: str


@v1_router.post("/admin/users/{user_id}/role")
def admin_user_role(
    user_id: str,
    body: RoleActionRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> RoleActionResponse:
    require_role(principal, "admin")
    target_uuid = _parse_uuid(user_id, "user-not-found")
    target_user = db.execute(select(User).where(User.id == str(target_uuid))).scalar_one_or_none()
    if target_user is None:
        raise ProblemDetail(status=404, title="Not Found", detail="user-not-found", type_uri="https://panoptix.local/problems/not-found")
    role_row = db.execute(select(Role).where(Role.name == body.role_name)).scalar_one_or_none()
    if role_row is None:
        raise ProblemDetail(status=404, title="Not Found", detail="role-not-found", type_uri="https://panoptix.local/problems/not-found")
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    existing = db.execute(
        select(UserRole).where(UserRole.user_id == str(target_uuid), UserRole.role_id == role_row.id)
    ).scalar_one_or_none()
    if body.action == "grant":
        if existing is not None:
            raise ProblemDetail(status=409, title="Conflict", detail="role-already-granted", type_uri="https://panoptix.local/problems/conflict")
        db.add(UserRole(user_id=target_uuid, role_id=role_row.id))
        db.flush()
        _record_user_audit_required(
            db, settings=settings, request=request, actor_id=actor.id,
            action="admin.user.role.granted",
            resource=f"user:{target_uuid}",
            payload={"user_id": str(target_uuid), "role_name": body.role_name},
        )
    else:
        if existing is None:
            raise ProblemDetail(status=404, title="Not Found", detail="role-not-granted", type_uri="https://panoptix.local/problems/not-found")
        db.delete(existing)
        db.flush()
        _record_user_audit_required(
            db, settings=settings, request=request, actor_id=actor.id,
            action="admin.user.role.revoked",
            resource=f"user:{target_uuid}",
            payload={"user_id": str(target_uuid), "role_name": body.role_name},
        )
    db.commit()
    return RoleActionResponse(user_id=str(target_uuid), role_name=body.role_name, action=body.action, status="ok")


class DisableUserRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=512)


class DisableUserResponse(BaseModel):
    user_id: str
    disabled_at: str
    sessions_revoked: int


@v1_router.post("/admin/users/{user_id}/disable")
def admin_disable_user(
    user_id: str,
    body: DisableUserRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> DisableUserResponse:
    require_role(principal, "admin")
    target_uuid = _parse_uuid(user_id, "user-not-found")
    target_user = db.execute(select(User).where(User.id == str(target_uuid))).scalar_one_or_none()
    if target_user is None:
        raise ProblemDetail(status=404, title="Not Found", detail="user-not-found", type_uri="https://panoptix.local/problems/not-found")
    if target_user.disabled_at is not None:
        raise ProblemDetail(status=409, title="Conflict", detail="user-already-disabled", type_uri="https://panoptix.local/problems/conflict")
    now = datetime.now(timezone.utc)
    target_user.disabled_at = now
    db.flush()
    sessions_revoked = revoke_all_user_sessions(db, target_uuid)
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db, settings=settings, request=request, actor_id=actor.id,
        action="admin.user.disabled",
        resource=f"user:{target_uuid}",
        payload={"user_id": str(target_uuid), "reason": body.reason, "sessions_revoked": sessions_revoked},
    )
    db.commit()
    return DisableUserResponse(user_id=str(target_uuid), disabled_at=now.isoformat(), sessions_revoked=sessions_revoked)


@v1_router.get("/privacy/notice")
def get_privacy_notice(
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> PrivacyNoticeResponse:
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    acceptance = db.execute(
        select(PrivacyNoticeAcceptance)
        .where(PrivacyNoticeAcceptance.user_id == str(user.id))
        .where(PrivacyNoticeAcceptance.notice_version == CURRENT_PRIVACY_NOTICE_VERSION)
    ).scalar_one_or_none()
    return PrivacyNoticeResponse(
        notice_version=CURRENT_PRIVACY_NOTICE_VERSION,
        title=CURRENT_PRIVACY_NOTICE_TITLE,
        body=CURRENT_PRIVACY_NOTICE_BODY,
        accepted=acceptance is not None,
        accepted_at=acceptance.accepted_at if acceptance is not None else None,
    )


@v1_router.post("/privacy/notice/accept")
def accept_privacy_notice(
    body: PrivacyNoticeAcceptRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> PrivacyNoticeAcceptResponse:
    if body.notice_version != CURRENT_PRIVACY_NOTICE_VERSION:
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="privacy-notice-version-mismatch",
            type_uri="https://panoptix.local/problems/conflict",
        )
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    acceptance = db.execute(
        select(PrivacyNoticeAcceptance)
        .where(PrivacyNoticeAcceptance.user_id == str(user.id))
        .where(PrivacyNoticeAcceptance.notice_version == CURRENT_PRIVACY_NOTICE_VERSION)
    ).scalar_one_or_none()
    if acceptance is None:
        acceptance = PrivacyNoticeAcceptance(
            user_id=user.id,
            notice_version=CURRENT_PRIVACY_NOTICE_VERSION,
            accepted_at=datetime.now(timezone.utc),
        )
        db.add(acceptance)
        _record_user_audit_required(
            db,
            settings=settings,
            request=request,
            actor_id=user.id,
            action="privacy.notice.accepted",
            resource=f"privacy_notice:{CURRENT_PRIVACY_NOTICE_VERSION}",
            payload={"notice_version": CURRENT_PRIVACY_NOTICE_VERSION},
        )
        db.commit()
    return PrivacyNoticeAcceptResponse(
        notice_version=acceptance.notice_version,
        accepted_at=acceptance.accepted_at,
        status="accepted",
    )


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
            settings=settings,
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
            settings=settings,
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
            settings=settings,
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
            settings=settings,
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
        settings=settings,
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


@v1_router.get("/admin/audit/verify")
def verify_admin_audit_chain(
    start_id: int | None = Query(default=None, ge=1),
    end_id: int | None = Query(default=None, ge=1),
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> AuditVerificationResponse:
    require_role(principal, "admin")
    if start_id is not None and end_id is not None and start_id > end_id:
        raise ProblemDetail(
            status=422,
            title="Unprocessable Entity",
            detail="audit-range-invalid",
            type_uri="https://panoptix.local/problems/unprocessable-entity",
        )
    if not settings.AUDIT_HMAC_KEY.strip() or settings.AUDIT_HMAC_KEY.strip() == "replace-me":
        raise ProblemDetail(
            status=503,
            title="Service Unavailable",
            detail="audit-hmac-key-invalid",
            type_uri="https://panoptix.local/problems/service-unavailable",
        )
    query = select(AuditLog)
    if start_id is not None:
        query = query.where(AuditLog.id >= start_id)
    if end_id is not None:
        query = query.where(AuditLog.id <= end_id)
    rows = db.execute(query.order_by(AuditLog.id)).scalars().all()
    previous_hash = None
    if start_id is not None:
        previous_hash = db.execute(
            select(AuditLog.hash).where(AuditLog.id < start_id).order_by(AuditLog.id.desc()).limit(1)
        ).scalar_one_or_none()
    key_versions = {row.hmac_key_version for row in rows}
    key_rows = (
        db.execute(select(AuditHmacKey).where(AuditHmacKey.version.in_(key_versions))).scalars().all()
        if key_versions
        else []
    )
    key_map = {row.version: bytes(row.key_enc) for row in key_rows}
    result = verify_audit_chain_by_key_version(
        rows,
        audit_hmac_keys_by_version=key_map,
        start_prev_hash=previous_hash,
    )
    return AuditVerificationResponse(valid=result.valid, checked=result.checked, error=result.error)


@v1_router.get("/admin/audit/export")
def export_admin_audit(
    start_id: int | None = Query(default=None, ge=1),
    end_id: int | None = Query(default=None, ge=1),
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    if start_id is not None and end_id is not None and start_id > end_id:
        raise ProblemDetail(
            status=422,
            title="Unprocessable Entity",
            detail="audit-range-invalid",
            type_uri="https://panoptix.local/problems/unprocessable-entity",
        )
    if not settings.AUDIT_HMAC_KEY.strip() or settings.AUDIT_HMAC_KEY.strip() == "replace-me":
        raise ProblemDetail(
            status=503,
            title="Service Unavailable",
            detail="audit-hmac-key-invalid",
            type_uri="https://panoptix.local/problems/service-unavailable",
        )
    query = select(AuditLog)
    if start_id is not None:
        query = query.where(AuditLog.id >= start_id)
    if end_id is not None:
        query = query.where(AuditLog.id <= end_id)
    rows = list(db.execute(query.order_by(AuditLog.id)).scalars().all())
    items = [_audit_export_item(row) for row in rows]
    manifest = _signed_audit_export_manifest(
        items,
        signature_key_version=settings.AUDIT_HMAC_KEY_VERSION,
        signature_key=settings.AUDIT_HMAC_KEY,
    )
    return {"format": "audit-export-v1", "manifest": manifest, "items": items}


@v1_router.get("/admin/audit")
def list_admin_audit(
    cursor: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None, max_length=128),
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    if not settings.AUDIT_HMAC_KEY.strip() or settings.AUDIT_HMAC_KEY.strip() == "replace-me":
        raise ProblemDetail(
            status=503,
            title="Service Unavailable",
            detail="audit-hmac-key-invalid",
            type_uri="https://panoptix.local/problems/service-unavailable",
        )
    query = select(AuditLog)
    if action is not None:
        query = query.where(AuditLog.action == action)
    if cursor is not None:
        query = query.where(AuditLog.id < cursor)
    query = query.order_by(AuditLog.id.desc()).limit(limit + 1)
    rows = list(db.execute(query).scalars().all())
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    next_cursor: str | None = str(rows[-1].id) if has_more and rows else None
    items = [
        {
            "id": row.id,
            "ts": row.ts.isoformat() if row.ts else None,
            "actor_id": str(row.actor_id) if row.actor_id else None,
            "actor_type": row.actor_type.value if row.actor_type else None,
            "action": row.action,
            "resource": row.resource,
            "payload": row.payload,
            "ip": row.ip,
            "ua": row.ua,
        }
        for row in rows
    ]
    return {"items": items, "next_cursor": next_cursor}


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
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)

    is_admin = "admin" in principal.roles

    if not is_admin:
        own_sessions = list_active_sessions(db, user.id)
        own_ids = {str(s.id) for s in own_sessions}
        if str(body.session_id) not in own_ids:
            _record_user_audit_safely(
                db,
                settings=settings,
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
        settings=settings,
        request=request,
        actor_id=user.id,
        action="session.revoke.succeeded" if revoked else "session.revoke.not_found",
        resource=f"session:{body.session_id}",
        payload={"session_id": body.session_id, "revoked": revoked},
    )
    return {"revoked": revoked, "session_id": str(body.session_id)}


def _audit_export_item(row: AuditLog) -> dict[str, object]:
    return {
        "id": row.id,
        "ts": row.ts.isoformat() if row.ts else None,
        "actor_id": str(row.actor_id) if row.actor_id else None,
        "actor_type": row.actor_type.value if row.actor_type else None,
        "action": row.action,
        "resource": row.resource,
        "payload": row.payload,
        "ip": row.ip,
        "ua": row.ua,
    }


def _signed_audit_export_manifest(
    items: Sequence[dict[str, object]],
    *,
    signature_key_version: int,
    signature_key: str,
) -> dict[str, object]:
    content_sha256 = hashlib.sha256(_canonical_json_bytes(items)).hexdigest()
    manifest: dict[str, object] = {
        "row_count": len(items),
        "start_id": items[0]["id"] if items else None,
        "end_id": items[-1]["id"] if items else None,
        "content_sha256": content_sha256,
        "signature_algorithm": "HMAC-SHA256",
        "signature_key_version": signature_key_version,
    }
    manifest["signature"] = hmac.new(
        signature_key.strip().encode("utf-8"),
        _canonical_json_bytes(manifest),
        hashlib.sha256,
    ).hexdigest()
    return manifest


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _iter_camera_event_sse(rows: Sequence[CameraEvent]) -> Generator[str, None, None]:
    for row in rows:
        line = json.dumps(
            {
                "event_id": str(row.id),
                "camera_id": str(row.camera_id),
                "gateway_id": str(row.gateway_id) if row.gateway_id else None,
                "kind": row.kind.value if hasattr(row.kind, "value") else row.kind,
                "source": row.source.value if hasattr(row.source, "value") else row.source,
                "at": row.at.isoformat(),
            },
            separators=(",", ":"),
            ensure_ascii=True,
        )
        yield f"event: camera_event\ndata: {line}\n\n"


def _parse_datetime(value: str, detail: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail=detail,
            type_uri="https://panoptix.local/problems/bad-request",
        ) from exc


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
    settings: Settings,
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
            audit_hmac_key_version=settings.AUDIT_HMAC_KEY_VERSION,
            audit_hmac_key=settings.AUDIT_HMAC_KEY,
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
    settings: Settings,
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
            audit_hmac_key_version=settings.AUDIT_HMAC_KEY_VERSION,
            audit_hmac_key=settings.AUDIT_HMAC_KEY,
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


class EnqueueCommandRequest(BaseModel):
    kind: str = Field(max_length=128)
    payload: dict[str, object] = Field(default_factory=dict)
    expires_in_seconds: int = Field(default=300, ge=10, le=3600)


class EnqueueCommandResponse(BaseModel):
    command_id: str
    gateway_id: str
    kind: str
    status: str
    expires_at: str


@v1_router.post("/admin/gateways/{gateway_id}/commands", status_code=201)
def enqueue_gateway_command(
    gateway_id: str,
    body: EnqueueCommandRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> EnqueueCommandResponse:
    require_role(principal, "admin")
    gw_uuid = _parse_uuid(gateway_id, "gateway-id-invalid")
    gw_row = db.execute(
        select(EdgeGateway).where(EdgeGateway.id == str(gw_uuid))
    ).scalar_one_or_none()
    if gw_row is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="gateway-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=body.expires_in_seconds)
    row = enqueue_command(db, gateway_id=gw_uuid, kind=body.kind, payload=body.payload, expires_at=expires_at)
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=user.id,
        action="command.enqueue",
        resource=f"gateway:{gw_uuid}",
        payload={"command_id": str(row.id), "gateway_id": str(gw_uuid), "kind": body.kind},
    )
    db.commit()
    return EnqueueCommandResponse(
        command_id=str(row.id),
        gateway_id=str(row.gateway_id),
        kind=row.kind,
        status=row.status.value,
        expires_at=row.expires_at.isoformat(),
    )


@v1_router.get("/admin/gateways/{gateway_id}/commands")
def list_gateway_commands(
    gateway_id: str,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    require_role(principal, "admin")
    gw_uuid = _parse_uuid(gateway_id, "gateway-id-invalid")

    gw_row = db.execute(
        select(EdgeGateway).where(EdgeGateway.id == str(gw_uuid))
    ).scalar_one_or_none()
    if gw_row is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="gateway-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )

    query = select(GatewayCommandQueue).where(
        GatewayCommandQueue.gateway_id == str(gw_uuid)
    )

    if status is not None:
        if status not in ("pending", "accepted", "rejected", "expired", "cancelled"):
            raise ProblemDetail(
                status=400,
                title="Bad Request",
                detail="status-invalid",
                type_uri="https://panoptix.local/problems/bad-request",
            )
        query = query.where(GatewayCommandQueue.status == status)

    if cursor is not None:
        cursor_uuid = _parse_uuid(cursor, "cursor-invalid")
        cursor_row = db.execute(
            select(GatewayCommandQueue).where(GatewayCommandQueue.id == str(cursor_uuid))
        ).scalar_one_or_none()
        if cursor_row is not None:
            query = query.where(GatewayCommandQueue.issued_at < cursor_row.issued_at)

    query = query.order_by(GatewayCommandQueue.issued_at.desc()).limit(limit + 1)
    rows = list(db.execute(query).scalars().all())

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    next_cursor: str | None = str(rows[-1].id) if has_more and rows else None

    items = [
        {
            "command_id": str(row.id),
            "gateway_id": str(row.gateway_id),
            "kind": row.kind,
            "payload": row.payload,
            "status": row.status.value if hasattr(row.status, "value") else row.status,
            "issued_at": row.issued_at.isoformat() if row.issued_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "acked_at": row.acked_at.isoformat() if row.acked_at else None,
            "error": row.error,
        }
        for row in rows
    ]
    return {"items": items, "next_cursor": next_cursor}


class CancelCommandResponse(BaseModel):
    command_id: str
    gateway_id: str
    kind: str
    status: str
    cancelled_at: str


@v1_router.post("/admin/gateways/{gateway_id}/commands/{command_id}/cancel")
def cancel_gateway_command(
    gateway_id: str,
    command_id: str,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> CancelCommandResponse:
    require_role(principal, "admin")
    gw_uuid = _parse_uuid(gateway_id, "gateway-id-invalid")
    cmd_uuid = _parse_uuid(command_id, "command-id-invalid")

    gw_row = db.execute(
        select(EdgeGateway).where(EdgeGateway.id == str(gw_uuid))
    ).scalar_one_or_none()
    if gw_row is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="gateway-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )

    cmd_row = db.execute(
        select(GatewayCommandQueue)
        .where(GatewayCommandQueue.id == str(cmd_uuid))
        .where(GatewayCommandQueue.gateway_id == str(gw_uuid))
    ).scalar_one_or_none()
    if cmd_row is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="command-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )

    if cmd_row.status != CommandStatus.pending:
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="command-not-pending",
            type_uri="https://panoptix.local/problems/conflict",
        )

    now = datetime.now(timezone.utc)
    cmd_row.status = CommandStatus.cancelled
    cmd_row.acked_at = now
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=user.id,
        action="command.cancel",
        resource=f"command:{cmd_uuid}",
        payload={"command_id": str(cmd_uuid), "gateway_id": str(gw_uuid), "kind": cmd_row.kind},
    )
    db.commit()

    return CancelCommandResponse(
        command_id=str(cmd_row.id),
        gateway_id=str(cmd_row.gateway_id),
        kind=cmd_row.kind,
        status="cancelled",
        cancelled_at=now.isoformat(),
    )


class ExpireCommandsResponse(BaseModel):
    expired_count: int


@v1_router.post("/admin/commands/cleanup")
def expire_pending_commands(
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> ExpireCommandsResponse:
    require_role(principal, "admin")
    count = expire_stale_commands(db)
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=user.id,
        action="commands.cleanup",
        resource="commands",
        payload={"expired_count": count},
    )
    db.commit()
    return ExpireCommandsResponse(expired_count=count)


class MaintenanceResponse(BaseModel):
    expired_commands: int
    stops_enqueued: int


@v1_router.post("/admin/jobs/run-maintenance")
def run_maintenance(
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> MaintenanceResponse:
    require_role(principal, "admin")
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)

    def _audit(action: str, resource: str, payload: dict[str, object | None]) -> None:
        _record_user_audit_required(
            db,
            settings=settings,
            request=request,
            actor_id=user.id,
            action=action,
            resource=resource,
            payload=payload,
        )

    result = run_admin_maintenance_job(db, audit=_audit)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=user.id,
        action="admin.maintenance.run",
        resource="maintenance",
        payload={"expired_commands": result.expired_commands, "stops_enqueued": result.stops_enqueued},
    )
    db.commit()
    return MaintenanceResponse(expired_commands=result.expired_commands, stops_enqueued=result.stops_enqueued)


# ── Admin Camera CRUD ──


class CreateGatewayRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    mtls_fingerprint: str | None = Field(default=None, max_length=255)
    cert_expires_at: datetime | None = None


class DisableGatewayRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class GatewayCameraAssignmentRequest(BaseModel):
    action: str
    camera_id: str


@v1_router.post("/admin/gateways", status_code=201)
def create_gateway(
    body: CreateGatewayRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    now = datetime.now(timezone.utc)
    raw_token = generate_service_token()
    gateway = EdgeGateway(
        id=uuid.uuid4(),
        name=body.name,
        status=GatewayStatus.enabled,
        service_token_hash=hash_service_token(raw_token),
        mtls_fingerprint=body.mtls_fingerprint,
        cert_expires_at=body.cert_expires_at,
        created_at=now,
    )
    db.add(gateway)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="gateway.create",
        resource=f"gateway:{gateway.id}",
        payload={"gateway_id": str(gateway.id), "name": body.name, "credential_issued": True},
    )
    db.commit()
    return {
        "gateway_id": str(gateway.id),
        "name": gateway.name,
        "status": gateway.status.value,
        "created_at": gateway.created_at.isoformat(),
        "service_token": raw_token,
    }


@v1_router.post("/admin/gateways/{gateway_id}/disable")
def disable_gateway(
    gateway_id: str,
    body: DisableGatewayRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    gateway_uuid = _parse_uuid(gateway_id, "gateway-id-invalid")
    gateway = db.execute(select(EdgeGateway).where(EdgeGateway.id == str(gateway_uuid))).scalar_one_or_none()
    if gateway is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="gateway-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )
    if gateway.status == GatewayStatus.disabled or gateway.disabled_at is not None:
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="gateway-already-disabled",
            type_uri="https://panoptix.local/problems/conflict",
        )

    now = datetime.now(timezone.utc)
    gateway.status = GatewayStatus.disabled
    gateway.disabled_at = now
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="gateway.disable",
        resource=f"gateway:{gateway_uuid}",
        payload={"gateway_id": str(gateway_uuid), "reason": body.reason},
    )
    db.commit()
    return {
        "gateway_id": str(gateway_uuid),
        "name": gateway.name,
        "status": gateway.status.value,
        "disabled_at": gateway.disabled_at.isoformat(),
    }


class RotateCredentialRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=512)


@v1_router.post("/admin/gateways/{gateway_id}/rotate-credential")
def rotate_gateway_credential(
    gateway_id: str,
    body: RotateCredentialRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    gateway_uuid = _parse_uuid(gateway_id, "gateway-id-invalid")
    gateway = db.execute(select(EdgeGateway).where(EdgeGateway.id == str(gateway_uuid))).scalar_one_or_none()
    if gateway is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="gateway-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )
    if gateway.status == GatewayStatus.disabled or gateway.disabled_at is not None:
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="gateway-disabled",
            type_uri="https://panoptix.local/problems/conflict",
        )
    raw_token = generate_service_token()
    gateway.service_token_hash = hash_service_token(raw_token)
    now = datetime.now(timezone.utc)
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="gateway.credential.rotated",
        resource=f"gateway:{gateway_uuid}",
        payload={"gateway_id": str(gateway_uuid), "reason": body.reason},
    )
    db.commit()
    return {
        "gateway_id": str(gateway_uuid),
        "service_token": raw_token,
        "rotated_at": now.isoformat(),
    }


@v1_router.post("/admin/gateways/{gateway_id}/cameras")
def manage_gateway_camera_assignment(
    gateway_id: str,
    body: GatewayCameraAssignmentRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    gateway_uuid = _parse_uuid(gateway_id, "gateway-id-invalid")
    camera_uuid = _parse_uuid(body.camera_id, "camera-id-invalid")

    gateway = db.execute(select(EdgeGateway).where(EdgeGateway.id == str(gateway_uuid))).scalar_one_or_none()
    if gateway is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="gateway-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )

    camera = get_active_camera(db, camera_uuid)
    if camera is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="camera-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )

    if body.action not in ("grant", "revoke"):
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="action-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        )

    active_assignment = db.execute(
        select(GatewayCameraAssignment).where(
            GatewayCameraAssignment.gateway_id == str(gateway_uuid),
            GatewayCameraAssignment.camera_id == str(camera_uuid),
            GatewayCameraAssignment.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)

    if body.action == "grant":
        if active_assignment is not None:
            raise ProblemDetail(
                status=409,
                title="Conflict",
                detail="gateway-camera-assignment-already-active",
                type_uri="https://panoptix.local/problems/conflict",
            )
        assignment = GatewayCameraAssignment(
            gateway_id=gateway_uuid,
            camera_id=camera_uuid,
            granted_by=actor.id,
            granted_at=datetime.now(timezone.utc),
        )
        db.add(assignment)
    else:
        if active_assignment is None:
            raise ProblemDetail(
                status=404,
                title="Not Found",
                detail="gateway-camera-assignment-not-found",
                type_uri="https://panoptix.local/problems/not-found",
            )
        active_assignment.revoked_at = datetime.now(timezone.utc)

    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action=f"gateway.camera.{body.action}",
        resource=f"gateway:{gateway_uuid}",
        payload={"gateway_id": str(gateway_uuid), "camera_id": str(camera_uuid), "action": body.action},
    )
    db.commit()
    return {
        "gateway_id": str(gateway_uuid),
        "camera_id": str(camera_uuid),
        "action": body.action,
        "status": "applied",
    }


class CreateCameraRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    source_type: str
    livekit_room_name: str = Field(min_length=1, max_length=64)


class CameraAclRequest(BaseModel):
    action: str
    user_email: str = Field(min_length=1, max_length=320)


class DisableCameraRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


@v1_router.post("/admin/cameras", status_code=201)
def create_camera(
    body: CreateCameraRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")

    if body.source_type not in [e.value for e in CameraSourceType]:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="source-type-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        )

    existing = db.execute(
        select(Camera).where(Camera.livekit_room_name == body.livekit_room_name)
    ).scalar_one_or_none()
    if existing is not None:
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="room-name-taken",
            type_uri="https://panoptix.local/problems/conflict",
        )

    camera = Camera(
        id=uuid.uuid4(),
        display_name=body.display_name,
        source_type=CameraSourceType(body.source_type),
        livekit_room_name=body.livekit_room_name,
    )
    db.add(camera)

    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=user.id,
        action="camera.create",
        resource=f"camera:{camera.id}",
        payload={"camera_id": str(camera.id), "display_name": body.display_name, "source_type": body.source_type},
    )
    db.commit()

    return {
        "camera_id": str(camera.id),
        "display_name": camera.display_name,
        "source_type": camera.source_type.value,
        "livekit_room_name": camera.livekit_room_name,
    }


@v1_router.post("/admin/cameras/{camera_id}/acl")
def manage_camera_acl(
    camera_id: str,
    body: CameraAclRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    cam_uuid = _parse_uuid(camera_id, "camera-id-invalid")

    camera = db.execute(select(Camera).where(Camera.id == str(cam_uuid))).scalar_one_or_none()
    if camera is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="camera-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )

    if body.action not in ("grant", "revoke"):
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="action-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        )

    target_user = get_or_create_user(db, email=body.user_email, idp_subject=None)

    if body.action == "grant":
        existing_acl = db.execute(
            select(CameraAcl).where(
                CameraAcl.user_id == str(target_user.id),
                CameraAcl.camera_id == str(cam_uuid),
                CameraAcl.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if existing_acl is not None:
            raise ProblemDetail(
                status=409,
                title="Conflict",
                detail="acl-already-active",
                type_uri="https://panoptix.local/problems/conflict",
            )
        acl = CameraAcl(user_id=target_user.id, camera_id=cam_uuid, granted_at=datetime.now(timezone.utc))
        db.add(acl)
    else:
        existing_acl = db.execute(
            select(CameraAcl).where(
                CameraAcl.user_id == str(target_user.id),
                CameraAcl.camera_id == str(cam_uuid),
                CameraAcl.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if existing_acl is None:
            raise ProblemDetail(
                status=404,
                title="Not Found",
                detail="acl-not-found",
                type_uri="https://panoptix.local/problems/not-found",
            )
        existing_acl.revoked_at = datetime.now(timezone.utc)

    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action=f"camera.acl.{body.action}",
        resource=f"camera:{cam_uuid}",
        payload={"camera_id": str(cam_uuid), "user_email": body.user_email, "action": body.action},
    )
    db.commit()

    return {"camera_id": str(cam_uuid), "user_email": body.user_email, "action": body.action, "status": "applied"}


@v1_router.post("/admin/cameras/{camera_id}/disable")
def disable_camera(
    camera_id: str,
    body: DisableCameraRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    cam_uuid = _parse_uuid(camera_id, "camera-id-invalid")

    camera = db.execute(select(Camera).where(Camera.id == str(cam_uuid))).scalar_one_or_none()
    if camera is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="camera-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )
    if camera.retired_at is not None:
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="camera-already-retired",
            type_uri="https://panoptix.local/problems/conflict",
        )

    camera.retired_at = datetime.now(timezone.utc)

    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=user.id,
        action="camera.disable",
        resource=f"camera:{cam_uuid}",
        payload={"camera_id": str(cam_uuid), "reason": body.reason},
    )
    db.commit()

    return {
        "camera_id": str(cam_uuid),
        "display_name": camera.display_name,
        "retired_at": camera.retired_at.isoformat(),
    }
