from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.errors import ProblemDetail
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.models.enums import ActorType
from cctv_api.models.tables import VisitorVisit
from cctv_api.security.audit import AuditLogError, record_audit_event
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
from cctv_api.security.visitor_cookie import create_visitor_cookie

router = APIRouter()

CURRENT_VISITOR_NOTICE_TITLE = "Panoptix Visitor Security Notice"
CURRENT_VISITOR_NOTICE_BODY = (
    "Panoptix records limited browser and network context from this entry page "
    "for access security and investigation before continuing to the protected system."
)


class VisitorNoticeResponse(BaseModel):
    notice_version: str
    title: str
    body: str


class VisitorCollectRequest(BaseModel):
    notice_version: str = Field(min_length=1, max_length=64)
    notice_acknowledged: bool
    page_path: str = Field(min_length=1, max_length=512)
    screen_width: int | None = Field(default=None, ge=1, le=32768)
    screen_height: int | None = Field(default=None, ge=1, le=32768)
    timezone: str | None = Field(default=None, max_length=128)
    language: str | None = Field(default=None, max_length=64)


class VisitorCollectResponse(BaseModel):
    visit_id: uuid.UUID
    status: str
    collected_at: datetime


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
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
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
        "items": [_visit_response(row) for row in rows],
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
    return _visit_response(row)


def _require_collector_enabled(settings: Settings) -> None:
    if not settings.VISITOR_COLLECTOR_ENABLED:
        raise _not_found("visitor-collector-disabled")


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


def _visit_response(row: VisitorVisit) -> dict[str, object]:
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
        "login": {
            "logged_in": row.session_id is not None,
            "user_id": str(row.user_id) if row.user_id else None,
            "session_id": str(row.session_id) if row.session_id else None,
            "logged_in_at": row.logged_in_at.isoformat() if row.logged_in_at else None,
        },
    }


def _stored_ip_payload(value: Any) -> dict[str, object]:
    return value if isinstance(value, dict) and value else ip_intelligence_payload(None)


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
