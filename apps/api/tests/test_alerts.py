from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.integrations.email_alerts import AlertEmailSendError
from cctv_api.main import create_app
from cctv_api.models.enums import ActorType, AlertCategory, AlertNotificationStatus, AlertSeverity, AlertStatus, GatewayStatus
from cctv_api.models.tables import Alert, AlertNotification, AuditLog, BackupRun, EdgeGateway, Role, User, UserRole
from cctv_api.security.alerts import create_alert, detect_alert_from_audit_event
from cctv_api.security.audit import record_audit_event


_ADMIN_HEADERS = {
    "x-panoptix-dev-auth": "1",
    "x-panoptix-dev-email": "admin@example.test",
    "x-panoptix-dev-subject": "admin@example.test",
    "x-panoptix-dev-roles": "admin",
}

_VIEWER_HEADERS = {
    "x-panoptix-dev-auth": "1",
    "x-panoptix-dev-email": "viewer@example.test",
    "x-panoptix-dev-subject": "viewer@example.test",
    "x-panoptix-dev-roles": "viewer",
}

_AUDIT_KEY = "test-audit-key-with-enough-entropy"


def _client(test_db_session: DbSession, **settings_overrides: object) -> TestClient:
    settings = {
        "APP_ENV": "development",
        "ALLOW_DEV_AUTH": True,
        "AUDIT_HMAC_KEY_VERSION": 1,
        "AUDIT_HMAC_KEY": _AUDIT_KEY,
        "LIVEKIT_CLOUD_URL": "wss://livekit.example.test",
        "LIVEKIT_CLOUD_API_KEY": "test-livekit-key",
        "LIVEKIT_CLOUD_API_SECRET": "test-livekit-secret-with-at-least-32-bytes",
    }
    settings.update(settings_overrides)
    app = create_app(settings=Settings(**settings))

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


def _seed_alert(db: DbSession, *, status: AlertStatus = AlertStatus.open) -> Alert:
    alert = Alert(
        id=uuid.uuid4(),
        severity=AlertSeverity.high,
        category=AlertCategory.security,
        title="Seeded alert",
        message="Seeded alert message",
        status=status,
        source="test",
        resource="test:resource",
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def _seed_user(db: DbSession, *, email: str = "target@example.test") -> User:
    user = User(id=uuid.uuid4(), email=email, idp_subject=email, created_at=datetime.now(timezone.utc))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_role(db: DbSession, *, role_id: int, name: str) -> Role:
    role = Role(id=role_id, name=name)
    db.add(role)
    db.commit()
    return role


def _assign_role(db: DbSession, *, user: User, role: Role) -> None:
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()


def _seed_gateway(db: DbSession) -> EdgeGateway:
    gateway = EdgeGateway(id=uuid.uuid4(), name="Alert Test Gateway", status=GatewayStatus.enabled)
    db.add(gateway)
    db.commit()
    db.refresh(gateway)
    return gateway


def test_alert_list_requires_auth(test_db_session: DbSession) -> None:
    response = _client(test_db_session).get("/api/v1/admin/alerts")
    assert response.status_code == 401


def test_alert_list_requires_admin(test_db_session: DbSession) -> None:
    response = _client(test_db_session).get("/api/v1/admin/alerts", headers=_VIEWER_HEADERS)
    assert response.status_code == 403


def test_alert_list_and_detail_admin_success(test_db_session: DbSession) -> None:
    alert = _seed_alert(test_db_session)
    client = _client(test_db_session)

    list_response = client.get("/api/v1/admin/alerts", headers=_ADMIN_HEADERS)
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["alert_id"] == str(alert.id)

    detail_response = client.get(f"/api/v1/admin/alerts/{alert.id}", headers=_ADMIN_HEADERS)
    assert detail_response.status_code == 200
    assert detail_response.json()["title"] == "Seeded alert"


def test_alert_acknowledge_and_resolve_write_audit(test_db_session: DbSession) -> None:
    alert = _seed_alert(test_db_session)
    client = _client(test_db_session)

    ack = client.post(f"/api/v1/admin/alerts/{alert.id}/acknowledge", headers=_ADMIN_HEADERS)
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"

    resolved = client.post(f"/api/v1/admin/alerts/{alert.id}/resolve", headers=_ADMIN_HEADERS)
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    actions = set(test_db_session.execute(select(AuditLog.action)).scalars().all())
    assert "admin.alert.acknowledged" in actions
    assert "admin.alert.resolved" in actions


def test_break_glass_open_creates_critical_alert(test_db_session: DbSession) -> None:
    response = _client(test_db_session).post(
        "/api/v1/admin/break-glass/open",
        headers=_ADMIN_HEADERS,
        json={"reason": "IdP outage"},
    )
    assert response.status_code == 200

    alert = test_db_session.execute(select(Alert).where(Alert.title == "Break-glass access opened")).scalar_one()
    assert alert.severity == AlertSeverity.critical
    assert alert.category == AlertCategory.security


def test_admin_role_grant_creates_high_alert(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    _seed_role(test_db_session, role_id=1, name="admin")

    response = _client(test_db_session).post(
        f"/api/v1/admin/users/{user.id}/role",
        headers=_ADMIN_HEADERS,
        json={"action": "grant", "role_name": "admin"},
    )
    assert response.status_code == 200

    alert = test_db_session.execute(select(Alert).where(Alert.title == "Admin role granted")).scalar_one()
    assert alert.severity == AlertSeverity.high
    assert alert.metadata_json["role_name"] == "admin"


def test_gateway_disable_creates_high_alert(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)

    response = _client(test_db_session).post(
        f"/api/v1/admin/gateways/{gateway.id}/disable",
        headers=_ADMIN_HEADERS,
        json={"reason": "maintenance"},
    )
    assert response.status_code == 200

    alert = test_db_session.execute(select(Alert).where(Alert.title == "Gateway disabled")).scalar_one()
    assert alert.severity == AlertSeverity.high
    assert alert.metadata_json["gateway_id"] == str(gateway.id)


def test_audit_verification_failure_creates_critical_alert(test_db_session: DbSession) -> None:
    row = record_audit_event(
        test_db_session,
        actor_type=ActorType.system,
        actor_id=None,
        action="system.maintenance.run",
        resource="system",
        payload={"ok": True},
        audit_hmac_key_version=1,
        audit_hmac_key=_AUDIT_KEY,
    )
    row.resource = "tampered"
    test_db_session.commit()

    response = _client(test_db_session).get("/api/v1/admin/audit/verify", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    assert response.json()["valid"] is False

    alert = test_db_session.execute(select(Alert).where(Alert.title == "Audit chain verification failed")).scalar_one()
    assert alert.severity == AlertSeverity.critical


def test_detection_idempotent_for_same_source_event(test_db_session: DbSession) -> None:
    audit = record_audit_event(
        test_db_session,
        actor_type=ActorType.system,
        actor_id=None,
        action="system.break_glass.opened",
        resource="break-glass:test",
        payload={"reason": "test"},
        audit_hmac_key_version=1,
        audit_hmac_key=_AUDIT_KEY,
    )
    settings = Settings(
        APP_ENV="development",
        ALLOW_DEV_AUTH=True,
        AUDIT_HMAC_KEY_VERSION=1,
        AUDIT_HMAC_KEY=_AUDIT_KEY,
    )

    first = detect_alert_from_audit_event(test_db_session, settings=settings, audit_log=audit)
    second = detect_alert_from_audit_event(test_db_session, settings=settings, audit_log=audit)

    assert first is not None
    assert second is not None
    assert str(first.id) == str(second.id)
    assert [str(row.id) for row in test_db_session.execute(select(Alert).where(Alert.source_event_id == audit.id)).scalars().all()] == [str(first.id)]


def test_high_value_audit_events_create_security_alerts(test_db_session: DbSession) -> None:
    settings = Settings(
        APP_ENV="development",
        ALLOW_DEV_AUTH=True,
        AUDIT_HMAC_KEY_VERSION=1,
        AUDIT_HMAC_KEY=_AUDIT_KEY,
    )
    cases = [
        ("auth.csrf.denied", "CSRF protection failure", AlertCategory.security),
        ("auth.login.denied.user_disabled", "Disabled user attempted login", AlertCategory.security),
        ("auth.gateway.denied.credential_invalid", "Invalid gateway credential used", AlertCategory.security),
        ("gateway.heartbeat.denied.signing_failed", "Gateway heartbeat signing failed", AlertCategory.operations),
        (
            "gateway.control.denied.unauthenticated",
            "Unauthenticated gateway control attempt",
            AlertCategory.security,
        ),
        ("gateway.control.denied.signing_failed", "Gateway control signing failed", AlertCategory.operations),
        (
            "gateway.ingest.denied.livekit_config",
            "Gateway ingest failed due LiveKit config",
            AlertCategory.operations,
        ),
        (
            "viewer.token.denied.livekit_config",
            "Viewer token failed due LiveKit config",
            AlertCategory.operations,
        ),
        ("system.alert.email.failed", "Alert email delivery failed", AlertCategory.availability),
    ]

    for index, (action, title, category) in enumerate(cases, start=1):
        audit = record_audit_event(
            test_db_session,
            actor_type=ActorType.system,
            actor_id=None,
            action=action,
            resource=f"test-resource:{index}",
            payload={
                "detail": "test-detail",
                "reason": "test-reason",
                "gateway_id": "gateway-1",
                "camera_id": "camera-1",
            },
            audit_hmac_key_version=1,
            audit_hmac_key=_AUDIT_KEY,
        )

        alert = detect_alert_from_audit_event(test_db_session, settings=settings, audit_log=audit)

        assert alert is not None
        assert alert.title == title
        assert alert.severity == AlertSeverity.high
        assert alert.category == category
        assert alert.metadata_json["action"] == action


def test_email_disabled_creates_alert_without_notification(test_db_session: DbSession) -> None:
    settings = Settings(
        APP_ENV="development",
        ALLOW_DEV_AUTH=True,
        AUDIT_HMAC_KEY_VERSION=1,
        AUDIT_HMAC_KEY=_AUDIT_KEY,
    )

    with patch("cctv_api.security.alerts.send_alert_email") as send_email:
        create_alert(
            test_db_session,
            settings=settings,
            severity=AlertSeverity.critical,
            category=AlertCategory.security,
            title="Email disabled",
            message="No email should be attempted.",
            source="test-email-disabled",
            source_event_id=1,
        )

    send_email.assert_not_called()
    assert test_db_session.execute(select(AlertNotification)).scalar_one_or_none() is None


def test_email_enabled_records_sent_notification(test_db_session: DbSession) -> None:
    settings = Settings(
        APP_ENV="development",
        ALLOW_DEV_AUTH=True,
        AUDIT_HMAC_KEY_VERSION=1,
        AUDIT_HMAC_KEY=_AUDIT_KEY,
        ALERT_EMAIL_ENABLED=True,
        ALERT_EMAIL_SMTP_HOST="smtp.example.test",
        ALERT_EMAIL_SMTP_PASSWORD="smtp-password-with-enough-length",
        ALERT_EMAIL_FROM="alerts@example.test",
        ALERT_EMAIL_TO="secops@example.test",
    )

    with patch("cctv_api.security.alerts.send_alert_email") as send_email:
        create_alert(
            test_db_session,
            settings=settings,
            severity=AlertSeverity.high,
            category=AlertCategory.security,
            title="Email enabled",
            message="Email should be attempted.",
            source="test-email-enabled",
            source_event_id=1,
        )

    send_email.assert_called_once()
    notification = test_db_session.execute(select(AlertNotification)).scalar_one()
    assert notification.status == AlertNotificationStatus.sent
    assert notification.sent_at is not None


def test_email_admins_mode_sends_to_active_admins_only(test_db_session: DbSession) -> None:
    admin_role = _seed_role(test_db_session, role_id=10, name="admin")
    viewer_role = _seed_role(test_db_session, role_id=11, name="viewer")
    admin_one = _seed_user(test_db_session, email="admin-one@example.test")
    admin_two = _seed_user(test_db_session, email="admin-two@example.test")
    disabled_admin = _seed_user(test_db_session, email="disabled-admin@example.test")
    viewer = _seed_user(test_db_session, email="viewer-only@example.test")
    disabled_admin.disabled_at = datetime.now(timezone.utc)
    test_db_session.commit()
    _assign_role(test_db_session, user=admin_one, role=admin_role)
    _assign_role(test_db_session, user=admin_two, role=admin_role)
    _assign_role(test_db_session, user=disabled_admin, role=admin_role)
    _assign_role(test_db_session, user=viewer, role=viewer_role)

    settings = Settings(
        APP_ENV="development",
        ALLOW_DEV_AUTH=True,
        AUDIT_HMAC_KEY_VERSION=1,
        AUDIT_HMAC_KEY=_AUDIT_KEY,
        ALERT_EMAIL_ENABLED=True,
        ALERT_EMAIL_SMTP_HOST="smtp.example.test",
        ALERT_EMAIL_SMTP_PASSWORD="smtp-password-with-enough-length",
        ALERT_EMAIL_FROM="alerts@example.test",
        ALERT_EMAIL_RECIPIENT_MODE="admins",
    )

    with patch("cctv_api.security.alerts.send_alert_email") as send_email:
        create_alert(
            test_db_session,
            settings=settings,
            severity=AlertSeverity.high,
            category=AlertCategory.security,
            title="Admins mode",
            message="Email active admins only.",
            source="test-email-admins",
            source_event_id=1,
        )

    recipients = [call.kwargs["recipient"] for call in send_email.call_args_list]
    assert recipients == ["admin-one@example.test", "admin-two@example.test"]
    notification_recipients = list(
        test_db_session.execute(select(AlertNotification.recipient)).scalars().all()
    )
    assert notification_recipients == recipients


def test_email_both_mode_merges_static_and_admin_recipients_without_duplicates(
    test_db_session: DbSession,
) -> None:
    admin_role = _seed_role(test_db_session, role_id=12, name="admin")
    admin = _seed_user(test_db_session, email="Admin-One@example.test")
    _assign_role(test_db_session, user=admin, role=admin_role)

    settings = Settings(
        APP_ENV="development",
        ALLOW_DEV_AUTH=True,
        AUDIT_HMAC_KEY_VERSION=1,
        AUDIT_HMAC_KEY=_AUDIT_KEY,
        ALERT_EMAIL_ENABLED=True,
        ALERT_EMAIL_SMTP_HOST="smtp.example.test",
        ALERT_EMAIL_SMTP_PASSWORD="smtp-password-with-enough-length",
        ALERT_EMAIL_FROM="alerts@example.test",
        ALERT_EMAIL_TO="admin-one@example.test,secops@example.test",
        ALERT_EMAIL_RECIPIENT_MODE="both",
    )

    with patch("cctv_api.security.alerts.send_alert_email") as send_email:
        create_alert(
            test_db_session,
            settings=settings,
            severity=AlertSeverity.critical,
            category=AlertCategory.security,
            title="Both mode",
            message="Email static and admins.",
            source="test-email-both",
            source_event_id=1,
        )

    recipients = [call.kwargs["recipient"] for call in send_email.call_args_list]
    assert recipients == ["admin-one@example.test", "secops@example.test"]


def test_email_severity_threshold_still_applies_to_admin_mode(test_db_session: DbSession) -> None:
    admin_role = _seed_role(test_db_session, role_id=13, name="admin")
    admin = _seed_user(test_db_session, email="admin-threshold@example.test")
    _assign_role(test_db_session, user=admin, role=admin_role)

    settings = Settings(
        APP_ENV="development",
        ALLOW_DEV_AUTH=True,
        AUDIT_HMAC_KEY_VERSION=1,
        AUDIT_HMAC_KEY=_AUDIT_KEY,
        ALERT_EMAIL_ENABLED=True,
        ALERT_EMAIL_SMTP_HOST="smtp.example.test",
        ALERT_EMAIL_SMTP_PASSWORD="smtp-password-with-enough-length",
        ALERT_EMAIL_FROM="alerts@example.test",
        ALERT_EMAIL_RECIPIENT_MODE="admins",
        ALERT_EMAIL_MIN_SEVERITY="critical",
    )

    with patch("cctv_api.security.alerts.send_alert_email") as send_email:
        create_alert(
            test_db_session,
            settings=settings,
            severity=AlertSeverity.high,
            category=AlertCategory.security,
            title="Below threshold",
            message="No email should be attempted.",
            source="test-email-threshold",
            source_event_id=1,
        )

    send_email.assert_not_called()
    assert test_db_session.execute(select(AlertNotification)).scalar_one_or_none() is None


def test_email_failure_records_failed_notification_without_rollback(test_db_session: DbSession) -> None:
    settings = Settings(
        APP_ENV="development",
        ALLOW_DEV_AUTH=True,
        AUDIT_HMAC_KEY_VERSION=1,
        AUDIT_HMAC_KEY=_AUDIT_KEY,
        ALERT_EMAIL_ENABLED=True,
        ALERT_EMAIL_SMTP_HOST="smtp.example.test",
        ALERT_EMAIL_SMTP_PASSWORD="smtp-password-with-enough-length",
        ALERT_EMAIL_FROM="alerts@example.test",
        ALERT_EMAIL_TO="secops@example.test",
    )

    with patch(
        "cctv_api.security.alerts.send_alert_email",
        side_effect=AlertEmailSendError("alert-email-send-failed"),
    ):
        alert = create_alert(
            test_db_session,
            settings=settings,
            severity=AlertSeverity.critical,
            category=AlertCategory.security,
            title="Email failed",
            message="Alert should remain created.",
            source="test-email-failed",
            source_event_id=1,
        )

    notification = test_db_session.execute(select(AlertNotification)).scalar_one()
    assert str(notification.alert_id) == str(alert.id)
    assert notification.status == AlertNotificationStatus.failed
    assert notification.error == "alert-email-send-failed"
    delivery_alert = test_db_session.execute(
        select(Alert).where(Alert.title == "Alert email delivery failed")
    ).scalar_one()
    assert delivery_alert.source == "alert_email"
    assert delivery_alert.category == AlertCategory.availability
    assert delivery_alert.metadata_json["notification_id"] == str(notification.id)


def test_backup_status_missing_creates_medium_alert(test_db_session: DbSession) -> None:
    response = _client(test_db_session).get("/api/v1/admin/backups/status", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    assert response.json()["status"] == "missing"

    alert = test_db_session.execute(select(Alert).where(Alert.source == "backup_status")).scalar_one()
    assert alert.severity == AlertSeverity.medium


def test_backup_status_ok_does_not_create_alert(test_db_session: DbSession) -> None:
    now = datetime.now(timezone.utc)
    test_db_session.add(
        BackupRun(
            id=uuid.uuid4(),
            started_at=now,
            finished_at=now,
            size_bytes=1024,
            sha256="a" * 64,
            restore_format_ok=True,
            restore_schema_ok=True,
            upload_status="uploaded",
        )
    )
    test_db_session.commit()

    response = _client(test_db_session).get("/api/v1/admin/backups/status", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert test_db_session.execute(select(Alert).where(Alert.source == "backup_status")).scalar_one_or_none() is None


def test_email_secret_not_exposed_in_alert_response_or_audit(test_db_session: DbSession) -> None:
    secret = "super-secret-smtp-password"
    settings = Settings(
        APP_ENV="development",
        ALLOW_DEV_AUTH=True,
        AUDIT_HMAC_KEY_VERSION=1,
        AUDIT_HMAC_KEY=_AUDIT_KEY,
        ALERT_EMAIL_ENABLED=True,
        ALERT_EMAIL_SMTP_HOST="smtp.example.test",
        ALERT_EMAIL_SMTP_PASSWORD=secret,
        ALERT_EMAIL_FROM="alerts@example.test",
        ALERT_EMAIL_TO="secops@example.test",
    )

    with patch(
        "cctv_api.security.alerts.send_alert_email",
        side_effect=AlertEmailSendError("alert-email-send-failed"),
    ):
        alert = create_alert(
            test_db_session,
            settings=settings,
            severity=AlertSeverity.critical,
            category=AlertCategory.security,
            title="Secret check",
            message="Secret must not leak.",
            source="test-secret-check",
            source_event_id=1,
            metadata={"password": secret, "token": secret},
        )

    client = _client(test_db_session)
    response = client.get(f"/api/v1/admin/alerts/{alert.id}", headers=_ADMIN_HEADERS)
    assert response.status_code == 200

    joined = str(response.json())
    joined += str(test_db_session.execute(select(AlertNotification)).scalar_one().error)
    joined += str([row.payload for row in test_db_session.execute(select(AuditLog)).scalars().all()])
    assert secret not in joined
