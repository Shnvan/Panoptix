from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.models.enums import (
    ActorType,
    AlertSeverity,
    AlertStatus,
    EventCategory,
    EventOutcome,
    EventSeverity,
)
from cctv_api.models.tables import (
    Alert,
    AuditLog,
    Camera,
    CameraAcl,
    EdgeGateway,
    GatewayCameraAssignment,
    LoginBaseline,
    Role,
    Session,
    StreamGrant,
    User,
    UserRole,
)
from cctv_api.security.alerts import alert_to_response
from cctv_api.security.ip_intelligence import (
    IpIntelligenceProviderState,
    IpIntelligenceResult,
    get_ip_intelligence_provider,
    ip_intelligence_payload,
)
from cctv_api.security.device_intelligence import device_detail_payload

MAX_DISTINCT_IPS = 50
MAX_DISTINCT_USER_AGENTS = 20
MAX_RECENT_ALERTS = 10
MAX_RECENT_ENRICHED_SESSIONS = 10
MAX_RECENT_STREAM_GRANTS = 10


def build_user_actor_profile(
    db: DbSession,
    user_id: uuid.UUID,
    settings: Settings,
) -> dict[str, object] | None:
    user = db.execute(select(User).where(User.id == str(user_id))).scalar_one_or_none()
    if user is None:
        return None

    roles = _get_user_roles(db, user_id)
    sessions = _get_user_sessions(db, user_id)
    camera_access = _get_user_camera_access(db, user_id)
    stream_grants = _get_stream_grants(db, user_id=user_id)
    activity = _compute_activity_summary(db, ActorType.user, user_id)
    is_disabled = user.disabled_at is not None
    risk = _compute_risk_indicators(activity, is_disabled=is_disabled)
    containment = _build_user_containment_status(user, sessions)
    recent_sessions = _get_recent_user_sessions(db, user_id)

    return {
        "actor_type": ActorType.user.value,
        "actor_id": str(user.id),
        "identity": {
            "user_id": str(user.id),
            "email": user.email,
            "idp_subject": user.idp_subject,
            "role_default": user.role_default,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "disabled_at": user.disabled_at.isoformat() if user.disabled_at else None,
            "account_status": "disabled" if is_disabled else "active",
        },
        "roles": sorted(roles),
        "sessions": sessions,
        "camera_access": camera_access,
        "stream_grants": stream_grants,
        "activity_summary": activity,
        "risk_indicators": risk,
        "containment_status": containment,
        "alerts": _get_actor_alerts(db, ActorType.user, user_id),
        "behavior_baseline": _get_user_behavior_baseline(db, user_id),
        **_unsupported_stub_fields(),
        "ip_details": _get_user_ip_details(recent_sessions, settings),
        "device_details": _get_user_device_details(recent_sessions),
    }


def build_gateway_actor_profile(db: DbSession, gateway_id: uuid.UUID) -> dict[str, object] | None:
    gw = db.execute(select(EdgeGateway).where(EdgeGateway.id == str(gateway_id))).scalar_one_or_none()
    if gw is None:
        return None

    camera_access = _get_gateway_camera_assignments(db, gateway_id)
    stream_grants = _get_stream_grants(db, gateway_id=gateway_id)
    activity = _compute_activity_summary(db, ActorType.gateway, gateway_id)
    is_disabled = gw.disabled_at is not None
    risk = _compute_risk_indicators(activity, is_disabled=is_disabled)
    containment = _build_gateway_containment_status(gw)

    return {
        "actor_type": ActorType.gateway.value,
        "actor_id": str(gw.id),
        "identity": {
            "gateway_id": str(gw.id),
            "name": gw.name,
            "status": gw.status.value if gw.status else None,
            "created_at": gw.created_at.isoformat() if gw.created_at else None,
            "disabled_at": gw.disabled_at.isoformat() if gw.disabled_at else None,
            "last_seen_at": gw.last_seen_at.isoformat() if gw.last_seen_at else None,
            "mtls_fingerprint": gw.mtls_fingerprint,
            "cert_expires_at": gw.cert_expires_at.isoformat() if gw.cert_expires_at else None,
            "account_status": "disabled" if is_disabled else "active",
        },
        "roles": [],
        "sessions": None,
        "camera_access": camera_access,
        "stream_grants": stream_grants,
        "activity_summary": activity,
        "risk_indicators": risk,
        "containment_status": containment,
        "alerts": _get_actor_alerts(db, ActorType.gateway, gateway_id),
        "behavior_baseline": None,
        **_unsupported_stub_fields(),
    }


def build_system_actor_profile(
    db: DbSession, actor_type: ActorType, actor_id: uuid.UUID | None,
) -> dict[str, object]:
    activity = _compute_activity_summary(db, actor_type, actor_id)
    risk = _compute_risk_indicators(activity, is_disabled=False)

    return {
        "actor_type": actor_type.value,
        "actor_id": str(actor_id) if actor_id else None,
        "identity": None,
        "roles": [],
        "sessions": None,
        "camera_access": None,
        "stream_grants": None,
        "activity_summary": activity,
        "risk_indicators": risk,
        "containment_status": None,
        "alerts": _get_actor_alerts(db, actor_type, actor_id),
        "behavior_baseline": None,
        **_unsupported_stub_fields(),
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_user_roles(db: DbSession, user_id: uuid.UUID) -> list[str]:
    stmt = (
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == str(user_id))
    )
    return list(db.execute(stmt).scalars().all())


def _get_user_sessions(db: DbSession, user_id: uuid.UUID) -> dict[str, object]:
    rows: Sequence[Session] = list(
        db.execute(
            select(Session)
            .where(Session.user_id == str(user_id))
            .order_by(Session.created_at.desc())
        ).scalars().all()
    )
    active = [r for r in rows if r.revoked_at is None]
    revoked = [r for r in rows if r.revoked_at is not None]
    return {
        "active": [
            {
                "session_id": str(s.id),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "last_seen_at": s.last_seen_at.isoformat() if s.last_seen_at else None,
                "ip": s.ip,
                "ua_fp": s.ua_fp,
            }
            for s in active
        ],
        "active_count": len(active),
        "total_count": len(rows),
        "revoked_count": len(revoked),
    }


def _get_recent_user_sessions(db: DbSession, user_id: uuid.UUID) -> list[Session]:
    return list(
        db.execute(
            select(Session)
            .where(Session.user_id == str(user_id))
            .order_by(Session.created_at.desc(), Session.id.desc())
            .limit(MAX_RECENT_ENRICHED_SESSIONS)
        ).scalars().all()
    )


def _get_user_ip_details(sessions: list[Session], settings: Settings) -> dict[str, object]:
    provider_state = get_ip_intelligence_provider(settings)
    ips = [_session_ip(session) for session in sessions]
    distinct_ips = list(dict.fromkeys(ip for ip in ips if ip is not None))
    try:
        lookups, lookup_unavailable = _lookup_recent_ips(distinct_ips, provider_state)
    finally:
        _close_ip_provider(provider_state)
    enriched_results = [
        result for result in lookups.values() if result is not None and result.has_data
    ]
    status = (
        "unavailable"
        if lookup_unavailable and not enriched_results
        else provider_state.status
    )

    return {
        "available": provider_state.available and status == "ok",
        "status": status,
        "provider": provider_state.provider_name,
        "distinct_ip_count": len(distinct_ips),
        "enriched_ip_count": len(enriched_results),
        "recent_sessions": [
            {
                **_session_enrichment_context(session),
                "ip": ip,
                **ip_intelligence_payload(lookups.get(ip) if ip is not None else None),
            }
            for session, ip in zip(sessions, ips, strict=True)
        ],
    }


def _lookup_recent_ips(
    ips: list[str],
    provider_state: IpIntelligenceProviderState,
) -> tuple[dict[str, IpIntelligenceResult | None], bool]:
    if provider_state.provider is None:
        return {}, False

    results: dict[str, IpIntelligenceResult | None] = {}
    lookup_unavailable = False
    for ip in ips:
        try:
            results[ip] = provider_state.provider.lookup(ip)
        except Exception:
            results[ip] = None
            lookup_unavailable = True
    return results, lookup_unavailable


def _close_ip_provider(provider_state: IpIntelligenceProviderState) -> None:
    close = getattr(provider_state.provider, "close", None)
    if callable(close):
        close()


def _get_user_device_details(sessions: list[Session]) -> dict[str, object]:
    user_agents = [session.ua_fp for session in sessions if session.ua_fp]
    return {
        "available": bool(user_agents),
        "distinct_user_agent_count": len(set(user_agents)),
        "recent_sessions": [
            {
                **_session_enrichment_context(session),
                "ua_fp": session.ua_fp,
                **device_detail_payload(session.ua_fp),
            }
            for session in sessions
        ],
    }


def _session_enrichment_context(session: Session) -> dict[str, str | None]:
    return {
        "session_id": str(session.id),
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "last_seen_at": session.last_seen_at.isoformat() if session.last_seen_at else None,
        "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
    }


def _session_ip(session: Session) -> str | None:
    return str(session.ip) if session.ip is not None else None


def _get_user_camera_access(db: DbSession, user_id: uuid.UUID) -> dict[str, object]:
    stmt = (
        select(CameraAcl, Camera.display_name)
        .join(Camera, Camera.id == CameraAcl.camera_id)
        .where(CameraAcl.user_id == str(user_id))
    )
    rows = list(db.execute(stmt).all())
    active = [(acl, name) for acl, name in rows if acl.revoked_at is None]
    revoked_count = sum(1 for acl, _ in rows if acl.revoked_at is not None)
    return {
        "active_grants": [
            {
                "camera_id": str(acl.camera_id),
                "display_name": name,
                "granted_at": acl.granted_at.isoformat() if acl.granted_at else None,
                "granted_by": str(acl.granted_by) if acl.granted_by else None,
            }
            for acl, name in active
        ],
        "active_count": len(active),
        "revoked_count": revoked_count,
    }


def _get_gateway_camera_assignments(db: DbSession, gateway_id: uuid.UUID) -> dict[str, object]:
    stmt = (
        select(GatewayCameraAssignment, Camera.display_name)
        .join(Camera, Camera.id == GatewayCameraAssignment.camera_id)
        .where(GatewayCameraAssignment.gateway_id == str(gateway_id))
    )
    rows = list(db.execute(stmt).all())
    active = [(a, name) for a, name in rows if a.revoked_at is None]
    revoked_count = sum(1 for a, _ in rows if a.revoked_at is not None)
    return {
        "active_grants": [
            {
                "camera_id": str(a.camera_id),
                "display_name": name,
                "granted_at": a.granted_at.isoformat() if a.granted_at else None,
                "granted_by": str(a.granted_by) if a.granted_by else None,
            }
            for a, name in active
        ],
        "active_count": len(active),
        "revoked_count": revoked_count,
    }


def _get_stream_grants(
    db: DbSession,
    *,
    user_id: uuid.UUID | None = None,
    gateway_id: uuid.UUID | None = None,
) -> dict[str, object]:
    filters = []
    if user_id is not None:
        filters.append(StreamGrant.user_id == str(user_id))
    elif gateway_id is not None:
        filters.append(StreamGrant.gateway_id == str(gateway_id))
    else:
        return {"total_issued": 0, "denied_count": 0, "last_issued_at": None, "recent": []}

    count_row = db.execute(
        select(
            func.count().label("total"),
            func.sum(case((StreamGrant.denied_reason.isnot(None), 1), else_=0)).label("denied"),
            func.max(StreamGrant.issued_at).label("last_issued"),
        ).where(*filters)
    ).one()

    total = count_row.total or 0
    denied = int(count_row.denied or 0)
    last_issued = count_row.last_issued

    recent_rows: Sequence[StreamGrant] = list(
        db.execute(
            select(StreamGrant)
            .where(*filters)
            .order_by(StreamGrant.issued_at.desc())
            .limit(MAX_RECENT_STREAM_GRANTS)
        ).scalars().all()
    )
    return {
        "total_issued": total,
        "denied_count": denied,
        "last_issued_at": last_issued.isoformat() if last_issued else None,
        "recent": [
            {
                "id": str(g.id),
                "camera_id": str(g.camera_id),
                "kind": g.kind.value if hasattr(g.kind, "value") else g.kind,
                "issued_at": g.issued_at.isoformat() if g.issued_at else None,
                "expires_at": g.expires_at.isoformat() if g.expires_at else None,
                "denied_reason": g.denied_reason,
            }
            for g in recent_rows
        ],
    }


def _get_actor_alerts(
    db: DbSession,
    actor_type: ActorType,
    actor_id: uuid.UUID | None,
) -> dict[str, object]:
    actor_filter = Alert.actor_type == actor_type
    if actor_id is None:
        actor_filter = actor_filter & Alert.actor_id.is_(None)
    else:
        actor_filter = actor_filter & (Alert.actor_id == str(actor_id))

    status_cols = {
        status.value: func.sum(case((Alert.status == status, 1), else_=0))
        for status in AlertStatus
    }
    severity_cols = {
        severity.value: func.sum(case((Alert.severity == severity, 1), else_=0))
        for severity in AlertSeverity
    }
    aggregate = db.execute(
        select(
            func.count().label("total"),
            *[col.label(f"status_{key}") for key, col in status_cols.items()],
            *[col.label(f"severity_{key}") for key, col in severity_cols.items()],
        ).where(actor_filter)
    ).one()

    recent: Sequence[Alert] = list(
        db.execute(
            select(Alert)
            .where(actor_filter)
            .order_by(Alert.created_at.desc(), Alert.id.desc())
            .limit(MAX_RECENT_ALERTS)
        ).scalars().all()
    )
    return {
        "total_count": aggregate.total or 0,
        "counts_by_status": {
            key: int(getattr(aggregate, f"status_{key}") or 0) for key in status_cols
        },
        "counts_by_severity": {
            key: int(getattr(aggregate, f"severity_{key}") or 0) for key in severity_cols
        },
        "recent": [alert_to_response(alert) for alert in recent],
    }


def _get_user_behavior_baseline(db: DbSession, user_id: uuid.UUID) -> dict[str, object]:
    baseline = db.execute(
        select(LoginBaseline).where(LoginBaseline.user_id == str(user_id))
    ).scalar_one_or_none()
    if baseline is None:
        return {
            "available": False,
            "login_count": 0,
            "last_login_at": None,
            "last_login_country": None,
            "known_ip_count": 0,
            "known_country_count": 0,
            "known_user_agent_count": 0,
            "updated_at": None,
        }

    return {
        "available": True,
        "login_count": baseline.login_count or 0,
        "last_login_at": baseline.last_login_at.isoformat() if baseline.last_login_at else None,
        "last_login_country": baseline.last_login_country,
        "known_ip_count": len(baseline.known_ips) if baseline.known_ips else 0,
        "known_country_count": len(baseline.known_countries) if baseline.known_countries else 0,
        "known_user_agent_count": (
            len(baseline.known_user_agents) if baseline.known_user_agents else 0
        ),
        "updated_at": baseline.updated_at.isoformat() if baseline.updated_at else None,
    }


def _compute_activity_summary(
    db: DbSession, actor_type: ActorType, actor_id: uuid.UUID | None,
) -> dict[str, object]:
    base_filter = AuditLog.actor_type == actor_type
    if actor_id is not None:
        base_filter = base_filter & (AuditLog.actor_id == str(actor_id))
    else:
        base_filter = base_filter & AuditLog.actor_id.is_(None)

    severity_cols = {
        sev.value: func.sum(case((AuditLog.event_severity == sev, 1), else_=0))
        for sev in EventSeverity
    }
    outcome_cols = {
        out.value: func.sum(case((AuditLog.event_outcome == out, 1), else_=0))
        for out in EventOutcome
    }
    category_cols = {
        cat.value: func.sum(case((AuditLog.event_category == cat, 1), else_=0))
        for cat in EventCategory
    }

    agg = db.execute(
        select(
            func.count().label("total"),
            func.min(AuditLog.ts).label("first_ts"),
            func.max(AuditLog.ts).label("last_ts"),
            *[col.label(f"sev_{k}") for k, col in severity_cols.items()],
            *[col.label(f"out_{k}") for k, col in outcome_cols.items()],
            *[col.label(f"cat_{k}") for k, col in category_cols.items()],
        ).where(base_filter)
    ).one()

    total = agg.total or 0

    ip_rows = list(
        db.execute(
            select(AuditLog.ip)
            .where(base_filter, AuditLog.ip.isnot(None))
            .distinct()
            .limit(MAX_DISTINCT_IPS + 1)
        ).scalars().all()
    )
    ips_truncated = len(ip_rows) > MAX_DISTINCT_IPS
    distinct_ips = ip_rows[:MAX_DISTINCT_IPS]

    ua_rows = list(
        db.execute(
            select(AuditLog.ua)
            .where(base_filter, AuditLog.ua.isnot(None))
            .distinct()
            .limit(MAX_DISTINCT_USER_AGENTS + 1)
        ).scalars().all()
    )
    uas_truncated = len(ua_rows) > MAX_DISTINCT_USER_AGENTS
    distinct_uas = ua_rows[:MAX_DISTINCT_USER_AGENTS]

    action_rows = list(
        db.execute(
            select(AuditLog.action).where(base_filter).distinct()
        ).scalars().all()
    )

    return {
        "total_events": total,
        "first_event_at": agg.first_ts.isoformat() if agg.first_ts else None,
        "last_event_at": agg.last_ts.isoformat() if agg.last_ts else None,
        "events_by_severity": {k: int(getattr(agg, f"sev_{k}") or 0) for k in severity_cols},
        "events_by_outcome": {k: int(getattr(agg, f"out_{k}") or 0) for k in outcome_cols},
        "events_by_category": {k: int(getattr(agg, f"cat_{k}") or 0) for k in category_cols},
        "distinct_ips": distinct_ips,
        "distinct_ips_truncated": ips_truncated,
        "distinct_user_agents": distinct_uas,
        "distinct_user_agents_truncated": uas_truncated,
        "distinct_actions": sorted(action_rows),
    }


def _compute_risk_indicators(
    activity: dict[str, object], *, is_disabled: bool,
) -> dict[str, object]:
    by_sev: dict[str, int] = activity.get("events_by_severity", {})  # type: ignore[assignment]
    by_out: dict[str, int] = activity.get("events_by_outcome", {})  # type: ignore[assignment]
    distinct_ips: list[str] = activity.get("distinct_ips", [])  # type: ignore[assignment]

    high_count = by_sev.get("high", 0)
    critical_count = by_sev.get("critical", 0)
    denied_count = by_out.get("denied", 0)
    failed_count = by_out.get("failure", 0)

    return {
        "has_denied_events": denied_count > 0,
        "denied_event_count": denied_count,
        "has_high_severity_events": high_count > 0,
        "high_severity_event_count": high_count,
        "has_critical_severity_events": critical_count > 0,
        "critical_severity_event_count": critical_count,
        "has_failed_events": failed_count > 0,
        "failed_event_count": failed_count,
        "is_disabled": is_disabled,
        "multiple_ips_observed": len(distinct_ips) > 1,
        "distinct_ip_count": len(distinct_ips),
    }


def _build_user_containment_status(
    user: User, sessions: dict[str, object],
) -> dict[str, object]:
    is_disabled = user.disabled_at is not None
    active_count: int = sessions.get("active_count", 0)  # type: ignore[assignment]
    actions = [
        {
            "action": "disable_account",
            "endpoint": f"POST /api/v1/admin/users/{user.id}/disable",
            "available": not is_disabled,
            "reason": "already disabled" if is_disabled else None,
        },
        {
            "action": "revoke_all_sessions",
            "endpoint": "POST /api/v1/sessions/revoke",
            "available": active_count > 0,
            "reason": "no active sessions" if active_count == 0 else None,
        },
        {
            "action": "reset_mfa",
            "endpoint": f"POST /api/v1/admin/users/{user.id}/mfa/reset",
            "available": True,
            "reason": None,
        },
    ]
    return {
        "account_disabled": is_disabled,
        "active_session_count": active_count,
        "available_actions": actions,
    }


def _build_gateway_containment_status(gw: EdgeGateway) -> dict[str, object]:
    is_disabled = gw.disabled_at is not None
    actions = [
        {
            "action": "disable_gateway",
            "endpoint": f"POST /api/v1/admin/gateways/{gw.id}/disable",
            "available": not is_disabled,
            "reason": "already disabled" if is_disabled else None,
        },
        {
            "action": "rotate_credential",
            "endpoint": f"POST /api/v1/admin/gateways/{gw.id}/rotate-credential",
            "available": True,
            "reason": None,
        },
    ]
    return {
        "gateway_disabled": is_disabled,
        "available_actions": actions,
    }


def _unsupported_stub_fields() -> dict[str, None]:
    return {
        "ip_details": None,
        "device_details": None,
        "mfa_details": None,
        "threat_intelligence": None,
        "incidents": None,
        "analyst_notes": None,
    }
