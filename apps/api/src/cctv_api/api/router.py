from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.errors import ProblemDetail
from cctv_api.api.gateways import router as gateway_router
from cctv_api.db import db_session
from cctv_api.security.dependencies import require_authenticated_user
from cctv_api.security.identity import Principal
from cctv_api.security.sessions import list_active_sessions, revoke_session
from cctv_api.security.users import get_or_create_user

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(gateway_router)


@v1_router.get("/me")
def get_me(principal: Principal = Depends(require_authenticated_user)) -> dict[str, object]:
    return principal.to_response()


@v1_router.get("/cameras")
def list_cameras(
    _principal: Principal = Depends(require_authenticated_user),
) -> dict[str, object]:
    return {"items": [], "next_cursor": None}


@v1_router.get("/sessions/active")
def get_active_sessions(
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)
    sessions = list_active_sessions(db, user.id)
    return {
        "items": [
            {
                "id": str(s.id),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "last_seen_at": s.last_seen_at.isoformat() if s.last_seen_at else None,
                "ua_fp": s.ua_fp,
            }
            for s in sessions
        ],
    }


class RevokeSessionRequest(BaseModel):
    session_id: uuid.UUID


@v1_router.post("/sessions/revoke")
def revoke_user_session(
    body: RevokeSessionRequest,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
) -> dict[str, object]:
    user = get_or_create_user(db, email=principal.email or principal.subject, idp_subject=principal.subject)

    is_admin = "admin" in principal.roles

    if not is_admin:
        own_sessions = list_active_sessions(db, user.id)
        own_ids = {s.id for s in own_sessions}
        if body.session_id not in own_ids:
            raise ProblemDetail(
                status=403,
                title="Forbidden",
                detail="session-not-owned",
                type_uri="https://panoptix.local/problems/forbidden",
            )

    revoked = revoke_session(db, body.session_id)
    return {"revoked": revoked, "session_id": str(body.session_id)}
