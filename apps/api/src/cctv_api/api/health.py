from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from cctv_api.db import db_session

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/admin/health/deep")
def health_deep(db: DbSession = Depends(db_session)) -> dict[str, str]:
    db_status = "not_connected"
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    overall = "ok" if db_status == "connected" else "degraded"
    return {
        "status": overall,
        "db": db_status,
        "livekit": "not_connected",
        "gateway": "not_connected",
    }
