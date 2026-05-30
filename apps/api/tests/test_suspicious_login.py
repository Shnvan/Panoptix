"""Tests for suspicious login detection (pilot).

Covers all 5 detection signals, feature-off behaviour, duplicate
suppression, and baseline update logic.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.models.enums import AlertCategory, AlertSeverity
from cctv_api.models.tables import Alert, LoginBaseline, User
from cctv_api.security.suspicious_login import check_login_suspicion

_AUDIT_KEY = "test-audit-key-with-enough-entropy"


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "APP_ENV": "development",
        "ALLOW_DEV_AUTH": True,
        "AUDIT_HMAC_KEY_VERSION": 1,
        "AUDIT_HMAC_KEY": _AUDIT_KEY,
        "SUSPICIOUS_LOGIN_DETECTION_ENABLED": True,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _seed_user(db: DbSession, email: str = "suspect@example.test") -> User:
    user = User(id=uuid.uuid4(), email=email, idp_subject=email, created_at=datetime.now(timezone.utc))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── 1. First login: no alert, baseline created ──


def test_first_login_creates_baseline_no_alert(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    settings = _settings()

    alerts = check_login_suspicion(
        test_db_session,
        settings=settings,
        user_id=user.id,
        ip="1.2.3.4",
        country="PH",
        user_agent="Chrome/1",
        login_time=_now(),
    )

    assert alerts == []
    baseline = test_db_session.execute(
        select(LoginBaseline).where(LoginBaseline.user_id == user.id)
    ).scalar_one()
    assert baseline.login_count == 1
    assert "1.2.3.4" in baseline.known_ips
    assert "PH" in baseline.known_countries


# ── 2. Same IP second login: no alert ──


def test_same_ip_no_alert(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    settings = _settings()
    # Use a fixed hour that is guaranteed to be within normal hours (6-23)
    now = datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc)

    # First login
    check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="1.2.3.4", country="PH", user_agent="Chrome/1", login_time=now,
    )
    # Second login same IP, 1 hour later
    alerts = check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="1.2.3.4", country="PH", user_agent="Chrome/1",
        login_time=now + timedelta(hours=1),
    )

    assert alerts == []


# ── 3. New IP login: medium alert ──


def test_new_ip_creates_medium_alert(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    settings = _settings()
    now = _now()

    check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="1.2.3.4", country="PH", user_agent="Chrome/1", login_time=now,
    )
    alerts = check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="5.6.7.8", country="PH", user_agent="Chrome/1",
        login_time=now + timedelta(hours=2),
    )

    new_ip_alerts = [a for a in alerts if a.title == "Login from new IP address"]
    assert len(new_ip_alerts) == 1
    assert new_ip_alerts[0].severity == AlertSeverity.medium
    assert new_ip_alerts[0].category == AlertCategory.security


# ── 4. New country login: high alert ──


def test_new_country_creates_high_alert(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    settings = _settings()
    now = _now()

    check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="1.2.3.4", country="PH", user_agent="Chrome/1", login_time=now,
    )
    alerts = check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="1.2.3.4", country="US", user_agent="Chrome/1",
        login_time=now + timedelta(hours=12),
    )

    country_alerts = [a for a in alerts if a.title == "Login from new country"]
    assert len(country_alerts) == 1
    assert country_alerts[0].severity == AlertSeverity.high


# ── 5. Unusual hour login: low alert ──


def test_unusual_hour_creates_low_alert(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    settings = _settings()
    # Set normal hours to 8-22
    settings.SUSPICIOUS_LOGIN_USUAL_HOURS_START = 8
    settings.SUSPICIOUS_LOGIN_USUAL_HOURS_END = 22

    # First login at normal hour
    normal_time = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
    check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="1.2.3.4", country="PH", user_agent="Chrome/1", login_time=normal_time,
    )
    # Second login at 3 AM
    odd_time = datetime(2026, 5, 22, 3, 0, 0, tzinfo=timezone.utc)
    alerts = check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="1.2.3.4", country="PH", user_agent="Chrome/1", login_time=odd_time,
    )

    hour_alerts = [a for a in alerts if a.title == "Login at unusual hour"]
    assert len(hour_alerts) == 1
    assert hour_alerts[0].severity == AlertSeverity.low


# ── 6. Impossible travel: critical alert ──


def test_impossible_travel_creates_critical_alert(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    settings = _settings()
    now = _now()

    # Login from Philippines
    check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="1.2.3.4", country="PH", user_agent="Chrome/1", login_time=now,
    )
    # Login from UK 10 minutes later
    alerts = check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="5.6.7.8", country="GB", user_agent="Chrome/1",
        login_time=now + timedelta(minutes=10),
    )

    travel_alerts = [a for a in alerts if a.title == "Impossible travel detected"]
    assert len(travel_alerts) == 1
    assert travel_alerts[0].severity == AlertSeverity.critical


# ── 7. Rapid sessions: medium alert ──


def test_rapid_sessions_creates_medium_alert(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    settings = _settings(SUSPICIOUS_LOGIN_RAPID_SESSION_COUNT=3)
    now = _now()

    # First login (baseline)
    check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="1.2.3.4", country="PH", user_agent="Chrome/1", login_time=now,
    )

    # Create sessions manually to simulate rapid creation
    from cctv_api.models.tables import Session
    for i in range(3):
        test_db_session.add(Session(
            id=uuid.uuid4(), user_id=user.id,
            created_at=now + timedelta(seconds=i * 10),
        ))
    test_db_session.commit()

    # Now check — should detect rapid sessions
    alerts = check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="1.2.3.4", country="PH", user_agent="Chrome/1",
        login_time=now + timedelta(seconds=60),
    )

    rapid_alerts = [a for a in alerts if a.title == "Rapid session creation"]
    assert len(rapid_alerts) == 1


# ── 8. Feature disabled: no alerts, no baseline ──


def test_feature_disabled_no_alerts(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    settings = _settings(SUSPICIOUS_LOGIN_DETECTION_ENABLED=False)

    alerts = check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="1.2.3.4", country="PH", user_agent="Chrome/1", login_time=_now(),
    )

    assert alerts == []
    baseline = test_db_session.execute(
        select(LoginBaseline).where(LoginBaseline.user_id == user.id)
    ).scalar_one_or_none()
    assert baseline is None


# ── 9. Duplicate alert suppression ──


def test_duplicate_alert_suppression(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    settings = _settings()
    now = _now()

    # First login
    check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="1.2.3.4", country="PH", user_agent="Chrome/1", login_time=now,
    )
    # Second login with new IP
    check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="5.6.7.8", country="PH", user_agent="Chrome/1",
        login_time=now + timedelta(hours=2),
    )
    # Third login with yet another new IP — should not create duplicate new_ip alert
    check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="9.10.11.12", country="PH", user_agent="Chrome/1",
        login_time=now + timedelta(hours=4),
    )

    all_new_ip = test_db_session.execute(
        select(Alert).where(Alert.resource == f"user:{user.id}:new_ip")
    ).scalars().all()
    # Duplicate suppression via resource match in create_alert
    assert len(all_new_ip) == 1


# ── 10. Baseline IP cap eviction ──


def test_baseline_ip_cap_eviction(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    settings = _settings(SUSPICIOUS_LOGIN_MAX_KNOWN_IPS=10)
    now = _now()

    # First login
    check_login_suspicion(
        test_db_session, settings=settings, user_id=user.id,
        ip="0.0.0.1", country="PH", user_agent="Chrome/1", login_time=now,
    )

    # Add 15 different IPs over time
    for i in range(2, 17):
        check_login_suspicion(
            test_db_session, settings=settings, user_id=user.id,
            ip=f"10.0.0.{i}", country="PH", user_agent="Chrome/1",
            login_time=now + timedelta(hours=i),
        )

    baseline = test_db_session.execute(
        select(LoginBaseline).where(LoginBaseline.user_id == user.id)
    ).scalar_one()
    assert len(baseline.known_ips) <= 10
    # Oldest IPs should have been evicted
    assert "0.0.0.1" not in baseline.known_ips
