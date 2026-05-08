from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Public health probe. Must not expose version, framework, or DB info."""
    return {"status": "ok"}


@router.get("/api/v1/admin/health/deep")
def health_deep() -> dict[str, str]:
    """Deep health check placeholder. Will require admin auth in security phase."""
    return {"status": "ok", "db": "not_connected", "livekit": "not_connected", "gateway": "not_connected"}
