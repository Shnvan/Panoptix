from __future__ import annotations

from fastapi import Depends, Request

from cctv_api.api.errors import ProblemDetail
from cctv_api.core.config import Settings, get_settings
from cctv_api.security.cloudflare_access import AccessVerificationError, CloudflareAccessVerifier
from cctv_api.security.identity import Principal


def _auth_problem(detail: str) -> ProblemDetail:
    return ProblemDetail(
        status=401,
        title="Unauthorized",
        detail=detail,
        type_uri="https://panoptix.local/problems/unauthorized",
    )


def require_authenticated_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Principal:
    verifier = CloudflareAccessVerifier(settings)
    try:
        return verifier.verify_browser_request(request)
    except AccessVerificationError as exc:
        raise _auth_problem(exc.detail) from exc


def require_gateway_identity(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Principal:
    verifier = CloudflareAccessVerifier(settings)
    try:
        return verifier.verify_gateway_request(request)
    except AccessVerificationError as exc:
        raise _auth_problem(exc.detail) from exc
