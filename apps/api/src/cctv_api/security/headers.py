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
    apply_security_headers(response, settings, request)
    return response


def apply_security_headers(
    response: Response,
    settings: Settings,
    request: Request | None = None,
) -> None:
    # ── Standard security headers (§16.5) ──
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")

    # ── Permissions-Policy (§16.5 / Inv 5 — CCTV-only defence in depth) ──
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), autoplay=(self), display-capture=()",
    )

    # ── CSP — strict, no unsafe-inline, no unsafe-eval (§16.5) ──
    response.headers.setdefault(
        "Content-Security-Policy",
        _content_security_policy(settings, path=_request_path(request)),
    )

    # ── HSTS preload (§16.5) ──
    response.headers.setdefault(
        "Strict-Transport-Security",
        "max-age=63072000; includeSubDomains; preload",
    )

    # ── Cross-origin isolation (§16.5) ──
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

    # ── Strip server banners (§16.5 — no Server/X-Powered-By) ──
    if "server" in response.headers:
        del response.headers["server"]
    if "x-powered-by" in response.headers:
        del response.headers["x-powered-by"]

    # ── CORS (§16.13) ──
    _apply_cors_headers(response, settings, request)


def _content_security_policy(settings: Settings, path: str = "") -> str:
    if settings.APP_ENV == "development" and path == "/docs":
        return "; ".join(
            [
                "default-src 'none'",
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
                "img-src 'self' data: https://fastapi.tiangolo.com",
                "connect-src 'self'",
                "frame-ancestors 'none'",
                "base-uri 'none'",
                "form-action 'self'",
            ]
        )

    # Dynamic connect-src based on active LiveKit mode (§16.5, M-08)
    livekit_origin = _active_livekit_connect_src(settings)

    directives = [
        "default-src 'none'",
        f"connect-src 'self' {livekit_origin}".strip() if livekit_origin else "connect-src 'self'",
        "media-src blob:",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'self'",
    ]
    if settings.CSP_REPORT_URI.strip():
        directives.append(f"report-uri {settings.CSP_REPORT_URI.strip()}")
    return "; ".join(directives)


def _active_livekit_connect_src(settings: Settings) -> str:
    """Return the active LiveKit WSS origin for CSP connect-src.

    The middleware reads ``LIVEKIT_MODE`` and emits only the active
    LiveKit origin — never a wildcard.  Both cloud and fallback values
    are pre-approved in code (§16.5 / M-08).
    """
    if settings.LIVEKIT_MODE == "fallback":
        url = settings.LIVEKIT_FALLBACK_URL.strip()
    else:
        url = settings.LIVEKIT_CONNECT_SRC.strip()

    if not url or "replace-me" in url:
        return ""
    return url


def _apply_cors_headers(
    response: Response,
    settings: Settings,
    request: Request | None,
) -> None:
    """Apply per-route CORS policy (§16.13).

    Rules:
    - Gateway APIs (``/api/v1/gateways/*``): not browser-callable.
      Preflight ``OPTIONS`` gets 405; no ``Access-Control-Allow-Origin``.
    - Webhook (``/api/v1/webhooks/livekit``): server-to-server only.
      No ``Access-Control-Allow-Origin``; preflight returns 405.
    - Authenticated browser APIs: exact origin only, credentials allowed,
      no wildcard.
    """
    path = _request_path(request)

    # Gateway and webhook routes are NOT browser-callable — no CORS headers
    if _is_gateway_route(path) or _is_webhook_route(path):
        return

    # For browser-facing routes: exact origin, credentials, limited methods
    origin = settings.APP_PUBLIC_BASE_URL.rstrip("/")
    if not origin or "example.test" in origin:
        # Safety: do not emit CORS in placeholder/test config
        return

    response.headers.setdefault("Access-Control-Allow-Origin", origin)
    response.headers.setdefault("Access-Control-Allow-Credentials", "true")
    response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    response.headers.setdefault(
        "Access-Control-Allow-Headers",
        "Content-Type, x-panoptix-csrf-token",
    )


def _request_path(request: Request | None) -> str:
    if request is None:
        return ""
    return request.url.path


def _is_gateway_route(path: str) -> bool:
    return path.startswith("/api/v1/gateways/") or path == "/api/v1/gateway-control/ws"


def _is_webhook_route(path: str) -> bool:
    return path == "/api/v1/webhooks/livekit"
