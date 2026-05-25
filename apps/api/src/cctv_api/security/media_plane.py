from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.models.tables import SystemConfig

MEDIA_PLANE_KEY = "media_plane_mode"
VALID_MODES = ("cloud", "fallback")


def get_media_plane_mode(db: DbSession) -> str:
    row = db.execute(
        select(SystemConfig).where(SystemConfig.key == MEDIA_PLANE_KEY)
    ).scalar_one_or_none()
    if row is None:
        return "cloud"
    return row.value


def set_media_plane_mode(
    db: DbSession,
    *,
    mode: str,
    actor_id: object,
) -> tuple[str, str]:
    if mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail="mode-invalid")

    current = get_media_plane_mode(db)
    if mode == current:
        raise HTTPException(status_code=409, detail="mode-already-active")

    now = datetime.now(timezone.utc)
    row = db.execute(
        select(SystemConfig).where(SystemConfig.key == MEDIA_PLANE_KEY)
    ).scalar_one_or_none()
    actor_uuid = _uuid.UUID(str(actor_id)) if actor_id is not None else None
    if row is None:
        row = SystemConfig(
            key=MEDIA_PLANE_KEY,
            value=mode,
            updated_by=actor_uuid,
            updated_at=now,
        )
        db.add(row)
    else:
        row.value = mode
        row.updated_by = actor_uuid
        row.updated_at = now

    previous = current
    return previous, mode
