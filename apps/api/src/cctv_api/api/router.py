from __future__ import annotations

from fastapi import APIRouter, Depends

from cctv_api.security.dependencies import require_authenticated_user
from cctv_api.security.identity import Principal

v1_router = APIRouter(prefix="/api/v1")


@v1_router.get("/me")
def get_me(principal: Principal = Depends(require_authenticated_user)) -> dict[str, object]:
    return principal.to_response()


@v1_router.get("/cameras")
def list_cameras(
    _principal: Principal = Depends(require_authenticated_user),
) -> dict[str, object]:
    return {"items": [], "next_cursor": None}
