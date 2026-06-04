from __future__ import annotations

import html as _html
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.integrations.email_alerts import AlertEmailConfigError, AlertEmailSendError, send_alert_email
from cctv_api.models.enums import (
    ActorType,
    AlertCategory,
    AlertNotificationStatus,
    AlertSeverity,
    AlertStatus,
)
from cctv_api.models.tables import (
    Alert,
    AlertNotification,
    AuditLog,
    GatewayCommandQueue,
    Role,
    User,
    UserRole,
    VisitorVisit,
)
from cctv_api.security.audit import AuditLogError, record_audit_event, scrub_audit_payload


SEVERITY_ORDER = {
    AlertSeverity.informational: 0,
    AlertSeverity.low: 1,
    AlertSeverity.medium: 2,
    AlertSeverity.high: 3,
    AlertSeverity.critical: 4,
}


def alert_to_response(alert: Alert) -> dict[str, object | None]:
    return {
        "alert_id": str(alert.id),
        "severity": _enum_value(alert.severity),
        "category": _enum_value(alert.category),
        "title": alert.title,
        "message": alert.message,
        "status": _enum_value(alert.status),
        "source": alert.source,
        "source_event_id": alert.source_event_id,
        "resource": alert.resource,
        "actor_type": _enum_value(alert.actor_type),
        "actor_id": str(alert.actor_id) if alert.actor_id is not None else None,
        "metadata": alert.metadata_json,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "acknowledged_by": (
            str(alert.acknowledged_by) if alert.acknowledged_by is not None else None
        ),
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "resolved_by": str(alert.resolved_by) if alert.resolved_by is not None else None,
    }


def create_alert(
    db: DbSession,
    *,
    settings: Settings,
    severity: AlertSeverity,
    category: AlertCategory,
    title: str,
    message: str,
    source: str,
    source_event_id: int | None = None,
    resource: str | None = None,
    actor_type: ActorType | None = None,
    actor_id: uuid.UUID | None = None,
    metadata: dict[str, object | None] | None = None,
    send_notifications: bool = True,
) -> Alert:
    existing = _find_existing_alert(
        db,
        source=source,
        source_event_id=source_event_id,
        resource=resource,
    )
    if existing is not None:
        return existing

    alert = Alert(
        severity=severity,
        category=category,
        title=title,
        message=message,
        source=source,
        source_event_id=source_event_id,
        resource=resource,
        actor_type=actor_type,
        actor_id=actor_id,
        metadata_json=scrub_audit_payload(metadata) if metadata is not None else None,
    )
    db.add(alert)
    db.flush()

    _record_system_audit_safely(
        db,
        settings=settings,
        action="system.alert.created",
        resource=f"alert:{alert.id}",
        payload={
            "alert_id": str(alert.id),
            "severity": severity.value,
            "category": category.value,
            "source": source,
            "source_event_id": source_event_id,
            "linked_resource": resource,
        },
    )
    if send_notifications:
        _send_email_notifications_if_needed(db, settings=settings, alert=alert)
    return alert


def detect_alert_from_audit_event(
    db: DbSession,
    *,
    settings: Settings,
    audit_log: AuditLog | None,
) -> Alert | None:
    if audit_log is None:
        return None

    payload = audit_log.payload or {}
    if audit_log.action == "system.break_glass.opened":
        return create_alert(
            db,
            settings=settings,
            severity=AlertSeverity.critical,
            category=AlertCategory.security,
            title="Break-glass access opened",
            message="Emergency break-glass access was opened. Review the reason and active window immediately.",
            source="audit_log",
            source_event_id=audit_log.id,
            resource=audit_log.resource,
            actor_type=audit_log.actor_type,
            actor_id=audit_log.actor_id,
            metadata={"action": audit_log.action, "reason": payload.get("reason")},
        )

    if audit_log.action == "audit.log.verified" and payload.get("valid") is False:
        return create_alert(
            db,
            settings=settings,
            severity=AlertSeverity.critical,
            category=AlertCategory.compliance,
            title="Audit chain verification failed",
            message="Audit verification reported an invalid chain. Treat this as possible tampering until reviewed.",
            source="audit_log",
            source_event_id=audit_log.id,
            resource=audit_log.resource,
            actor_type=audit_log.actor_type,
            actor_id=audit_log.actor_id,
            metadata={
                "action": audit_log.action,
                "checked": payload.get("checked"),
                "error": payload.get("error"),
            },
        )

    if audit_log.action == "admin.user.role.granted" and payload.get("role_name") == "admin":
        return create_alert(
            db,
            settings=settings,
            severity=AlertSeverity.high,
            category=AlertCategory.security,
            title="Admin role granted",
            message="A user was granted the admin role. Confirm the change was expected and approved.",
            source="audit_log",
            source_event_id=audit_log.id,
            resource=audit_log.resource,
            actor_type=audit_log.actor_type,
            actor_id=audit_log.actor_id,
            metadata={
                "action": audit_log.action,
                "target_user_id": payload.get("user_id"),
                "role_name": payload.get("role_name"),
            },
        )

    if audit_log.action == "gateway.disable":
        return create_alert(
            db,
            settings=settings,
            severity=AlertSeverity.high,
            category=AlertCategory.operations,
            title="Gateway disabled",
            message="A gateway was disabled. Confirm this was an expected operational action.",
            source="audit_log",
            source_event_id=audit_log.id,
            resource=audit_log.resource,
            actor_type=audit_log.actor_type,
            actor_id=audit_log.actor_id,
            metadata={
                "action": audit_log.action,
                "gateway_id": payload.get("gateway_id"),
                "reason": payload.get("reason"),
            },
        )

    audit_alerts: dict[str, tuple[AlertSeverity, AlertCategory, str, str]] = {
        "auth.csrf.denied": (
            AlertSeverity.high,
            AlertCategory.security,
            "CSRF protection failure",
            "A browser request failed CSRF validation. Review the source and session context.",
        ),
        "auth.login.denied.user_disabled": (
            AlertSeverity.high,
            AlertCategory.security,
            "Disabled user attempted login",
            "A disabled user attempted to access Panoptix.",
        ),
        "auth.gateway.denied.credential_invalid": (
            AlertSeverity.high,
            AlertCategory.security,
            "Invalid gateway credential used",
            "A gateway request used an invalid or unconfigured gateway credential.",
        ),
        "gateway.heartbeat.denied.signing_failed": (
            AlertSeverity.high,
            AlertCategory.operations,
            "Gateway heartbeat signing failed",
            "The backend could not sign pending gateway commands during heartbeat.",
        ),
        "gateway.control.denied.unauthenticated": (
            AlertSeverity.high,
            AlertCategory.security,
            "Unauthenticated gateway control attempt",
            "A gateway control WebSocket connection was rejected before authentication.",
        ),
        "gateway.control.denied.signing_failed": (
            AlertSeverity.high,
            AlertCategory.operations,
            "Gateway control signing failed",
            "The backend could not sign gateway control commands.",
        ),
        "gateway.ingest.denied.livekit_config": (
            AlertSeverity.high,
            AlertCategory.operations,
            "Gateway ingest failed due LiveKit config",
            "A gateway publish token could not be minted because LiveKit configuration failed closed.",
        ),
        "viewer.token.denied.livekit_config": (
            AlertSeverity.high,
            AlertCategory.operations,
            "Viewer token failed due LiveKit config",
            "A viewer token could not be minted because LiveKit configuration failed closed.",
        ),
        "system.alert.email.failed": (
            AlertSeverity.high,
            AlertCategory.availability,
            "Alert email delivery failed",
            "An alert email delivery attempt failed. Review SMTP/Resend configuration and provider logs.",
        ),
    }
    if audit_log.action in audit_alerts:
        severity, category, title, message = audit_alerts[audit_log.action]
        return create_alert(
            db,
            settings=settings,
            severity=severity,
            category=category,
            title=title,
            message=message,
            source="audit_log",
            source_event_id=audit_log.id,
            resource=audit_log.resource,
            actor_type=audit_log.actor_type,
            actor_id=audit_log.actor_id,
            metadata={
                "action": audit_log.action,
                "detail": payload.get("detail"),
                "reason": payload.get("reason"),
                "gateway_id": payload.get("gateway_id"),
                "camera_id": payload.get("camera_id"),
            },
        )

    return None


def create_visitor_entry_alert(
    db: DbSession,
    *,
    settings: Settings,
    visit: VisitorVisit,
    risk_context: dict[str, object],
) -> Alert:
    risk_flags = [
        key
        for key, value in risk_context.items()
        if key != "repeat_visitor_count" and value is True
    ]
    server_context = visit.server_context if isinstance(visit.server_context, dict) else {}
    return create_alert(
        db,
        settings=settings,
        severity=AlertSeverity.high,
        category=AlertCategory.security,
        title="Visitor continued to secure sign-in",
        message="A visitor continued from the public entry notice toward secure sign-in.",
        source="visitor_entry",
        resource=f"visitor_visit:{visit.id}",
        actor_type=ActorType.system,
        actor_id=None,
        metadata={
            "visit_id": str(visit.id),
            "page_path": visit.page_path,
            "cf_country": server_context.get("cf_country"),
            "risk_flags": risk_flags,
            "repeat_visitor_count": risk_context.get("repeat_visitor_count"),
            "ip_enrichment_status": visit.ip_enrichment_status,
        },
    )


def detect_alert_from_gateway_command_rejection(
    db: DbSession,
    *,
    settings: Settings,
    command: GatewayCommandQueue,
) -> Alert:
    return create_alert(
        db,
        settings=settings,
        severity=AlertSeverity.medium,
        category=AlertCategory.operations,
        title="Gateway command rejected",
        message="A gateway rejected a backend command. Review the command status and gateway logs.",
        source="gateway_command",
        resource=f"command:{command.id}",
        actor_type=ActorType.gateway,
        actor_id=command.gateway_id,
        metadata={
            "command_id": str(command.id),
            "gateway_id": str(command.gateway_id),
            "kind": command.kind,
            "error": command.error,
        },
    )


def detect_alert_from_backup_status(
    db: DbSession,
    *,
    settings: Settings,
    status: str,
    checks: dict[str, object | None],
) -> Alert | None:
    if status == "ok":
        return None
    return create_alert(
        db,
        settings=settings,
        severity=AlertSeverity.medium,
        category=AlertCategory.availability,
        title="Backup status requires attention",
        message="Backup readiness is not ok. Review backup runs and restore-drill evidence.",
        source="backup_status",
        source_event_id=0,
        resource="backup-status",
        actor_type=ActorType.system,
        actor_id=None,
        metadata={"status": status, "checks": checks},
    )


def acknowledge_alert(
    db: DbSession,
    *,
    settings: Settings,
    alert: Alert,
    actor_id: uuid.UUID,
) -> Alert:
    if _alert_status(alert.status) == AlertStatus.resolved:
        return alert
    now = datetime.now(timezone.utc)
    alert.status = AlertStatus.acknowledged
    alert.acknowledged_at = now
    alert.acknowledged_by = actor_id
    db.flush()
    _record_user_alert_audit_safely(
        db,
        settings=settings,
        actor_id=actor_id,
        action="admin.alert.acknowledged",
        resource=f"alert:{alert.id}",
        payload={"alert_id": str(alert.id), "previous_status": "open"},
    )
    return alert


def resolve_alert(
    db: DbSession,
    *,
    settings: Settings,
    alert: Alert,
    actor_id: uuid.UUID,
) -> Alert:
    now = datetime.now(timezone.utc)
    previous_status = _enum_value(alert.status)
    alert.status = AlertStatus.resolved
    alert.resolved_at = now
    alert.resolved_by = actor_id
    if alert.acknowledged_at is None:
        alert.acknowledged_at = now
        alert.acknowledged_by = actor_id
    db.flush()
    _record_user_alert_audit_safely(
        db,
        settings=settings,
        actor_id=actor_id,
        action="admin.alert.resolved",
        resource=f"alert:{alert.id}",
        payload={"alert_id": str(alert.id), "previous_status": previous_status},
    )
    return alert


def _find_existing_alert(
    db: DbSession,
    *,
    source: str,
    source_event_id: int | None,
    resource: str | None,
) -> Alert | None:
    query = select(Alert).where(Alert.source == source)
    if source_event_id is not None:
        query = query.where(Alert.source_event_id == source_event_id)
    elif resource is not None:
        query = query.where(Alert.resource == resource)
    else:
        return None
    return db.execute(query.order_by(Alert.created_at.desc()).limit(1)).scalar_one_or_none()


def _send_email_notifications_if_needed(
    db: DbSession,
    *,
    settings: Settings,
    alert: Alert,
) -> None:
    if not settings.ALERT_EMAIL_ENABLED:
        return
    severity = _alert_severity(alert.severity)
    if SEVERITY_ORDER[severity] < SEVERITY_ORDER[_alert_min_severity(settings)]:
        return

    recipients = _email_recipients_for_alert(db, settings)
    if not recipients:
        return

    for recipient in recipients:
        notification = AlertNotification(
            alert_id=alert.id,
            recipient=recipient,
            status=AlertNotificationStatus.pending,
        )
        db.add(notification)
        db.flush()
        try:
            send_alert_email(
                settings,
                recipient=recipient,
                subject=f"[Panoptix {severity.value.upper()}] {alert.title}",
                body=_email_body(alert),
                html_body=_email_html_body(alert),
            )
        except (AlertEmailConfigError, AlertEmailSendError) as exc:
            notification.status = AlertNotificationStatus.failed
            notification.error = str(exc)
            _record_system_audit_safely(
                db,
                settings=settings,
                action="system.alert.email.failed",
                resource=f"alert:{alert.id}",
                payload={
                    "alert_id": str(alert.id),
                    "notification_id": str(notification.id),
                    "recipient": recipient,
                    "error": str(exc),
                },
            )
            _create_email_delivery_failed_alert(
                db,
                settings=settings,
                alert=alert,
                notification=notification,
            )
            continue
        notification.status = AlertNotificationStatus.sent
        notification.sent_at = datetime.now(timezone.utc)
        _record_system_audit_safely(
            db,
            settings=settings,
            action="system.alert.email.sent",
            resource=f"alert:{alert.id}",
            payload={
                "alert_id": str(alert.id),
                "notification_id": str(notification.id),
                "recipient": recipient,
            },
        )


def _create_email_delivery_failed_alert(
    db: DbSession,
    *,
    settings: Settings,
    alert: Alert,
    notification: AlertNotification,
) -> None:
    create_alert(
        db,
        settings=settings,
        severity=AlertSeverity.high,
        category=AlertCategory.availability,
        title="Alert email delivery failed",
        message="An alert email delivery attempt failed. Review SMTP/Resend configuration and provider logs.",
        source="alert_email",
        resource=f"alert_notification:{notification.id}",
        actor_type=ActorType.system,
        actor_id=None,
        metadata={
            "alert_id": str(alert.id),
            "notification_id": str(notification.id),
            "alert_title": alert.title,
            "alert_severity": _enum_value(alert.severity),
            "delivery_status": "failed",
        },
        send_notifications=False,
    )


def _email_recipients_for_alert(db: DbSession, settings: Settings) -> list[str]:
    mode = settings.ALERT_EMAIL_RECIPIENT_MODE
    recipients: list[str] = []
    if mode in {"static", "both"}:
        recipients.extend(_static_email_recipients(settings))
    if mode in {"admins", "both"}:
        recipients.extend(_admin_email_recipients(db))
    return _dedupe_email_recipients(recipients)


def _static_email_recipients(settings: Settings) -> list[str]:
    return [part.strip() for part in settings.ALERT_EMAIL_TO.split(",") if part.strip()]


def _admin_email_recipients(db: DbSession) -> list[str]:
    stmt = (
        select(User.email)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.name == "admin", User.disabled_at.is_(None))
        .order_by(User.email.asc())
    )
    return [email.strip() for email in db.execute(stmt).scalars().all() if email.strip()]


def _dedupe_email_recipients(recipients: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for recipient in recipients:
        normalized = recipient.strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _alert_min_severity(settings: Settings) -> AlertSeverity:
    try:
        return AlertSeverity(settings.ALERT_EMAIL_MIN_SEVERITY)
    except ValueError:
        return AlertSeverity.high


def _email_body(alert: Alert) -> str:
    return "\n".join(
        [
            f"Panoptix alert: {alert.title}",
            f"Severity: {_enum_value(alert.severity)}",
            f"Category: {_enum_value(alert.category)}",
            f"Status: {_enum_value(alert.status)}",
            f"Resource: {alert.resource or 'none'}",
            "",
            alert.message,
            "",
            "No secrets, tokens, camera credentials, or raw provider responses are included in this notification.",
        ]
    )


def _email_html_body(alert: Alert) -> str:
    """Return a branded HTML alert email with inline styles only.

    All user-controlled strings are passed through html.escape().  No external
    CSS, no remote resources.  The plain-text body remains the MIME fallback.
    """
    severity_val = _enum_value(alert.severity) or "unknown"
    category_val = _enum_value(alert.category) or "unknown"
    status_val = _enum_value(alert.status) or "unknown"

    _BADGE_COLORS: dict[str, str] = {
        "critical": "#dc2626",
        "high": "#f97316",
        "medium": "#d97706",
        "low": "#737373",
        "informational": "#525252",
    }
    badge_color = _BADGE_COLORS.get(severity_val, "#737373")

    t = _html.escape(alert.title or "")
    msg = _html.escape(alert.message or "")
    sev = _html.escape(severity_val.upper())
    cat = _html.escape(category_val)
    sts = _html.escape(status_val)
    res = _html.escape(alert.resource) if alert.resource else None
    if alert.created_at:
        created_at = alert.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created = created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    else:
        created = "\u2014"

    label_style = (
        "padding:8px 12px;color:#a3a3a3;font-size:13px;"
        "white-space:nowrap;border-bottom:1px solid #262626;"
    )
    value_style = (
        "padding:8px 12px;color:#fafafa;font-size:13px;"
        "border-bottom:1px solid #262626;"
    )

    info_rows: list[tuple[str, str]] = [
        ("Severity", sev),
        ("Category", cat),
        ("Status", sts),
    ]
    if res is not None:
        info_rows.append(("Resource", res))
    info_rows.append(("Time (UTC)", created))

    rows_html = "".join(
        f'<tr><td style="{label_style}">{label}</td>'
        f'<td style="{value_style}">{value}</td></tr>'
        for label, value in info_rows
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Panoptix Security Alert</title>
</head>
<body style="margin:0;padding:0;background-color:#000000;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#000000;">
<tr><td align="center" style="padding:32px 16px;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

<tr><td style="background-color:#0a0a0a;border:1px solid #262626;border-bottom:none;padding:20px 24px;border-radius:8px 8px 0 0;">
<span style="font-size:18px;font-weight:700;color:#fafafa;letter-spacing:-0.3px;">Panoptix</span>
<span style="font-size:13px;color:#a3a3a3;margin-left:8px;">Security Alert System</span>
</td></tr>

<tr><td style="background-color:{badge_color};padding:6px 24px;">
<span style="font-size:12px;font-weight:700;color:#ffffff;letter-spacing:0.5px;">{sev}&nbsp;ALERT</span>
</td></tr>

<tr><td style="background-color:#171717;border-left:1px solid #262626;border-right:1px solid #262626;padding:24px 24px 0 24px;">
<h1 style="margin:0 0 12px 0;font-size:16px;font-weight:600;color:#fafafa;line-height:1.4;">{t}</h1>
<p style="margin:0 0 20px 0;font-size:14px;color:#a3a3a3;line-height:1.6;">{msg}</p>
</td></tr>

<tr><td style="background-color:#171717;border-left:1px solid #262626;border-right:1px solid #262626;padding:0 24px 16px 24px;">
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid #262626;">
{rows_html}
</table>
</td></tr>

<tr><td style="background-color:#0a0a0a;border:1px solid #262626;border-top:none;padding:16px 24px;border-radius:0 0 8px 8px;">
<p style="margin:0;font-size:12px;color:#525252;line-height:1.5;">No secrets, tokens, camera credentials, or raw provider responses are included in this notification. This message was generated by the Panoptix backend security alert system.</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def _record_system_audit_safely(
    db: DbSession,
    *,
    settings: Settings,
    action: str,
    resource: str,
    payload: dict[str, object | None],
) -> None:
    try:
        record_audit_event(
            db,
            actor_type=ActorType.system,
            actor_id=None,
            action=action,
            resource=resource,
            payload=payload,
            audit_hmac_key_version=settings.AUDIT_HMAC_KEY_VERSION,
            audit_hmac_key=settings.AUDIT_HMAC_KEY,
        )
    except AuditLogError:
        return


def _record_user_alert_audit_safely(
    db: DbSession,
    *,
    settings: Settings,
    actor_id: uuid.UUID,
    action: str,
    resource: str,
    payload: dict[str, object | None],
) -> None:
    try:
        record_audit_event(
            db,
            actor_type=ActorType.user,
            actor_id=actor_id,
            action=action,
            resource=resource,
            payload=payload,
            audit_hmac_key_version=settings.AUDIT_HMAC_KEY_VERSION,
            audit_hmac_key=settings.AUDIT_HMAC_KEY,
        )
    except AuditLogError:
        return


def _enum_value(value: object) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _alert_severity(value: AlertSeverity | str) -> AlertSeverity:
    return value if isinstance(value, AlertSeverity) else AlertSeverity(str(value))


def _alert_status(value: AlertStatus | str) -> AlertStatus:
    return value if isinstance(value, AlertStatus) else AlertStatus(str(value))
