from __future__ import annotations

from fastapi import APIRouter

v1_router = APIRouter(prefix="/api/v1")


@v1_router.get("/me")
def get_me() -> dict[str, str]:
    """Placeholder for user profile/bootstrap endpoint. Requires auth (security phase)."""
    return {"status": "not_implemented"}


@v1_router.get("/cameras")
def list_cameras() -> dict[str, str]:
    """Placeholder for camera list endpoint. Requires auth + ACL (security phase)."""
    return {"status": "not_implemented"}
