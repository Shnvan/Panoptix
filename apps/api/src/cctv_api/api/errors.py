from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class ProblemDetail(Exception):
    """RFC 9457 Problem Details exception."""

    def __init__(
        self,
        *,
        status: int = 500,
        title: str = "Internal Server Error",
        detail: str = "",
        type_uri: str = "about:blank",
        extra: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        delete_cookies: list[dict[str, Any]] | None = None,
    ) -> None:
        self.status = status
        self.title = title
        self.detail = detail
        self.type_uri = type_uri
        self.extra = extra or {}
        self.headers = headers or {}
        self.delete_cookies = delete_cookies or []
        super().__init__(detail)


async def problem_detail_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ProblemDetail)
    body: dict[str, Any] = {
        "type": exc.type_uri,
        "title": exc.title,
        "status": exc.status,
        "detail": exc.detail,
    }
    body.update(exc.extra)
    response = JSONResponse(status_code=exc.status, content=body, headers=exc.headers or None)
    for cookie in exc.delete_cookies:
        response.delete_cookie(**cookie)
    return response
