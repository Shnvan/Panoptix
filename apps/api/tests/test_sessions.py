from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session as DbSession

from cctv_api.security.csrf import CsrfTokenError, create_csrf_token, verify_csrf_token
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


def test_csrf_token_roundtrip() -> None:
    session_id = uuid.uuid4()
    token = create_csrf_token(session_id, SIGNING_KEY)
    verify_csrf_token(token, session_id=session_id, signing_key=SIGNING_KEY)


def test_csrf_token_rejects_wrong_session() -> None:
    token = create_csrf_token(uuid.uuid4(), SIGNING_KEY)
    with pytest.raises(CsrfTokenError) as exc_info:
        verify_csrf_token(token, session_id=uuid.uuid4(), signing_key=SIGNING_KEY)
    assert exc_info.value.detail == "csrf-token-invalid"


def test_csrf_token_rejects_tampered_signature() -> None:
    session_id = uuid.uuid4()
    token = create_csrf_token(session_id, SIGNING_KEY)
    with pytest.raises(CsrfTokenError) as exc_info:
        verify_csrf_token(token[:-4] + "XXXX", session_id=session_id, signing_key=SIGNING_KEY)
    assert exc_info.value.detail == "csrf-token-invalid"


def test_csrf_token_rejects_placeholder_key() -> None:
    with pytest.raises(CsrfTokenError) as exc_info:
        create_csrf_token(uuid.uuid4(), "replace-me")
    assert exc_info.value.detail == "csrf-signing-key-invalid"


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


# ── Session TTL enforcement (§16.4) ──


def test_session_not_expired_when_within_limits(test_db_session: DbSession) -> None:
    from datetime import datetime, timezone

    from cctv_api.security.sessions import is_session_expired

    user = get_or_create_user(test_db_session, email="ttl@example.test", idp_subject="ttl-1")
    session_row = create_session(test_db_session, user_id=user.id)

    now = datetime.now(timezone.utc)

    result = is_session_expired(
        session_row,
        idle_timeout_seconds=900,
        absolute_timeout_seconds=28800,
        now=now,
    )

    assert result is None


def test_session_expired_by_idle_timeout(test_db_session: DbSession) -> None:
    from datetime import datetime, timedelta, timezone

    from cctv_api.security.sessions import is_session_expired

    user = get_or_create_user(test_db_session, email="idle@example.test", idp_subject="idle-1")
    session_row = create_session(test_db_session, user_id=user.id)

    # Simulate 20 minutes of inactivity (idle limit = 15 min)
    now = datetime.now(timezone.utc) + timedelta(minutes=20)

    result = is_session_expired(
        session_row,
        idle_timeout_seconds=900,
        absolute_timeout_seconds=28800,
        now=now,
    )

    assert result == "session-idle-expired"


def test_session_expired_by_absolute_timeout(test_db_session: DbSession) -> None:
    from datetime import datetime, timedelta, timezone

    from cctv_api.security.sessions import is_session_expired, touch_session

    user = get_or_create_user(test_db_session, email="abs@example.test", idp_subject="abs-1")
    session_row = create_session(test_db_session, user_id=user.id)

    # Touch the session so idle is fresh, but absolute is exceeded (9 hours)
    touch_session(test_db_session, session_row.id)
    test_db_session.refresh(session_row)

    now = datetime.now(timezone.utc) + timedelta(hours=9)

    result = is_session_expired(
        session_row,
        idle_timeout_seconds=900,
        absolute_timeout_seconds=28800,
        now=now,
    )

    assert result == "session-absolute-expired"


def test_session_idle_timer_resets_with_last_seen(test_db_session: DbSession) -> None:
    from datetime import datetime, timedelta, timezone

    from cctv_api.security.sessions import is_session_expired, touch_session

    user = get_or_create_user(test_db_session, email="touch@example.test", idp_subject="touch-1")
    session_row = create_session(test_db_session, user_id=user.id)

    # Touch session to update last_seen_at
    touch_session(test_db_session, session_row.id)
    test_db_session.refresh(session_row)

    # Check 5 minutes after touch — should still be valid
    now = datetime.now(timezone.utc) + timedelta(minutes=5)

    result = is_session_expired(
        session_row,
        idle_timeout_seconds=900,
        absolute_timeout_seconds=28800,
        now=now,
    )

    assert result is None


def test_absolute_timeout_takes_precedence_over_fresh_idle(test_db_session: DbSession) -> None:
    from datetime import datetime, timedelta, timezone

    from cctv_api.security.sessions import is_session_expired

    user = get_or_create_user(test_db_session, email="precedence@example.test", idp_subject="prec-1")
    session_row = create_session(test_db_session, user_id=user.id)

    # Manually set last_seen_at to "just now" but created_at is 9 hours ago
    just_now = datetime.now(timezone.utc) + timedelta(hours=9)
    session_row.last_seen_at = just_now

    result = is_session_expired(
        session_row,
        idle_timeout_seconds=900,
        absolute_timeout_seconds=28800,
        now=just_now,
    )

    # Absolute wins even though idle timer is fresh
    assert result == "session-absolute-expired"
