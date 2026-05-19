from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.errors import ProblemDetail
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.models.enums import ActorType, EventCategory, EventOutcome, EventSeverity
from cctv_api.models.tables import AuditLog, EdgeGateway, User
from cctv_api.security.actor_investigation import (
    build_gateway_actor_profile,
    build_system_actor_profile,
    build_user_actor_profile,
)
from cctv_api.security.audit import AuditLogError, record_audit_event
from cctv_api.security.dependencies import require_authenticated_user
from cctv_api.security.identity import Principal
from cctv_api.security.policy import require_role
from cctv_api.security.users import get_or_create_user

router = APIRouter(prefix="/admin/actors")

_SYSTEM_PROFILE_ACTORS = {
    ActorType.system,
    ActorType.break_glass,
    ActorType.service_token_monitor,
}


@router.get("/{actor_type}/{actor_id}/profile")
def get_actor_profile(
    actor_type: str,
    actor_id: str,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    _ensure_audit_hmac_configured(settings)

    actor_type_enum = _parse_actor_type(actor_type)
    actor_uuid = _parse_actor_id(actor_type_enum, actor_id)

    if actor_type_enum == ActorType.user:
        assert actor_uuid is not None
        profile = build_user_actor_profile(db, actor_uuid)
        if profile is None:
            raise _not_found("user-not-found")
    elif actor_type_enum == ActorType.gateway:
        assert actor_uuid is not None
        profile = build_gateway_actor_profile(db, actor_uuid)
        if profile is None:
            raise _not_found("gateway-not-found")
    else:
        profile = build_system_actor_profile(db, actor_type_enum, actor_uuid)

    admin = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_safely(
        db,
        settings=settings,
        request=request,
        actor_id=admin.id,
        action="admin.actor.profile.viewed",
        resource=_actor_resource(actor_type_enum, actor_uuid),
        payload={"actor_type": actor_type_enum.value, "actor_id": str(actor_uuid) if actor_uuid else None},
    )
    return profile


@router.get("/{actor_type}/{actor_id}/activity")
def get_actor_activity(
    actor_type: str,
    actor_id: str,
    request: Request,
    cursor: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None, max_length=128),
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
    _ensure_audit_hmac_configured(settings)

    actor_type_enum = _parse_actor_type(actor_type)
    actor_uuid = _parse_actor_id(actor_type_enum, actor_id)
    _ensure_backing_actor_exists(db, actor_type_enum, actor_uuid)

    query = select(AuditLog).where(AuditLog.actor_type == actor_type_enum)
    if actor_uuid is None:
        query = query.where(AuditLog.actor_id.is_(None))
    else:
        query = query.where(AuditLog.actor_id == str(actor_uuid))

    if action is not None:
        query = query.where(AuditLog.action == action)
    if severity is not None:
        query = query.where(AuditLog.event_severity == _parse_severity(severity))
    if category is not None:
        query = query.where(AuditLog.event_category == _parse_category(category))
    if outcome is not None:
        query = query.where(AuditLog.event_outcome == _parse_outcome(outcome))
    if resource is not None:
        query = query.where(AuditLog.resource == resource)
    if session_id is not None:
        sid_uuid = _parse_uuid(session_id, "session-id-invalid")
        query = query.where(AuditLog.session_id == str(sid_uuid))
    if ts_from is not None:
        query = query.where(AuditLog.ts >= _parse_datetime(ts_from, "ts-from-invalid"))
    if ts_to is not None:
        query = query.where(AuditLog.ts <= _parse_datetime(ts_to, "ts-to-invalid"))
    if cursor is not None:
        query = query.where(AuditLog.id < cursor)

    rows = list(db.execute(query.order_by(AuditLog.id.desc()).limit(limit + 1)).scalars().all())
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    items = [_audit_log_item(row) for row in rows]
    next_cursor: str | None = str(rows[-1].id) if has_more and rows else None

    filters = {
        "action": action,
        "severity": severity,
        "category": category,
        "outcome": outcome,
        "resource": resource,
        "session_id": session_id,
        "ts_from": ts_from,
        "ts_to": ts_to,
    }
    admin = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    _record_user_audit_safely(
        db,
        settings=settings,
        request=request,
        actor_id=admin.id,
        action="admin.actor.activity.viewed",
        resource=_actor_resource(actor_type_enum, actor_uuid),
        payload={
            "actor_type": actor_type_enum.value,
            "actor_id": str(actor_uuid) if actor_uuid else None,
            "cursor": cursor,
            "limit": limit,
            "rows_returned": len(items),
            "filters": filters,
        },
    )
    return {"items": items, "next_cursor": next_cursor}


def _ensure_audit_hmac_configured(settings: Settings) -> None:
    if not settings.AUDIT_HMAC_KEY.strip() or settings.AUDIT_HMAC_KEY.strip() == "replace-me":
        raise ProblemDetail(
            status=503,
            title="Service Unavailable",
            detail="audit-hmac-key-invalid",
            type_uri="https://panoptix.local/problems/service-unavailable",
        )


def _parse_actor_type(value: str) -> ActorType:
    try:
        return ActorType(value)
    except ValueError as exc:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="actor-type-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        ) from exc


def _parse_actor_id(actor_type: ActorType, value: str) -> uuid.UUID | None:
    if actor_type in _SYSTEM_PROFILE_ACTORS and value == "none":
        return None
    return _parse_uuid(value, "actor-id-invalid")


def _ensure_backing_actor_exists(
    db: DbSession, actor_type: ActorType, actor_id: uuid.UUID | None
) -> None:
    if actor_type == ActorType.user:
        row = db.execute(select(User.id).where(User.id == str(actor_id))).scalar_one_or_none()
        if row is None:
            raise _not_found("user-not-found")
    elif actor_type == ActorType.gateway:
        row = db.execute(select(EdgeGateway.id).where(EdgeGateway.id == str(actor_id))).scalar_one_or_none()
        if row is None:
            raise _not_found("gateway-not-found")


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


def _parse_severity(value: str) -> EventSeverity:
    try:
        return EventSeverity(value)
    except ValueError as exc:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="severity-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        ) from exc


def _parse_category(value: str) -> EventCategory:
    try:
        return EventCategory(value)
    except ValueError as exc:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="category-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        ) from exc


def _parse_outcome(value: str) -> EventOutcome:
    try:
        return EventOutcome(value)
    except ValueError as exc:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="outcome-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        ) from exc


def _not_found(detail: str) -> ProblemDetail:
    return ProblemDetail(
        status=404,
        title="Not Found",
        detail=detail,
        type_uri="https://panoptix.local/problems/not-found",
    )


def _audit_log_item(row: AuditLog) -> dict[str, object]:
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
        "event_severity": row.event_severity.value if row.event_severity else None,
        "event_outcome": row.event_outcome.value if row.event_outcome else None,
        "event_category": row.event_category.value if row.event_category else None,
        "session_id": str(row.session_id) if row.session_id else None,
    }


def _actor_resource(actor_type: ActorType, actor_id: uuid.UUID | None) -> str:
    return f"actor:{actor_type.value}:{actor_id if actor_id else 'none'}"


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
            session_id=_audit_session_id(request),
        )
    except AuditLogError:
        return


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


def _request_ua(request: Request) -> str | None:
    return request.headers.get("user-agent")
