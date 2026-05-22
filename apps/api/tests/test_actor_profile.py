from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import (
    ActorType,
    AlertCategory,
    AlertSeverity,
    AlertStatus,
    CameraSourceType,
    EventCategory,
    EventOutcome,
    EventSeverity,
    GatewayStatus,
    StreamKind,
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
    Session as UserSession,
    StreamGrant,
    User,
    UserRole,
)
from cctv_api.security.audit import record_audit_event
from cctv_api.security.ip_intelligence import (
    IpCarrier,
    IpCompany,
    IpIntelligenceProviderState,
    IpIntelligenceResult,
    IpLocation,
    IpNetwork,
    IpSecurity,
)
from cctv_api.security.users import get_or_create_user

AUDIT_HMAC_KEY_VERSION = 1
AUDIT_HMAC_KEY = "test-audit-hmac-key-with-enough-entropy"


def _client_with_db(
    test_db_session: DbSession,
    *,
    audit_hmac_key: str = AUDIT_HMAC_KEY,
    **setting_overrides: object,
) -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            AUDIT_HMAC_KEY_VERSION=AUDIT_HMAC_KEY_VERSION,
            AUDIT_HMAC_KEY=audit_hmac_key,
            **setting_overrides,
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
    minutes_ago: int = 10,
) -> UserSession:
    now = datetime.now(timezone.utc)
    session = UserSession(
        id=uuid.uuid4(),
        user_id=user.id,
        cf_jti=str(uuid.uuid4()),
        ua_fp=ua_fp,
        ip=ip,
        created_at=now - timedelta(minutes=minutes_ago),
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


def _alert(
    db: DbSession,
    *,
    actor_type: ActorType | None,
    actor_id: uuid.UUID | None,
    title: str,
    severity: AlertSeverity = AlertSeverity.low,
    created_at: datetime | None = None,
    resource: str | None = "resource:test",
    metadata: dict[str, object] | None = None,
) -> Alert:
    alert = Alert(
        severity=severity,
        category=AlertCategory.security,
        title=title,
        message=f"{title} message",
        status=AlertStatus.open,
        source="actor_profile_test",
        resource=resource,
        actor_type=actor_type,
        actor_id=actor_id,
        metadata_json=metadata,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(alert)
    db.commit()
    return alert


class _FakeIpProvider:
    def __init__(
        self,
        results: dict[str, IpIntelligenceResult | None] | None = None,
        *,
        fail: bool = False,
    ) -> None:
        self.results = results or {}
        self.fail = fail
        self.lookups: list[str] = []

    def lookup(self, ip: str) -> IpIntelligenceResult | None:
        self.lookups.append(ip)
        if self.fail:
            raise RuntimeError("lookup failed")
        return self.results.get(ip)


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
    assert data["ip_details"]["available"] is False
    assert data["ip_details"]["status"] == "not_configured"
    assert data["ip_details"]["provider"] is None
    assert data["device_details"]["available"] is True
    assert data["device_details"]["distinct_user_agent_count"] == 2
    assert data["mfa_details"] is None
    assert data["threat_intelligence"] is None
    assert data["alerts"]["total_count"] == 0
    assert data["alerts"]["recent"] == []
    assert data["incidents"] is None
    assert data["analyst_notes"] is None
    assert data["behavior_baseline"]["available"] is False
    assert "unsupported_sections" not in data


def test_user_profile_returns_device_details_from_recent_sessions(test_db_session: DbSession) -> None:
    user = _user(test_db_session, "device-details@example.test")
    session = _session(
        test_db_session,
        user,
        ua_fp=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        ),
    )
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/profile", headers=_admin_headers())

    assert response.status_code == 200
    device_details = response.json()["device_details"]
    assert device_details["available"] is True
    assert device_details["distinct_user_agent_count"] == 1
    recent = device_details["recent_sessions"][0]
    assert recent["session_id"] == str(session.id)
    assert recent["browser"]["family"] == "Chrome"
    assert recent["os"]["family"] == "Windows"
    assert recent["device"]["device_class"] == "desktop"


def test_user_profile_enriches_bounded_recent_ips_and_deduplicates_lookups(
    test_db_session: DbSession,
    monkeypatch,
) -> None:
    user = _user(test_db_session, "ip-details@example.test")
    sessions = [
        _session(
            test_db_session,
            user,
            minutes_ago=index,
            ip="203.0.113.10" if index < 2 else f"203.0.113.{10 + index}",
        )
        for index in range(12)
    ]
    result = IpIntelligenceResult(
        ip_type="IPv4",
        location=IpLocation(
            continent="Asia",
            country_code="PH",
            country="Philippines",
            region="Calabarzon",
            city="Santa Rosa",
            timezone="Asia/Manila",
        ),
        network=IpNetwork(
            asn=9299,
            organization="Philippine Long Distance Telephone Company",
            domain="pldt.com",
            connection_type="isp",
        ),
        company=IpCompany(name="PLDT", domain="pldt.com", type="isp"),
        carrier=IpCarrier(name=None),
        security=IpSecurity(
            is_anonymous=False,
            is_vpn=False,
            is_proxy=False,
            is_tor=False,
            is_tor_exit=False,
            is_cloud_provider=False,
            is_relay=False,
            is_threat=False,
            is_attacker=False,
            is_abuser=False,
        ),
    )
    results = {
        "203.0.113.10": result,
        **{f"203.0.113.{10 + index}": result for index in range(2, 10)},
    }
    provider = _FakeIpProvider(results)
    monkeypatch.setattr(
        "cctv_api.security.actor_investigation.get_ip_intelligence_provider",
        lambda _settings: IpIntelligenceProviderState(
            status="ok",
            provider_name="ipregistry",
            provider=provider,
        ),
    )
    alert_count = test_db_session.execute(select(func.count()).select_from(Alert)).scalar_one()
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/profile", headers=_admin_headers())

    assert response.status_code == 200
    ip_details = response.json()["ip_details"]
    assert ip_details["available"] is True
    assert ip_details["status"] == "ok"
    assert ip_details["provider"] == "ipregistry"
    assert ip_details["distinct_ip_count"] == 9
    assert ip_details["enriched_ip_count"] == 9
    assert len(ip_details["recent_sessions"]) == 10
    assert [item["session_id"] for item in ip_details["recent_sessions"]] == [
        str(session.id) for session in sessions[:10]
    ]
    assert ip_details["recent_sessions"][0]["ip_type"] == "IPv4"
    assert ip_details["recent_sessions"][0]["location"]["city"] == "Santa Rosa"
    assert ip_details["recent_sessions"][0]["network"]["asn"] == 9299
    assert ip_details["recent_sessions"][0]["security"]["is_vpn"] is False
    assert provider.lookups == list(results)
    assert test_db_session.execute(select(func.count()).select_from(Alert)).scalar_one() == alert_count


def test_user_profile_ip_details_degrade_when_provider_not_configured(
    test_db_session: DbSession,
) -> None:
    user = _user(test_db_session, "ip-not-configured@example.test")
    _session(test_db_session, user)
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/profile", headers=_admin_headers())

    assert response.status_code == 200
    ip_details = response.json()["ip_details"]
    assert ip_details["available"] is False
    assert ip_details["status"] == "not_configured"
    assert ip_details["provider"] is None
    assert ip_details["enriched_ip_count"] == 0
    assert ip_details["recent_sessions"][0]["location"]["country_code"] is None


def test_user_profile_ip_details_return_ipregistry_subset(
    test_db_session: DbSession,
    monkeypatch,
) -> None:
    payload = {
        "ip": "203.0.113.10",
        "type": "IPv4",
        "carrier": {"name": "Example Mobile", "mcc": "515", "mnc": "02"},
        "company": {"name": "Example Company", "domain": "example.test", "type": "isp"},
        "connection": {
            "asn": 64500,
            "domain": "network.example",
            "organization": "Example Network",
            "route": "203.0.113.0/24",
            "type": "isp",
        },
        "currency": {"code": "PHP"},
        "location": {
            "continent": {"code": "AS", "name": "Asia"},
            "country": {
                "code": "PH",
                "name": "Philippines",
                "capital": "Manila",
                "population": 100,
            },
            "region": {"code": "PH-40", "name": "Calabarzon"},
            "city": "Santa Rosa",
            "postal": "4026",
            "latitude": 14.312,
            "longitude": 121.111,
        },
        "security": {
            "is_anonymous": False,
            "is_abuser": False,
            "is_attacker": True,
            "is_bogon": False,
            "is_cloud_provider": False,
            "is_proxy": False,
            "is_relay": False,
            "is_threat": True,
            "is_tor": False,
            "is_tor_exit": False,
            "is_vpn": False,
        },
        "time_zone": {"id": "Asia/Manila", "current_time": "2026-05-22T14:00:00+08:00"},
    }

    def _mock_get(*_args: object, **_kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
            request=httpx.Request("GET", "https://api.ipregistry.co/203.0.113.10"),
        )

    monkeypatch.setattr(
        "cctv_api.security.ip_intelligence.httpx.get",
        _mock_get,
    )
    user = _user(test_db_session, "ip-ipregistry@example.test")
    _session(test_db_session, user)
    client = _client_with_db(
        test_db_session,
        ACTOR_IP_ENRICHMENT_ENABLED=True,
        ACTOR_IP_IPREGISTRY_API_KEY="test-key",
    )

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/profile", headers=_admin_headers())

    assert response.status_code == 200
    ip_details = response.json()["ip_details"]
    recent = ip_details["recent_sessions"][0]
    assert ip_details["available"] is True
    assert ip_details["status"] == "ok"
    assert ip_details["provider"] == "ipregistry"
    assert recent["ip_type"] == "IPv4"
    assert recent["location"]["continent"] == "Asia"
    assert recent["location"]["country_code"] == "PH"
    assert recent["location"]["timezone"] == "Asia/Manila"
    assert recent["network"] == {
        "asn": 64500,
        "organization": "Example Network",
        "domain": "network.example",
        "connection_type": "isp",
    }
    assert recent["company"]["domain"] == "example.test"
    assert recent["carrier"]["name"] == "Example Mobile"
    assert recent["security"]["is_threat"] is True
    assert set(recent) == {
        "session_id",
        "created_at",
        "last_seen_at",
        "revoked_at",
        "ip",
        "ip_type",
        "location",
        "network",
        "company",
        "carrier",
        "security",
    }
    assert "postal" not in recent["location"]
    assert "latitude" not in recent["location"]
    assert "route" not in recent["network"]
    assert "mcc" not in recent["carrier"]
    assert "is_bogon" not in recent["security"]
    assert "currency" not in recent


def test_user_profile_ip_details_return_nulls_for_missing_ipregistry_fields(
    test_db_session: DbSession,
    monkeypatch,
) -> None:
    def _mock_get(*_args: object, **_kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "type": "IPv6",
                "location": {"country": {"code": "PH", "name": "Philippines"}},
            },
            request=httpx.Request("GET", "https://api.ipregistry.co/2001:db8::1"),
        )

    monkeypatch.setattr(
        "cctv_api.security.ip_intelligence.httpx.get",
        _mock_get,
    )
    user = _user(test_db_session, "ip-null-fields@example.test")
    _session(test_db_session, user, ip="2001:db8::1")
    client = _client_with_db(
        test_db_session,
        ACTOR_IP_ENRICHMENT_ENABLED=True,
        ACTOR_IP_IPREGISTRY_API_KEY="test-key",
    )

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/profile", headers=_admin_headers())

    assert response.status_code == 200
    recent = response.json()["ip_details"]["recent_sessions"][0]
    assert recent["ip_type"] == "IPv6"
    assert recent["location"]["country"] == "Philippines"
    assert recent["network"]["organization"] is None
    assert recent["company"]["name"] is None
    assert recent["carrier"]["name"] is None
    assert recent["security"]["is_vpn"] is None


def test_user_profile_ip_details_report_unavailable_when_ipregistry_fails(
    test_db_session: DbSession,
    monkeypatch,
) -> None:
    user = _user(test_db_session, "ip-failure@example.test")
    _session(test_db_session, user)

    def _mock_get(*_args: object, **_kwargs: object) -> httpx.Response:
        return httpx.Response(
            503,
            request=httpx.Request("GET", "https://api.ipregistry.co/203.0.113.10"),
        )

    monkeypatch.setattr(
        "cctv_api.security.ip_intelligence.httpx.get",
        _mock_get,
    )
    client = _client_with_db(
        test_db_session,
        ACTOR_IP_ENRICHMENT_ENABLED=True,
        ACTOR_IP_IPREGISTRY_API_KEY="test-key",
    )

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/profile", headers=_admin_headers())

    assert response.status_code == 200
    ip_details = response.json()["ip_details"]
    assert ip_details["available"] is False
    assert ip_details["status"] == "unavailable"
    assert ip_details["enriched_ip_count"] == 0
    assert ip_details["recent_sessions"][0]["security"]["is_anonymous"] is None


def test_user_profile_ip_details_ignore_malformed_ipregistry_response(
    test_db_session: DbSession,
    monkeypatch,
) -> None:
    user = _user(test_db_session, "ip-malformed@example.test")
    _session(test_db_session, user)

    def _mock_get(*_args: object, **_kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            json=["unexpected-payload"],
            request=httpx.Request("GET", "https://api.ipregistry.co/203.0.113.10"),
        )

    monkeypatch.setattr(
        "cctv_api.security.ip_intelligence.httpx.get",
        _mock_get,
    )
    client = _client_with_db(
        test_db_session,
        ACTOR_IP_ENRICHMENT_ENABLED=True,
        ACTOR_IP_IPREGISTRY_API_KEY="test-key",
    )

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/profile", headers=_admin_headers())

    assert response.status_code == 200
    ip_details = response.json()["ip_details"]
    assert ip_details["status"] == "unavailable"
    assert ip_details["recent_sessions"][0]["network"]["organization"] is None


def test_user_profile_returns_direct_linked_alert_summary_and_recent_items(
    test_db_session: DbSession,
) -> None:
    user = _user(test_db_session, "alerts@example.test")
    direct_old = _alert(
        test_db_session,
        actor_type=ActorType.user,
        actor_id=user.id,
        title="Direct old",
        severity=AlertSeverity.medium,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    direct_new = _alert(
        test_db_session,
        actor_type=ActorType.user,
        actor_id=user.id,
        title="Direct new",
        severity=AlertSeverity.high,
    )
    _alert(
        test_db_session,
        actor_type=ActorType.system,
        actor_id=None,
        title="Only mentions target",
        severity=AlertSeverity.critical,
        resource=f"user:{user.id}",
        metadata={"target_user_id": str(user.id)},
    )
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/profile", headers=_admin_headers())

    assert response.status_code == 200
    alerts = response.json()["alerts"]
    assert alerts["total_count"] == 2
    assert alerts["counts_by_status"] == {"open": 2, "acknowledged": 0, "resolved": 0}
    assert alerts["counts_by_severity"]["medium"] == 1
    assert alerts["counts_by_severity"]["high"] == 1
    assert alerts["counts_by_severity"]["critical"] == 0
    assert [item["alert_id"] for item in alerts["recent"]] == [
        str(direct_new.id),
        str(direct_old.id),
    ]
    assert alerts["recent"][0]["title"] == "Direct new"


def test_user_profile_returns_safe_login_baseline_summary(test_db_session: DbSession) -> None:
    user = _user(test_db_session, "baseline@example.test")
    baseline = LoginBaseline(
        user_id=user.id,
        known_ips=["203.0.113.10", "203.0.113.11"],
        known_countries=["PH", "SG"],
        known_user_agents=["ua-one", "ua-two", "ua-three"],
        last_login_ip="203.0.113.11",
        last_login_at=datetime.now(timezone.utc) - timedelta(minutes=3),
        last_login_country="PH",
        login_count=8,
        updated_at=datetime.now(timezone.utc),
    )
    test_db_session.add(baseline)
    test_db_session.commit()
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/admin/actors/user/{user.id}/profile", headers=_admin_headers())

    assert response.status_code == 200
    behavior_baseline = response.json()["behavior_baseline"]
    assert behavior_baseline["available"] is True
    assert behavior_baseline["login_count"] == 8
    assert behavior_baseline["last_login_country"] == "PH"
    assert behavior_baseline["known_ip_count"] == 2
    assert behavior_baseline["known_country_count"] == 2
    assert behavior_baseline["known_user_agent_count"] == 3
    assert "known_ips" not in behavior_baseline
    assert "known_countries" not in behavior_baseline
    assert "known_user_agents" not in behavior_baseline
    assert "last_login_ip" not in behavior_baseline


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
    assert data["behavior_baseline"] is None
    assert data["ip_details"] is None
    assert data["device_details"] is None


def test_gateway_profile_returns_direct_linked_alerts(test_db_session: DbSession) -> None:
    gateway = _gateway(test_db_session)
    direct = _alert(
        test_db_session,
        actor_type=ActorType.gateway,
        actor_id=gateway.id,
        title="Gateway rejected command",
        severity=AlertSeverity.high,
    )
    _alert(
        test_db_session,
        actor_type=ActorType.gateway,
        actor_id=uuid.uuid4(),
        title="Other gateway alert",
        severity=AlertSeverity.critical,
    )
    client = _client_with_db(test_db_session)

    response = client.get(
        f"/api/v1/admin/actors/gateway/{gateway.id}/profile",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    alerts = response.json()["alerts"]
    assert alerts["total_count"] == 1
    assert alerts["recent"][0]["alert_id"] == str(direct.id)


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
    assert data["behavior_baseline"] is None
    assert data["ip_details"] is None
    assert data["device_details"] is None


def test_system_actor_profile_returns_null_actor_alerts_only(test_db_session: DbSession) -> None:
    direct = _alert(
        test_db_session,
        actor_type=ActorType.system,
        actor_id=None,
        title="System backup alert",
        severity=AlertSeverity.medium,
    )
    _alert(
        test_db_session,
        actor_type=ActorType.break_glass,
        actor_id=None,
        title="Break-glass alert",
        severity=AlertSeverity.critical,
    )
    _alert(
        test_db_session,
        actor_type=ActorType.system,
        actor_id=uuid.uuid4(),
        title="System uuid actor alert",
        severity=AlertSeverity.high,
    )
    client = _client_with_db(test_db_session)

    response = client.get("/api/v1/admin/actors/system/none/profile", headers=_admin_headers())

    assert response.status_code == 200
    alerts = response.json()["alerts"]
    assert alerts["total_count"] == 1
    assert alerts["recent"][0]["alert_id"] == str(direct.id)


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
