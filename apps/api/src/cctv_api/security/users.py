from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.models.tables import Role, User, UserRole


def get_or_create_user(
    db: DbSession,
    *,
    email: str,
    idp_subject: str | None = None,
) -> User:
    stmt = select(User).where(User.email == email)
    user = db.execute(stmt).scalar_one_or_none()
    if user is not None:
        return user

    user = User(id=uuid.uuid4(), email=email, idp_subject=idp_subject)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_roles(db: DbSession, user_id: uuid.UUID) -> set[str]:
    stmt = (
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return set(db.execute(stmt).scalars().all())
