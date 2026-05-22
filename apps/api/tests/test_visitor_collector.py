from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

import cctv_api.api.visitors as visitors
import cctv_api.security.dependencies as dependencies
from cctv_api.api.visitors import CURRENT_VISITOR_NOTICE_BODY
from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.tables import AuditLog, Role, Session as UserSession, User, UserRole, VisitorVisit
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
            location=IpLocation(country_code="PH", country="Philippines", city="Santa Rosa"),
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
    assert "known_ips" not in data
    audit = test_db_session.execute(
        select(AuditLog).where(AuditLog.action == "admin.visitor.visit.viewed")
    ).scalar_one()
    assert audit.resource == f"visitor-visit:{visit.id}"


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
