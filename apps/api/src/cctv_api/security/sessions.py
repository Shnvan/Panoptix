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


def list_active_sessions(db: DbSession, user_id: uuid.UUID) -> list[Session]:
    stmt = (
        select(Session)
        .where(Session.user_id == str(user_id), Session.revoked_at.is_(None))
        .order_by(Session.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())
