from __future__ import annotations

import uuid

from fastapi import Depends, Request, Response, WebSocket
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.errors import ProblemDetail
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.security.cloudflare_access import AccessVerificationError, CloudflareAccessVerifier
from cctv_api.security.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CsrfTokenError,
    create_csrf_token,
    verify_csrf_token,
)
from cctv_api.security.identity import Principal, PrincipalKind
from cctv_api.security.session_cookie import create_session_cookie, read_session_cookie
from cctv_api.security.sessions import (
    create_session,
    get_active_session,
    is_session_expired,
    revoke_session,
    touch_session,
)
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
            raise _auth_problem("csrf-token-required", status=403)
        ip = request.client.host if request.client else None
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
    else:
        # ── Session TTL enforcement (§16.4) ──
        expiry_reason = is_session_expired(
            session_row,
            idle_timeout_seconds=settings.SESSION_IDLE_TIMEOUT_SECONDS,
            absolute_timeout_seconds=settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS,
        )
        if expiry_reason is not None:
            revoke_session(db, session_row.id)
            raise _auth_problem(expiry_reason)

        if _csrf_required(request):
            _verify_request_csrf(request, session_row.id, settings)
        touch_session(db, session_row.id)

    _set_csrf_cookie(response, session_row.id, settings)
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


def _verify_request_csrf(request: Request, session_id: uuid.UUID, settings: Settings) -> None:
    header_token = request.headers.get(CSRF_HEADER_NAME)
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not header_token or not cookie_token:
        raise _auth_problem("csrf-token-required", status=403)
    if header_token != cookie_token:
        raise _auth_problem("csrf-token-invalid", status=403)
    try:
        verify_csrf_token(header_token, session_id=session_id, signing_key=settings.CSRF_SIGNING_KEY)
    except CsrfTokenError as exc:
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
