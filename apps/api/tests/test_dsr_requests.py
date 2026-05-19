from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import DpaKind, RequestType, SubjectType
from cctv_api.models.tables import AuditLog, DpaArtifact, DsrRequest, Site


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


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "requester_contact": "requester@example.test",
        "subject_type": "user",
        "request_type": "access",
        "due_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }
    payload.update(overrides)
    return payload


def _seed_dsr(db: DbSession, *, status: str = "open") -> DsrRequest:
    dsr = DsrRequest(
        id=uuid.uuid4(),
        requester_contact="existing@example.test",
        subject_type=SubjectType.user,
        request_type=RequestType.access,
        received_at=datetime.now(timezone.utc),
        due_at=datetime.now(timezone.utc) + timedelta(days=30),
        status=status,
    )
    db.add(dsr)
    db.commit()
    db.refresh(dsr)
    return dsr


def _seed_site(db: DbSession) -> Site:
    site = Site(id=uuid.uuid4(), name="HQ")
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


def _seed_artifact(db: DbSession) -> DpaArtifact:
    artifact = DpaArtifact(
        id=uuid.uuid4(),
        kind=DpaKind.ropa,
        effective_at=datetime.now(timezone.utc),
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def test_create_dsr_requires_auth(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    resp = client.post("/api/v1/admin/dsr-requests", json=_payload())
    assert resp.status_code == 401


def test_create_dsr_requires_admin(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    resp = client.post("/api/v1/admin/dsr-requests", json=_payload(), headers=_VIEWER_HEADERS)
    assert resp.status_code == 403


def test_create_dsr_success_with_links_and_audit(test_db_session: DbSession) -> None:
    site = _seed_site(test_db_session)
    artifact = _seed_artifact(test_db_session)
    client = _client(test_db_session)

    resp = client.post(
        "/api/v1/admin/dsr-requests",
        json=_payload(site_id=str(site.id), artifact_id=str(artifact.id), camera_scope_note="Lobby camera"),
        headers=_ADMIN_HEADERS,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["requester_contact"] == "requester@example.test"
    assert data["subject_type"] == "user"
    assert data["request_type"] == "access"
    assert data["status"] == "open"
    assert data["site_id"] == str(site.id)
    assert data["artifact_id"] == str(artifact.id)

    row = test_db_session.execute(select(DsrRequest).where(DsrRequest.id == data["request_id"])).scalar_one()
    assert row.camera_scope_note == "Lobby camera"

    audit = test_db_session.execute(select(AuditLog).where(AuditLog.action == "admin.dsr.created")).scalar_one()
    assert audit.payload["request_id"] == data["request_id"]
    assert audit.payload["artifact_id"] == str(artifact.id)


def test_list_dsr_requests_success(test_db_session: DbSession) -> None:
    _seed_dsr(test_db_session, status="open")
    _seed_dsr(test_db_session, status="completed")
    client = _client(test_db_session)

    resp = client.get("/api/v1/admin/dsr-requests?status=open", headers=_ADMIN_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["items"][0]["status"] == "open"


def test_get_dsr_success_and_audit(test_db_session: DbSession) -> None:
    dsr = _seed_dsr(test_db_session)
    client = _client(test_db_session)

    resp = client.get(f"/api/v1/admin/dsr-requests/{dsr.id}", headers=_ADMIN_HEADERS)

    assert resp.status_code == 200
    assert resp.json()["request_id"] == str(dsr.id)
    audit = test_db_session.execute(select(AuditLog).where(AuditLog.action == "admin.dsr.viewed")).scalar_one()
    assert audit.payload["request_id"] == str(dsr.id)


def test_update_dsr_success_and_audit(test_db_session: DbSession) -> None:
    dsr = _seed_dsr(test_db_session)
    client = _client(test_db_session)

    resp = client.patch(
        f"/api/v1/admin/dsr-requests/{dsr.id}",
        json={
            "status": "completed",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "outcome": "Request fulfilled by manual review.",
        },
        headers=_ADMIN_HEADERS,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["outcome"] == "Request fulfilled by manual review."

    test_db_session.refresh(dsr)
    assert dsr.status == "completed"

    audit = test_db_session.execute(select(AuditLog).where(AuditLog.action == "admin.dsr.updated")).scalar_one()
    assert audit.payload["before"]["status"] == "open"
    assert audit.payload["after"]["status"] == "completed"


def test_dsr_not_found(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    resp = client.get(f"/api/v1/admin/dsr-requests/{uuid.uuid4()}", headers=_ADMIN_HEADERS)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "dsr-request-not-found"


def test_create_dsr_invalid_values_return_bad_request(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    resp = client.post("/api/v1/admin/dsr-requests", json=_payload(subject_type="visitor"), headers=_ADMIN_HEADERS)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "subject-type-invalid"

    resp = client.post("/api/v1/admin/dsr-requests", json=_payload(request_type="download"), headers=_ADMIN_HEADERS)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "request-type-invalid"

    resp = client.post("/api/v1/admin/dsr-requests", json=_payload(status="waiting"), headers=_ADMIN_HEADERS)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "dsr-status-invalid"


def test_create_dsr_missing_linked_records(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    resp = client.post("/api/v1/admin/dsr-requests", json=_payload(site_id=str(uuid.uuid4())), headers=_ADMIN_HEADERS)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "site-not-found"

    resp = client.post("/api/v1/admin/dsr-requests", json=_payload(artifact_id=str(uuid.uuid4())), headers=_ADMIN_HEADERS)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "artifact-not-found"
