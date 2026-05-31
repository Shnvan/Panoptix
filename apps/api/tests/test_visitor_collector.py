from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

import cctv_api.api.visitors as visitors
import cctv_api.security.dependencies as dependencies
from cctv_api.api.visitors import CURRENT_VISITOR_NOTICE_BODY
from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.integrations.github_invites import GitHubInviteResult
from cctv_api.main import create_app
from cctv_api.models.enums import AlertNotificationStatus, AlertSeverity, VisitorAccessRequestStatus
from cctv_api.models.tables import (
    Alert,
    AlertNotification,
    AuditLog,
    Role,
    Session as UserSession,
    User,
    UserRole,
    VisitorAccessRequest,
    VisitorVisit,
)
from cctv_api.security.identity import Principal, PrincipalKind
from cctv_api.security.ip_intelligence import (
    IpIntelligenceProviderState,
    IpIntelligenceResult,
    IpLocation,
    IpNetwork,
    IpSecurity,
)
from cctv_api.security.rate_limit import get_rate_limiter

VISITOR_SIGNING_KEY = "test-visitor-cookie-signing-key-with-enough-entropy"
SESSION_SIGNING_KEY = "test-session-signing-key-with-enough-entropy"
CSRF_SIGNING_KEY = "test-csrf-signing-key-with-enough-entropy"

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


class _Provider:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.lookups: list[str] = []

    def lookup(self, ip: str) -> IpIntelligenceResult | None:
        self.lookups.append(ip)
        if self.fails:
            raise RuntimeError("provider-down")
        return IpIntelligenceResult(
            ip_type="IPv4",
            location=IpLocation(
                country_code="PH",
                country="Philippines",
                city="Santa Rosa",
                timezone="Asia/Manila",
            ),
            network=IpNetwork(asn=9299, organization="PLDT"),
            security=IpSecurity(is_vpn=False, is_proxy=False, is_threat=False),
        )


class _BrowserVerifier:
    def __init__(_self, _settings: Settings) -> None:
        pass

    def verify_browser_request(_self, _request):  # type: ignore[no-untyped-def]
        return Principal(
            kind=PrincipalKind.USER,
            subject="admin@example.test",
            email="admin@example.test",
            roles=frozenset({"admin"}),
            is_dev=False,
        )


_SAFE_PRODUCTION_OVERRIDES = {
    "CF_ACCESS_ISSUER": "https://team.cloudflareaccess.com",
    "CF_ACCESS_AUD_DASHBOARD": "dashboard-aud",
    "CF_ACCESS_AUD_ADMIN": "admin-aud",
    "CF_ACCESS_AUD_GATEWAY": "gateway-aud",
    "CF_ACCESS_JWKS_URL": "https://team.cloudflareaccess.com/cdn-cgi/access/certs",
    "DATABASE_URL": "postgresql+psycopg://user:pass@db:5432/panoptix",
    "MIGRATION_DATABASE_URL": "postgresql+psycopg://migrator:pass@db:5432/panoptix",
    "GATEWAY_SERVICE_TOKEN": "real-gateway-token",
    "GATEWAY_COMMAND_SIGNING_KEY": "real-signing-key",
}


def _client(test_db_session: DbSession, **settings_overrides: object) -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            VISITOR_COLLECTOR_ENABLED=True,
            VISITOR_COOKIE_SIGNING_KEY=VISITOR_SIGNING_KEY,
            AUDIT_HMAC_KEY_VERSION=1,
            AUDIT_HMAC_KEY="test-audit-key-with-enough-entropy",
            **settings_overrides,
        )
    )

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app, base_url="https://testserver")


def _collect_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "notice_version": "2026-05-22",
        "notice_acknowledged": True,
        "page_path": "/",
        "screen_width": 1920,
        "screen_height": 1080,
        "timezone": "Asia/Manila",
        "language": "en-PH",
    }
    values.update(overrides)
    return values


def _patch_provider(monkeypatch, provider: _Provider) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        visitors,
        "get_ip_intelligence_provider",
        lambda _settings: IpIntelligenceProviderState(
            status="ok",
            provider_name="ipregistry",
            provider=provider,
        ),
    )


def test_visitor_notice_and_collection_store_security_core_subset(
    test_db_session: DbSession,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    provider = _Provider()
    _patch_provider(monkeypatch, provider)
    client = _client(test_db_session, TRUST_CF_CONNECTING_IP=True)

    notice = client.get("/api/v1/visitor/notice")
    response = client.post(
        "/api/v1/visitor/collect",
        headers={
            "cf-connecting-ip": "122.54.90.97",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/148.0 Safari/537.36",
        },
        json=_collect_payload(),
    )

    assert notice.status_code == 200
    assert notice.json()["body"] == CURRENT_VISITOR_NOTICE_BODY
    assert response.status_code == 201
    assert response.json()["status"] == "recorded"
    assert client.cookies.get("panoptix_visitor") is not None
    row = test_db_session.execute(select(VisitorVisit)).scalar_one()
    assert row.ip == "122.54.90.97"
    assert row.page_path == "/"
    assert row.ip_enrichment_status == "ok"
    assert row.ip_enrichment_provider == "ipregistry"
    assert row.ip_enrichment["location"]["country"] == "Philippines"
    assert row.ip_enrichment["security"]["is_threat"] is False
    assert "latitude" not in row.ip_enrichment
    assert "currency" not in row.ip_enrichment
    assert provider.lookups == ["122.54.90.97"]


def test_visitor_collection_creates_sanitized_high_alert(
    test_db_session: DbSession,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    _patch_provider(monkeypatch, _Provider())
    client = _client(test_db_session, TRUST_CF_CONNECTING_IP=True)

    response = client.post(
        "/api/v1/visitor/collect",
        headers={"cf-connecting-ip": "122.54.90.97", "cf-ipcountry": "PH"},
        json=_collect_payload(
            page_path="/entry",
            timezone="America/New_York",
            language="en-US",
            webrtc_context={
                "available": True,
                "tested": True,
                "candidate_count": 1,
                "candidate_types": ["srflx"],
                "public_ip_candidates": ["122.54.90.98"],
                "raw_candidates": ["candidate:raw-secret"],
            },
        ),
    )

    assert response.status_code == 201
    visit = test_db_session.execute(select(VisitorVisit)).scalar_one()
    alert = test_db_session.execute(select(Alert).where(Alert.source == "visitor_entry")).scalar_one()
    metadata = alert.metadata_json
    assert alert.title == "Visitor continued to secure sign-in"
    assert alert.severity == AlertSeverity.high
    assert alert.resource == f"visitor_visit:{visit.id}"
    assert metadata == {
        "visit_id": str(visit.id),
        "page_path": "/entry",
        "cf_country": "PH",
        "risk_flags": [
            "timezone_ip_mismatch",
            "language_country_mismatch",
            "webrtc_public_ip_request_ip_mismatch",
        ],
        "repeat_visitor_count": 1,
        "ip_enrichment_status": "ok",
    }
    joined = str(metadata)
    assert "raw_candidates" not in joined
    assert "cookie" not in joined.lower()
    assert "token" not in joined.lower()


def test_visitor_collection_emails_active_admins_when_enabled(
    test_db_session: DbSession,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    _patch_provider(monkeypatch, _Provider())
    admin_role = Role(id=20, name="admin")
    viewer_role = Role(id=21, name="viewer")
    admin = User(id=uuid.uuid4(), email="admin-entry@example.test", idp_subject="admin-entry")
    disabled_admin = User(
        id=uuid.uuid4(),
        email="disabled-entry@example.test",
        idp_subject="disabled-entry",
        disabled_at=datetime.now(timezone.utc),
    )
    viewer = User(id=uuid.uuid4(), email="viewer-entry@example.test", idp_subject="viewer-entry")
    test_db_session.add_all([admin_role, viewer_role])
    test_db_session.flush()
    for user in (admin, disabled_admin, viewer):
        test_db_session.add(user)
        test_db_session.flush()
    test_db_session.add_all(
        [
            UserRole(user_id=admin.id, role_id=admin_role.id),
            UserRole(user_id=disabled_admin.id, role_id=admin_role.id),
            UserRole(user_id=viewer.id, role_id=viewer_role.id),
        ]
    )
    test_db_session.commit()
    client = _client(
        test_db_session,
        ALERT_EMAIL_ENABLED=True,
        ALERT_EMAIL_SMTP_HOST="smtp.example.test",
        ALERT_EMAIL_SMTP_PASSWORD="smtp-password-with-enough-length",
        ALERT_EMAIL_FROM="alerts@example.test",
        ALERT_EMAIL_RECIPIENT_MODE="admins",
    )

    with patch("cctv_api.security.alerts.send_alert_email") as send_email:
        response = client.post("/api/v1/visitor/collect", json=_collect_payload(page_path="/entry"))

    assert response.status_code == 201
    send_email.assert_called_once()
    assert send_email.call_args.kwargs["recipient"] == "admin-entry@example.test"
    notification = test_db_session.execute(select(AlertNotification)).scalar_one()
    assert notification.recipient == "admin-entry@example.test"
    assert notification.status == AlertNotificationStatus.sent


def test_repeated_visitor_collections_create_separate_alerts(
    test_db_session: DbSession,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    _patch_provider(monkeypatch, _Provider())
    client = _client(test_db_session)

    first = client.post("/api/v1/visitor/collect", json=_collect_payload())
    second = client.post("/api/v1/visitor/collect", json=_collect_payload(page_path="/entry"))

    assert first.status_code == 201
    assert second.status_code == 201
    alerts = test_db_session.execute(
        select(Alert).where(Alert.source == "visitor_entry").order_by(Alert.created_at.asc())
    ).scalars().all()
    assert len(alerts) == 2
    assert alerts[0].resource != alerts[1].resource
    assert alerts[0].metadata_json["repeat_visitor_count"] == 1
    assert alerts[1].metadata_json["repeat_visitor_count"] == 2


def test_visitor_collection_stores_expanded_context_and_server_headers(
    test_db_session: DbSession,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    _patch_provider(monkeypatch, _Provider())
    client = _client(test_db_session, TRUST_CF_CONNECTING_IP=True)
    payload = _collect_payload(
        page_path="/entry",
        referrer="https://example.test/source",
        viewport_width=1440,
        viewport_height=900,
        device_pixel_ratio=1.25,
        touch_supported=True,
        max_touch_points=5,
        color_scheme="dark",
        cookies_enabled=True,
        do_not_track="1",
        global_privacy_control=True,
        languages=["en-PH", "fil-PH"],
        network_context={
            "effective_type": "4g",
            "downlink_mbps": 10.5,
            "rtt_ms": 75,
            "save_data": False,
        },
        timing_context={
            "notice_loaded_at_ms": 30,
            "continue_clicked_at_ms": 2500,
            "collect_started_at_ms": 2510,
            "webrtc_elapsed_ms": 900,
        },
        webrtc_context={
            "available": True,
            "tested": True,
            "candidate_count": 3,
            "candidate_types": ["host", "srflx", "relay"],
            "local_ip_candidates": ["192.168.1.10"],
            "public_ip_candidates": ["122.54.90.97"],
            "relay_ip_candidates": ["203.0.113.20"],
            "mdns_hostname_seen": True,
            "error": None,
        },
    )

    response = client.post(
        "/api/v1/visitor/collect",
        headers={
            "cf-connecting-ip": "122.54.90.97",
            "cf-ray": "abc123-MNL",
            "cf-ipcountry": "PH",
        },
        json=payload,
    )

    assert response.status_code == 201
    row = test_db_session.execute(select(VisitorVisit)).scalar_one()
    assert row.browser_context["referrer"] == "https://example.test/source"
    assert row.browser_context["viewport"] == {"width": 1440, "height": 900}
    assert row.browser_context["privacy"] == {
        "do_not_track": "1",
        "global_privacy_control": True,
    }
    assert row.network_context == {
        "effective_type": "4g",
        "downlink_mbps": 10.5,
        "rtt_ms": 75,
        "save_data": False,
    }
    assert row.timing_context["webrtc_elapsed_ms"] == 900
    assert row.webrtc_context["public_ip_candidates"] == ["122.54.90.97"]
    assert row.server_context == {"cf_ray_id": "abc123-MNL", "cf_country": "PH"}


def test_visitor_collection_filters_raw_or_invalid_webrtc_values(
    test_db_session: DbSession,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    _patch_provider(monkeypatch, _Provider())
    client = _client(test_db_session)

    response = client.post(
        "/api/v1/visitor/collect",
        json=_collect_payload(
            webrtc_context={
                "available": True,
                "tested": True,
                "candidate_count": 2,
                "candidate_types": ["host", "made-up-type"],
                "local_ip_candidates": ["192.168.1.10", "candidate:raw 1 udp 1 192.168.1.11"],
                "public_ip_candidates": ["122.54.90.97", "not-an-ip"],
                "relay_ip_candidates": ["203.0.113.20"],
                "mdns_hostname_seen": True,
                "error": "some verbose provider/browser failure detail",
                "raw_sdp": "v=0...",
                "raw_candidates": ["candidate:raw"],
            }
        ),
    )

    assert response.status_code == 201
    row = test_db_session.execute(select(VisitorVisit)).scalar_one()
    assert row.webrtc_context["candidate_types"] == ["host", "unknown"]
    assert row.webrtc_context["local_ip_candidates"] == ["192.168.1.10"]
    assert row.webrtc_context["public_ip_candidates"] == ["122.54.90.97"]
    assert row.webrtc_context["error"] == "unknown"
    assert "raw_sdp" not in row.webrtc_context
    assert "raw_candidates" not in row.webrtc_context


def test_visitor_collection_requires_current_acknowledged_notice(test_db_session: DbSession) -> None:
    client = _client(test_db_session)

    missing_ack = client.post(
        "/api/v1/visitor/collect",
        json=_collect_payload(notice_acknowledged=False),
    )
    stale_notice = client.post(
        "/api/v1/visitor/collect",
        json=_collect_payload(notice_version="old"),
    )

    assert missing_ack.status_code == 400
    assert missing_ack.json()["detail"] == "visitor-notice-acknowledgement-required"
    assert stale_notice.status_code == 409
    assert stale_notice.json()["detail"] == "visitor-notice-version-mismatch"
    assert test_db_session.execute(select(VisitorVisit)).scalars().all() == []


def test_visitor_collection_degrades_when_ipregistry_fails(
    test_db_session: DbSession,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    _patch_provider(monkeypatch, _Provider(fails=True))
    client = _client(test_db_session)

    response = client.post("/api/v1/visitor/collect", json=_collect_payload())

    assert response.status_code == 201
    row = test_db_session.execute(select(VisitorVisit)).scalar_one()
    assert row.ip_enrichment_status == "unavailable"
    assert row.ip_enrichment["location"]["country"] is None


def test_visitor_collection_is_rate_limited(test_db_session: DbSession) -> None:
    get_rate_limiter().reset()
    client = _client(
        test_db_session,
        RATE_LIMIT_VISITOR_COLLECT_MAX=1,
        RATE_LIMIT_VISITOR_COLLECT_WINDOW=60,
    )

    assert client.post("/api/v1/visitor/collect", json=_collect_payload()).status_code == 201
    response = client.post("/api/v1/visitor/collect", json=_collect_payload())

    assert response.status_code == 429
    assert response.json()["detail"] == "visitor-collect-rate-limited"
    get_rate_limiter().reset()


def test_public_access_request_creates_pending_request_and_links_visitor_cookie(
    test_db_session: DbSession,
) -> None:
    client = _client(test_db_session)
    collect = client.post("/api/v1/visitor/collect", json=_collect_payload())
    assert collect.status_code == 201

    response = client.post(
        "/api/v1/visitor/access-requests",
        headers={"user-agent": "Mozilla/5.0"},
        json={
            "applicant_name": "Ivan Liao",
            "email": "IVAN@example.test",
            "organization": "Security Team",
            "reason": "Need viewer access for CCTV monitoring.",
            "requested_role": "viewer",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    row = test_db_session.execute(select(VisitorAccessRequest)).scalar_one()
    visit = test_db_session.execute(select(VisitorVisit)).scalar_one()
    assert row.email == "ivan@example.test"
    assert row.requested_role == "viewer"
    assert row.status == VisitorAccessRequestStatus.pending
    assert str(row.visitor_visit_id) == str(visit.id)
    audit = test_db_session.execute(
        select(AuditLog).where(AuditLog.action == "visitor.access_request.created")
    ).scalar_one()
    assert audit.resource == f"visitor-access-request:{row.id}"


def test_public_access_request_forces_admin_request_to_viewer(
    test_db_session: DbSession,
) -> None:
    client = _client(test_db_session)

    response = client.post(
        "/api/v1/visitor/access-requests",
        json={
            "applicant_name": "Ivan Liao",
            "email": "ivan@example.test",
            "organization": "Security Team",
            "reason": "Need access for CCTV monitoring.",
            "requested_role": "admin",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    row = test_db_session.execute(select(VisitorAccessRequest)).scalar_one()
    assert row.requested_role == "viewer"


def test_public_access_request_without_role_defaults_to_viewer(
    test_db_session: DbSession,
) -> None:
    client = _client(test_db_session)

    response = client.post(
        "/api/v1/visitor/access-requests",
        json={
            "applicant_name": "Ivan Liao",
            "email": "ivan@example.test",
            "organization": "Security Team",
            "reason": "Need access for CCTV monitoring.",
        },
    )

    assert response.status_code == 201
    row = test_db_session.execute(select(VisitorAccessRequest)).scalar_one()
    assert row.requested_role == "viewer"


def test_public_access_request_rejects_invalid_duplicate_and_rate_limited_requests(
    test_db_session: DbSession,
) -> None:
    get_rate_limiter().reset()
    client = _client(
        test_db_session,
        RATE_LIMIT_VISITOR_COLLECT_MAX=10,
        RATE_LIMIT_VISITOR_COLLECT_WINDOW=60,
    )
    invalid_email = client.post(
        "/api/v1/visitor/access-requests",
        json={
            "applicant_name": "Ivan",
            "email": "not-an-email",
            "reason": "Need access.",
            "requested_role": "viewer",
        },
    )
    invalid_role = client.post(
        "/api/v1/visitor/access-requests",
        json={
            "applicant_name": "Ivan",
            "email": "ivan@example.test",
            "reason": "Need access.",
            "requested_role": "owner",
        },
    )
    first = client.post(
        "/api/v1/visitor/access-requests",
        json={
            "applicant_name": "Ivan",
            "email": "ivan@example.test",
            "reason": "Need access.",
            "requested_role": "viewer",
        },
    )
    duplicate = client.post(
        "/api/v1/visitor/access-requests",
        json={
            "applicant_name": "Ivan",
            "email": "ivan@example.test",
            "reason": "Need access again.",
            "requested_role": "viewer",
        },
    )

    assert invalid_email.status_code == 400
    assert invalid_email.json()["detail"] == "email-invalid"
    assert invalid_role.status_code == 400
    assert invalid_role.json()["detail"] == "requested-role-invalid"
    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "access-request-already-pending"

    get_rate_limiter().reset()
    limited_client = _client(
        test_db_session,
        RATE_LIMIT_VISITOR_COLLECT_MAX=1,
        RATE_LIMIT_VISITOR_COLLECT_WINDOW=60,
    )
    assert limited_client.post(
        "/api/v1/visitor/access-requests",
        json={
            "applicant_name": "One",
            "email": "one@example.test",
            "reason": "Need access.",
            "requested_role": "viewer",
        },
    ).status_code == 201
    limited = limited_client.post(
        "/api/v1/visitor/access-requests",
        json={
            "applicant_name": "Two",
            "email": "two@example.test",
            "reason": "Need access.",
            "requested_role": "viewer",
        },
    )
    assert limited.status_code == 429
    assert limited.json()["detail"] == "access-request-rate-limited"
    get_rate_limiter().reset()


def test_admin_access_request_review_requires_admin_and_supports_reject(
    test_db_session: DbSession,
) -> None:
    row = VisitorAccessRequest(
        id=uuid.uuid4(),
        applicant_name="Ivan",
        email="ivan@example.test",
        reason="Need access.",
        requested_role="viewer",
        status=VisitorAccessRequestStatus.pending,
    )
    test_db_session.add(row)
    test_db_session.commit()
    client = _client(test_db_session)

    unauthenticated = client.get("/api/v1/admin/access-requests")
    viewer = client.get("/api/v1/admin/access-requests", headers=_VIEWER_HEADERS)
    listed = client.get("/api/v1/admin/access-requests", headers=_ADMIN_HEADERS)
    rejected = client.post(
        f"/api/v1/admin/access-requests/{row.id}/reject",
        headers=_ADMIN_HEADERS,
        json={"decision_note": "Not approved for pilot."},
    )

    assert unauthenticated.status_code == 401
    assert viewer.status_code == 403
    assert listed.status_code == 200
    assert listed.json()["items"][0]["email"] == "ivan@example.test"
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    audit = test_db_session.execute(
        select(AuditLog).where(AuditLog.action == "admin.access_request.rejected")
    ).scalar_one()
    assert audit.resource == f"visitor-access-request:{row.id}"


def test_admin_access_request_approve_invites_and_assigns_requested_role(
    test_db_session: DbSession,
) -> None:
    role = Role(id=1, name="viewer")
    row = VisitorAccessRequest(
        id=uuid.uuid4(),
        applicant_name="Ivan",
        email="ivan@example.test",
        organization="Security Team",
        reason="Need access.",
        requested_role="viewer",
        status=VisitorAccessRequestStatus.pending,
    )
    test_db_session.add_all([role, row])
    test_db_session.commit()
    client = _client(test_db_session, GITHUB_INVITES_ENABLED=True)

    with patch("cctv_api.api.visitors.create_github_org_invitation") as mock_invite:
        mock_invite.return_value = GitHubInviteResult(
            invitation_id=123,
            org="panoptix-test",
            status="invited",
        )
        response = client.post(
            f"/api/v1/admin/access-requests/{row.id}/approve",
            headers=_ADMIN_HEADERS,
            json={"decision_note": "Approved for pilot."},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert data["github_invitation_id"] == 123
    user = test_db_session.execute(select(User).where(User.email == "ivan@example.test")).scalar_one()
    assigned = test_db_session.execute(select(UserRole).where(UserRole.user_id == str(user.id))).scalar_one()
    assert assigned.role_id == 1
    mock_invite.assert_called_once()
    audit = test_db_session.execute(
        select(AuditLog).where(AuditLog.action == "admin.access_request.approved")
    ).scalar_one()
    assert audit.payload["target_email"] == "ivan@example.test"


def test_admin_access_request_approve_denies_disabled_user_without_invite(
    test_db_session: DbSession,
) -> None:
    role = Role(id=1, name="viewer")
    user = User(id=uuid.uuid4(), email="disabled@example.test", disabled_at=datetime.now(timezone.utc))
    row = VisitorAccessRequest(
        id=uuid.uuid4(),
        applicant_name="Disabled User",
        email="disabled@example.test",
        reason="Need access.",
        requested_role="viewer",
        status=VisitorAccessRequestStatus.pending,
    )
    test_db_session.add_all([role, user, row])
    test_db_session.commit()
    client = _client(test_db_session, GITHUB_INVITES_ENABLED=True)

    with patch("cctv_api.api.visitors.create_github_org_invitation") as mock_invite:
        response = client.post(
            f"/api/v1/admin/access-requests/{row.id}/approve",
            headers=_ADMIN_HEADERS,
            json={"decision_note": "Check disabled account."},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "user-disabled"
    mock_invite.assert_not_called()
    test_db_session.refresh(row)
    assert row.status == VisitorAccessRequestStatus.pending
    audit = test_db_session.execute(
        select(AuditLog).where(AuditLog.action == "admin.access_request.approve.denied.user_disabled")
    ).scalar_one()
    assert audit.resource == f"visitor-access-request:{row.id}"


def test_admin_visitor_read_apis_require_admin_and_audit_detail(
    test_db_session: DbSession,
) -> None:
    visit = VisitorVisit(
        id=uuid.uuid4(),
        page_path="/",
        notice_version="2026-05-22",
        ip="203.0.113.5",
        ua="Mozilla/5.0 Chrome/148.0",
        screen_width=1366,
        screen_height=768,
        browser_timezone="Asia/Manila",
        browser_language="en",
        ip_enrichment_status="not_configured",
        ip_enrichment_provider=None,
        ip_enrichment={},
    )
    test_db_session.add(visit)
    test_db_session.commit()
    client = _client(test_db_session)

    denied = client.get("/api/v1/admin/visitor-visits", headers=_VIEWER_HEADERS)
    listed = client.get("/api/v1/admin/visitor-visits", headers=_ADMIN_HEADERS)
    detail = client.get(f"/api/v1/admin/visitor-visits/{visit.id}", headers=_ADMIN_HEADERS)

    assert denied.status_code == 403
    assert listed.status_code == 200
    assert listed.json()["items"][0]["login"]["logged_in"] is False
    assert detail.status_code == 200
    data = detail.json()
    assert data["visit_id"] == str(visit.id)
    assert data["ip_details"]["ip"] == "203.0.113.5"
    assert data["screen"] == {"width": 1366, "height": 768}
    assert data["browser_context"] == {}
    assert data["risk_context"]["repeat_visitor_count"] == 1
    assert "known_ips" not in data
    audit = test_db_session.execute(
        select(AuditLog).where(AuditLog.action == "admin.visitor.visit.viewed")
    ).scalar_one()
    assert audit.resource == f"visitor-visit:{visit.id}"


def test_admin_visitor_detail_returns_expanded_risk_context(
    test_db_session: DbSession,
) -> None:
    user = User(email="admin@example.test", idp_subject="admin@example.test")
    test_db_session.add(user)
    test_db_session.flush()
    session = UserSession(user_id=user.id, ip="122.54.90.98", ua_fp="Mozilla/5.0 Chrome/148.0")
    visit = VisitorVisit(
        id=uuid.uuid4(),
        page_path="/entry",
        notice_version="2026-05-22",
        ip="122.54.90.97",
        ua="Mozilla/5.0 Chrome/148.0",
        screen_width=1366,
        screen_height=768,
        browser_timezone="America/New_York",
        browser_language="en-US",
        ip_enrichment_status="ok",
        ip_enrichment_provider="ipregistry",
        ip_enrichment={
            "ip_type": "IPv4",
            "location": {
                "country_code": "PH",
                "country": "Philippines",
                "timezone": "Asia/Manila",
            },
            "network": {},
            "company": {},
            "carrier": {},
            "security": {},
        },
        browser_context={"languages": ["en-US"], "referrer": "https://example.test"},
        network_context={"effective_type": "4g"},
        webrtc_context={"public_ip_candidates": ["122.54.90.99"]},
        timing_context={"collect_started_at_ms": 1200},
        server_context={"cf_ray_id": "abc123-MNL", "cf_country": "PH"},
    )
    test_db_session.add(session)
    test_db_session.flush()
    visit.user_id = user.id
    visit.session_id = session.id
    test_db_session.add(visit)
    test_db_session.commit()
    client = _client(test_db_session)

    response = client.get(f"/api/v1/admin/visitor-visits/{visit.id}", headers=_ADMIN_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["entry_context"]["referrer"] == "https://example.test"
    assert data["network_context"] == {"effective_type": "4g"}
    assert data["webrtc_details"] == {"public_ip_candidates": ["122.54.90.99"]}
    assert data["server_context"] == {"cf_ray_id": "abc123-MNL", "cf_country": "PH"}
    assert data["login"]["ip"] == "122.54.90.98"
    assert data["risk_context"] == {
        "timezone_ip_mismatch": True,
        "language_country_mismatch": True,
        "webrtc_public_ip_request_ip_mismatch": True,
        "ip_changed_between_entry_and_login": True,
        "repeat_visitor_count": 1,
    }


def test_new_authenticated_session_links_entry_visit(
    test_db_session: DbSession,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(dependencies, "CloudflareAccessVerifier", _BrowserVerifier)
    user = User(email="admin@example.test", idp_subject="admin@example.test")
    role = Role(id=1, name="admin")
    test_db_session.add_all([user, role])
    test_db_session.flush()
    test_db_session.add(UserRole(user_id=user.id, role_id=role.id))
    test_db_session.commit()
    browser = _production_browser_client(test_db_session)
    visit_client = _client(test_db_session)
    collect = visit_client.post("/api/v1/visitor/collect", json=_collect_payload())
    visitor_cookie = visit_client.cookies.get("panoptix_visitor")
    browser.cookies.set("panoptix_visitor", visitor_cookie or "", domain="testserver.local", path="/")

    response = browser.get("/api/v1/me")

    assert collect.status_code == 201
    assert response.status_code == 200
    visit = test_db_session.execute(select(VisitorVisit)).scalar_one()
    session = test_db_session.execute(select(UserSession)).scalar_one()
    assert str(visit.user_id) == str(user.id)
    assert str(visit.session_id) == str(session.id)
    assert visit.logged_in_at is not None


def test_stale_visitor_cookie_does_not_break_session_creation(
    test_db_session: DbSession,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(dependencies, "CloudflareAccessVerifier", _BrowserVerifier)
    browser = _production_browser_client(test_db_session)
    browser.cookies.set("panoptix_visitor", "bad-cookie", domain="testserver.local", path="/")

    response = browser.get("/api/v1/me")

    assert response.status_code == 200
    assert len(test_db_session.execute(select(UserSession)).scalars().all()) == 1


def _production_browser_client(test_db_session: DbSession) -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="production",
            ALLOW_DEV_AUTH=False,
            SESSION_SIGNING_KEY=SESSION_SIGNING_KEY,
            CSRF_SIGNING_KEY=CSRF_SIGNING_KEY,
            VISITOR_COOKIE_SIGNING_KEY=VISITOR_SIGNING_KEY,
            AUDIT_HMAC_KEY_VERSION=1,
            AUDIT_HMAC_KEY="test-audit-key-with-enough-entropy",
            **_SAFE_PRODUCTION_OVERRIDES,
        )
    )

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app, base_url="https://testserver")
