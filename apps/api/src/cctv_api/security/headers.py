from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from cctv_api.core.config import Settings


async def add_security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
    settings: Settings,
) -> Response:
    response = await call_next(request)
    apply_security_headers(response, settings)
    return response


def apply_security_headers(response: Response, settings: Settings) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", _content_security_policy(settings))


def _content_security_policy(settings: Settings) -> str:
    directives = [
        "default-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'none'",
    ]
    if settings.CSP_REPORT_URI.strip():
        directives.append(f"report-uri {settings.CSP_REPORT_URI.strip()}")
    return "; ".join(directives)
