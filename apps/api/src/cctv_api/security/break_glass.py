from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.errors import ProblemDetail
from cctv_api.models.tables import BreakGlassUsage

BREAK_GLASS_WINDOW_MINUTES = 90

ROTATION_CHECKLIST = [
    "Audit HMAC key (new version)",
    "LiveKit API keys",
    "CF Access service tokens",
    "All gateway credentials",
]


def _get_latest_unclosed(db: DbSession) -> BreakGlassUsage | None:
    return db.execute(
        select(BreakGlassUsage)
        .where(BreakGlassUsage.closed_at.is_(None))
        .order_by(BreakGlassUsage.opened_at.desc())
    ).scalar_one_or_none()


def get_active_window(db: DbSession, *, now: datetime | None = None) -> BreakGlassUsage | None:
    now = now or datetime.now(timezone.utc)
    usage = _get_latest_unclosed(db)
    if usage is None:
        return None
    auto_disable = usage.auto_disable_at
    if auto_disable.tzinfo is None:
        auto_disable = auto_disable.replace(tzinfo=timezone.utc)
    if now >= auto_disable:
        return None
    return usage


def assert_break_glass_active(db: DbSession, *, now: datetime | None = None) -> BreakGlassUsage:
    usage = get_active_window(db, now=now)
    if usage is None:
        raise ProblemDetail(
            status=403,
            title="Forbidden",
            detail="break-glass-expired",
            type_uri="https://panoptix.local/problems/forbidden",
        )
    return usage


def open_break_glass_window(
    db: DbSession,
    *,
    reason: str,
    window_minutes: int = BREAK_GLASS_WINDOW_MINUTES,
    now: datetime | None = None,
) -> BreakGlassUsage:
    now = now or datetime.now(timezone.utc)
    existing = get_active_window(db, now=now)
    if existing is not None:
        raise ProblemDetail(
            status=409,
            title="Conflict",
            detail="break-glass-already-active",
            type_uri="https://panoptix.local/problems/conflict",
        )
    usage = BreakGlassUsage(
        opened_at=now,
        opened_by_reason=reason,
        auto_disable_at=now + timedelta(minutes=window_minutes),
    )
    db.add(usage)
    db.flush()
    return usage


def close_break_glass_window(
    db: DbSession,
    *,
    reason: str,
    now: datetime | None = None,
) -> BreakGlassUsage:
    now = now or datetime.now(timezone.utc)
    usage = _get_latest_unclosed(db)
    if usage is None:
        raise ProblemDetail(
            status=404,
            title="Not Found",
            detail="no-active-break-glass-window",
            type_uri="https://panoptix.local/problems/not-found",
        )
    usage.closed_at = now
    usage.closed_reason = reason
    db.flush()
    return usage


def get_break_glass_status(db: DbSession) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    usage = get_active_window(db, now=now)
    if usage is None:
        return {"active": False}
    return {
        "active": True,
        "auto_disable_at": usage.auto_disable_at.isoformat(),
    }
