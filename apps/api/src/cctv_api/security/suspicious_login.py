"""Suspicious login detection — pilot.

Analyses each new session creation against a per-user login baseline
and raises alerts via the existing alert system when anomalies are
detected.

Signals:
- new_ip          — IP address never seen before for this user
- new_country     — Country code (CF-IPCountry) never seen before
- unusual_hour    — Login outside the user's normal hours
- impossible_travel — Login from a different country within a short window
- rapid_sessions  — Many sessions created in quick succession
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.models.enums import ActorType, AlertCategory, AlertSeverity
from cctv_api.models.tables import Alert, LoginBaseline, Session
from cctv_api.security.alerts import create_alert


def check_login_suspicion(
    db: DbSession,
    *,
    settings: Settings,
    user_id: uuid.UUID,
    ip: str | None,
    country: str | None,
    user_agent: str | None,
    login_time: datetime,
) -> list[Alert]:
    """Run all heuristic checks and return any alerts created."""
    if not settings.SUSPICIOUS_LOGIN_DETECTION_ENABLED:
        return []

    baseline = _get_or_create_baseline(db, user_id)
    alerts: list[Alert] = []

    # Skip all signal checks on the very first login — just record the baseline
    if baseline.login_count == 0:
        _update_baseline(baseline, ip, country, user_agent, login_time, settings)
        db.flush()
        return alerts

    signal = _check_impossible_travel(baseline, country, login_time, settings)
    if signal is not None:
        alerts.append(
            create_alert(
                db,
                settings=settings,
                severity=AlertSeverity.critical,
                category=AlertCategory.security,
                title="Impossible travel detected",
                message=signal,
                source="suspicious_login",
                resource=f"user:{user_id}:impossible_travel",
                actor_type=ActorType.user,
                actor_id=user_id,
                metadata={"signal": "impossible_travel", "ip": ip, "country": country},
            )
        )

    signal = _check_new_country(baseline, country)
    if signal is not None:
        alerts.append(
            create_alert(
                db,
                settings=settings,
                severity=AlertSeverity.high,
                category=AlertCategory.security,
                title="Login from new country",
                message=signal,
                source="suspicious_login",
                resource=f"user:{user_id}:new_country",
                actor_type=ActorType.user,
                actor_id=user_id,
                metadata={"signal": "new_country", "ip": ip, "country": country},
            )
        )

    signal = _check_new_ip(baseline, ip)
    if signal is not None:
        alerts.append(
            create_alert(
                db,
                settings=settings,
                severity=AlertSeverity.medium,
                category=AlertCategory.security,
                title="Login from new IP address",
                message=signal,
                source="suspicious_login",
                resource=f"user:{user_id}:new_ip",
                actor_type=ActorType.user,
                actor_id=user_id,
                metadata={"signal": "new_ip", "ip": ip},
            )
        )

    signal = _check_rapid_sessions(db, user_id, login_time, settings)
    if signal is not None:
        alerts.append(
            create_alert(
                db,
                settings=settings,
                severity=AlertSeverity.medium,
                category=AlertCategory.security,
                title="Rapid session creation",
                message=signal,
                source="suspicious_login",
                resource=f"user:{user_id}:rapid_sessions",
                actor_type=ActorType.user,
                actor_id=user_id,
                metadata={"signal": "rapid_sessions", "ip": ip},
            )
        )

    signal = _check_unusual_hour(baseline, settings, login_time)
    if signal is not None:
        alerts.append(
            create_alert(
                db,
                settings=settings,
                severity=AlertSeverity.low,
                category=AlertCategory.security,
                title="Login at unusual hour",
                message=signal,
                source="suspicious_login",
                resource=f"user:{user_id}:unusual_hour",
                actor_type=ActorType.user,
                actor_id=user_id,
                metadata={"signal": "unusual_hour", "hour": login_time.hour},
            )
        )

    _update_baseline(baseline, ip, country, user_agent, login_time, settings)
    db.flush()
    return alerts


# ── Internal helpers ──


def _get_or_create_baseline(db: DbSession, user_id: uuid.UUID) -> LoginBaseline:
    baseline = db.execute(
        select(LoginBaseline).where(LoginBaseline.user_id == user_id)
    ).scalar_one_or_none()
    if baseline is not None:
        return baseline

    baseline = LoginBaseline(user_id=user_id)
    db.add(baseline)
    db.flush()
    return baseline


def _check_new_ip(baseline: LoginBaseline, ip: str | None) -> str | None:
    if ip is None:
        return None
    known: list[str] = list(baseline.known_ips) if baseline.known_ips else []
    if ip in known:
        return None
    return f"Login from IP {ip} which has not been seen before for this user."


def _check_new_country(baseline: LoginBaseline, country: str | None) -> str | None:
    if country is None:
        return None
    known: list[str] = list(baseline.known_countries) if baseline.known_countries else []
    if country in known:
        return None
    known_str = ", ".join(known) if known else "none"
    return f"Login from country {country}. Previously seen countries: {known_str}."


def _check_unusual_hour(
    baseline: LoginBaseline,
    settings: Settings,
    login_time: datetime,
) -> str | None:
    start = settings.SUSPICIOUS_LOGIN_USUAL_HOURS_START
    end = settings.SUSPICIOUS_LOGIN_USUAL_HOURS_END
    hour = login_time.hour

    if start <= end:
        # Normal range, e.g. 6–23
        if start <= hour <= end:
            return None
    else:
        # Wrapping range, e.g. 22–6 (night shift)
        if hour >= start or hour <= end:
            return None

    return f"Login at {hour:02d}:00 UTC which is outside normal hours ({start:02d}:00–{end:02d}:00)."


def _check_impossible_travel(
    baseline: LoginBaseline,
    country: str | None,
    login_time: datetime,
    settings: Settings,
) -> str | None:
    if country is None or baseline.last_login_country is None:
        return None
    if country == baseline.last_login_country:
        return None
    if baseline.last_login_at is None:
        return None

    last_login = baseline.last_login_at
    if last_login.tzinfo is None:
        last_login = last_login.replace(tzinfo=timezone.utc)

    window = timedelta(minutes=settings.SUSPICIOUS_LOGIN_IMPOSSIBLE_TRAVEL_MINUTES)
    elapsed = login_time - last_login

    if elapsed > window:
        return None

    minutes = int(elapsed.total_seconds() / 60)
    return (
        f"Login from {country} only {minutes} minutes after a login from "
        f"{baseline.last_login_country}. This may indicate credential compromise."
    )


def _check_rapid_sessions(
    db: DbSession,
    user_id: uuid.UUID,
    login_time: datetime,
    settings: Settings,
) -> str | None:
    window_start = login_time - timedelta(
        seconds=settings.SUSPICIOUS_LOGIN_RAPID_SESSION_WINDOW_SECONDS
    )
    count = db.execute(
        select(func.count())
        .select_from(Session)
        .where(
            Session.user_id == user_id,
            Session.created_at >= window_start,
        )
    ).scalar_one()

    threshold = settings.SUSPICIOUS_LOGIN_RAPID_SESSION_COUNT
    if count < threshold:
        return None

    window_min = settings.SUSPICIOUS_LOGIN_RAPID_SESSION_WINDOW_SECONDS // 60
    return (
        f"{count} sessions created in the last {window_min} minutes "
        f"(threshold: {threshold}). This may indicate automated credential stuffing."
    )


def _update_baseline(
    baseline: LoginBaseline,
    ip: str | None,
    country: str | None,
    user_agent: str | None,
    login_time: datetime,
    settings: Settings,
) -> None:
    max_ips = settings.SUSPICIOUS_LOGIN_MAX_KNOWN_IPS

    if ip is not None:
        known_ips: list[str] = list(baseline.known_ips) if baseline.known_ips else []
        if ip not in known_ips:
            known_ips.append(ip)
            # Evict oldest entries when cap is reached
            if len(known_ips) > max_ips:
                known_ips = known_ips[-max_ips:]
            baseline.known_ips = known_ips  # type: ignore[assignment]

    if country is not None:
        known_countries: list[str] = list(baseline.known_countries) if baseline.known_countries else []
        if country not in known_countries:
            known_countries.append(country)
            baseline.known_countries = known_countries  # type: ignore[assignment]

    if user_agent is not None:
        known_uas: list[str] = list(baseline.known_user_agents) if baseline.known_user_agents else []
        ua_short = user_agent[:255]
        if ua_short not in known_uas:
            known_uas.append(ua_short)
            # Cap at 50 user agents
            if len(known_uas) > 50:
                known_uas = known_uas[-50:]
            baseline.known_user_agents = known_uas  # type: ignore[assignment]

    baseline.last_login_ip = ip
    baseline.last_login_at = login_time
    baseline.last_login_country = country
    baseline.login_count = (baseline.login_count or 0) + 1
    baseline.updated_at = login_time
