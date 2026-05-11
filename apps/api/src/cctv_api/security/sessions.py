from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session as DbSession

from cctv_api.models.tables import Session


def create_session(
    db: DbSession,
    *,
    user_id: uuid.UUID,
    cf_jti: str | None = None,
    ua_fp: str | None = None,
    ip: str | None = None,
) -> Session:
    session_row = Session(
        id=uuid.uuid4(),
        user_id=user_id,
        cf_jti=cf_jti,
        ua_fp=ua_fp,
        ip=ip,
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    return session_row


def get_active_session(db: DbSession, session_id: uuid.UUID) -> Session | None:
    stmt = select(Session).where(Session.id == str(session_id), Session.revoked_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def is_session_expired(
    session_row: Session,
    *,
    idle_timeout_seconds: int,
    absolute_timeout_seconds: int,
    now: datetime | None = None,
) -> str | None:
    """Check whether a session has exceeded its TTL.

    Returns ``None`` if the session is still valid, or a short reason
    string (``"session-idle-expired"`` / ``"session-absolute-expired"``)
    for the auth dependency to use as the error detail.
    """
    current = now or datetime.now(timezone.utc)

    # Absolute timeout — §16.4: 8 h max session lifetime
    created = session_row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if (current - created).total_seconds() > absolute_timeout_seconds:
        return "session-absolute-expired"

    # Idle timeout — §16.4: 15 min of inactivity
    last_active = session_row.last_seen_at or session_row.created_at
    if last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)
    if (current - last_active).total_seconds() > idle_timeout_seconds:
        return "session-idle-expired"

    return None


def touch_session(db: DbSession, session_id: uuid.UUID) -> None:
    stmt = (
        update(Session)
        .where(Session.id == str(session_id), Session.revoked_at.is_(None))
        .values(last_seen_at=datetime.now(timezone.utc))
    )
    db.execute(stmt)
    db.commit()


def revoke_session(db: DbSession, session_id: uuid.UUID) -> bool:
    session_row = get_active_session(db, session_id)
    if session_row is None:
        return False

    session_row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return True


def revoke_all_user_sessions(db: DbSession, user_id: uuid.UUID) -> int:
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(Session)
        .where(Session.user_id == str(user_id), Session.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.flush()
    return result.rowcount  # type: ignore[attr-defined]


def list_active_sessions(db: DbSession, user_id: uuid.UUID) -> list[Session]:
    stmt = (
        select(Session)
        .where(Session.user_id == str(user_id), Session.revoked_at.is_(None))
        .order_by(Session.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())
