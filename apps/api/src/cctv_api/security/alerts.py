from __future__ import annotations

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
from cctv_api.models.tables import Alert, AlertNotification, AuditLog, GatewayCommandQueue, Role, User, UserRole
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

    return None


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
