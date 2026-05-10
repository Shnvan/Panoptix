from __future__ import annotations

from fastapi import Depends, Request, Response, WebSocket
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.errors import ProblemDetail
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.security.cloudflare_access import AccessVerificationError, CloudflareAccessVerifier
from cctv_api.security.identity import Principal, PrincipalKind
from cctv_api.security.session_cookie import create_session_cookie, read_session_cookie
from cctv_api.security.sessions import create_session, get_active_session, touch_session
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
        touch_session(db, session_row.id)

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
