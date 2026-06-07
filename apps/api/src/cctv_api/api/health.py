from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.models.enums import GatewayStatus
from cctv_api.models.tables import EdgeGateway
from cctv_api.security.livekit_rooms import (
    _is_placeholder,
    _livekit_admin_token,
    _livekit_credentials,
    _livekit_http_url,
)

router = APIRouter()

_LIST_ROOMS_PATH = "/twirp/livekit.RoomService/ListRooms"


def _probe_livekit(settings: Settings) -> str:
    try:
        api_key, api_secret = _livekit_credentials(settings)
        if _is_placeholder(api_key) or _is_placeholder(api_secret):
            return "not_configured"
        base_url = _livekit_http_url(settings)
        token = _livekit_admin_token(api_key, api_secret)
        resp = httpx.post(
            f"{base_url}{_LIST_ROOMS_PATH}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"names": []},
            timeout=5.0,
        )
        return "connected" if resp.status_code == 200 else "error"
    except Exception:
        return "error"


def _probe_gateways(db: DbSession, settings: Settings) -> str:
    try:
        rows = db.execute(
            select(EdgeGateway).where(EdgeGateway.status == GatewayStatus.enabled)
        ).scalars().all()
        if not rows:
            return "no_gateways"
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        threshold = now - timedelta(
            seconds=settings.GATEWAY_STALE_THRESHOLD_SECONDS
        )

        def _as_naive_utc(dt: datetime) -> datetime:
            return dt.replace(tzinfo=None) if dt.tzinfo else dt

        has_recent = any(
            gw.last_seen_at is not None
            and _as_naive_utc(gw.last_seen_at) >= threshold
            for gw in rows
        )
        return "connected" if has_recent else "stale"
    except Exception:
        return "error"


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/admin/health/deep")
def health_deep(
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    db_status = "not_connected"
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    livekit_status = _probe_livekit(settings)
    gateway_status = _probe_gateways(db, settings)

    livekit_ok = livekit_status in ("connected", "not_configured")
    gateway_ok = gateway_status in ("connected", "no_gateways")
    overall = "ok" if (db_status == "connected" and livekit_ok and gateway_ok) else "degraded"

    return {
        "status": overall,
        "db": db_status,
        "livekit": livekit_status,
        "gateway": gateway_status,
        "assistant": "enabled" if settings.AI_ASSISTANT_ENABLED else "disabled",
    }
