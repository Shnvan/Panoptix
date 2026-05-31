from __future__ import annotations

import uuid
import re
from ipaddress import ip_address
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.errors import ProblemDetail
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.integrations.github_invites import (
    GitHubInviteConfigError,
    GitHubInviteError,
    create_github_org_invitation,
)
from cctv_api.models.enums import ActorType, VisitorAccessRequestStatus
from cctv_api.models.tables import Role, User, UserRole, VisitorAccessRequest
from cctv_api.models.tables import Session as UserSession
from cctv_api.models.tables import VisitorVisit
from cctv_api.security.audit import AuditLogError, record_audit_event
from cctv_api.security.alerts import create_visitor_entry_alert
from cctv_api.security.dependencies import require_authenticated_user
from cctv_api.security.device_intelligence import device_detail_payload
from cctv_api.security.identity import Principal
from cctv_api.security.ip_intelligence import (
    IpIntelligenceProviderState,
    get_ip_intelligence_provider,
    ip_intelligence_payload,
)
from cctv_api.security.policy import require_role
from cctv_api.security.rate_limit import RateLimitConfig, get_rate_limiter
from cctv_api.security.request_ip import browser_request_ip
from cctv_api.security.users import get_or_create_user
from cctv_api.security.users import get_user_roles
from cctv_api.security.visitor_cookie import create_visitor_cookie, read_visitor_cookie

router = APIRouter()

CURRENT_VISITOR_NOTICE_TITLE = "Panoptix Visitor Security Notice"
CURRENT_VISITOR_NOTICE_BODY = (
    "Panoptix records limited browser and network context from this entry page, "
    "including WebRTC network candidates when available, for access security and "
    "investigation before continuing to the protected system."
)


class VisitorNoticeResponse(BaseModel):
    notice_version: str
    title: str
    body: str


class VisitorNetworkContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    effective_type: str | None = Field(default=None, max_length=32)
    downlink_mbps: float | None = Field(default=None, ge=0, le=10000)
    rtt_ms: int | None = Field(default=None, ge=0, le=600000)
    save_data: bool | None = None


class VisitorTimingContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    notice_loaded_at_ms: int | None = Field(default=None, ge=0, le=86400000)
    continue_clicked_at_ms: int | None = Field(default=None, ge=0, le=86400000)
    collect_started_at_ms: int | None = Field(default=None, ge=0, le=86400000)
    webrtc_elapsed_ms: int | None = Field(default=None, ge=0, le=30000)


class VisitorWebRtcContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    available: bool | None = None
    tested: bool | None = None
    candidate_count: int | None = Field(default=None, ge=0, le=100)
    candidate_types: list[str] = Field(default_factory=list, max_length=10)
    local_ip_candidates: list[str] = Field(default_factory=list, max_length=10)
    public_ip_candidates: list[str] = Field(default_factory=list, max_length=10)
    relay_ip_candidates: list[str] = Field(default_factory=list, max_length=10)
    mdns_hostname_seen: bool | None = None
    error: str | None = Field(default=None, max_length=64)


class VisitorCollectRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    notice_version: str = Field(min_length=1, max_length=64)
    notice_acknowledged: bool
    page_path: str = Field(min_length=1, max_length=512)
    screen_width: int | None = Field(default=None, ge=1, le=32768)
    screen_height: int | None = Field(default=None, ge=1, le=32768)
    timezone: str | None = Field(default=None, max_length=128)
    language: str | None = Field(default=None, max_length=64)
    referrer: str | None = Field(default=None, max_length=2048)
    viewport_width: int | None = Field(default=None, ge=1, le=32768)
    viewport_height: int | None = Field(default=None, ge=1, le=32768)
    device_pixel_ratio: float | None = Field(default=None, ge=0.1, le=16)
    touch_supported: bool | None = None
    max_touch_points: int | None = Field(default=None, ge=0, le=32)
    color_scheme: Literal["light", "dark", "no-preference"] | None = None
    cookies_enabled: bool | None = None
    do_not_track: str | None = Field(default=None, max_length=32)
    global_privacy_control: bool | None = None
    languages: list[str] = Field(default_factory=list, max_length=10)
    network_context: VisitorNetworkContext | None = None
    timing_context: VisitorTimingContext | None = None
    webrtc_context: VisitorWebRtcContext | None = None


class VisitorCollectResponse(BaseModel):
    visit_id: uuid.UUID
    status: str
    collected_at: datetime


class VisitorAccessRequestCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    applicant_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=320)
    organization: str | None = Field(default=None, max_length=255)
    reason: str = Field(min_length=1, max_length=2000)
    requested_role: str = Field(default="viewer", min_length=1, max_length=64)


class VisitorAccessRequestDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    decision_note: str | None = Field(default=None, max_length=2000)


class VisitorAccessRequestResponse(BaseModel):
    request_id: uuid.UUID
    applicant_name: str
    email: str
    organization: str | None
    reason: str
    requested_role: str
    status: str
    visitor_visit_id: uuid.UUID | None
    requester_ip: str | None
    created_at: datetime | None
    decided_at: datetime | None
    decided_by_user_id: uuid.UUID | None
    decision_note: str | None
    github_invitation_id: int | None
    github_org: str | None
    github_invite_status: str | None


class VisitorAccessRequestCreateResponse(BaseModel):
    request_id: uuid.UUID
    status: str
    next_step: str


@router.get("/visitor/notice")
def get_visitor_notice(
    settings: Settings = Depends(get_settings),
) -> VisitorNoticeResponse:
    _require_collector_enabled(settings)
    return VisitorNoticeResponse(
        notice_version=settings.VISITOR_NOTICE_VERSION,
        title=CURRENT_VISITOR_NOTICE_TITLE,
        body=CURRENT_VISITOR_NOTICE_BODY,
    )


@router.post("/visitor/collect", status_code=201)
def collect_visitor_visit(
    body: VisitorCollectRequest,
    request: Request,
    response: Response,
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> VisitorCollectResponse:
    _require_collector_enabled(settings)
    _require_notice_acknowledged(body, settings)
    ip = browser_request_ip(request, settings)
    _check_collect_rate_limit(ip, settings)
    enrichment_status, enrichment_provider, enrichment = _enrich_ip(ip, settings)
    visit = VisitorVisit(
        id=uuid.uuid4(),
        page_path=body.page_path,
        notice_version=body.notice_version,
        ip=ip,
        ua=_request_ua(request),
        screen_width=body.screen_width,
        screen_height=body.screen_height,
        browser_timezone=_optional_value(body.timezone),
        browser_language=_optional_value(body.language),
        ip_enrichment_status=enrichment_status,
        ip_enrichment_provider=enrichment_provider,
        ip_enrichment=enrichment,
        browser_context=_browser_context_payload(body),
        network_context=_network_context_payload(body.network_context),
        webrtc_context=_webrtc_context_payload(body.webrtc_context),
        timing_context=_timing_context_payload(body.timing_context),
        server_context=_server_context_payload(request),
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    _create_collect_alert_safely(db, settings=settings, visit=visit)
    response.set_cookie(
        key=settings.VISITOR_COOKIE_NAME,
        value=create_visitor_cookie(visit.id, settings.VISITOR_COOKIE_SIGNING_KEY),
        max_age=settings.VISITOR_RETENTION_DAYS * 86400,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        domain=_optional_value(settings.VISITOR_COOKIE_DOMAIN),
    )
    return VisitorCollectResponse(
        visit_id=visit.id,
        status="recorded",
        collected_at=visit.collected_at,
    )


@router.post("/visitor/access-requests", status_code=201)
def create_visitor_access_request(
    body: VisitorAccessRequestCreate,
    request: Request,
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> VisitorAccessRequestCreateResponse:
    _require_collector_enabled(settings)
    email = _normalize_email(body.email)
    requested_role = _normalize_requested_role(body.requested_role)
    applicant_name = _bounded_required(body.applicant_name, "applicant-name-required", 255)
    reason = _bounded_required(body.reason, "access-request-reason-required", 2000)
    organization = _optional_bounded(body.organization, 255)
    ip = browser_request_ip(request, settings)
    _check_access_request_rate_limit(ip=ip, email=email, settings=settings)

    existing = db.execute(
        select(VisitorAccessRequest)
        .where(VisitorAccessRequest.email == email)
        .where(VisitorAccessRequest.status == VisitorAccessRequestStatus.pending)
    ).scalar_one_or_none()
    if existing is not None:
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="access-request-already-pending",
            type_uri="https://panoptix.local/problems/conflict",
        )

    access_request = VisitorAccessRequest(
        id=uuid.uuid4(),
        visitor_visit_id=_visitor_visit_id_from_cookie(request, settings),
        applicant_name=applicant_name,
        email=email,
        organization=organization,
        reason=reason,
        requested_role=requested_role,
        requester_ip=ip,
        requester_ua=_request_ua(request),
        request_context=_server_context_payload(request),
    )
    db.add(access_request)
    db.flush()
    _record_public_access_request_audit_safely(db, settings=settings, request=request, row=access_request)
    db.commit()
    db.refresh(access_request)
    return VisitorAccessRequestCreateResponse(
        request_id=access_request.id,
        status=access_request.status.value,
        next_step="An administrator must review this request before any account invite is sent.",
    )


@router.get("/admin/visitor-visits")
def list_visitor_visits(
    cursor: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    require_role(principal, "admin")
    query = select(VisitorVisit).order_by(VisitorVisit.collected_at.desc(), VisitorVisit.id.desc())
    if cursor is not None:
        cursor_id = _parse_uuid(cursor, "cursor-invalid")
        cursor_visit = db.execute(
            select(VisitorVisit).where(VisitorVisit.id == str(cursor_id))
        ).scalar_one_or_none()
        if cursor_visit is not None:
            query = query.where(VisitorVisit.collected_at < cursor_visit.collected_at)
    rows = list(db.execute(query.limit(limit + 1)).scalars().all())
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    return {
        "items": [_visit_response(row, db) for row in rows],
        "next_cursor": str(rows[-1].id) if has_more and rows else None,
    }


@router.get("/admin/visitor-visits/{visit_id}")
def get_visitor_visit(
    visit_id: str,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_role(principal, "admin")
    row = db.execute(
        select(VisitorVisit).where(VisitorVisit.id == str(_parse_uuid(visit_id, "visit-id-invalid")))
    ).scalar_one_or_none()
    if row is None:
        raise _not_found("visitor-visit-not-found")

    admin = get_or_create_user(
        db,
        email=principal.email or principal.subject,
        idp_subject=principal.subject,
    )
    _record_detail_audit_safely(db, request=request, settings=settings, actor_id=admin.id, row=row)
    return _visit_response(row, db)


@router.get("/admin/access-requests")
def list_access_requests(
    status: str | None = Query(default=None, max_length=32),
    cursor: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    require_role(principal, "admin")
    query = select(VisitorAccessRequest).order_by(
        VisitorAccessRequest.created_at.desc(), VisitorAccessRequest.id.desc()
    )
    if status is not None:
        query = query.where(VisitorAccessRequest.status == _parse_access_request_status(status))
    if cursor is not None:
        cursor_id = _parse_uuid(cursor, "cursor-invalid")
        cursor_row = db.execute(
            select(VisitorAccessRequest).where(VisitorAccessRequest.id == str(cursor_id))
        ).scalar_one_or_none()
        if cursor_row is not None:
            query = query.where(VisitorAccessRequest.created_at < cursor_row.created_at)
    rows = list(db.execute(query.limit(limit + 1)).scalars().all())
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    return {
        "items": [_access_request_response(row) for row in rows],
        "next_cursor": str(rows[-1].id) if has_more and rows else None,
    }


@router.get("/admin/access-requests/{request_id}")
def get_access_request(
    request_id: str,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> VisitorAccessRequestResponse:
    require_role(principal, "admin")
    return _access_request_response(_get_access_request_or_404(db, request_id))


@router.post("/admin/access-requests/{request_id}/approve")
def approve_access_request(
    request_id: str,
    body: VisitorAccessRequestDecision,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> VisitorAccessRequestResponse:
    require_role(principal, "admin")
    row = _get_access_request_or_404(db, request_id)
    _require_pending_access_request(row)
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    role = _role_or_404(db, row.requested_role)
    target_user = db.execute(select(User).where(User.email == row.email)).scalar_one_or_none()
    if target_user is not None and target_user.disabled_at is not None:
        _record_access_request_audit_safely(
            db,
            settings=settings,
            request=request,
            actor_id=actor.id,
            action="admin.access_request.approve.denied.user_disabled",
            row=row,
            payload={"target_email": row.email, "decision_note": body.decision_note},
        )
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="user-disabled",
            type_uri="https://panoptix.local/problems/conflict",
        )
    if target_user is None:
        target_user = User(id=uuid.uuid4(), email=row.email, idp_subject=None)
        db.add(target_user)
        db.flush()
    existing_role_ids = set(
        db.execute(select(UserRole.role_id).where(UserRole.user_id == str(target_user.id))).scalars().all()
    )
    if role.id not in existing_role_ids:
        db.add(UserRole(user_id=target_user.id, role_id=role.id))
    db.flush()

    try:
        invite_result = create_github_org_invitation(settings, email=row.email)
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

    row.status = VisitorAccessRequestStatus.approved
    row.decided_at = datetime.now(timezone.utc)
    row.decided_by_user_id = actor.id
    row.decision_note = _optional_bounded(body.decision_note, 2000)
    row.github_invitation_id = invite_result.invitation_id
    row.github_org = invite_result.org
    row.github_invite_status = invite_result.status
    _record_access_request_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="admin.access_request.approved",
        row=row,
        payload={
            "target_user_id": str(target_user.id),
            "target_email": row.email,
            "role_names": sorted(set(get_user_roles(db, target_user.id)) | {row.requested_role}),
            "github_org": invite_result.org,
            "github_invitation_id": invite_result.invitation_id,
            "github_invite_status": invite_result.status,
            "decision_note": row.decision_note,
        },
    )
    db.commit()
    db.refresh(row)
    return _access_request_response(row)


@router.post("/admin/access-requests/{request_id}/reject")
def reject_access_request(
    request_id: str,
    body: VisitorAccessRequestDecision,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> VisitorAccessRequestResponse:
    require_role(principal, "admin")
    row = _get_access_request_or_404(db, request_id)
    _require_pending_access_request(row)
    actor = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    row.status = VisitorAccessRequestStatus.rejected
    row.decided_at = datetime.now(timezone.utc)
    row.decided_by_user_id = actor.id
    row.decision_note = _optional_bounded(body.decision_note, 2000)
    _record_access_request_audit_required(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="admin.access_request.rejected",
        row=row,
        payload={"target_email": row.email, "decision_note": row.decision_note},
    )
    db.commit()
    db.refresh(row)
    return _access_request_response(row)


def _require_collector_enabled(settings: Settings) -> None:
    if not settings.VISITOR_COLLECTOR_ENABLED:
        raise _not_found("visitor-collector-disabled")


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="email-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        )
    return email


def _normalize_requested_role(value: str) -> str:
    role = value.strip().lower()
    if role not in {"viewer", "admin"}:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="requested-role-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        )
    return role


def _bounded_required(value: str, detail: str, max_length: int) -> str:
    stripped = value.strip()
    if not stripped:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail=detail,
            type_uri="https://panoptix.local/problems/bad-request",
        )
    return stripped[:max_length]


def _optional_bounded(value: str | None, max_length: int) -> str | None:
    stripped = value.strip() if value else ""
    return stripped[:max_length] if stripped else None


def _visitor_visit_id_from_cookie(request: Request, settings: Settings) -> uuid.UUID | None:
    cookie = request.cookies.get(settings.VISITOR_COOKIE_NAME)
    if not cookie:
        return None
    return read_visitor_cookie(cookie, settings.VISITOR_COOKIE_SIGNING_KEY)


def _check_access_request_rate_limit(*, ip: str | None, email: str, settings: Settings) -> None:
    limiter = get_rate_limiter()
    for key in (f"visitor-access-request:ip:{ip or 'unknown'}", f"visitor-access-request:email:{email}"):
        result = limiter.check(
            key,
            RateLimitConfig(
                max_requests=settings.RATE_LIMIT_VISITOR_COLLECT_MAX,
                window_seconds=settings.RATE_LIMIT_VISITOR_COLLECT_WINDOW,
            ),
        )
        if not result.allowed:
            raise ProblemDetail(
                status=429,
                title="Too Many Requests",
                detail="access-request-rate-limited",
                type_uri="https://panoptix.local/problems/rate-limited",
                headers={"Retry-After": str(result.retry_after)},
            )


def _require_notice_acknowledged(body: VisitorCollectRequest, settings: Settings) -> None:
    if not body.notice_acknowledged:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="visitor-notice-acknowledgement-required",
            type_uri="https://panoptix.local/problems/bad-request",
        )
    if body.notice_version != settings.VISITOR_NOTICE_VERSION:
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="visitor-notice-version-mismatch",
            type_uri="https://panoptix.local/problems/conflict",
        )


def _check_collect_rate_limit(ip: str | None, settings: Settings) -> None:
    result = get_rate_limiter().check(
        f"visitor-collect:{ip or 'unknown'}",
        RateLimitConfig(
            max_requests=settings.RATE_LIMIT_VISITOR_COLLECT_MAX,
            window_seconds=settings.RATE_LIMIT_VISITOR_COLLECT_WINDOW,
        ),
    )
    if not result.allowed:
        raise ProblemDetail(
            status=429,
            title="Too Many Requests",
            detail="visitor-collect-rate-limited",
            type_uri="https://panoptix.local/problems/rate-limited",
            headers={"Retry-After": str(result.retry_after)},
        )


def _enrich_ip(ip: str | None, settings: Settings) -> tuple[str, str | None, dict[str, object]]:
    state = get_ip_intelligence_provider(settings)
    result = None
    try:
        if state.provider is not None and ip is not None:
            result = state.provider.lookup(ip)
    except Exception:
        return "unavailable", state.provider_name, ip_intelligence_payload(None)
    finally:
        _close_ip_provider(state)
    return state.status, state.provider_name, ip_intelligence_payload(result)


def _close_ip_provider(state: IpIntelligenceProviderState) -> None:
    close = getattr(state.provider, "close", None)
    if callable(close):
        close()


def _visit_response(row: VisitorVisit, db: DbSession) -> dict[str, object]:
    session_row = _linked_session(db, row)
    browser_context = _stored_dict(row.browser_context)
    network_context = _stored_dict(row.network_context)
    webrtc_context = _stored_dict(row.webrtc_context)
    timing_context = _stored_dict(row.timing_context)
    server_context = _stored_dict(row.server_context)
    return {
        "visit_id": str(row.id),
        "collected_at": row.collected_at.isoformat() if row.collected_at else None,
        "page_path": row.page_path,
        "notice_version": row.notice_version,
        "ip_details": {
            "ip": str(row.ip) if row.ip is not None else None,
            "status": row.ip_enrichment_status,
            "provider": row.ip_enrichment_provider,
            **_stored_ip_payload(row.ip_enrichment),
        },
        "user_agent": row.ua,
        **device_detail_payload(row.ua),
        "screen": {"width": row.screen_width, "height": row.screen_height},
        "timezone": row.browser_timezone,
        "language": row.browser_language,
        "entry_context": {
            "page_path": row.page_path,
            "referrer": browser_context.get("referrer"),
            "server": server_context,
        },
        "browser_context": browser_context,
        "network_context": network_context,
        "webrtc_details": webrtc_context,
        "timing": timing_context,
        "server_context": server_context,
        "risk_context": _risk_context(row, db, session_row, browser_context, webrtc_context),
        "login": {
            "logged_in": row.session_id is not None,
            "user_id": str(row.user_id) if row.user_id else None,
            "session_id": str(row.session_id) if row.session_id else None,
            "logged_in_at": row.logged_in_at.isoformat() if row.logged_in_at else None,
            "ip": str(session_row.ip) if session_row is not None and session_row.ip is not None else None,
        },
    }


def _stored_ip_payload(value: Any) -> dict[str, object]:
    return value if isinstance(value, dict) and value else ip_intelligence_payload(None)


def _stored_dict(value: Any) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _browser_context_payload(body: VisitorCollectRequest) -> dict[str, object]:
    languages = _bounded_string_list(body.languages, max_items=10, max_length=64)
    if body.language and body.language not in languages:
        languages.insert(0, body.language[:64])
    return {
        "referrer": _optional_value(body.referrer),
        "screen": {"width": body.screen_width, "height": body.screen_height},
        "viewport": {"width": body.viewport_width, "height": body.viewport_height},
        "device_pixel_ratio": body.device_pixel_ratio,
        "touch_supported": body.touch_supported,
        "max_touch_points": body.max_touch_points,
        "color_scheme": body.color_scheme,
        "cookies_enabled": body.cookies_enabled,
        "privacy": {
            "do_not_track": _optional_value(body.do_not_track),
            "global_privacy_control": body.global_privacy_control,
        },
        "timezone": _optional_value(body.timezone),
        "language": _optional_value(body.language),
        "languages": languages[:10],
    }


def _network_context_payload(value: VisitorNetworkContext | None) -> dict[str, object]:
    if value is None:
        return {
            "effective_type": None,
            "downlink_mbps": None,
            "rtt_ms": None,
            "save_data": None,
        }
    return {
        "effective_type": _optional_value(value.effective_type),
        "downlink_mbps": value.downlink_mbps,
        "rtt_ms": value.rtt_ms,
        "save_data": value.save_data,
    }


def _timing_context_payload(value: VisitorTimingContext | None) -> dict[str, object]:
    if value is None:
        return {
            "notice_loaded_at_ms": None,
            "continue_clicked_at_ms": None,
            "collect_started_at_ms": None,
            "webrtc_elapsed_ms": None,
        }
    return {
        "notice_loaded_at_ms": value.notice_loaded_at_ms,
        "continue_clicked_at_ms": value.continue_clicked_at_ms,
        "collect_started_at_ms": value.collect_started_at_ms,
        "webrtc_elapsed_ms": value.webrtc_elapsed_ms,
    }


def _webrtc_context_payload(value: VisitorWebRtcContext | None) -> dict[str, object]:
    if value is None:
        return {
            "available": None,
            "tested": None,
            "candidate_count": None,
            "candidate_types": [],
            "local_ip_candidates": [],
            "public_ip_candidates": [],
            "relay_ip_candidates": [],
            "mdns_hostname_seen": None,
            "error": None,
        }
    return {
        "available": value.available,
        "tested": value.tested,
        "candidate_count": value.candidate_count,
        "candidate_types": _candidate_types(value.candidate_types),
        "local_ip_candidates": _ip_candidate_list(value.local_ip_candidates),
        "public_ip_candidates": _ip_candidate_list(value.public_ip_candidates),
        "relay_ip_candidates": _ip_candidate_list(value.relay_ip_candidates),
        "mdns_hostname_seen": value.mdns_hostname_seen,
        "error": _safe_webrtc_error(value.error),
    }


def _server_context_payload(request: Request) -> dict[str, object]:
    return {
        "cf_ray_id": _bounded_header(request.headers.get("cf-ray"), 128),
        "cf_country": _bounded_header(request.headers.get("cf-ipcountry"), 8),
    }


def _candidate_types(values: list[str]) -> list[str]:
    allowed = {"host", "srflx", "relay", "prflx", "unknown"}
    normalized: list[str] = []
    for value in values:
        lowered = value.strip().lower()
        if lowered not in allowed:
            lowered = "unknown"
        if lowered not in normalized:
            normalized.append(lowered)
        if len(normalized) >= 10:
            break
    return normalized


def _ip_candidate_list(values: list[str]) -> list[str]:
    candidates: list[str] = []
    for value in values:
        candidate = _validated_ip_string(value)
        if candidate is None or candidate in candidates:
            continue
        candidates.append(candidate)
        if len(candidates) >= 10:
            break
    return candidates


def _validated_ip_string(value: str) -> str | None:
    try:
        return str(ip_address(value.strip()))
    except ValueError:
        return None


def _safe_webrtc_error(value: str | None) -> str | None:
    allowed = {"not_supported", "blocked", "timeout", "failed", "unknown"}
    if value is None:
        return None
    normalized = value.strip().lower().replace("-", "_")[:64]
    return normalized if normalized in allowed else "unknown"


def _bounded_string_list(values: list[str], *, max_items: int, max_length: int) -> list[str]:
    bounded: list[str] = []
    for value in values:
        stripped = value.strip()
        if not stripped or stripped in bounded:
            continue
        bounded.append(stripped[:max_length])
        if len(bounded) >= max_items:
            break
    return bounded


def _bounded_header(value: str | None, max_length: int) -> str | None:
    stripped = value.strip() if value else ""
    return stripped[:max_length] if stripped else None


def _linked_session(db: DbSession, row: VisitorVisit) -> UserSession | None:
    if row.session_id is None:
        return None
    return db.execute(select(UserSession).where(UserSession.id == str(row.session_id))).scalar_one_or_none()


def _risk_context(
    row: VisitorVisit,
    db: DbSession,
    session_row: UserSession | None,
    browser_context: dict[str, object],
    webrtc_context: dict[str, object],
) -> dict[str, object]:
    return {
        "timezone_ip_mismatch": _timezone_ip_mismatch(row),
        "language_country_mismatch": _language_country_mismatch(row, browser_context),
        "webrtc_public_ip_request_ip_mismatch": _webrtc_public_ip_mismatch(row, webrtc_context),
        "ip_changed_between_entry_and_login": _ip_changed_between_entry_and_login(row, session_row),
        "repeat_visitor_count": _repeat_visitor_count(row, db),
    }


def _timezone_ip_mismatch(row: VisitorVisit) -> bool | None:
    ip_timezone = _stored_ip_location(row).get("timezone")
    if not row.browser_timezone or not isinstance(ip_timezone, str) or not ip_timezone:
        return None
    return row.browser_timezone != ip_timezone


def _language_country_mismatch(row: VisitorVisit, browser_context: dict[str, object]) -> bool | None:
    country_code = _stored_ip_location(row).get("country_code")
    if not isinstance(country_code, str) or not country_code:
        return None
    languages = browser_context.get("languages")
    candidates = languages if isinstance(languages, list) else [row.browser_language]
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        region = _language_region(candidate)
        if region:
            return region.upper() != country_code.upper()
    return None


def _stored_ip_location(row: VisitorVisit) -> dict[str, object]:
    location = _stored_ip_payload(row.ip_enrichment).get("location")
    return location if isinstance(location, dict) else {}


def _language_region(language: str) -> str | None:
    normalized = language.replace("_", "-")
    parts = normalized.split("-")
    return parts[1] if len(parts) >= 2 and len(parts[1]) == 2 else None


def _webrtc_public_ip_mismatch(row: VisitorVisit, webrtc_context: dict[str, object]) -> bool | None:
    public_ips = webrtc_context.get("public_ip_candidates")
    if row.ip is None or not isinstance(public_ips, list) or not public_ips:
        return None
    return str(row.ip) not in {value for value in public_ips if isinstance(value, str)}


def _ip_changed_between_entry_and_login(
    row: VisitorVisit, session_row: UserSession | None
) -> bool | None:
    if row.ip is None or session_row is None or session_row.ip is None:
        return None
    return str(row.ip) != str(session_row.ip)


def _repeat_visitor_count(row: VisitorVisit, db: DbSession) -> int | None:
    if row.ip is None or not row.ua:
        return None
    return db.execute(
        select(func.count())
        .select_from(VisitorVisit)
        .where(VisitorVisit.ip == str(row.ip))
        .where(VisitorVisit.ua == row.ua)
    ).scalar_one()


def _create_collect_alert_safely(
    db: DbSession,
    *,
    settings: Settings,
    visit: VisitorVisit,
) -> None:
    try:
        browser_context = _stored_dict(visit.browser_context)
        webrtc_context = _stored_dict(visit.webrtc_context)
        risk_context = _risk_context(visit, db, None, browser_context, webrtc_context)
        create_visitor_entry_alert(db, settings=settings, visit=visit, risk_context=risk_context)
        db.commit()
    except Exception:
        db.rollback()


def _access_request_response(row: VisitorAccessRequest) -> VisitorAccessRequestResponse:
    return VisitorAccessRequestResponse(
        request_id=row.id,
        applicant_name=row.applicant_name,
        email=row.email,
        organization=row.organization,
        reason=row.reason,
        requested_role=row.requested_role,
        status=row.status.value,
        visitor_visit_id=row.visitor_visit_id,
        requester_ip=str(row.requester_ip) if row.requester_ip is not None else None,
        created_at=row.created_at,
        decided_at=row.decided_at,
        decided_by_user_id=row.decided_by_user_id,
        decision_note=row.decision_note,
        github_invitation_id=row.github_invitation_id,
        github_org=row.github_org,
        github_invite_status=row.github_invite_status,
    )


def _parse_access_request_status(value: str) -> VisitorAccessRequestStatus:
    try:
        return VisitorAccessRequestStatus(value)
    except ValueError as exc:
        raise ProblemDetail(
            status=400,
            title="Bad Request",
            detail="access-request-status-invalid",
            type_uri="https://panoptix.local/problems/bad-request",
        ) from exc


def _get_access_request_or_404(db: DbSession, request_id: str) -> VisitorAccessRequest:
    row = db.execute(
        select(VisitorAccessRequest).where(
            VisitorAccessRequest.id == str(_parse_uuid(request_id, "access-request-id-invalid"))
        )
    ).scalar_one_or_none()
    if row is None:
        raise _not_found("access-request-not-found")
    return row


def _require_pending_access_request(row: VisitorAccessRequest) -> None:
    if row.status != VisitorAccessRequestStatus.pending:
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="access-request-not-pending",
            type_uri="https://panoptix.local/problems/conflict",
        )


def _role_or_404(db: DbSession, role_name: str) -> Role:
    role = db.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none()
    if role is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="role-not-found",
            type_uri="https://panoptix.local/problems/not-found",
        )
    return role


def _record_public_access_request_audit_safely(
    db: DbSession,
    *,
    settings: Settings,
    request: Request,
    row: VisitorAccessRequest,
) -> None:
    try:
        record_audit_event(
            db,
            actor_type=ActorType.system,
            audit_hmac_key_version=settings.AUDIT_HMAC_KEY_VERSION,
            audit_hmac_key=settings.AUDIT_HMAC_KEY,
            actor_id=None,
            action="visitor.access_request.created",
            resource=f"visitor-access-request:{row.id}",
            payload={
                "request_id": str(row.id),
                "email": row.email,
                "requested_role": row.requested_role,
                "visitor_visit_id": str(row.visitor_visit_id) if row.visitor_visit_id else None,
            },
            ip=browser_request_ip(request, settings),
            ua=_request_ua(request),
            session_id=None,
        )
    except AuditLogError:
        return


def _record_access_request_audit_safely(
    db: DbSession,
    *,
    settings: Settings,
    request: Request,
    actor_id: uuid.UUID,
    action: str,
    row: VisitorAccessRequest,
    payload: dict[str, object] | None = None,
) -> None:
    try:
        _record_access_request_audit_required(
            db,
            settings=settings,
            request=request,
            actor_id=actor_id,
            action=action,
            row=row,
            payload=payload,
        )
    except AuditLogError:
        return


def _record_access_request_audit_required(
    db: DbSession,
    *,
    settings: Settings,
    request: Request,
    actor_id: uuid.UUID,
    action: str,
    row: VisitorAccessRequest,
    payload: dict[str, object] | None = None,
) -> None:
    base_payload: dict[str, object] = {
        "request_id": str(row.id),
        "email": row.email,
        "requested_role": row.requested_role,
        "status": row.status.value,
    }
    if payload:
        base_payload.update(payload)
    record_audit_event(
        db,
        actor_type=ActorType.user,
        audit_hmac_key_version=settings.AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=settings.AUDIT_HMAC_KEY,
        actor_id=actor_id,
        action=action,
        resource=f"visitor-access-request:{row.id}",
        payload=base_payload,
        ip=browser_request_ip(request, settings),
        ua=_request_ua(request),
        session_id=getattr(request.state, "audit_session_id", None),
    )


def _record_detail_audit_safely(
    db: DbSession,
    *,
    request: Request,
    settings: Settings,
    actor_id: uuid.UUID,
    row: VisitorVisit,
) -> None:
    try:
        record_audit_event(
            db,
            actor_type=ActorType.user,
            audit_hmac_key_version=settings.AUDIT_HMAC_KEY_VERSION,
            audit_hmac_key=settings.AUDIT_HMAC_KEY,
            actor_id=actor_id,
            action="admin.visitor.visit.viewed",
            resource=f"visitor-visit:{row.id}",
            payload={
                "visit_id": str(row.id),
                "logged_in": row.session_id is not None,
            },
            ip=browser_request_ip(request, settings),
            ua=_request_ua(request),
            session_id=getattr(request.state, "audit_session_id", None),
        )
    except AuditLogError:
        return


def _request_ua(request: Request) -> str | None:
    user_agent = request.headers.get("user-agent")
    return user_agent[:512] if user_agent else None


def _optional_value(value: str | None) -> str | None:
    stripped = value.strip() if value else ""
    return stripped or None


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


def _not_found(detail: str) -> ProblemDetail:
    return ProblemDetail(
        status=404,
        title="Not Found",
        detail=detail,
        type_uri="https://panoptix.local/problems/not-found",
    )
