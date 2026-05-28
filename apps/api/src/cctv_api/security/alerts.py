from __future__ import annotations

import base64
import os
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
                body=_email_text_body(alert),
                text_body=_email_text_body(alert),
                html_body=_email_html_body(alert, settings),
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


# ---------------------------------------------------------------------------
# Recommended action lookup — keyed by alert title then category fallback
# ---------------------------------------------------------------------------

_RECOMMENDED_ACTIONS: dict[str, str] = {
    "Break-glass access opened": (
        "Review the emergency window in the Panoptix admin console and verify the declared reason. "
        "Close the window once the situation is resolved and rotate credentials per the runbook."
    ),
    "Audit chain verification failed": (
        "Treat as possible tampering. Do not modify audit records. "
        "Escalate immediately for forensic review."
    ),
    "Admin role granted": (
        "Confirm the role grant was expected and approved. "
        "If not, revoke the role immediately and open a security incident."
    ),
    "Gateway disabled": (
        "Confirm this was a planned maintenance action. "
        "If unexpected, investigate the actor and re-enable only after review."
    ),
    "CSRF protection failure": (
        "A request failed CSRF validation. "
        "Check recent sessions for the source IP and review access logs."
    ),
    "Disabled user attempted login": (
        "A disabled account tried to access Panoptix. "
        "Confirm the account should remain disabled and review recent authentication events."
    ),
    "Invalid gateway credential used": (
        "A gateway used an invalid or unconfigured token. "
        "Rotate gateway service tokens and review gateway deployment configuration."
    ),
    "Gateway heartbeat signing failed": (
        "The backend could not sign pending commands. "
        "Check the GATEWAY_COMMAND_SIGNING_KEY configuration and backend logs."
    ),
    "Unauthenticated gateway control attempt": (
        "A WebSocket connection was rejected before authentication. "
        "Review the gateway agent version and Cloudflare Access service-token headers."
    ),
    "Gateway control signing failed": (
        "Signing failed for a gateway control command. "
        "Check signing key configuration and gateway logs."
    ),
    "Gateway ingest failed due LiveKit config": (
        "LiveKit configuration failed closed. "
        "Verify LIVEKIT_CLOUD_URL, LIVEKIT_CLOUD_API_KEY, and LIVEKIT_CLOUD_API_SECRET in Railway."
    ),
    "Viewer token failed due LiveKit config": (
        "LiveKit configuration failed closed. "
        "Verify LIVEKIT_CLOUD_URL, LIVEKIT_CLOUD_API_KEY, and LIVEKIT_CLOUD_API_SECRET in Railway."
    ),
    "Alert email delivery failed": (
        "SMTP or Resend configuration may be incorrect. "
        "Check ALERT_EMAIL_SMTP_HOST, ALERT_EMAIL_FROM, and provider delivery logs."
    ),
    "Backup status requires attention": (
        "Backup readiness is not ok. "
        "Review backup runs in the admin console and check the last restore-drill evidence."
    ),
    "Gateway command rejected": (
        "A gateway rejected a backend command. "
        "Review the command queue and gateway operational logs."
    ),
    "Visitor continued to secure sign-in": (
        "A visitor continued from the public entry notice toward secure sign-in. "
        "Review the visitor record in the admin console — pay close attention to elevated risk flags."
    ),
}

_CATEGORY_ACTIONS: dict[str, str] = {
    "security": (
        "Review the alert details and recent audit logs. "
        "If the activity looks suspicious, consider opening a security incident."
    ),
    "operations": (
        "Review operational logs and the relevant gateway or service configuration."
    ),
    "compliance": (
        "Review compliance records. "
        "Consider escalating if data integrity may be affected."
    ),
    "availability": (
        "Review service health. "
        "Restore the affected configuration or contact your infrastructure provider."
    ),
}

_SEVERITY_COLOURS: dict[str, str] = {
    "critical": "#dc2626",
    "high": "#ea580c",
    "medium": "#d97706",
    "low": "#2563eb",
    "informational": "#4b5563",
}

# Panoptix logo — 48×48 px PNG encoded as Base64 (Option C: small inline embed,
# avoids external image requests which are blocked by many corporate email clients)
_LOGO_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAARrklEQVR42oWae5TdVXXHP/uc3+8+"
    "5s47k8dMCGHIgwgJAklNwChIUCpieFioLJZiFduldqmUWpe2hbhUatvFssvWqsASq+IjoiBYQLpo"
    "pCAkRJCHJJAHIeQ9eczrzr339zhn94/fvTN3boZ21rprfvfe8/ud/fju/d17nys0/amqsEFEvoTf"
    "oZof5NDlHNyyXk68tlLHjw5obazTpLEBRATUe1AFn4CLAc3eq89eNF17h6gDVdQ78Cm4tL4OkLoM"
    "QTGl0D4mhc590jlrs+/qvz88+5ZH8Cm68Ror1/7MNcsszcKLiAJE6b4PBbsf+JzZ/dgKDr8EJw5"
    "BrYJ39c206U5tfpq0fEmm0OR3Lduq1i+nHiaAGAuFPHT2QKkfP3vwKd+79KvhH33lIQVBQSTbWZq"
    "FV9W29Nhv7g5evvtatt6LO1FRCfBqMBiDZHafLjQt9hD9fxRs0nFy3ZRCioCqgldSVTzG9hSFU1f"
    "g55zzDXPRdz7LBhE2oCJooKoCG0RV8+7wrx8InvryOrfltyltGGkLDXgr0wSRFglafdniBWnyQuNz"
    "aXmeyOSaunkFrBBm96RjVS8vPqP2jJFPp49cPyf8sr1Oz7raqv7Mi+pGK3KtSw5t+o9gy4YPu6ee"
    "j6UjzKFuSoDGhirTYdFq+ZO1mQ4VlVaXZMI3vKCZ8RtIVNVMoca6OI3N0sW5tHvF18Ir7vuCbrwm"
    "M25S2/v+4JmvPuAfviOhGISonxJ80ooytbe2YqNVdjnZQzrTOmbwSJONVJuCFFRExaXODL4lSHoH"
    "1+SufGiL2aQasONXG3h2o5IzBpqFb8KsNm0iwjQNm+GgrXA7+U8bz5AZnl9/ibaGhyLqxYsIJ/bC"
    "0N5bAcya8qsX2jeeOM8PjYC1dtLS2jCDTEFnhkQyLWClCePSotS0WK4v8G/uyckUI9ONYMRYP1ZV"
    "Wzm+Lvr+quUmOPK7K+Toy6iIn4ZtfTN8zJQq6/99S7aZNGddCWnC/OReMiN8pCF8hqUmPRRV9cZX"
    "clIdu9wwsnc1wwdBVDIS0ilBFfB6cgpEptZNQqE190+XShv3S8OjTcHbDPRmYRvPaX6egCAQx5g0"
    "Od9QPnoq1TJYpkeptPhzWm7Xlo0bxjRgZErIhmLTgrFVOZ2R0JCZQkinvk0dqjpoqI2WSJOMpFRP"
    "Jp5mDGqT1SYt0wzQVss141inw2ZGomslPDmZxX2dsL1HMF2GxBV96lss0gSdZitNulFPVtLIzHHR"
    "SAatKVh1htiaKf6kJT2T7eUVVV8MxBh7clppuRQzQzC3KjFDvDSva03LrY9qhpE2M73OzEMesGFo"
    "TkKavJklWsigFV5ep9tgJrKbRo4meykzGExmToPC9Nwc5KzBu+mLfEupoDN4RZsg0Ay3mVAhrc6t"
    "e7MWQxSfvHZakM/g5aZMGKXSFuCTGTJMI+toS55uyulvgqY3ry8UjIFqnK1feklmrdcfh8BMxYnI"
    "yZ6uF6eTH5lsjceYQBoNRSPDiDaRTVNQi5xMOtM8JU1ZqBnvvk5wAmMxLFoLF34BBpbB+BDcdRF4"
    "fzJMfNN738w/U8Y0xoqZ1LwBBWkJHmktif8Pi2tr+hWQALzix1P8u76I/un3gGE4+DTpcz/Cj0Tg"
    "kvo9JvMSZnrT0xKG2qiMRQjwvomoZMZSf3osyAx1vdQ3BryDNIU0s5ym4MRgrrkTs/htsOMXkFbh"
    "tHX4BQXMx98DW7+NPvufaL6uhwVCIAzqyjiaqwRpissAl5zMAW9WAk1rERuEZDIL1jKhNQQ6F8Cs"
    "JdC7GF8aQBasxPTNgV0PQ1iEsA3icfJ93WhYRP/4a3DG1Wg0jB/eix57FRn6A2bsIEaBQsOTblIG"
    "rVesgaZxppE2M2z90khLcDUCu+7mOIYaaCGHLrwAWfJuOOU86JyHBBZ8DesjmDgO+zZDobtR2MPw"
    "btSnYAtIWw/0z8MGgxCsBZNHkxQ/tIt02wOYbb/ARBEUwimY19NwMJ1omDkjNV+bAJIYKqB9p8IF"
    "18OySzEdvRAPQ/kgHNoNSSW7xwSoCcHm665vsGkIJpetKR+D8SOgLnuJIGEbQfsc9N0341d/lPS/"
    "b8dufwRTAI3q3GqEqSzkm9iwlR0nY8PAaIx29cPlN8GZlyJU4cROOP77SYERgwZtWd0vFlFF657V"
    "Fp5SQGyIkkPw2XjGOzSuQm0XHN+J7ToFc9VtpP1n4zbfTbB4OdSGUbEE6tLMMtPIqF7btCoznqKr"
    "boAjL8Ch59El64i7B0jKKbp4HdI2F1sQ3As/JVdsJz93kMBXxtHuAYQaZmQvI2MpLk0JA5tZ3IIt"
    "FLP5fqmP+MB22P88QUcGA1dxyNq/JFj9EcRVcMf3QRRjimGWaFwCquRLQu2Z76LL1iE2zALaO8RH"
    "iIK3IbLyQ3D0VTA5NKlhS73IdXeio8eR09+GPvXvyOPfQEeOooe2UVy0GqNJDZ/vQpJxNCoTRwnG"
    "TBX2GZkGqEsh10386wmsCGIDfCVFlq/HXnAjHHgGHdqOFLtJugZxIwlaTiDsApPDhII59jrJvheh"
    "1AfOQ1hAgyKaAN3zodSbESP1oe74EUzlMEFR4dBWdP5KXGAxCP6130LPEjUYi6+NotnHCK4+2tGm"
    "QZogxuLTFD2+kyCnqE/wYR6z+qMw9AeQrOYRVyG88l9IV38Ud96H4YZH0GVXQc0TGEH2Pwv5LtSn"
    "mFwJ3zYXn5Bxi3rUu+zlkiyW0gitlbOUmytBWMSECkMvQZpOGMm3wcghnDPQMZs2m9GvlSyDmQZD"
    "2wBNY6gOZ+k8djB3KVLqgWgCjM34qTqK8WVya64jWHM9+FFYvA5vBGMUGXk9w6UYJAiR+efiPBnT"
    "JtV6U+gRTevFXf2IShXSSpbKQ1EzMQQn9tQMuWLNJo507zZ08F10GSWfs5nMRrJA9g7EZpZJk6yz"
    "c6DFPtDMYlnrmCCiEE+gx3bA8V0wdghKs9BCe1bMReXsAMYESDxOeMYlJIFBR46jB16E9tloWqt3"
    "NVOlBm096JHtWd8hltCkmGSsZkwg47l2Q7z1Z5rMv4Rwdgf9pRRjDb4+aW80EiIm27hRFUfl+uFd"
    "CppkiHYurivCFKtpOnX+Z+ttlwnxtXFypyxHF1+CixT/1B2obUfa+9A0ygq8tIa090HQgdt6D5IT"
    "cE4JC0iQO2Y0sG/k2nOY8SGtPXUf7l1/T1teWVBKaS8GKIJzaUY8YQ7y7XgHJhT06A40qmQ1lEv"
    "rp5X1E0sXZ62jzcHIIaiV8Qjac3oGNe8yK0wMUbj4s6RdvfiDrxH9/K9xLoeZexbSezoybzk+6CG"
    "6/2/R42+gNsAlqnT0IYXSroAwt5lCsDLfbjV66SEm8p20XX474ZNfZ87B/bS1QU7jjA1tgHT0407s"
    "JuzIIyOjpK88RvjWy2D/7yAsZVBqRH9aQzoHSJ6+B+PAqWIG3464Gra9D2yIJjXCrnnIdXdQ+cGN"
    "sPP3JEc+ghm8AOnsh4mj+N1PYOMyphiQOvCRkOtbjM5e8kRA19z79MThT4VaNtIZEm39CRMn9lN4"
    "xxcwI9sJn/05ZmIIRRB1yJxlpLufJHCKFCzJk3di+s8mmH8OenRnPZMoEuYxC1YRv/Ik7pVHUa+k"
    "fedSWrSG5PA2Jl55muTITnxcQXLtdK29juJHvsfE/bfi976AvvBfUC9ibV4gH+KcRxG1Rk0ysKYa"
    "9qx8SDbppmDtdz+3Jdj3/Lmu4r1Xa+NyQhoUsGevJ1h0DkHffMTVMGGBqDxO5d7PUsp5QHCpx1Ek"
    "vPDThEvWZKW0CJo64hd/TfL0HdhASdKQ0o0/QW3AwTs+jhw/jA2yCjyOQWbNYuGn7kHCPLUXHyF6"
    "7j70+A7ETU0hJWuz0+4zFgXuT+64PxhYd1V2yPfo9euDvVt/6V/dkWBtqN7g0pRoQkkdlD75A4KS"
    "RcePId0LGHnwNsJ9W7GFeinhHa4KdPVhehai6vDH90B5FFuwJFVH4eqv0fbW9zLx8m84eNdnaOvJ"
    "0ZjoR9UIuudz6se+hcFBsQONI+ID20lfP5ZkaAd+/CjqIjWJd71X/lVgz//EKpHu56xuvMba9T99"
    "5e/+7O1LLcPn+BPlWEKxRiAs5CFO8dYQnHkxjB3AhDmkeyGVlx8jDKU+VDNIPkBrZfzwIfzoYYxE"
    "mFxIXE0pvP9WiisuxQ/vI5w9iEsmKO94Ca+ONHE408a8D9xKblZ/xjVRGdIaQfdsCgvPprjkAgpv"
    "uYjikjVJx/pPhb7/7bfZfP8PVdXaDRu3sQHM4Sv++eG24TfeYRk53Y9MpFhBxIsNBDmyF866LCOY"
    "wCijhnNNIvBDtfJGgEOK9ol7r5BRAkDV6cQxtV36ZthXvQccOZcWgTymdsZb8whXEI0OYfDuk/sV3"
    "KA4swldGm8ZvDuJqxhvRuDeu7ILTl4Wevp8E3cs+qbrRwlneiKBsQOfPX1+xF65/nz/13Hvt4lMD"
    "G2DUOY8Vb6IJ1U3fQnuXICg6foTONddgl19MdSTGi8Fj8AhewaWOKDWUPvAPtJ15EX7kwFQ35h0a"
    "l+k45z2Ulq4hnRgnGTnMxJ7n8XEV8KhL8C5VfOLUxRp0dhhz2jlBahd80/SsuF71VgPXeBHRGX7s"
    "IaQPXn4Dh/f8jR05ciaVMah5dCQhXfdpzKrLkaPbIchBsYfxJ++h+tyDmPpYUwzEFShddhMdq67A"
    "jx7KuKDeeEtYoLJvO2Mv/g/4CYoLllM7vJtc73w633I+NrRZKRFaKJZA2vDtfZt9ruu2sLTowey4"
    "TWn8MEVajjeFDYh8Cf+GbiwO/Pw762Xk6BW+Uj5PqlF/MjbSYS69RYLTVqITxxARpDSLyqtPkex8"
    "DJuMQFTG9y6h49IvQm0UteHkXLUxJ/IuwccxYdesyRYTn+KjCh5VwuK4yRVfp9i12Rc67w+C/key"
    "H6NstHCtl6YJzf8CNLUpy4vUiioAAAAASUVORK5CYII="
)


def _recommended_action(alert: Alert) -> str:
    """Return a plain-text recommended action string for this alert."""
    if alert.title in _RECOMMENDED_ACTIONS:
        return _RECOMMENDED_ACTIONS[alert.title]
    category = _enum_value(alert.category) or ""
    return _CATEGORY_ACTIONS.get(
        category,
        "Review the alert details in the Panoptix admin console and take appropriate action.",
    )


def _severity_colour(alert: Alert) -> str:
    severity = _enum_value(alert.severity) or "informational"
    return _SEVERITY_COLOURS.get(severity, "#4b5563")


def _email_text_body(alert: Alert) -> str:
    """Plain-text email body — human-readable fallback for all mail clients."""
    severity = (_enum_value(alert.severity) or "").upper()
    category = _enum_value(alert.category) or ""
    status = _enum_value(alert.status) or ""
    resource = alert.resource or "—"
    actor = (
        f"{_enum_value(alert.actor_type)} / {alert.actor_id}"
        if alert.actor_type is not None
        else "—"
    )
    created = alert.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if alert.created_at else "—"
    sep = "-" * 60

    lines = [
        "PANOPTIX SECURITY ALERT",
        sep,
        "",
        f"Title    : {alert.title}",
        f"Severity : {severity}",
        f"Category : {category}",
        f"Status   : {status}",
        f"Alert ID : {alert.id}",
        f"Source   : {alert.source or '—'}",
        f"Resource : {resource}",
        f"Actor    : {actor}",
        f"Created  : {created}",
        "",
        sep,
        "SUMMARY",
        sep,
        "",
        alert.message,
        "",
        sep,
        "RECOMMENDED ACTION",
        sep,
        "",
        _recommended_action(alert),
        "",
    ]

    metadata = alert.metadata_json
    if isinstance(metadata, dict) and metadata:
        lines += [sep, "DETAILS", sep, ""]
        for key, value in list(metadata.items())[:10]:
            safe_val = str(value)[:200] if value is not None else "—"
            lines.append(f"  {key}: {safe_val}")
        lines.append("")

    lines += [
        sep,
        "You received this alert because you are an active Panoptix administrator.",
        "Panoptix will never ask for passwords, tokens, or camera credentials by email.",
        "No secrets, raw provider payloads, or RTSP credentials are included in this message.",
        sep,
    ]
    return "\n".join(lines)


def _email_html_body(alert: Alert, settings: Settings) -> str:  # noqa: PLR0914
    """HTML email body — rendered by Gmail, Outlook, and modern mail clients."""
    import html as _html  # local alias to avoid shadowing the module-level import

    severity_label = (_enum_value(alert.severity) or "informational").upper()
    severity_colour = _severity_colour(alert)
    category = (_enum_value(alert.category) or "").title()
    status = (_enum_value(alert.status) or "").title()
    resource = _html.escape(alert.resource or "—")
    source = _html.escape(alert.source or "—")
    actor_type_val = _enum_value(alert.actor_type)
    actor_id_val = str(alert.actor_id) if alert.actor_id is not None else None
    actor_str = _html.escape(
        f"{actor_type_val} / {actor_id_val}" if actor_type_val else "—"
    )
    created = (
        alert.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if alert.created_at else "—"
    )
    alert_id = str(alert.id)
    title_esc = _html.escape(alert.title)
    message_esc = _html.escape(alert.message)
    action_esc = _html.escape(_recommended_action(alert))
    base_url = _html.escape(settings.APP_PUBLIC_BASE_URL.rstrip("/"))

    # Logo — try url config, file path, or default to public website logo
    logo_path = getattr(settings, "ALERT_EMAIL_LOGO_PATH", "")
    if logo_path:
        if logo_path.startswith(("http://", "https://")):
            logo_src = logo_path
        elif os.path.isfile(logo_path):
            try:
                with open(logo_path, "rb") as fh:
                    logo_b64 = base64.b64encode(fh.read()).decode()
                logo_src = f"data:image/png;base64,{logo_b64}"
            except OSError:
                logo_src = "https://panoptix.site/logo.png"
        else:
            logo_src = "https://panoptix.site/logo.png"
    else:
        # Default to the site's public logo.
        # Fall back to production URL if testing on localhost so Gmail can load it correctly.
        clean_base = settings.APP_PUBLIC_BASE_URL.rstrip("/")
        if "127.0.0.1" in clean_base or "localhost" in clean_base or "cctv.example.test" in clean_base:
            logo_src = "https://panoptix.site/logo.png"
        else:
            logo_src = f"{clean_base}/logo.png"

    # Safe metadata rows (capped at 10 keys, values truncated at 200 chars)
    metadata = alert.metadata_json
    metadata_rows = ""
    if isinstance(metadata, dict) and metadata:
        for key, value in list(metadata.items())[:10]:
            safe_key = _html.escape(str(key))
            safe_val = (
                _html.escape(str(value)[:200])
                if value is not None
                else "<em style='color:#9ca3af'>—</em>"
            )
            metadata_rows += (
                f"<tr>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #1e293b;"
                f"color:#94a3b8;font-size:12px;white-space:nowrap;'>{safe_key}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #1e293b;"
                f"color:#e2e8f0;font-size:12px;word-break:break-all;'>{safe_val}</td>"
                f"</tr>"
            )

    metadata_section = ""
    if metadata_rows:
        metadata_section = (
            "<tr><td style='padding:24px 40px 4px'>"
            "<p style='margin:0;font-size:12px;font-weight:600;letter-spacing:.08em;"
            "color:#64748b;text-transform:uppercase;'>Details</p>"
            "</td></tr>"
            "<tr><td style='padding:0 40px 24px'>"
            "<table width='100%' cellpadding='0' cellspacing='0' style='"
            "border-collapse:collapse;border:1px solid #1e293b;border-radius:6px;overflow:hidden;'>"
            f"{metadata_rows}"
            "</table></td></tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Panoptix Alert: {title_esc}</title>
</head>
<body style="margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;">
    <tr><td align="center" style="padding:32px 16px;">

      <!-- Email card -->
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#1e293b;border-radius:12px;overflow:hidden;border:1px solid #334155;">

        <!-- Header -->
        <tr>
          <td style="background:#0f172a;padding:24px 40px;border-bottom:1px solid #334155;">
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding-right:14px;vertical-align:middle;">
                  <img src="{logo_src}" alt="Panoptix" width="48" height="48" style="display:block;border-radius:10px;">
                </td>
                <td style="vertical-align:middle;">
                  <p style="margin:0;font-size:20px;font-weight:700;color:#f8fafc;letter-spacing:-.3px;">Panoptix</p>
                  <p style="margin:2px 0 0;font-size:12px;color:#64748b;letter-spacing:.04em;">Security Alert System</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Severity banner -->
        <tr>
          <td style="background:{severity_colour};padding:10px 40px;">
            <p style="margin:0;font-size:11px;font-weight:700;color:#fff;letter-spacing:.12em;text-transform:uppercase;">{severity_label} SEVERITY ALERT</p>
          </td>
        </tr>

        <!-- Title -->
        <tr>
          <td style="padding:32px 40px 8px;">
            <h1 style="margin:0;font-size:22px;font-weight:700;color:#f1f5f9;line-height:1.3;">{title_esc}</h1>
          </td>
        </tr>

        <!-- Meta badges -->
        <tr>
          <td style="padding:8px 40px 24px;">
            <table cellpadding="0" cellspacing="0"><tr>
              <td style="padding-right:8px;">
                <span style="display:inline-block;padding:3px 10px;background:#0f172a;border:1px solid #334155;border-radius:999px;font-size:11px;color:#94a3b8;">{category}</span>
              </td>
              <td>
                <span style="display:inline-block;padding:3px 10px;background:#0f172a;border:1px solid #334155;border-radius:999px;font-size:11px;color:#94a3b8;">{status}</span>
              </td>
            </tr></table>
          </td>
        </tr>

        <!-- Divider -->
        <tr><td style="padding:0 40px;"><hr style="border:none;border-top:1px solid #334155;margin:0;"></td></tr>

        <!-- Summary -->
        <tr><td style="padding:24px 40px 4px;">
          <p style="margin:0;font-size:12px;font-weight:600;letter-spacing:.08em;color:#64748b;text-transform:uppercase;">Summary</p>
        </td></tr>
        <tr><td style="padding:8px 40px 24px;">
          <p style="margin:0;font-size:15px;color:#cbd5e1;line-height:1.6;">{message_esc}</p>
        </td></tr>

        <!-- Recommended Action -->
        <tr><td style="padding:0 40px 4px;">
          <p style="margin:0;font-size:12px;font-weight:600;letter-spacing:.08em;color:#64748b;text-transform:uppercase;">Recommended Action</p>
        </td></tr>
        <tr><td style="padding:8px 40px 24px;">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>
            <td style="padding:16px 20px;background:#0f172a;border-left:3px solid {severity_colour};border-radius:6px;">
              <p style="margin:0;font-size:14px;color:#e2e8f0;line-height:1.6;">{action_esc}</p>
            </td>
          </tr></table>
        </td></tr>

        <!-- Divider -->
        <tr><td style="padding:0 40px;"><hr style="border:none;border-top:1px solid #334155;margin:0;"></td></tr>

        <!-- Alert Information table -->
        <tr><td style="padding:24px 40px 4px;">
          <p style="margin:0;font-size:12px;font-weight:600;letter-spacing:.08em;color:#64748b;text-transform:uppercase;">Alert Information</p>
        </td></tr>
        <tr><td style="padding:8px 40px 24px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid #334155;border-radius:6px;overflow:hidden;">
            <tr>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;background:#0f172a;color:#64748b;font-size:12px;white-space:nowrap;">Alert ID</td>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;color:#94a3b8;font-size:12px;font-family:monospace;word-break:break-all;">{alert_id}</td>
            </tr>
            <tr>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;background:#0f172a;color:#64748b;font-size:12px;white-space:nowrap;">Severity</td>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;">
                <span style="display:inline-block;padding:2px 8px;background:{severity_colour};border-radius:4px;font-size:11px;font-weight:700;color:#fff;">{severity_label}</span>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;background:#0f172a;color:#64748b;font-size:12px;white-space:nowrap;">Category</td>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;color:#94a3b8;font-size:12px;">{category}</td>
            </tr>
            <tr>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;background:#0f172a;color:#64748b;font-size:12px;white-space:nowrap;">Status</td>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;color:#94a3b8;font-size:12px;">{status}</td>
            </tr>
            <tr>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;background:#0f172a;color:#64748b;font-size:12px;white-space:nowrap;">Source</td>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;color:#94a3b8;font-size:12px;">{source}</td>
            </tr>
            <tr>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;background:#0f172a;color:#64748b;font-size:12px;white-space:nowrap;">Resource</td>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;color:#94a3b8;font-size:12px;word-break:break-all;">{resource}</td>
            </tr>
            <tr>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;background:#0f172a;color:#64748b;font-size:12px;white-space:nowrap;">Actor</td>
              <td style="padding:8px 16px;border-bottom:1px solid #334155;color:#94a3b8;font-size:12px;">{actor_str}</td>
            </tr>
            <tr>
              <td style="padding:8px 16px;background:#0f172a;color:#64748b;font-size:12px;white-space:nowrap;">Created (UTC)</td>
              <td style="padding:8px 16px;color:#94a3b8;font-size:12px;">{created}</td>
            </tr>
          </table>
        </td></tr>

        {metadata_section}

        <!-- CTA button -->
        <tr><td align="center" style="padding:8px 40px 32px;">
          <a href="{base_url}" style="display:inline-block;padding:12px 32px;background:{severity_colour};border-radius:8px;font-size:14px;font-weight:600;color:#fff;text-decoration:none;letter-spacing:.02em;">Open Panoptix Console</a>
        </td></tr>

        <!-- Divider -->
        <tr><td style="padding:0 40px;"><hr style="border:none;border-top:1px solid #334155;margin:0;"></td></tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 40px;background:#0f172a;">
            <p style="margin:0;font-size:11px;color:#475569;line-height:1.6;">
              You received this alert because you are an active Panoptix administrator.<br>
              <strong style="color:#64748b;">Panoptix will never ask for passwords, tokens, or camera credentials by email.</strong><br>
              No secrets, raw provider payloads, or RTSP credentials are included in this message.
            </p>
          </td>
        </tr>

      </table>

    </td></tr>
  </table>

</body>
</html>"""
