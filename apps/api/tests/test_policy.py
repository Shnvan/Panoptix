from __future__ import annotations

import pytest

from cctv_api.api.errors import ProblemDetail
from cctv_api.security.identity import Principal, PrincipalKind
from cctv_api.security.policy import require_permission, require_role


def test_require_role_allows_matching_role() -> None:
    principal = Principal(kind=PrincipalKind.USER, subject="user-1", roles=frozenset({"viewer"}))
    assert require_role(principal, "viewer") is principal


def test_require_role_denies_missing_role() -> None:
    principal = Principal(kind=PrincipalKind.USER, subject="user-1")
    with pytest.raises(ProblemDetail) as exc_info:
        require_role(principal, "admin")
    assert exc_info.value.status == 403
    assert exc_info.value.detail == "role-required"


def test_require_permission_allows_matching_permission() -> None:
    principal = Principal(
        kind=PrincipalKind.USER,
        subject="user-1",
        permissions=frozenset({"camera:view"}),
    )
    assert require_permission(principal, "camera:view") is principal


def test_require_permission_denies_missing_permission() -> None:
    principal = Principal(kind=PrincipalKind.USER, subject="user-1")
    with pytest.raises(ProblemDetail) as exc_info:
        require_permission(principal, "camera:view")
    assert exc_info.value.status == 403
    assert exc_info.value.detail == "permission-required"
