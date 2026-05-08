from __future__ import annotations

from cctv_api.api.errors import ProblemDetail
from cctv_api.security.identity import Principal


def has_role(principal: Principal, role: str) -> bool:
    return role in principal.roles


def has_permission(principal: Principal, permission: str) -> bool:
    return permission in principal.permissions


def require_role(principal: Principal, role: str) -> Principal:
    if has_role(principal, role):
        return principal
    raise ProblemDetail(
        status=403,
        title="Forbidden",
        detail="role-required",
        type_uri="https://panoptix.local/problems/forbidden",
    )


def require_permission(principal: Principal, permission: str) -> Principal:
    if has_permission(principal, permission):
        return principal
    raise ProblemDetail(
        status=403,
        title="Forbidden",
        detail="permission-required",
        type_uri="https://panoptix.local/problems/forbidden",
    )
