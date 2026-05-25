from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.models.tables import Session, VisitorVisit
from cctv_api.security.visitor_cookie import read_visitor_cookie


def link_visitor_visit_to_session(
    db: DbSession,
    *,
    cookie_value: str | None,
    settings: Settings,
    user_id: uuid.UUID,
    session_row: Session,
    now: datetime | None = None,
) -> bool:
    visit_id = read_visitor_cookie(cookie_value or "", settings.VISITOR_COOKIE_SIGNING_KEY)
    if visit_id is None:
        return False

    current = now or datetime.now(timezone.utc)
    retention_cutoff = current - timedelta(days=settings.VISITOR_RETENTION_DAYS)
    visit = db.execute(
        select(VisitorVisit)
        .where(VisitorVisit.id == str(visit_id))
        .where(VisitorVisit.session_id.is_(None))
        .where(VisitorVisit.collected_at >= retention_cutoff)
    ).scalar_one_or_none()
    if visit is None:
        return False

    visit.user_id = user_id
    visit.session_id = session_row.id
    visit.logged_in_at = current
    db.commit()
    return True


def purge_expired_visitor_visits(
    db: DbSession,
    *,
    retention_days: int,
    now: datetime | None = None,
) -> int:
    current = now or datetime.now(timezone.utc)
    result = db.execute(
        delete(VisitorVisit).where(
            VisitorVisit.collected_at < current - timedelta(days=retention_days)
        )
    )
    return result.rowcount  # type: ignore[attr-defined]
