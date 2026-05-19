from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import (
    ActorType,
    CameraSourceType,
    EventCategory,
    EventOutcome,
    EventSeverity,
    GatewayStatus,
    StreamKind,
)
from cctv_api.models.tables import (
    AuditLog,
    Camera,
    CameraAcl,
    EdgeGateway,
    GatewayCameraAssignment,
    Role,
    Session as UserSession,
    StreamGrant,
    User,
    UserRole,
)
from cctv_api.security.audit import record_audit_event
from cctv_api.security.users import get_or_create_user

AUDIT_HMAC_KEY_VERSION = 1
AUDIT_HMAC_KEY = "test-audit-hmac-key-with-enough-entropy"


def _client_with_db(test_db_session: DbSession, *, audit_hmac_key: str = AUDIT_HMAC_KEY) -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            AUDIT_HMAC_KEY_VERSION=AUDIT_HMAC_KEY_VERSION,
            AUDIT_HMAC_KEY=audit_hmac_key,
        )
    )

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


def _auth_headers(email: str = "viewer@example.test", roles: str = "viewer") -> dict[str, str]:
    return {
        "x-panoptix-dev-auth": "1",
        "x-panoptix-dev-email": email,
        "x-panoptix-dev-subject": email,
        "x-panoptix-dev-roles": roles,
    }


def _admin_headers() -> dict[str, str]:
    return _auth_headers(email="admin@example.test", roles="admin")


def _user(db: DbSession, email: str, *, disabled: bool = False) -> User:
    user = get_or_create_user(db, email=email, idp_subject=email)
    if disabled:
        user.disabled_at = datetime.now(timezone.utc)
        db.commit()
    return user


def _role(db: DbSession, name: str, role_id: int = 1) -> Role:
    role = Role(id=role_id, name=name)
    db.add(role)
    db.commit()
    return role


def _grant_role(db: DbSession, user: User, role: Role) -> None:
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()


def _camera(db: DbSession, name: str = "Front Door") -> Camera:
    camera = Camera(
        id=uuid.uuid4(),
        display_name=name,
        source_type=CameraSourceType.rtsp,
        room_uuid=uuid.uuid4(),
        livekit_room_name=f"room-{uuid.uuid4()}",
    )
    db.add(camera)
    db.commit()
    return camera


def _gateway(db: DbSession, name: str = "Edge 1", *, disabled: bool = False) -> EdgeGateway:
    gateway = EdgeGateway(
        id=uuid.uuid4(),
        name=name,
        status=GatewayStatus.disabled if disabled else GatewayStatus.enabled,
        mtls_fingerprint="sha256:test",
        cert_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        last_seen_at=datetime.now(timezone.utc),
        disabled_at=datetime.now(timezone.utc) if disabled else None,
    )
    db.add(gateway)
    db.commit()
    return gateway


def _session(
    db: DbSession,
    user: User,
    *,
    revoked: bool = False,
    ip: str = "203.0.113.10",
    ua_fp: str = "ua-test",
) -> UserSession:
    now = datetime.now(timezone.utc)
    session = UserSession(
        id=uuid.uuid4(),
        user_id=user.id,
        cf_jti=str(uuid.uuid4()),
        ua_fp=ua_fp,
        ip=ip,
        created_at=now - timedelta(minutes=10),
        last_seen_at=now,
        revoked_at=now if revoked else None,
    )
    db.add(session)
    db.commit()
    return session


def _stream_grant(
    db: DbSession,
    camera: Camera,
    *,
    user: User | None = None,
    gateway: EdgeGateway | None = None,
    denied_reason: str | None = None,
) -> StreamGrant:
    now = datetime.now(timezone.utc)
    grant = StreamGrant(
        id=uuid.uuid4(),
        user_id=user.id if user is not None else None,
        gateway_id=gateway.id if gateway is not None else None,
        camera_id=camera.id,
        jti=str(uuid.uuid4()),
        kind=StreamKind.viewer_subscribe if user is not None else StreamKind.gateway_publish,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        denied_reason=denied_reason,
    )
    db.add(grant)
    db.commit()
    return grant


def _audit(
    db: DbSession,
    *,
    actor_type: ActorType,
    actor_id: uuid.UUID | None,
    action: str,
    severity: EventSeverity = EventSeverity.low,
    outcome: EventOutcome = EventOutcome.success,
    category: EventCategory = EventCategory.system,
    ip: str | None = None,
    ua: str | None = None,
    resource: str = "resource:test",
) -> AuditLog:
    return record_audit_event(
        db,
        actor_type=actor_type,
        actor_id=actor_id,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action=action,
        resource=resource,
        ip=ip,
        ua=ua,
        event_severity=severity,
        event_outcome=outcome,
        event_category=category,
    )


def test_actor_profile_requires_authentication(test_db_session: DbSession) -> None:
    user = _user(test_db_session, "target@example.test")
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/profile")

    assert response.status_code == 401


def test_actor_profile_requires_admin_role(test_db_session: DbSession) -> None:
    user = _user(test_db_session, "target@example.test")
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/profile", headers=_auth_headers())

    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_actor_activity_requires_authentication(test_db_session: DbSession) -> None:
    user = _user(test_db_session, "target@example.test")
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/activity")

    assert response.status_code == 401


def test_actor_activity_requires_admin_role(test_db_session: DbSession) -> None:
    user = _user(test_db_session, "target@example.test")
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/activity", headers=_auth_headers())

    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_actor_profile_rejects_invalid_actor_type_and_id(test_db_session: DbSession) -> None:
    client = _client_with_db(test_db_session)

    invalid_type = client.get("/api/v1/admin/actors/not-real/none/profile", headers=_admin_headers())
    invalid_id = client.get("/api/v1/admin/actors/user/not-a-uuid/profile", headers=_admin_headers())
    none_user = client.get("/api/v1/admin/actors/user/none/profile", headers=_admin_headers())

    assert invalid_type.status_code == 400
    assert invalid_type.json()["detail"] == "actor-type-invalid"
    assert invalid_id.status_code == 400
    assert invalid_id.json()["detail"] == "actor-id-invalid"
    assert none_user.status_code == 400
    assert none_user.json()["detail"] == "actor-id-invalid"


def test_actor_profile_returns_404_for_missing_user_or_gateway(test_db_session: DbSession) -> None:
    client = _client_with_db(test_db_session)

    missing_user = client.get(f"/api/v1/admin/actors/user/{uuid.uuid4()}/profile", headers=_admin_headers())
    missing_gateway = client.get(f"/api/v1/admin/actors/gateway/{uuid.uuid4()}/profile", headers=_admin_headers())

    assert missing_user.status_code == 404
    assert missing_user.json()["detail"] == "user-not-found"
    assert missing_gateway.status_code == 404
    assert missing_gateway.json()["detail"] == "gateway-not-found"


def test_user_actor_profile_aggregates_identity_access_activity_and_risk(test_db_session: DbSession) -> None:
    user = _user(test_db_session, "target@example.test")
    other_user = _user(test_db_session, "other@example.test")
    role = _role(test_db_session, "viewer")
    _grant_role(test_db_session, user, role)
    active_session = _session(test_db_session, user, ip="203.0.113.10", ua_fp="ua-active")
    _session(test_db_session, user, revoked=True, ip="203.0.113.11", ua_fp="ua-revoked")
    camera = _camera(test_db_session)
    test_db_session.add(CameraAcl(user_id=user.id, camera_id=camera.id, granted_by=other_user.id))
    test_db_session.commit()
    _stream_grant(test_db_session, camera, user=user)
    _stream_grant(test_db_session, camera, user=user, denied_reason="acl_denied")
    _stream_grant(test_db_session, camera, user=other_user, denied_reason="other_user_denied")
    _audit(
        test_db_session,
        actor_type=ActorType.user,
        actor_id=user.id,
        action="test.actor.high_failure",
        severity=EventSeverity.high,
        outcome=EventOutcome.failure,
        category=EventCategory.authorization,
        ip="203.0.113.10",
        ua="ua-one",
    )
    _audit(
        test_db_session,
        actor_type=ActorType.user,
        actor_id=user.id,
        action="test.actor.denied",
        severity=EventSeverity.medium,
        outcome=EventOutcome.denied,
        category=EventCategory.authentication,
        ip="203.0.113.12",
        ua="ua-two",
    )
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/profile", headers=_admin_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["actor_type"] == "user"
    assert data["actor_id"] == str(user.id)
    assert data["identity"]["email"] == "target@example.test"
    assert data["identity"]["account_status"] == "active"
    assert data["roles"] == ["viewer"]
    assert data["sessions"]["active_count"] == 1
    assert data["sessions"]["revoked_count"] == 1
    assert data["sessions"]["active"][0]["session_id"] == str(active_session.id)
    assert data["camera_access"]["active_count"] == 1
    assert data["camera_access"]["active_grants"][0]["display_name"] == "Front Door"
    assert data["stream_grants"]["total_issued"] == 2
    assert data["stream_grants"]["denied_count"] == 1
    assert len(data["stream_grants"]["recent"]) == 2
    assert data["activity_summary"]["total_events"] == 2
    assert data["activity_summary"]["events_by_severity"]["high"] == 1
    assert data["activity_summary"]["events_by_outcome"]["denied"] == 1
    assert data["risk_indicators"]["has_denied_events"] is True
    assert data["risk_indicators"]["has_high_severity_events"] is True
    assert data["risk_indicators"]["has_failed_events"] is True
    assert data["risk_indicators"]["multiple_ips_observed"] is True
    assert data["containment_status"]["account_disabled"] is False
    assert data["ip_details"] is None
    assert data["device_details"] is None
    assert data["mfa_details"] is None
    assert data["threat_intelligence"] is None
    assert data["alerts"] is None
    assert data["incidents"] is None
    assert data["analyst_notes"] is None
    assert data["behavior_baseline"] is None
    assert "unsupported_sections" not in data


def test_disabled_user_profile_exposes_disabled_containment(test_db_session: DbSession) -> None:
    user = _user(test_db_session, "disabled@example.test", disabled=True)
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/profile", headers=_admin_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["identity"]["account_status"] == "disabled"
    assert data["risk_indicators"]["is_disabled"] is True
    assert data["containment_status"]["account_disabled"] is True
    disable_action = next(a for a in data["containment_status"]["available_actions"] if a["action"] == "disable_account")
    assert disable_action["available"] is False
    assert disable_action["reason"] == "already disabled"


def test_gateway_actor_profile_aggregates_identity_assignments_and_containment(test_db_session: DbSession) -> None:
    gateway = _gateway(test_db_session, disabled=True)
    camera = _camera(test_db_session, "Gate Camera")
    test_db_session.add(GatewayCameraAssignment(gateway_id=gateway.id, camera_id=camera.id))
    test_db_session.commit()
    _stream_grant(test_db_session, camera, gateway=gateway, denied_reason="gateway_disabled")
    _audit(
        test_db_session,
        actor_type=ActorType.gateway,
        actor_id=gateway.id,
        action="test.gateway.denied",
        severity=EventSeverity.high,
        outcome=EventOutcome.denied,
    )
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/gateway/{gateway.id}/profile", headers=_admin_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["actor_type"] == "gateway"
    assert data["identity"]["name"] == "Edge 1"
    assert data["identity"]["status"] == "disabled"
    assert data["identity"]["account_status"] == "disabled"
    assert data["sessions"] is None
    assert data["camera_access"]["active_count"] == 1
    assert data["camera_access"]["active_grants"][0]["display_name"] == "Gate Camera"
    assert data["stream_grants"]["total_issued"] == 1
    assert data["stream_grants"]["denied_count"] == 1
    assert data["risk_indicators"]["is_disabled"] is True
    assert data["containment_status"]["gateway_disabled"] is True


def test_system_actor_profile_accepts_none_actor_id(test_db_session: DbSession) -> None:
    _audit(
        test_db_session,
        actor_type=ActorType.system,
        actor_id=None,
        action="test.system.maintenance",
        severity=EventSeverity.low,
        outcome=EventOutcome.success,
    )
    client = _client_with_db(test_db_session)

    response = client.get("/api/v1/admin/actors/system/none/profile", headers=_admin_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["actor_type"] == "system"
    assert data["actor_id"] is None
    assert data["identity"] is None
    assert data["sessions"] is None
    assert data["activity_summary"]["total_events"] == 1


def test_break_glass_actor_profile_accepts_none_actor_id(test_db_session: DbSession) -> None:
    _audit(
        test_db_session,
        actor_type=ActorType.break_glass,
        actor_id=None,
        action="test.break_glass",
        severity=EventSeverity.critical,
    )
    client = _client_with_db(test_db_session)

    response = client.get("/api/v1/admin/actors/break_glass/none/profile", headers=_admin_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["actor_type"] == "break_glass"
    assert data["actor_id"] is None
    assert data["activity_summary"]["events_by_severity"]["critical"] == 1


def test_actor_activity_orders_and_paginates_by_descending_audit_id(test_db_session: DbSession) -> None:
    user = _user(test_db_session, "activity@example.test")
    first = _audit(test_db_session, actor_type=ActorType.user, actor_id=user.id, action="test.first")
    second = _audit(test_db_session, actor_type=ActorType.user, actor_id=user.id, action="test.second")
    third = _audit(test_db_session, actor_type=ActorType.user, actor_id=user.id, action="test.third")
    _audit(test_db_session, actor_type=ActorType.system, actor_id=None, action="test.other")
    client = _client_with_db(test_db_session)

    page_one = client.get(f"/api/v1/admin/actors/user/{user.id}/activity?limit=2", headers=_admin_headers())

    assert page_one.status_code == 200
    data = page_one.json()
    assert [item["id"] for item in data["items"]] == [third.id, second.id]
    assert data["next_cursor"] == str(second.id)

    page_two = client.get(
        f"/api/v1/admin/actors/user/{user.id}/activity?limit=2&cursor={data['next_cursor']}",
        headers=_admin_headers(),
    )

    assert page_two.status_code == 200
    assert [item["id"] for item in page_two.json()["items"]] == [first.id]
    assert page_two.json()["next_cursor"] is None


def test_actor_activity_filters_by_severity_and_date_range(test_db_session: DbSession) -> None:
    user = _user(test_db_session, "filters@example.test")
    old = _audit(
        test_db_session,
        actor_type=ActorType.user,
        actor_id=user.id,
        action="test.old_high",
        severity=EventSeverity.high,
    )
    new = _audit(
        test_db_session,
        actor_type=ActorType.user,
        actor_id=user.id,
        action="test.new_high",
        severity=EventSeverity.high,
    )
    low = _audit(
        test_db_session,
        actor_type=ActorType.user,
        actor_id=user.id,
        action="test.new_low",
        severity=EventSeverity.low,
    )
    old.ts = datetime.now(timezone.utc) - timedelta(days=3)
    new.ts = datetime.now(timezone.utc)
    low.ts = datetime.now(timezone.utc)
    test_db_session.commit()
    client = _client_with_db(test_db_session)

    response = client.get(
        f"/api/v1/admin/actors/user/{user.id}/activity",
        params={
            "severity": "high",
            "ts_from": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        },
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["action"] for item in items] == ["test.new_high"]


def test_actor_activity_empty_for_actor_with_no_events(test_db_session: DbSession) -> None:
    user = _user(test_db_session, "empty@example.test")
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/activity", headers=_admin_headers())

    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


def test_actor_activity_rejects_invalid_filter_values(test_db_session: DbSession) -> None:
    user = _user(test_db_session, "invalid-filter@example.test")
    client = _client_with_db(test_db_session)

    bad_severity = client.get(
        f"/api/v1/admin/actors/user/{user.id}/activity?severity=bad",
        headers=_admin_headers(),
    )
    bad_session = client.get(
        f"/api/v1/admin/actors/user/{user.id}/activity?session_id=bad",
        headers=_admin_headers(),
    )

    assert bad_severity.status_code == 400
    assert bad_severity.json()["detail"] == "severity-invalid"
    assert bad_session.status_code == 400
    assert bad_session.json()["detail"] == "session-id-invalid"


def test_actor_activity_returns_404_for_missing_backing_actor(test_db_session: DbSession) -> None:
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/user/{uuid.uuid4()}/activity", headers=_admin_headers())

    assert response.status_code == 404
    assert response.json()["detail"] == "user-not-found"


def test_profile_and_activity_views_are_audited(test_db_session: DbSession) -> None:
    user = _user(test_db_session, "audited@example.test")
    _audit(test_db_session, actor_type=ActorType.user, actor_id=user.id, action="test.target")
    client = _client_with_db(test_db_session)

    profile = client.get(f"/api/v1/admin/actors/user/{user.id}/profile", headers=_admin_headers())
    activity = client.get(f"/api/v1/admin/actors/user/{user.id}/activity?limit=10", headers=_admin_headers())

    assert profile.status_code == 200
    assert activity.status_code == 200
    actions = list(test_db_session.execute(select(AuditLog.action).order_by(AuditLog.id)).scalars().all())
    assert "admin.actor.profile.viewed" in actions
    assert "admin.actor.activity.viewed" in actions
    profile_row = test_db_session.execute(
        select(AuditLog).where(AuditLog.action == "admin.actor.profile.viewed")
    ).scalar_one()
    activity_row = test_db_session.execute(
        select(AuditLog).where(AuditLog.action == "admin.actor.activity.viewed")
    ).scalar_one()
    assert profile_row.resource == f"actor:user:{user.id}"
    assert profile_row.payload == {"actor_type": "user", "actor_id": str(user.id)}
    assert activity_row.payload["actor_type"] == "user"
    assert activity_row.payload["actor_id"] == str(user.id)
    assert activity_row.payload["limit"] == 10
    assert activity_row.payload["rows_returned"] == 1
