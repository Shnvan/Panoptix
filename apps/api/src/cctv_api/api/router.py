from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from collections.abc import Generator, Sequence
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession
from starlette.responses import StreamingResponse

from cctv_api.api.errors import ProblemDetail
from cctv_api.api.actor_profile import router as actor_profile_router
from cctv_api.api.gateways import router as gateway_router
from cctv_api.api.livekit_webhooks import router as livekit_webhook_router
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.gateway.command_queue import enqueue_command, expire_stale_commands
from cctv_api.integrations.github_invites import (
    GitHubInviteConfigError,
    GitHubInviteError,
    create_github_org_invitation,
)
from cctv_api.jobs.maintenance import run_admin_maintenance_job
from cctv_api.models.enums import ActorType, AlertCategory, AlertSeverity, AlertStatus, BackupUploadStatus, CameraPublishStatus, CameraSourceType, CommandStatus, DpaKind, EventCategory, EventOutcome, EventSeverity, GatewayStatus, RequestType, StreamKind, SubjectType
from cctv_api.models.tables import (
    Alert,
    AuditHmacKey,
    AuditLog,
    BackupRun,
    Camera,
    CameraAcl,
    CameraEvent,
    CameraPublishState,
    DpaArtifact,
    DsrRequest,
    EdgeGateway,
    GatewayCameraAssignment,
    GatewayCommandQueue,
    PrivacyNoticeAcceptance,
    Role,
    Site,
    User,
    UserRole,
)
from cctv_api.security.audit import (
    AuditLogError,
    record_audit_event,
    verify_audit_chain_by_key_version,
)
from cctv_api.security.alerts import (
    acknowledge_alert,
    alert_to_response,
    detect_alert_from_audit_event,
    detect_alert_from_backup_status,
    resolve_alert,
)
from cctv_api.security.dependencies import require_authenticated_user
from cctv_api.security.identity import Principal
from cctv_api.security.livekit_rooms import remove_gateway_participants, remove_room_viewers, remove_user_participants
from cctv_api.security.livekit_tokens import LiveKitTokenConfigError, mint_viewer_subscribe_token
from cctv_api.security.policy import require_role
from cctv_api.security.rate_limit import RateLimitConfig, get_rate_limiter
from cctv_api.security.service_tokens import generate_service_token, hash_service_token
from cctv_api.security.sessions import list_active_sessions, revoke_all_user_sessions, revoke_session
from cctv_api.security.stream_access import (
    get_active_camera,
    record_stream_grant,
    user_has_active_camera_acl,
)
from cctv_api.security.break_glass import (
    ROTATION_CHECKLIST,
    close_break_glass_window,
    get_break_glass_status,
    open_break_glass_window,
)
from cctv_api.security.media_plane import set_media_plane_mode
from cctv_api.security.users import get_or_create_user, get_user_roles

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(actor_profile_router)
v1_router.include_router(gateway_router)
v1_router.include_router(livekit_webhook_router)

CURRENT_PRIVACY_NOTICE_VERSION = "2026-05-10"
CURRENT_PRIVACY_NOTICE_TITLE = "Panoptix CCTV Operator Privacy Notice"
CURRENT_PRIVACY_NOTICE_BODY = (
    "Panoptix provides live-view access to assigned CCTV cameras only. "
    "Use is audited. Do not record, publish, or share camera views outside approved operations."
)

DSR_STATUSES = frozenset({"open", "verified", "in_progress", "completed", "rejected", "cancelled"})


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


class InviteUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role_names: list[str] = Field(default_factory=lambda: ["viewer"], max_length=8)
    reason: str | None = Field(default=None, max_length=512)


class InviteUserResponse(BaseModel):
    user_id: str
    email: str
    roles: list[str]
    github_invitation_id: int | None
    github_org: str
    status: str
    next_step: str


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
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _check_rate_limit(
        key=f"admin-mutation:{actor.id}",
        max_requests=settings.RATE_LIMIT_ADMIN_MUTATION_MAX,
        window_seconds=settings.RATE_LIMIT_ADMIN_MUTATION_WINDOW,
        audit_action="admin.rate_limited",
        resource="endpoint:/api/v1/admin/users/{user_id}/role",
        db=db,
        settings=settings,
        request=request,
        actor_id=actor.id,
    )
    target_uuid = _parse_uuid(user_id, "user-not-found")
    target_user = db.execute(select(User).where(User.id == str(target_uuid))).scalar_one_or_none()
    if target_user is None:
        raise ProblemDetail(status=404, title="Not Found", detail="user-not-found", type_uri="https://panoptix.local/problems/not-found")
    role_row = db.execute(select(Role).where(Role.name == body.role_name)).scalar_one_or_none()
    if role_row is None:
        raise ProblemDetail(status=404, title="Not Found", detail="role-not-found", type_uri="https://panoptix.local/problems/not-found")
    existing = db.execute(
        select(UserRole).where(UserRole.user_id == str(target_uuid), UserRole.role_id == role_row.id)
    ).scalar_one_or_none()
    roles_before = sorted(get_user_roles(db, target_uuid))
    if body.action == "grant":
        if existing is not None:
            raise ProblemDetail(status=409, title="Conflict", detail="role-already-granted", type_uri="https://panoptix.local/problems/conflict")
        db.add(UserRole(user_id=target_uuid, role_id=role_row.id))
        db.flush()
        roles_after = sorted(get_user_roles(db, target_uuid))
        audit_log = _record_user_audit_required(
            db, settings=settings, request=request, actor_id=actor.id,
            action="admin.user.role.granted",
            resource=f"user:{target_uuid}",
            payload={"user_id": str(target_uuid), "role_name": body.role_name, "roles_before": roles_before, "roles_after": roles_after},
        )
        _detect_alert_from_audit_safely(db, settings=settings, audit_log=audit_log)
    else:
        if existing is None:
            raise ProblemDetail(status=404, title="Not Found", detail="role-not-granted", type_uri="https://panoptix.local/problems/not-found")
        db.delete(existing)
        db.flush()
        roles_after = sorted(get_user_roles(db, target_uuid))
        _record_user_audit_required(
            db, settings=settings, request=request, actor_id=actor.id,
            action="admin.user.role.revoked",
            resource=f"user:{target_uuid}",
            payload={"user_id": str(target_uuid), "role_name": body.role_name, "roles_before": roles_before, "roles_after": roles_after},
        )
    db.commit()
    return RoleActionResponse(user_id=str(target_uuid), role_name=body.role_name, action=body.action, status="ok")


class DisableUserRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=512)


class DisableUserResponse(BaseModel):
    user_id: str
    disabled_at: str
    sessions_revoked: int
    participants_removed: int = 0
    participant_errors: list[str] = Field(default_factory=list)


class DisableGatewayResponse(BaseModel):
    gateway_id: str
    name: str
    status: str
    disabled_at: str
    participants_removed: int = 0
    participant_errors: list[str] = Field(default_factory=list)


class DisableCameraResponse(BaseModel):
    camera_id: str
    display_name: str
    retired_at: str
    participants_removed: int = 0
    participant_errors: list[str] = Field(default_factory=list)


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

    # ── LiveKit participant kill (§13.5 rule 11) ──
    acl_rooms = (
        db.execute(
            select(Camera.livekit_room_name)
            .join(CameraAcl, CameraAcl.camera_id == Camera.id)
            .where(CameraAcl.user_id == str(target_uuid))
            .where(CameraAcl.revoked_at.is_(None))
            .where(Camera.retired_at.is_(None))
        )
        .scalars()
        .all()
    )
    removal = remove_user_participants(settings, user_id=target_uuid, room_names=list(acl_rooms))

    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db, settings=settings, request=request, actor_id=actor.id,
        action="admin.user.disabled",
        resource=f"user:{target_uuid}",
        payload={
            "user_id": str(target_uuid),
            "reason": body.reason,
            "sessions_revoked": sessions_revoked,
            "participants_removed": removal.participants_removed,
            "participant_errors": removal.errors,
        },
    )
    db.commit()
    return DisableUserResponse(
        user_id=str(target_uuid),
        disabled_at=now.isoformat(),
        sessions_revoked=sessions_revoked,
        participants_removed=removal.participants_removed,
        participant_errors=removal.errors,
    )


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

    # ── Rate limit check (§16.17) ──
    _check_rate_limit(
        key=f"viewer-token:{user.id}",
        max_requests=settings.RATE_LIMIT_VIEWER_TOKEN_MAX,
        window_seconds=settings.RATE_LIMIT_VIEWER_TOKEN_WINDOW,
        audit_action="viewer.token.rate_limited",
        resource=f"camera:{camera_uuid}",
        db=db,
        settings=settings,
        request=request,
        actor_id=user.id,
    )

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
    request: Request,
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
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    audit_log = _record_user_audit_safely(
        db, settings=settings, request=request, actor_id=actor.id,
        action="audit.log.verified",
        resource="audit-log",
        payload={
            "start_id": start_id,
            "end_id": end_id,
            "checked": result.checked,
            "valid": result.valid,
            "error": result.error,
        },
    )
    if not result.valid:
        _detect_alert_from_audit_safely(db, settings=settings, audit_log=audit_log)
    return AuditVerificationResponse(valid=result.valid, checked=result.checked, error=result.error)


@v1_router.get("/admin/audit/export")
def export_admin_audit(
    request: Request,
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
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_safely(
        db, settings=settings, request=request, actor_id=actor.id,
        action="audit.log.exported",
        resource="audit-log",
        payload={"start_id": start_id, "end_id": end_id, "rows_exported": len(items)},
    )
    return {"format": "audit-export-v1", "manifest": manifest, "items": items}


@v1_router.get("/admin/audit")
def list_admin_audit(
    request: Request,
    cursor: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None, max_length=128),
    actor_type: str | None = Query(default=None, max_length=32),
    actor_id: str | None = Query(default=None, max_length=36),
    severity: str | None = Query(default=None, max_length=32),
    category: str | None = Query(default=None, max_length=32),
    outcome: str | None = Query(default=None, max_length=32),
    resource: str | None = Query(default=None, max_length=256),
    session_id: str | None = Query(default=None, max_length=36),
    ts_from: str | None = Query(default=None),
    ts_to: str | None = Query(default=None),
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
    if actor_type is not None:
        try:
            at_enum = ActorType(actor_type)
        except ValueError:
            raise ProblemDetail(status=400, title="Bad Request", detail="actor-type-invalid", type_uri="https://panoptix.local/problems/bad-request")
        query = query.where(AuditLog.actor_type == at_enum)
    if actor_id is not None:
        actor_uuid = _parse_uuid(actor_id, "actor-id-invalid")
        query = query.where(AuditLog.actor_id == str(actor_uuid))
    if severity is not None:
        try:
            sev_enum = EventSeverity(severity)
        except ValueError:
            raise ProblemDetail(status=400, title="Bad Request", detail="severity-invalid", type_uri="https://panoptix.local/problems/bad-request")
        query = query.where(AuditLog.event_severity == sev_enum)
    if category is not None:
        try:
            cat_enum = EventCategory(category)
        except ValueError:
            raise ProblemDetail(status=400, title="Bad Request", detail="category-invalid", type_uri="https://panoptix.local/problems/bad-request")
        query = query.where(AuditLog.event_category == cat_enum)
    if outcome is not None:
        try:
            out_enum = EventOutcome(outcome)
        except ValueError:
            raise ProblemDetail(status=400, title="Bad Request", detail="outcome-invalid", type_uri="https://panoptix.local/problems/bad-request")
        query = query.where(AuditLog.event_outcome == out_enum)
    if resource is not None:
        query = query.where(AuditLog.resource == resource)
    if session_id is not None:
        sid_uuid = _parse_uuid(session_id, "session-id-invalid")
        query = query.where(AuditLog.session_id == str(sid_uuid))
    if ts_from is not None:
        ts_from_dt = _parse_datetime(ts_from, "ts-from-invalid")
        query = query.where(AuditLog.ts >= ts_from_dt)
    if ts_to is not None:
        ts_to_dt = _parse_datetime(ts_to, "ts-to-invalid")
        query = query.where(AuditLog.ts <= ts_to_dt)
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
            "ip": str(row.ip) if row.ip is not None else None,
            "ua": row.ua,
            "event_severity": row.event_severity.value if row.event_severity else None,
            "event_outcome": row.event_outcome.value if row.event_outcome else None,
            "event_category": row.event_category.value if row.event_category else None,
            "session_id": str(row.session_id) if row.session_id else None,
        }
        for row in rows
    ]
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_safely(
        db, settings=settings, request=request, actor_id=actor.id,
        action="audit.log.viewed",
        resource="audit-log",
        payload={"action_filter": action, "cursor": cursor, "limit": limit, "rows_returned": len(items)},
    )
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
        "ip": str(row.ip) if row.ip is not None else None,
        "ua": row.ua,
        "event_severity": row.event_severity.value if row.event_severity else None,
        "event_outcome": row.event_outcome.value if row.event_outcome else None,
        "event_category": row.event_category.value if row.event_category else None,
        "session_id": str(row.session_id) if row.session_id else None,
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


def _parse_alert_status(value: str) -> AlertStatus:
    try:
        return AlertStatus(value)
    except ValueError as exc:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="alert-status-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        ) from exc


def _parse_alert_severity(value: str) -> AlertSeverity:
    try:
        return AlertSeverity(value)
    except ValueError as exc:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="alert-severity-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        ) from exc


def _parse_alert_category(value: str) -> AlertCategory:
    try:
        return AlertCategory(value)
    except ValueError as exc:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="alert-category-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        ) from exc


def _normalize_invite_email(value: str) -> str:
    email = value.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="email-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        )
    return email


def _audit_session_id(request: Request) -> uuid.UUID | None:
    return getattr(request.state, "audit_session_id", None)


def _record_user_audit_safely(
    db: DbSession,
    *,
    settings: Settings,
    request: Request,
    actor_id: uuid.UUID,
    action: str,
    resource: str,
    payload: dict[str, object] | None = None,
) -> AuditLog | None:
    try:
        return record_audit_event(
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
            session_id=_audit_session_id(request),
        )
    except AuditLogError:
        return None


def _record_user_audit_required(
    db: DbSession,
    *,
    settings: Settings,
    request: Request,
    actor_id: uuid.UUID,
    action: str,
    resource: str,
    payload: dict[str, object] | None = None,
) -> AuditLog:
    try:
        return record_audit_event(
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
            session_id=_audit_session_id(request),
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


def _check_rate_limit(
    *,
    key: str,
    max_requests: int,
    window_seconds: int,
    audit_action: str,
    resource: str,
    db: DbSession,
    settings: Settings,
    request: Request,
    actor_id: uuid.UUID,
) -> None:
    """Check rate limit and raise 429 if exceeded (§16.17)."""
    limiter = get_rate_limiter()
    config = RateLimitConfig(max_requests=max_requests, window_seconds=window_seconds)
    result = limiter.check(key, config)
    if not result.allowed:
        _record_user_audit_safely(
            db,
            settings=settings,
            request=request,
            actor_id=actor_id,
            action=audit_action,
            resource=resource,
            payload={"retry_after": result.retry_after},
        )
        raise ProblemDetail(
            status=429,
            title="Too Many Requests",
            detail="rate-limit-exceeded",
            type_uri="https://panoptix.local/problems/rate-limit-exceeded",
            headers={"Retry-After": str(result.retry_after)},
        )


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
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _check_rate_limit(
        key=f"admin-mutation:{user.id}",
        max_requests=settings.RATE_LIMIT_ADMIN_MUTATION_MAX,
        window_seconds=settings.RATE_LIMIT_ADMIN_MUTATION_WINDOW,
        audit_action="admin.rate_limited",
        resource="endpoint:/api/v1/admin/gateways/{gateway_id}/commands",
        db=db,
        settings=settings,
        request=request,
        actor_id=user.id,
    )
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


class UpdateGatewayRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    mtls_fingerprint: str | None = Field(default=None, max_length=255)
    cert_expires_at: datetime | None = None


class DisableGatewayRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class GatewayCameraAssignmentRequest(BaseModel):
    action: str
    camera_id: str


@v1_router.get("/admin/dashboard")
def admin_dashboard(
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    require_role(principal, "admin")

    cameras_total = db.execute(select(func.count()).select_from(Camera)).scalar_one()
    cameras_active = db.execute(
        select(func.count()).select_from(Camera).where(Camera.retired_at.is_(None))
    ).scalar_one()

    gateways_total = db.execute(select(func.count()).select_from(EdgeGateway)).scalar_one()
    gateways_enabled = db.execute(
        select(func.count()).select_from(EdgeGateway).where(EdgeGateway.status == GatewayStatus.enabled)
    ).scalar_one()

    users_total = db.execute(select(func.count()).select_from(User)).scalar_one()
    users_active = db.execute(
        select(func.count()).select_from(User).where(User.disabled_at.is_(None))
    ).scalar_one()

    commands_pending = db.execute(
        select(func.count()).select_from(GatewayCommandQueue).where(GatewayCommandQueue.status == CommandStatus.pending)
    ).scalar_one()

    publishing_active = db.execute(
        select(func.count()).select_from(CameraPublishState).where(CameraPublishState.status == CameraPublishStatus.publishing)
    ).scalar_one()

    return {
        "cameras": {
            "total": cameras_total,
            "active": cameras_active,
            "retired": cameras_total - cameras_active,
        },
        "gateways": {
            "total": gateways_total,
            "enabled": gateways_enabled,
            "disabled": gateways_total - gateways_enabled,
        },
        "users": {
            "total": users_total,
            "active": users_active,
            "disabled": users_total - users_active,
        },
        "commands": {
            "pending": commands_pending,
        },
        "publishing": {
            "active": publishing_active,
        },
    }


@v1_router.get("/admin/gateways")
def list_admin_gateways(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=255),
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    require_role(principal, "admin")
    query = select(EdgeGateway).order_by(EdgeGateway.created_at.desc(), EdgeGateway.id.desc())
    if status is not None:
        try:
            status_enum = GatewayStatus(status)
        except ValueError:
            raise ProblemDetail(
                status=400,
                title="Bad Request",
                detail="status-invalid",
                type_uri="https://panoptix.local/problems/bad-request",
            )
        query = query.where(EdgeGateway.status == status_enum)
    if search is not None:
        query = query.where(EdgeGateway.name.ilike(f"%{search}%"))
    if cursor is not None:
        cursor_uuid = _parse_uuid(cursor, "cursor-invalid")
        cursor_row = db.execute(select(EdgeGateway).where(EdgeGateway.id == str(cursor_uuid))).scalar_one_or_none()
        if cursor_row is not None:
            query = query.where(EdgeGateway.created_at < cursor_row.created_at)
    rows = list(db.execute(query.limit(limit + 1)).scalars().all())
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    next_cursor: str | None = str(rows[-1].id) if has_more and rows else None
    items = []
    for row in rows:
        camera_count = db.execute(
            select(func.count())
            .select_from(GatewayCameraAssignment)
            .where(GatewayCameraAssignment.gateway_id == str(row.id))
            .where(GatewayCameraAssignment.revoked_at.is_(None))
        ).scalar_one()
        items.append({
            "gateway_id": str(row.id),
            "name": row.name,
            "status": row.status.value,
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "disabled_at": row.disabled_at.isoformat() if row.disabled_at else None,
            "camera_count": camera_count,
        })
    return {"items": items, "next_cursor": next_cursor}


@v1_router.get("/admin/gateways/{gateway_id}")
def get_admin_gateway(
    gateway_id: str,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    require_role(principal, "admin")
    gw_uuid = _parse_uuid(gateway_id, "gateway-id-invalid")
    gateway = db.execute(select(EdgeGateway).where(EdgeGateway.id == str(gw_uuid))).scalar_one_or_none()
    if gateway is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="gateway-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )
    camera_count = db.execute(
        select(func.count())
        .select_from(GatewayCameraAssignment)
        .where(GatewayCameraAssignment.gateway_id == str(gw_uuid))
        .where(GatewayCameraAssignment.revoked_at.is_(None))
    ).scalar_one()
    return {
        "gateway_id": str(gateway.id),
        "name": gateway.name,
        "status": gateway.status.value,
        "mtls_fingerprint": gateway.mtls_fingerprint,
        "cert_expires_at": gateway.cert_expires_at.isoformat() if gateway.cert_expires_at else None,
        "last_seen_at": gateway.last_seen_at.isoformat() if gateway.last_seen_at else None,
        "created_at": gateway.created_at.isoformat() if gateway.created_at else None,
        "disabled_at": gateway.disabled_at.isoformat() if gateway.disabled_at else None,
        "camera_count": camera_count,
    }


def _gateway_metadata(gateway: EdgeGateway) -> dict[str, object | None]:
    return {
        "name": gateway.name,
        "mtls_fingerprint": gateway.mtls_fingerprint,
        "cert_expires_at": gateway.cert_expires_at.isoformat() if gateway.cert_expires_at else None,
    }


def _gateway_response(gateway: EdgeGateway) -> dict[str, object | None]:
    return {
        "gateway_id": str(gateway.id),
        "name": gateway.name,
        "status": gateway.status.value,
        "mtls_fingerprint": gateway.mtls_fingerprint,
        "cert_expires_at": gateway.cert_expires_at.isoformat() if gateway.cert_expires_at else None,
        "last_seen_at": gateway.last_seen_at.isoformat() if gateway.last_seen_at else None,
        "created_at": gateway.created_at.isoformat() if gateway.created_at else None,
        "disabled_at": gateway.disabled_at.isoformat() if gateway.disabled_at else None,
    }


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


@v1_router.patch("/admin/gateways/{gateway_id}")
def update_gateway(
    gateway_id: str,
    body: UpdateGatewayRequest,
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

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="gateway-update-empty",
            type_uri="https://panoptix.local/problems/bad-request",
        )

    before = _gateway_metadata(gateway)
    if "name" in updates:
        if body.name is None:
            raise ProblemDetail(
                status=400,
                title="Bad Request",
                detail="gateway-name-required",
                type_uri="https://panoptix.local/problems/bad-request",
            )
        gateway.name = body.name
    if "mtls_fingerprint" in updates:
        gateway.mtls_fingerprint = body.mtls_fingerprint
    if "cert_expires_at" in updates:
        gateway.cert_expires_at = body.cert_expires_at
    db.flush()
    after = _gateway_metadata(gateway)

    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="gateway.update",
        resource=f"gateway:{gateway_uuid}",
        payload={"gateway_id": str(gateway_uuid), "before": before, "after": after},
    )
    db.commit()
    return _gateway_response(gateway)


@v1_router.post("/admin/gateways/{gateway_id}/disable")
def disable_gateway(
    gateway_id: str,
    body: DisableGatewayRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> DisableGatewayResponse:
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
    db.flush()

    assignment_rooms = (
        db.execute(
            select(Camera.livekit_room_name)
            .join(GatewayCameraAssignment, GatewayCameraAssignment.camera_id == Camera.id)
            .where(GatewayCameraAssignment.gateway_id == str(gateway_uuid))
            .where(GatewayCameraAssignment.revoked_at.is_(None))
            .where(Camera.retired_at.is_(None))
        )
        .scalars()
        .all()
    )
    removal = remove_gateway_participants(settings, gateway_id=gateway_uuid, room_names=list(assignment_rooms))

    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    audit_log = _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="gateway.disable",
        resource=f"gateway:{gateway_uuid}",
        payload={
            "gateway_id": str(gateway_uuid),
            "reason": body.reason,
            "participants_removed": removal.participants_removed,
            "participant_errors": removal.errors,
        },
    )
    _detect_alert_from_audit_safely(db, settings=settings, audit_log=audit_log)
    db.commit()
    return DisableGatewayResponse(
        gateway_id=str(gateway_uuid),
        name=gateway.name,
        status=gateway.status.value,
        disabled_at=gateway.disabled_at.isoformat(),
        participants_removed=removal.participants_removed,
        participant_errors=removal.errors,
    )


@v1_router.post("/admin/gateways/{gateway_id}/enable")
def enable_gateway(
    gateway_id: str,
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
    if gateway.status == GatewayStatus.retired:
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="gateway-retired",
            type_uri="https://panoptix.local/problems/conflict",
        )
    if gateway.status == GatewayStatus.enabled and gateway.disabled_at is None:
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="gateway-already-enabled",
            type_uri="https://panoptix.local/problems/conflict",
        )

    before = {"status": gateway.status.value, "disabled_at": gateway.disabled_at.isoformat() if gateway.disabled_at else None}
    gateway.status = GatewayStatus.enabled
    gateway.disabled_at = None
    db.flush()
    after = {"status": gateway.status.value, "disabled_at": None}

    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="gateway.enable",
        resource=f"gateway:{gateway_uuid}",
        payload={"gateway_id": str(gateway_uuid), "before": before, "after": after},
    )
    db.commit()
    return _gateway_response(gateway)


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
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _check_rate_limit(
        key=f"admin-mutation:{actor.id}",
        max_requests=settings.RATE_LIMIT_ADMIN_MUTATION_MAX,
        window_seconds=settings.RATE_LIMIT_ADMIN_MUTATION_WINDOW,
        audit_action="admin.rate_limited",
        resource="endpoint:/api/v1/admin/gateways/{gateway_id}/rotate-credential",
        db=db,
        settings=settings,
        request=request,
        actor_id=actor.id,
    )
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


@v1_router.get("/admin/cameras")
def list_admin_cameras(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    include_retired: bool = Query(default=False),
    search: str | None = Query(default=None, max_length=255),
    source_type: str | None = Query(default=None),
    gateway_id: str | None = Query(default=None),
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    require_role(principal, "admin")
    query = select(Camera).order_by(Camera.created_at.desc(), Camera.id.desc())
    if not include_retired:
        query = query.where(Camera.retired_at.is_(None))
    if search is not None:
        query = query.where(Camera.display_name.ilike(f"%{search}%"))
    if source_type is not None:
        try:
            st_enum = CameraSourceType(source_type)
        except ValueError:
            raise ProblemDetail(
                status=400,
                title="Bad Request",
                detail="source-type-invalid",
                type_uri="https://panoptix.local/problems/bad-request",
            )
        query = query.where(Camera.source_type == st_enum)
    if gateway_id is not None:
        gw_uuid = _parse_uuid(gateway_id, "gateway-id-invalid")
        query = query.where(Camera.gateway_id == str(gw_uuid))
    if cursor is not None:
        cursor_uuid = _parse_uuid(cursor, "cursor-invalid")
        cursor_row = db.execute(select(Camera).where(Camera.id == str(cursor_uuid))).scalar_one_or_none()
        if cursor_row is not None:
            query = query.where(Camera.created_at < cursor_row.created_at)
    rows = list(db.execute(query.limit(limit + 1)).scalars().all())
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    next_cursor: str | None = str(rows[-1].id) if has_more and rows else None
    items = []
    for row in rows:
        acl_count = db.execute(
            select(func.count())
            .select_from(CameraAcl)
            .where(CameraAcl.camera_id == str(row.id))
            .where(CameraAcl.revoked_at.is_(None))
        ).scalar_one()
        items.append({
            "camera_id": str(row.id),
            "display_name": row.display_name,
            "source_type": row.source_type.value if row.source_type else None,
            "livekit_room_name": row.livekit_room_name,
            "gateway_id": str(row.gateway_id) if row.gateway_id else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "retired_at": row.retired_at.isoformat() if row.retired_at else None,
            "acl_count": acl_count,
        })
    return {"items": items, "next_cursor": next_cursor}


@v1_router.get("/admin/cameras/{camera_id}")
def get_admin_camera(
    camera_id: str,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
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
    acl_count = db.execute(
        select(func.count())
        .select_from(CameraAcl)
        .where(CameraAcl.camera_id == str(cam_uuid))
        .where(CameraAcl.revoked_at.is_(None))
    ).scalar_one()
    return {
        "camera_id": str(camera.id),
        "display_name": camera.display_name,
        "source_type": camera.source_type.value if camera.source_type else None,
        "livekit_room_name": camera.livekit_room_name,
        "room_uuid": str(camera.room_uuid) if camera.room_uuid else None,
        "gateway_id": str(camera.gateway_id) if camera.gateway_id else None,
        "site_id": camera.site_id,
        "created_at": camera.created_at.isoformat() if camera.created_at else None,
        "retired_at": camera.retired_at.isoformat() if camera.retired_at else None,
        "acl_count": acl_count,
    }


def _camera_metadata(camera: Camera) -> dict[str, object | None]:
    return {
        "display_name": camera.display_name,
        "source_type": camera.source_type.value if camera.source_type else None,
        "livekit_room_name": camera.livekit_room_name,
    }


def _camera_response(camera: Camera) -> dict[str, object | None]:
    return {
        "camera_id": str(camera.id),
        "display_name": camera.display_name,
        "source_type": camera.source_type.value if camera.source_type else None,
        "livekit_room_name": camera.livekit_room_name,
        "room_uuid": str(camera.room_uuid) if camera.room_uuid else None,
        "gateway_id": str(camera.gateway_id) if camera.gateway_id else None,
        "site_id": str(camera.site_id) if camera.site_id else None,
        "created_at": camera.created_at.isoformat() if camera.created_at else None,
        "retired_at": camera.retired_at.isoformat() if camera.retired_at else None,
    }


class CreateCameraRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    source_type: str
    livekit_room_name: str = Field(min_length=1, max_length=64)


class UpdateCameraRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    source_type: str | None = None
    livekit_room_name: str | None = Field(default=None, min_length=1, max_length=64)


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


@v1_router.patch("/admin/cameras/{camera_id}")
def update_camera(
    camera_id: str,
    body: UpdateCameraRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object | None]:
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

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="camera-update-empty",
            type_uri="https://panoptix.local/problems/bad-request",
        )

    before = _camera_metadata(camera)
    if "display_name" in updates:
        if body.display_name is None:
            raise ProblemDetail(
                status=400,
                title="Bad Request",
                detail="camera-display-name-required",
                type_uri="https://panoptix.local/problems/bad-request",
            )
        camera.display_name = body.display_name
    if "source_type" in updates:
        if body.source_type is None:
            raise ProblemDetail(
                status=400,
                title="Bad Request",
                detail="source-type-invalid",
                type_uri="https://panoptix.local/problems/bad-request",
            )
        try:
            camera.source_type = CameraSourceType(body.source_type)
        except ValueError:
            raise ProblemDetail(
                status=400,
                title="Bad Request",
                detail="source-type-invalid",
                type_uri="https://panoptix.local/problems/bad-request",
            )
    if "livekit_room_name" in updates:
        if body.livekit_room_name is None:
            raise ProblemDetail(
                status=400,
                title="Bad Request",
                detail="room-name-required",
                type_uri="https://panoptix.local/problems/bad-request",
            )
        existing = db.execute(
            select(Camera)
            .where(Camera.livekit_room_name == body.livekit_room_name)
            .where(Camera.id != str(cam_uuid))
        ).scalar_one_or_none()
        if existing is not None:
            raise ProblemDetail(
                status=409,
                title="Conflict",
                detail="room-name-taken",
                type_uri="https://panoptix.local/problems/conflict",
            )
        camera.livekit_room_name = body.livekit_room_name
    db.flush()
    after = _camera_metadata(camera)

    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="camera.update",
        resource=f"camera:{cam_uuid}",
        payload={"camera_id": str(cam_uuid), "before": before, "after": after},
    )
    db.commit()
    return _camera_response(camera)


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

    had_access_before = db.execute(
        select(CameraAcl).where(
            CameraAcl.user_id == str(target_user.id),
            CameraAcl.camera_id == str(cam_uuid),
            CameraAcl.revoked_at.is_(None),
        )
    ).scalar_one_or_none() is not None

    if body.action == "grant":
        if had_access_before:
            raise ProblemDetail(
                status=409,
                title="Conflict",
                detail="acl-already-active",
                type_uri="https://panoptix.local/problems/conflict",
            )
        acl = CameraAcl(user_id=target_user.id, camera_id=cam_uuid, granted_at=datetime.now(timezone.utc))
        db.add(acl)
    else:
        if not had_access_before:
            raise ProblemDetail(
                status=404,
                title="Not Found",
                detail="acl-not-found",
                type_uri="https://panoptix.local/problems/not-found",
            )
        existing_acl = db.execute(
            select(CameraAcl).where(
                CameraAcl.user_id == str(target_user.id),
                CameraAcl.camera_id == str(cam_uuid),
                CameraAcl.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if existing_acl is not None:
            existing_acl.revoked_at = datetime.now(timezone.utc)

    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action=f"camera.acl.{body.action}",
        resource=f"camera:{cam_uuid}",
        payload={
            "camera_id": str(cam_uuid),
            "user_email": body.user_email,
            "action": body.action,
            "had_access_before": had_access_before,
            "has_access_after": body.action == "grant",
        },
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
) -> DisableCameraResponse:
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
    db.flush()

    removal = remove_room_viewers(settings, room_name=camera.livekit_room_name)

    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=user.id,
        action="camera.disable",
        resource=f"camera:{cam_uuid}",
        payload={
            "camera_id": str(cam_uuid),
            "reason": body.reason,
            "participants_removed": removal.participants_removed,
            "participant_errors": removal.errors,
        },
    )
    db.commit()

    return DisableCameraResponse(
        camera_id=str(cam_uuid),
        display_name=camera.display_name,
        retired_at=camera.retired_at.isoformat(),
        participants_removed=removal.participants_removed,
        participant_errors=removal.errors,
    )


# ── Break-glass emergency access ─────────────────────────────────────────


@v1_router.post("/admin/cameras/{camera_id}/enable")
def enable_camera(
    camera_id: str,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object | None]:
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
    if camera.retired_at is None:
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="camera-already-active",
            type_uri="https://panoptix.local/problems/conflict",
        )

    before = {"retired_at": camera.retired_at.isoformat()}
    camera.retired_at = None
    db.flush()
    after = {"retired_at": None}

    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="camera.enable",
        resource=f"camera:{cam_uuid}",
        payload={"camera_id": str(cam_uuid), "before": before, "after": after},
    )
    db.commit()
    return _camera_response(camera)


class BreakGlassOpenRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=512)


class BreakGlassCloseRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=512)


@v1_router.post("/admin/break-glass/open")
def admin_break_glass_open(
    body: BreakGlassOpenRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _check_rate_limit(
        key=f"admin-mutation:{user.id}",
        max_requests=settings.RATE_LIMIT_ADMIN_MUTATION_MAX,
        window_seconds=settings.RATE_LIMIT_ADMIN_MUTATION_WINDOW,
        audit_action="admin.rate_limited",
        resource="endpoint:/api/v1/admin/break-glass/open",
        db=db,
        settings=settings,
        request=request,
        actor_id=user.id,
    )
    usage = open_break_glass_window(
        db,
        reason=body.reason,
        window_minutes=settings.BREAK_GLASS_WINDOW_MINUTES,
    )
    audit_log = _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=user.id,
        action="system.break_glass.opened",
        resource=f"break-glass:{usage.id}",
        payload={
            "window_id": str(usage.id),
            "reason": body.reason,
            "auto_disable_at": usage.auto_disable_at.isoformat(),
        },
    )
    _detect_alert_from_audit_safely(db, settings=settings, audit_log=audit_log)
    db.commit()
    return {
        "window_id": str(usage.id),
        "opened_at": usage.opened_at.isoformat(),
        "auto_disable_at": usage.auto_disable_at.isoformat(),
    }


@v1_router.post("/admin/break-glass/close")
def admin_break_glass_close(
    body: BreakGlassCloseRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    usage = close_break_glass_window(db, reason=body.reason)
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=user.id,
        action="system.break_glass.closed",
        resource=f"break-glass:{usage.id}",
        payload={
            "window_id": str(usage.id),
            "reason": body.reason,
            "rotation_required": ROTATION_CHECKLIST,
        },
    )
    db.commit()
    return {
        "window_id": str(usage.id),
        "opened_at": usage.opened_at.isoformat(),
        "closed_at": usage.closed_at.isoformat() if usage.closed_at else None,
        "rotation_required": ROTATION_CHECKLIST,
    }


@v1_router.get("/admin/internal/break-glass-status")
def admin_break_glass_status(
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    return get_break_glass_status(db)


# ── LiveKit fallback toggle ──


class MediaPlaneModeRequest(BaseModel):
    mode: str = Field(pattern="^(cloud|fallback)$")
    reason: str = Field(min_length=1, max_length=500)


@v1_router.post("/admin/livekit/fallback")
def admin_livekit_fallback(
    body: MediaPlaneModeRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    previous, current = set_media_plane_mode(db, mode=body.mode, actor_id=user.id)
    action = (
        "system.media_plane.switched_to_fallback"
        if current == "fallback"
        else "system.media_plane.switched_to_primary"
    )
    now = datetime.now(timezone.utc)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=user.id,
        action=action,
        resource="system-config:media_plane_mode",
        payload={
            "previous_mode": previous,
            "current_mode": current,
            "reason": body.reason,
        },
    )
    db.commit()
    return {
        "media_plane_mode": current,
        "previous_mode": previous,
        "switched_at": now.isoformat(),
    }


# ── DPA export ──


# --- DSR workflow ---


class DsrCreateRequest(BaseModel):
    requester_contact: str = Field(min_length=1, max_length=320)
    subject_type: str
    request_type: str
    site_id: str | None = None
    camera_scope_note: str | None = Field(default=None, max_length=2000)
    received_at: datetime | None = None
    due_at: datetime
    verified_at: datetime | None = None
    status: str = "open"
    outcome: str | None = Field(default=None, max_length=4000)
    artifact_id: str | None = None


class DsrUpdateRequest(BaseModel):
    requester_contact: str | None = Field(default=None, min_length=1, max_length=320)
    subject_type: str | None = None
    request_type: str | None = None
    site_id: str | None = None
    camera_scope_note: str | None = Field(default=None, max_length=2000)
    received_at: datetime | None = None
    due_at: datetime | None = None
    verified_at: datetime | None = None
    status: str | None = None
    outcome: str | None = Field(default=None, max_length=4000)
    artifact_id: str | None = None


def _parse_dsr_subject_type(value: str) -> SubjectType:
    try:
        return SubjectType(value)
    except ValueError as exc:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="subject-type-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        ) from exc


def _detect_alert_from_audit_safely(
    db: DbSession,
    *,
    settings: Settings,
    audit_log: AuditLog | None,
) -> None:
    if audit_log is None:
        return
    try:
        detect_alert_from_audit_event(db, settings=settings, audit_log=audit_log)
    except Exception:
        return


def _parse_dsr_request_type(value: str) -> RequestType:
    try:
        return RequestType(value)
    except ValueError as exc:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="request-type-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        ) from exc


def _parse_dsr_status(value: str) -> str:
    if value not in DSR_STATUSES:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="dsr-status-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        )
    return value


def _validate_dsr_links(db: DbSession, *, site_id: str | None, artifact_id: str | None) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    site_uuid: uuid.UUID | None = None
    artifact_uuid: uuid.UUID | None = None

    if site_id is not None:
        site_uuid = _parse_uuid(site_id, "site-id-invalid")
        site = db.execute(select(Site).where(Site.id == str(site_uuid))).scalar_one_or_none()
        if site is None:
            raise ProblemDetail(
                status=404,
                title="Not Found",
                detail="site-not-found",
                type_uri="https://panoptix.local/problems/not-found",
            )

    if artifact_id is not None:
        artifact_uuid = _parse_uuid(artifact_id, "artifact-id-invalid")
        artifact = db.execute(select(DpaArtifact).where(DpaArtifact.id == str(artifact_uuid))).scalar_one_or_none()
        if artifact is None:
            raise ProblemDetail(
                status=404,
                title="Not Found",
                detail="artifact-not-found",
                type_uri="https://panoptix.local/problems/not-found",
            )

    return site_uuid, artifact_uuid


def _dsr_response(row: DsrRequest) -> dict[str, object | None]:
    return {
        "request_id": str(row.id),
        "requester_contact": row.requester_contact,
        "subject_type": row.subject_type.value if row.subject_type else None,
        "request_type": row.request_type.value if row.request_type else None,
        "site_id": str(row.site_id) if row.site_id else None,
        "camera_scope_note": row.camera_scope_note,
        "received_at": row.received_at.isoformat() if row.received_at else None,
        "due_at": row.due_at.isoformat() if row.due_at else None,
        "verified_at": row.verified_at.isoformat() if row.verified_at else None,
        "status": row.status,
        "outcome": row.outcome,
        "artifact_id": str(row.artefact_id) if row.artefact_id else None,
    }


def _dsr_not_found() -> ProblemDetail:
    return ProblemDetail(
        status=404,
        title="Not Found",
        detail="dsr-request-not-found",
        type_uri="https://panoptix.local/problems/not-found",
    )


@v1_router.get("/admin/dsr-requests")
def list_dsr_requests(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    require_role(principal, "admin")
    query = select(DsrRequest).order_by(DsrRequest.due_at.asc(), DsrRequest.received_at.desc())
    if status is not None:
        query = query.where(DsrRequest.status == _parse_dsr_status(status))
    rows = list(db.execute(query.limit(limit)).scalars().all())
    return {"items": [_dsr_response(row) for row in rows], "count": len(rows)}


@v1_router.post("/admin/dsr-requests", status_code=201)
def create_dsr_request(
    body: DsrCreateRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object | None]:
    require_role(principal, "admin")
    site_uuid, artifact_uuid = _validate_dsr_links(db, site_id=body.site_id, artifact_id=body.artifact_id)
    now = datetime.now(timezone.utc)
    dsr = DsrRequest(
        id=uuid.uuid4(),
        requester_contact=body.requester_contact,
        subject_type=_parse_dsr_subject_type(body.subject_type),
        request_type=_parse_dsr_request_type(body.request_type),
        site_id=site_uuid,
        camera_scope_note=body.camera_scope_note,
        received_at=body.received_at or now,
        due_at=body.due_at,
        verified_at=body.verified_at,
        status=_parse_dsr_status(body.status),
        outcome=body.outcome,
        artefact_id=artifact_uuid,
    )
    db.add(dsr)
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="admin.dsr.created",
        resource=f"dsr-request:{dsr.id}",
        payload=_dsr_response(dsr),
    )
    db.commit()
    return _dsr_response(dsr)


@v1_router.get("/admin/dsr-requests/{request_id}")
def get_dsr_request(
    request_id: str,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object | None]:
    require_role(principal, "admin")
    request_uuid = _parse_uuid(request_id, "dsr-request-id-invalid")
    dsr = db.execute(select(DsrRequest).where(DsrRequest.id == str(request_uuid))).scalar_one_or_none()
    if dsr is None:
        raise _dsr_not_found()
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="admin.dsr.viewed",
        resource=f"dsr-request:{request_uuid}",
        payload={"request_id": str(request_uuid), "status": dsr.status},
    )
    db.commit()
    return _dsr_response(dsr)


@v1_router.patch("/admin/dsr-requests/{request_id}")
def update_dsr_request(
    request_id: str,
    body: DsrUpdateRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object | None]:
    require_role(principal, "admin")
    request_uuid = _parse_uuid(request_id, "dsr-request-id-invalid")
    dsr = db.execute(select(DsrRequest).where(DsrRequest.id == str(request_uuid))).scalar_one_or_none()
    if dsr is None:
        raise _dsr_not_found()

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="dsr-update-empty",
            type_uri="https://panoptix.local/problems/bad-request",
        )

    before = _dsr_response(dsr)
    if "requester_contact" in updates:
        dsr.requester_contact = body.requester_contact or ""
    if "subject_type" in updates:
        if body.subject_type is None:
            raise ProblemDetail(status=400, title="Bad Request", detail="subject-type-invalid", type_uri="https://panoptix.local/problems/bad-request")
        dsr.subject_type = _parse_dsr_subject_type(body.subject_type)
    if "request_type" in updates:
        if body.request_type is None:
            raise ProblemDetail(status=400, title="Bad Request", detail="request-type-invalid", type_uri="https://panoptix.local/problems/bad-request")
        dsr.request_type = _parse_dsr_request_type(body.request_type)
    if "site_id" in updates or "artifact_id" in updates:
        site_uuid, artifact_uuid = _validate_dsr_links(
            db,
            site_id=body.site_id if "site_id" in updates else str(dsr.site_id) if dsr.site_id else None,
            artifact_id=body.artifact_id if "artifact_id" in updates else str(dsr.artefact_id) if dsr.artefact_id else None,
        )
        if "site_id" in updates:
            dsr.site_id = site_uuid
        if "artifact_id" in updates:
            dsr.artefact_id = artifact_uuid
    if "camera_scope_note" in updates:
        dsr.camera_scope_note = body.camera_scope_note
    if "received_at" in updates:
        if body.received_at is None:
            raise ProblemDetail(status=400, title="Bad Request", detail="received-at-required", type_uri="https://panoptix.local/problems/bad-request")
        dsr.received_at = body.received_at
    if "due_at" in updates:
        if body.due_at is None:
            raise ProblemDetail(status=400, title="Bad Request", detail="due-at-required", type_uri="https://panoptix.local/problems/bad-request")
        dsr.due_at = body.due_at
    if "verified_at" in updates:
        dsr.verified_at = body.verified_at
    if "status" in updates:
        if body.status is None:
            raise ProblemDetail(status=400, title="Bad Request", detail="dsr-status-invalid", type_uri="https://panoptix.local/problems/bad-request")
        dsr.status = _parse_dsr_status(body.status)
    if "outcome" in updates:
        dsr.outcome = body.outcome

    db.flush()
    after = _dsr_response(dsr)
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="admin.dsr.updated",
        resource=f"dsr-request:{request_uuid}",
        payload={"request_id": str(request_uuid), "before": before, "after": after},
    )
    db.commit()
    return after


class DpaExportRequest(BaseModel):
    kinds: list[str] | None = None


@v1_router.post("/admin/dpa/export")
def admin_dpa_export(
    body: DpaExportRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    query = select(DpaArtifact).order_by(DpaArtifact.id)
    if body.kinds is not None:
        valid_kinds: list[DpaKind] = []
        for k in body.kinds:
            try:
                valid_kinds.append(DpaKind(k))
            except ValueError:
                raise ProblemDetail(
                    status=400,
                    title="Bad Request",
                    detail=f"dpa-kind-invalid:{k}",
                    type_uri="https://panoptix.local/problems/bad-request",
                )
        query = query.where(DpaArtifact.kind.in_(valid_kinds))
    rows = list(db.execute(query).scalars().all())
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=user.id,
        action="admin.dpa.export",
        resource="dpa-artifacts",
        payload={"count": len(rows), "kinds_filter": body.kinds},
    )
    db.commit()
    items = [
        {
            "artifact_id": str(row.id),
            "kind": row.kind.value if row.kind else None,
            "path_to_r2": row.path_to_r2,
            "signed_hash": row.signed_hash,
            "effective_at": row.effective_at.isoformat() if row.effective_at else None,
            "superseded_at": row.superseded_at.isoformat() if row.superseded_at else None,
        }
        for row in rows
    ]
    return {"artifacts": items, "count": len(items)}


# ── Signage attestation ──


class SignageAttestRequest(BaseModel):
    notes: str = Field(min_length=1, max_length=1000)


@v1_router.post("/admin/sites/{site_id}/signage-attest", status_code=201)
def admin_signage_attest(
    site_id: str,
    body: SignageAttestRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    site_uuid = _parse_uuid(site_id, "site-id-invalid")
    site = db.execute(select(Site).where(Site.id == str(site_uuid))).scalar_one_or_none()
    if site is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="site-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )
    now = datetime.now(timezone.utc)
    artifact = DpaArtifact(
        id=uuid.uuid4(),
        kind=DpaKind.bystander_signage_attestation,
        signed_hash=hashlib.sha256(body.notes.encode()).hexdigest(),
        effective_at=now,
    )
    db.add(artifact)
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=user.id,
        action="admin.signage.attest",
        resource=f"site:{site_uuid}",
        payload={
            "artifact_id": str(artifact.id),
            "site_id": str(site_uuid),
            "notes": body.notes,
        },
    )
    db.commit()
    return {
        "artifact_id": str(artifact.id),
        "kind": artifact.kind.value,
        "site_id": str(site_uuid),
        "effective_at": artifact.effective_at.isoformat() if artifact.effective_at else None,
    }


# ── User MFA reset ──


class MfaResetRequest(BaseModel):
    verification_evidence: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=512)


@v1_router.post("/admin/users/{user_id}/mfa/reset")
def admin_mfa_reset(
    user_id: str,
    body: MfaResetRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    target_uuid = _parse_uuid(user_id, "user-not-found")
    target_user = db.execute(select(User).where(User.id == str(target_uuid))).scalar_one_or_none()
    if target_user is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="user-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    if str(actor.id) == str(target_uuid):
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="cannot-reset-own-mfa",
            type_uri="https://panoptix.local/problems/conflict",
        )
    now = datetime.now(timezone.utc)
    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="admin.user.mfa_reset",
        resource=f"user:{target_uuid}",
        payload={
            "target_user_id": str(target_uuid),
            "target_email": target_user.email,
            "verification_evidence": body.verification_evidence,
            "reason": body.reason,
        },
    )
    db.commit()
    return {
        "user_id": str(target_uuid),
        "mfa_reset_recorded_at": now.isoformat(),
        "recovery_note": "MFA reset recorded. Complete the reset in the IdP admin console.",
    }


# ── Stub endpoints (501 Not Implemented) ──


@v1_router.post("/admin/users/invite")
def admin_invite_user(
    body: InviteUserRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> InviteUserResponse:
    require_role(principal, "admin")

    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _check_rate_limit(
        key=f"admin-mutation:{actor.id}",
        max_requests=settings.RATE_LIMIT_ADMIN_MUTATION_MAX,
        window_seconds=settings.RATE_LIMIT_ADMIN_MUTATION_WINDOW,
        audit_action="admin.rate_limited",
        resource="endpoint:/api/v1/admin/users/invite",
        db=db,
        settings=settings,
        request=request,
        actor_id=actor.id,
    )

    email = _normalize_invite_email(body.email)
    role_names = sorted({role_name.strip() for role_name in body.role_names if role_name.strip()})
    if not role_names:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="role-names-required",
            type_uri="https://panoptix.local/problems/bad-request",
        )

    role_rows = db.execute(select(Role).where(Role.name.in_(role_names))).scalars().all()
    roles_by_name = {role.name: role for role in role_rows}
    missing_roles = sorted(set(role_names) - set(roles_by_name))
    if missing_roles:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="role-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )

    target_user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if target_user is None:
        target_user = User(id=uuid.uuid4(), email=email, idp_subject=None)
        db.add(target_user)
        db.flush()

    existing_role_ids = set(
        db.execute(select(UserRole.role_id).where(UserRole.user_id == str(target_user.id))).scalars().all()
    )
    for role_name in role_names:
        role = roles_by_name[role_name]
        if role.id not in existing_role_ids:
            db.add(UserRole(user_id=target_user.id, role_id=role.id))
    db.flush()
    roles_after = sorted(set(get_user_roles(db, target_user.id)) | set(role_names))

    try:
        invite_result = create_github_org_invitation(settings, email=email)
    except GitHubInviteConfigError as exc:
        db.rollback()
        raise ProblemDetail(
            status=503,
            title="Service Unavailable",
            detail=str(exc),
            type_uri="https://panoptix.local/problems/service-unavailable",
        ) from exc
    except GitHubInviteError as exc:
        db.rollback()
        raise ProblemDetail(
            status=502,
            title="Bad Gateway",
            detail=str(exc),
            type_uri="https://panoptix.local/problems/bad-gateway",
        ) from exc

    _record_user_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="admin.user.invited",
        resource=f"user:{target_user.id}",
        payload={
            "target_user_id": str(target_user.id),
            "target_email": email,
            "role_names": role_names,
            "github_org": invite_result.org,
            "github_invitation_id": invite_result.invitation_id,
            "github_invite_status": invite_result.status,
            "reason": body.reason,
        },
    )
    db.commit()
    return InviteUserResponse(
        user_id=str(target_user.id),
        email=email,
        roles=roles_after,
        github_invitation_id=invite_result.invitation_id,
        github_org=invite_result.org,
        status=invite_result.status,
        next_step="User must accept the GitHub organization invitation, then sign in through Cloudflare Access.",
    )


@v1_router.get("/admin/alerts")
def list_admin_alerts(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    require_role(principal, "admin")
    query = select(Alert)

    if status is not None:
        query = query.where(Alert.status == _parse_alert_status(status))
    if severity is not None:
        query = query.where(Alert.severity == _parse_alert_severity(severity))
    if category is not None:
        query = query.where(Alert.category == _parse_alert_category(category))
    if cursor:
        cursor_uuid = _parse_uuid(cursor, "alert-cursor-invalid")
        cursor_row = db.execute(select(Alert).where(Alert.id == str(cursor_uuid))).scalar_one_or_none()
        if cursor_row:
            query = query.where(Alert.created_at < cursor_row.created_at)

    rows = list(db.execute(query.order_by(Alert.created_at.desc()).limit(limit + 1)).scalars().all())
    next_cursor = str(rows[-1].id) if len(rows) > limit else None
    items = rows[:limit]
    return {"items": [alert_to_response(row) for row in items], "next_cursor": next_cursor}


@v1_router.get("/admin/alerts/{alert_id}")
def get_admin_alert(
    alert_id: str,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object | None]:
    require_role(principal, "admin")
    alert_uuid = _parse_uuid(alert_id, "alert-id-invalid")
    alert = db.execute(select(Alert).where(Alert.id == str(alert_uuid))).scalar_one_or_none()
    if alert is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="alert-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )
    return alert_to_response(alert)


@v1_router.post("/admin/alerts/{alert_id}/acknowledge")
def acknowledge_admin_alert(
    alert_id: str,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object | None]:
    require_role(principal, "admin")
    alert_uuid = _parse_uuid(alert_id, "alert-id-invalid")
    alert = db.execute(select(Alert).where(Alert.id == str(alert_uuid))).scalar_one_or_none()
    if alert is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="alert-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    acknowledge_alert(db, settings=settings, actor_id=actor.id, alert=alert)
    db.commit()
    return alert_to_response(alert)


@v1_router.post("/admin/alerts/{alert_id}/resolve")
def resolve_admin_alert(
    alert_id: str,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object | None]:
    require_role(principal, "admin")
    alert_uuid = _parse_uuid(alert_id, "alert-id-invalid")
    alert = db.execute(select(Alert).where(Alert.id == str(alert_uuid))).scalar_one_or_none()
    if alert is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="alert-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    resolve_alert(db, settings=settings, actor_id=actor.id, alert=alert)
    db.commit()
    return alert_to_response(alert)


@v1_router.get("/admin/backups/status")
def admin_backups_status(
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")

    latest_backup = db.execute(
        select(BackupRun).order_by(BackupRun.started_at.desc()).limit(1)
    ).scalar_one_or_none()
    latest_restore_drill = db.execute(
        select(BackupRun)
        .where(BackupRun.restore_schema_ok.isnot(None))
        .order_by(BackupRun.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest_backup is None:
        checks: dict[str, object] = {
            "has_backup": False,
            "latest_upload_uploaded": False,
            "latest_backup_finished": False,
            "latest_restore_format_ok": False,
            "restore_drill_recorded": False,
            "latest_restore_schema_ok": False,
            "latest_backup_age_hours": None,
        }
        response: dict[str, object] = {
            "status": "missing",
            "latest_backup": None,
            "latest_restore_drill": None,
            "checks": checks,
        }
        detect_alert_from_backup_status(
            db,
            settings=settings,
            status="missing",
            checks=checks,
        )
        return response

    latest_upload_uploaded = latest_backup.upload_status == BackupUploadStatus.uploaded
    latest_backup_finished = latest_backup.finished_at is not None
    latest_restore_format_ok = latest_backup.restore_format_ok is True
    restore_drill_recorded = latest_restore_drill is not None
    latest_restore_schema_ok = (
        latest_restore_drill.restore_schema_ok is True if latest_restore_drill else False
    )
    status = (
        "ok"
        if (
            latest_upload_uploaded
            and latest_backup_finished
            and latest_restore_format_ok
            and latest_restore_schema_ok
        )
        else "degraded"
    )

    checks = {
        "has_backup": True,
        "latest_upload_uploaded": latest_upload_uploaded,
        "latest_backup_finished": latest_backup_finished,
        "latest_restore_format_ok": latest_restore_format_ok,
        "restore_drill_recorded": restore_drill_recorded,
        "latest_restore_schema_ok": latest_restore_schema_ok,
        "latest_backup_age_hours": _age_hours(latest_backup.started_at),
    }
    response = {
        "status": status,
        "latest_backup": _backup_run_to_response(latest_backup),
        "latest_restore_drill": (
            _backup_run_to_response(latest_restore_drill)
            if latest_restore_drill is not None
            else None
        ),
        "checks": checks,
    }
    detect_alert_from_backup_status(
        db,
        settings=settings,
        status=status,
        checks=checks,
    )
    return response


def _backup_run_to_response(row: BackupRun) -> dict[str, object]:
    return {
        "id": str(row.id),
        "started_at": row.started_at.isoformat(),
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "size_bytes": row.size_bytes,
        "sha256": row.sha256,
        "restore_format_ok": row.restore_format_ok,
        "restore_schema_ok": row.restore_schema_ok,
        "row_count_estimate": row.row_count_estimate,
        "upload_status": row.upload_status.value,
        "notes": row.notes,
    }


def _age_hours(ts: datetime) -> float:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - ts).total_seconds() / 3600, 2)
