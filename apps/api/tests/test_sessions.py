from __future__ import annotations

import uuid

from sqlalchemy.orm import Session as DbSession

from cctv_api.security.sessions import create_session, get_active_session, list_active_sessions, revoke_session
from cctv_api.security.session_cookie import create_session_cookie, read_session_cookie
from cctv_api.security.users import get_or_create_user


SIGNING_KEY = "test-signing-key-do-not-use"


def test_session_cookie_roundtrip() -> None:
    session_id = uuid.uuid4()
    cookie = create_session_cookie(session_id, SIGNING_KEY)
    result = read_session_cookie(cookie, SIGNING_KEY)
    assert result == session_id


def test_session_cookie_rejects_tampered_signature() -> None:
    session_id = uuid.uuid4()
    cookie = create_session_cookie(session_id, SIGNING_KEY)
    tampered = cookie[:-4] + "XXXX"
    result = read_session_cookie(tampered, SIGNING_KEY)
    assert result is None


def test_session_cookie_rejects_wrong_key() -> None:
    session_id = uuid.uuid4()
    cookie = create_session_cookie(session_id, SIGNING_KEY)
    result = read_session_cookie(cookie, "wrong-key")
    assert result is None


def test_session_cookie_rejects_empty() -> None:
    assert read_session_cookie("", SIGNING_KEY) is None


def test_session_cookie_rejects_no_dot() -> None:
    assert read_session_cookie("no-dot-here", SIGNING_KEY) is None


def test_session_cookie_rejects_bad_uuid() -> None:
    cookie = "not-a-uuid.abcdef1234567890"
    result = read_session_cookie(cookie, SIGNING_KEY)
    assert result is None


def test_session_cookie_rejects_none_value() -> None:
    result = read_session_cookie("", SIGNING_KEY)
    assert result is None


def test_create_and_list_active_session(test_db_session: DbSession) -> None:
    user = get_or_create_user(
        test_db_session,
        email="viewer@example.test",
        idp_subject="subject-1",
    )

    session_row = create_session(
        test_db_session,
        user_id=user.id,
        cf_jti="cf-jti-1",
        ua_fp="test-agent",
        ip="127.0.0.1",
    )

    active = list_active_sessions(test_db_session, user.id)

    assert len(active) == 1
    assert active[0].id == session_row.id
    assert active[0].cf_jti == "cf-jti-1"
    assert active[0].ua_fp == "test-agent"


def test_revoke_session_hides_it_from_active_sessions(test_db_session: DbSession) -> None:
    user = get_or_create_user(
        test_db_session,
        email="admin@example.test",
        idp_subject="subject-2",
    )
    session_row = create_session(test_db_session, user_id=user.id)

    revoked = revoke_session(test_db_session, session_row.id)

    assert revoked is True
    assert get_active_session(test_db_session, session_row.id) is None
    assert list_active_sessions(test_db_session, user.id) == []


def test_revoke_session_returns_false_for_unknown_session(test_db_session: DbSession) -> None:
    assert revoke_session(test_db_session, uuid.uuid4()) is False
