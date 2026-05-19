from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import DpaKind
from cctv_api.models.tables import AuditLog, DpaArtifact, Site


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


def _client(test_db_session: DbSession) -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            AUDIT_HMAC_KEY_VERSION=1,
            AUDIT_HMAC_KEY="test-audit-key-with-enough-entropy",
        )
    )

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


def _seed_artifact(db: DbSession, *, kind: DpaKind = DpaKind.ropa) -> DpaArtifact:
    artifact = DpaArtifact(
        id=uuid.uuid4(),
        kind=kind,
        effective_at=datetime.now(timezone.utc),
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def _seed_site(db: DbSession, *, name: str = "HQ") -> Site:
    site = Site(id=uuid.uuid4(), name=name)
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


# ── DPA export ──


def test_dpa_export_unauthenticated(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post("/api/v1/admin/dpa/export", json={})
    assert resp.status_code == 401


def test_dpa_export_viewer_forbidden(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post("/api/v1/admin/dpa/export", json={}, headers=_VIEWER_HEADERS)
    assert resp.status_code == 403


def test_dpa_export_empty(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post("/api/v1/admin/dpa/export", json={}, headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["artifacts"] == []
    assert data["count"] == 0


def test_dpa_export_with_artifacts(test_db_session: DbSession) -> None:
    _seed_artifact(test_db_session, kind=DpaKind.ropa)
    _seed_artifact(test_db_session, kind=DpaKind.processor_dpa)
    c = _client(test_db_session)
    resp = c.post("/api/v1/admin/dpa/export", json={}, headers=_ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert len(data["artifacts"]) == 2
    audit = test_db_session.query(AuditLog).filter(
        AuditLog.action == "admin.dpa.export"
    ).first()
    assert audit is not None


def test_dpa_export_filtered_by_kind(test_db_session: DbSession) -> None:
    _seed_artifact(test_db_session, kind=DpaKind.ropa)
    _seed_artifact(test_db_session, kind=DpaKind.processor_dpa)
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/dpa/export",
        json={"kinds": ["ropa"]},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["artifacts"][0]["kind"] == "ropa"


def test_dpa_export_invalid_kind(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        "/api/v1/admin/dpa/export",
        json={"kinds": ["nonexistent"]},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 400
    assert "dpa-kind-invalid" in resp.json()["detail"]


# ── Signage attestation ──


def test_signage_unauthenticated(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/sites/{uuid.uuid4()}/signage-attest",
        json={"notes": "sign posted"},
    )
    assert resp.status_code == 401


def test_signage_viewer_forbidden(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/sites/{uuid.uuid4()}/signage-attest",
        json={"notes": "sign posted"},
        headers=_VIEWER_HEADERS,
    )
    assert resp.status_code == 403


def test_signage_site_not_found(test_db_session: DbSession) -> None:
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/sites/{uuid.uuid4()}/signage-attest",
        json={"notes": "sign posted"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "site-not-found"


def test_signage_success(test_db_session: DbSession) -> None:
    site = _seed_site(test_db_session, name="Main Office")
    c = _client(test_db_session)
    resp = c.post(
        f"/api/v1/admin/sites/{site.id}/signage-attest",
        json={"notes": "signage posted at main entrance"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["kind"] == "bystander_signage_attestation"
    assert data["site_id"] == str(site.id)
    assert "artifact_id" in data
    audit = test_db_session.query(AuditLog).filter(
        AuditLog.action == "admin.signage.attest"
    ).first()
    assert audit is not None
