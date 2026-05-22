from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import Depends, Request, Response, WebSocket
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.errors import ProblemDetail
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.models.enums import ActorType
from cctv_api.security.audit import AuditLogError, record_audit_event
from cctv_api.security.cloudflare_access import AccessVerificationError, CloudflareAccessVerifier
from cctv_api.security.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CsrfTokenError,
    create_csrf_token,
    verify_csrf_token,
)
from cctv_api.security.identity import Principal, PrincipalKind
from cctv_api.security.request_ip import browser_request_ip
from cctv_api.security.session_cookie import create_session_cookie, read_session_cookie
from cctv_api.security.sessions import (
    create_session,
    get_active_session,
    is_session_expired,
    revoke_session,
    touch_session,
)
from cctv_api.security.suspicious_login import check_login_suspicion
from cctv_api.security.users import get_or_create_user, get_user_roles


def _auth_problem(detail: str, *, status: int = 401) -> ProblemDetail:
    title = "Forbidden" if status == 403 else "Unauthorized"
    type_uri = "https://panoptix.local/problems/forbidden" if status == 403 else "https://panoptix.local/problems/unauthorized"
    return ProblemDetail(
        status=status,
        title=title,
        detail=detail,
        type_uri=type_uri,
    )


def require_authenticated_user(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    db: DbSession = Depends(db_session),
) -> Principal:
    verifier = CloudflareAccessVerifier(settings)
    try:
        principal = verifier.verify_browser_request(request)
    except AccessVerificationError as exc:
        action = (
            "auth.login.denied.jwt_missing"
            if exc.detail == "cf-access-token-required"
            else "auth.login.denied.jwt_invalid"
        )
        _record_auth_audit_safely(db, settings=settings, request=request, action=action, detail=exc.detail)
        raise _auth_problem(exc.detail) from exc

    if principal.is_dev:
        return principal

    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    db_roles = get_user_roles(db, user.id)

    cookie_value = request.cookies.get(settings.SESSION_COOKIE_NAME)
    session_id = read_session_cookie(cookie_value or "", settings.SESSION_SIGNING_KEY) if cookie_value else None

    session_row = get_active_session(db, session_id) if session_id else None

    if session_row is None:
        if _csrf_required(request):
            _record_auth_audit_safely(
                db, settings=settings, request=request,
                action="auth.csrf.denied", detail="csrf-token-required",
                actor_id=user.id,
            )
            raise _auth_problem("csrf-token-required", status=403)
        ip = browser_request_ip(request, settings)
        ua = request.headers.get("user-agent", "")[:255]
        session_row = create_session(db, user_id=user.id, ua_fp=ua, ip=ip)
        signed = create_session_cookie(session_row.id, settings.SESSION_SIGNING_KEY)
        response.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value=signed,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
        _record_auth_audit_safely(
            db, settings=settings, request=request,
            action="auth.session.created", detail=None,
            actor_id=user.id, session_id=session_row.id,
        )
        # ── Suspicious login detection (pilot) ──
        if settings.SUSPICIOUS_LOGIN_DETECTION_ENABLED:
            try:
                country = request.headers.get("cf-ipcountry")
                check_login_suspicion(
                    db,
                    settings=settings,
                    user_id=user.id,
                    ip=ip,
                    country=country,
                    user_agent=ua,
                    login_time=datetime.now(timezone.utc),
                )
            except Exception:
                pass  # Never block authentication on detection failure
    else:
        # ── Session TTL enforcement (§16.4) ──
        expiry_reason = is_session_expired(
            session_row,
            idle_timeout_seconds=settings.SESSION_IDLE_TIMEOUT_SECONDS,
            absolute_timeout_seconds=settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS,
        )
        if expiry_reason is not None:
            _record_auth_audit_safely(
                db, settings=settings, request=request,
                action="auth.session.expired", detail=expiry_reason,
                actor_id=user.id, session_id=session_row.id,
            )
            revoke_session(db, session_row.id)
            raise _auth_problem(expiry_reason)

        if _csrf_required(request):
            _verify_request_csrf(request, session_row.id, settings, db=db, user_id=user.id)
        touch_session(db, session_row.id)

    _set_csrf_cookie(response, session_row.id, settings)
    request.state.audit_session_id = session_row.id
    return Principal(
        kind=PrincipalKind.USER,
        subject=principal.subject,
        email=principal.email,
        roles=frozenset(db_roles),
        permissions=frozenset(),
        is_dev=False,
    )


def require_gateway_identity(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: DbSession = Depends(db_session),
) -> Principal:
    verifier = CloudflareAccessVerifier(settings)
    try:
        return verifier.verify_gateway_request(request, db)
    except AccessVerificationError as exc:
        _GATEWAY_AUTH_ACTION_MAP = {
            "gateway-identity-required": "auth.gateway.denied.identity_missing",
            "gateway-identity-invalid": "auth.gateway.denied.identity_invalid",
            "gateway-disabled": "auth.gateway.denied.disabled",
            "gateway-credential-invalid": "auth.gateway.denied.credential_invalid",
            "gateway-credential-not-configured": "auth.gateway.denied.credential_invalid",
        }
        action = _GATEWAY_AUTH_ACTION_MAP.get(exc.detail, "auth.gateway.denied.identity_invalid")
        _record_auth_audit_safely(
            db, settings=settings, request=request,
            action=action, detail=exc.detail,
            actor_type=ActorType.gateway,
        )
        raise _auth_problem(exc.detail, status=exc.status) from exc


def verify_gateway_identity_ws(
    websocket: WebSocket,
    settings: Settings = Depends(get_settings),
) -> Principal | None:
    verifier = CloudflareAccessVerifier(settings)
    try:
        return verifier.verify_gateway_websocket(websocket)
    except AccessVerificationError:
        return None


def _csrf_required(request: Request) -> bool:
    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False
    path = request.url.path
    if path.startswith("/api/v1/gateways/"):
        return False
    if path == "/api/v1/gateway-control/ws":
        return False
    if path == "/api/v1/webhooks/livekit":
        return False
    return path.startswith("/api/v1/admin/") or path in {
        "/api/v1/privacy/notice/accept",
        "/api/v1/sessions/revoke",
    }


def _verify_request_csrf(
    request: Request,
    session_id: uuid.UUID,
    settings: Settings,
    *,
    db: DbSession | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    header_token = request.headers.get(CSRF_HEADER_NAME)
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not header_token or not cookie_token:
        if db is not None:
            _record_auth_audit_safely(
                db, settings=settings, request=request,
                action="auth.csrf.denied", detail="csrf-token-required",
                actor_id=user_id, session_id=session_id,
            )
        raise _auth_problem("csrf-token-required", status=403)
    if header_token != cookie_token:
        if db is not None:
            _record_auth_audit_safely(
                db, settings=settings, request=request,
                action="auth.csrf.denied", detail="csrf-token-invalid",
                actor_id=user_id, session_id=session_id,
            )
        raise _auth_problem("csrf-token-invalid", status=403)
    try:
        verify_csrf_token(header_token, session_id=session_id, signing_key=settings.CSRF_SIGNING_KEY)
    except CsrfTokenError as exc:
        if db is not None:
            _record_auth_audit_safely(
                db, settings=settings, request=request,
                action="auth.csrf.denied", detail=exc.detail,
                actor_id=user_id, session_id=session_id,
            )
        raise _auth_problem(exc.detail, status=403) from exc


def _set_csrf_cookie(response: Response, session_id: uuid.UUID, settings: Settings) -> None:
    try:
        csrf_token = create_csrf_token(session_id, settings.CSRF_SIGNING_KEY)
    except CsrfTokenError:
        return
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=True,
        samesite="lax",
        path="/",
    )


def _record_auth_audit_safely(
    db: DbSession,
    *,
    settings: Settings,
    request: Request,
    action: str,
    detail: str | None,
    actor_id: uuid.UUID | None = None,
    actor_type: ActorType = ActorType.user,
    session_id: uuid.UUID | None = None,
) -> None:
    try:
        ip = browser_request_ip(request, settings)
        ua = request.headers.get("user-agent")
        record_audit_event(
            db,
            actor_type=actor_type,
            audit_hmac_key_version=settings.AUDIT_HMAC_KEY_VERSION,
            audit_hmac_key=settings.AUDIT_HMAC_KEY,
            actor_id=actor_id,
            action=action,
            resource=f"auth:{request.url.path}",
            payload={"detail": detail} if detail else None,
            ip=ip,
            ua=ua,
            session_id=session_id,
        )
    except (AuditLogError, Exception):
        pass
