from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import ActorType
from cctv_api.models.tables import AuditHmacKey, AuditLog
from cctv_api.security.audit import (
    AuditLogError,
    REDACTED_VALUE,
    record_audit_event,
    scrub_audit_payload,
    verify_audit_chain,
)
from cctv_api.security.sessions import create_session
from cctv_api.security.users import get_or_create_user


AUDIT_HMAC_KEY_VERSION = 1
AUDIT_HMAC_KEY = "test-audit-hmac-key-with-enough-entropy"
AUDIT_HMAC_KEY_VERSION_2 = 2
AUDIT_HMAC_KEY_2 = "test-second-audit-hmac-key-with-enough-entropy"


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


def _record_test_audit_row(
    db: DbSession,
    action: str,
    *,
    audit_hmac_key_version: int = AUDIT_HMAC_KEY_VERSION,
    audit_hmac_key: str = AUDIT_HMAC_KEY,
) -> AuditLog:
    return record_audit_event(
        db,
        actor_type=ActorType.user,
        audit_hmac_key_version=audit_hmac_key_version,
        audit_hmac_key=audit_hmac_key,
        action=action,
        resource=f"camera:{action}",
    )


def test_admin_audit_verify_requires_authentication(test_db_session: DbSession) -> None:
    client = _client_with_db(test_db_session)

    response = client.get("/api/v1/admin/audit/verify")

    assert response.status_code == 401
    assert response.json()["detail"] == "cf-access-token-required"


def test_admin_audit_verify_requires_admin_role(test_db_session: DbSession) -> None:
    client = _client_with_db(test_db_session)

    response = client.get("/api/v1/admin/audit/verify", headers=_auth_headers())

    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_admin_audit_verify_accepts_empty_chain(test_db_session: DbSession) -> None:
    client = _client_with_db(test_db_session)

    response = client.get(
        "/api/v1/admin/audit/verify",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "checked": 0, "error": None}


def test_admin_audit_verify_accepts_valid_chain(test_db_session: DbSession) -> None:
    _record_test_audit_row(test_db_session, "test.audit.first")
    _record_test_audit_row(test_db_session, "test.audit.second")
    client = _client_with_db(test_db_session)

    response = client.get(
        "/api/v1/admin/audit/verify",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "checked": 2, "error": None}
    audit_rows = test_db_session.execute(select(AuditLog).order_by(AuditLog.id)).scalars().all()
    assert [row.action for row in audit_rows] == ["test.audit.first", "test.audit.second"]


def test_admin_audit_verify_accepts_inclusive_subrange(test_db_session: DbSession) -> None:
    first = _record_test_audit_row(test_db_session, "test.audit.first")
    second = _record_test_audit_row(test_db_session, "test.audit.second")
    third = _record_test_audit_row(test_db_session, "test.audit.third")
    client = _client_with_db(test_db_session)

    response = client.get(
        f"/api/v1/admin/audit/verify?start_id={second.id}&end_id={third.id}",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "checked": 2, "error": None}
    assert second.prev_hash == first.hash


def test_admin_audit_verify_start_id_uses_prior_hash(test_db_session: DbSession) -> None:
    first = _record_test_audit_row(test_db_session, "test.audit.first")
    second = _record_test_audit_row(test_db_session, "test.audit.second")
    _record_test_audit_row(test_db_session, "test.audit.third")
    second.prev_hash = "tampered-previous-hash"
    client = _client_with_db(test_db_session)

    response = client.get(
        f"/api/v1/admin/audit/verify?start_id={second.id}&end_id={second.id}",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": False,
        "checked": 1,
        "error": "audit-chain-prev-hash-mismatch",
    }
    assert first.hash != second.prev_hash


def test_admin_audit_verify_accepts_end_id_only(test_db_session: DbSession) -> None:
    _record_test_audit_row(test_db_session, "test.audit.first")
    second = _record_test_audit_row(test_db_session, "test.audit.second")
    _record_test_audit_row(test_db_session, "test.audit.third")
    client = _client_with_db(test_db_session)

    response = client.get(
        f"/api/v1/admin/audit/verify?end_id={second.id}",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "checked": 2, "error": None}


def test_admin_audit_verify_accepts_start_id_only(test_db_session: DbSession) -> None:
    _record_test_audit_row(test_db_session, "test.audit.first")
    second = _record_test_audit_row(test_db_session, "test.audit.second")
    _record_test_audit_row(test_db_session, "test.audit.third")
    client = _client_with_db(test_db_session)

    response = client.get(
        f"/api/v1/admin/audit/verify?start_id={second.id}",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "checked": 2, "error": None}


def test_admin_audit_verify_accepts_empty_range(test_db_session: DbSession) -> None:
    _record_test_audit_row(test_db_session, "test.audit.first")
    client = _client_with_db(test_db_session)

    response = client.get(
        "/api/v1/admin/audit/verify?start_id=999",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "checked": 0, "error": None}


def test_admin_audit_verify_rejects_invalid_bounds(test_db_session: DbSession) -> None:
    client = _client_with_db(test_db_session)

    for query in ("start_id=0", "end_id=0", "start_id=3&end_id=2"):
        response = client.get(f"/api/v1/admin/audit/verify?{query}", headers=_admin_headers())
        assert response.status_code == 422


def test_admin_audit_verify_accepts_mixed_key_versions(test_db_session: DbSession) -> None:
    _record_test_audit_row(test_db_session, "test.audit.first")
    _record_test_audit_row(
        test_db_session,
        "test.audit.second",
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION_2,
        audit_hmac_key=AUDIT_HMAC_KEY_2,
    )
    client = _client_with_db(test_db_session)

    response = client.get("/api/v1/admin/audit/verify", headers=_admin_headers())

    assert response.status_code == 200
    assert response.json() == {"valid": True, "checked": 2, "error": None}


def test_admin_audit_verify_reports_missing_key_version(test_db_session: DbSession) -> None:
    _record_test_audit_row(test_db_session, "test.audit.first")
    key = test_db_session.get(AuditHmacKey, AUDIT_HMAC_KEY_VERSION)
    assert key is not None
    test_db_session.delete(key)
    test_db_session.commit()
    client = _client_with_db(test_db_session)

    response = client.get("/api/v1/admin/audit/verify", headers=_admin_headers())

    assert response.status_code == 200
    assert response.json() == {
        "valid": False,
        "checked": 1,
        "error": "audit-chain-key-missing",
    }


def test_admin_audit_verify_reports_invalid_stored_key(test_db_session: DbSession) -> None:
    _record_test_audit_row(test_db_session, "test.audit.first")
    key = test_db_session.get(AuditHmacKey, AUDIT_HMAC_KEY_VERSION)
    assert key is not None
    key.key_enc = b"replace-me"
    test_db_session.commit()
    client = _client_with_db(test_db_session)

    response = client.get("/api/v1/admin/audit/verify", headers=_admin_headers())

    assert response.status_code == 200
    assert response.json() == {
        "valid": False,
        "checked": 1,
        "error": "audit-chain-key-invalid",
    }


def test_admin_audit_verify_reports_hash_mismatch(test_db_session: DbSession) -> None:
    audit_log = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action="test.audit.created",
        resource="camera:test",
        payload={"camera_id": "camera-1"},
    )
    audit_log.payload = {"camera_id": "camera-2"}
    client = _client_with_db(test_db_session)

    response = client.get(
        "/api/v1/admin/audit/verify",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": False,
        "checked": 1,
        "error": "audit-chain-hash-mismatch",
    }


def test_admin_audit_verify_reports_prev_hash_mismatch(test_db_session: DbSession) -> None:
    _record_test_audit_row(test_db_session, "test.audit.first")
    second = _record_test_audit_row(test_db_session, "test.audit.second")
    second.prev_hash = "tampered-previous-hash"
    client = _client_with_db(test_db_session)

    response = client.get(
        "/api/v1/admin/audit/verify",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": False,
        "checked": 2,
        "error": "audit-chain-prev-hash-mismatch",
    }


def test_admin_audit_verify_fails_closed_with_placeholder_key(test_db_session: DbSession) -> None:
    client = _client_with_db(test_db_session, audit_hmac_key="replace-me")

    response = client.get(
        "/api/v1/admin/audit/verify",
        headers=_admin_headers(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "audit-hmac-key-invalid"


def test_record_audit_event_inserts_first_row_and_hmac_key(test_db_session: DbSession) -> None:
    actor_id = uuid.uuid4()

    audit_log = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        actor_id=actor_id,
        action="test.audit.created",
        resource="camera:test",
        payload={"camera_id": uuid.uuid4(), "nested": {"ok": True}},
        ip="127.0.0.1",
        ua="pytest",
    )

    key = test_db_session.get(AuditHmacKey, AUDIT_HMAC_KEY_VERSION)
    rows = test_db_session.execute(select(AuditLog)).scalars().all()
    assert key is not None
    assert bytes(key.key_enc) == AUDIT_HMAC_KEY.encode("utf-8")
    assert audit_log in rows
    assert audit_log.actor_type == ActorType.user
    assert str(audit_log.actor_id) == str(actor_id)
    assert audit_log.action == "test.audit.created"
    assert audit_log.resource == "camera:test"
    assert audit_log.hmac_key_version == AUDIT_HMAC_KEY_VERSION
    assert audit_log.prev_hash is None
    assert len(audit_log.hash) == 64
    assert audit_log.payload is not None
    assert isinstance(audit_log.payload["camera_id"], str)
    assert audit_log.payload["nested"] == {"ok": True}
    assert audit_log.ip == "127.0.0.1"
    assert audit_log.ua == "pytest"
    result = verify_audit_chain(rows, audit_hmac_key=AUDIT_HMAC_KEY)
    assert result.valid is True
    assert result.checked == 1


def test_record_audit_event_links_second_row_to_first_hash(test_db_session: DbSession) -> None:
    first = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action="test.audit.first",
        resource="camera:first",
    )
    second = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action="test.audit.second",
        resource="camera:second",
    )

    rows = test_db_session.execute(select(AuditLog).order_by(AuditLog.id)).scalars().all()
    assert second.prev_hash == first.hash
    result = verify_audit_chain(rows, audit_hmac_key=AUDIT_HMAC_KEY)
    assert result.valid is True
    assert result.checked == 2


def test_audit_chain_verification_fails_when_row_payload_is_tampered(test_db_session: DbSession) -> None:
    audit_log = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action="test.audit.created",
        resource="camera:test",
        payload={"camera_id": "camera-1"},
    )

    audit_log.payload = {"camera_id": "camera-2"}
    result = verify_audit_chain([audit_log], audit_hmac_key=AUDIT_HMAC_KEY)

    assert result.valid is False
    assert result.checked == 1
    assert result.error == "audit-chain-hash-mismatch"


def test_audit_chain_verification_fails_when_action_or_resource_is_tampered(
    test_db_session: DbSession,
) -> None:
    action_row = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action="test.audit.created",
        resource="camera:test",
    )
    action_row.action = "test.audit.tampered"

    action_result = verify_audit_chain([action_row], audit_hmac_key=AUDIT_HMAC_KEY)

    assert action_result.valid is False
    assert action_result.error == "audit-chain-hash-mismatch"

    test_db_session.rollback()
    resource_row = test_db_session.execute(select(AuditLog)).scalar_one()
    resource_row.resource = "camera:tampered"
    resource_result = verify_audit_chain([resource_row], audit_hmac_key=AUDIT_HMAC_KEY)

    assert resource_result.valid is False
    assert resource_result.error == "audit-chain-hash-mismatch"


def test_record_audit_event_fails_closed_without_real_hmac_key(test_db_session: DbSession) -> None:
    for invalid_key in ("", "replace-me"):
        try:
            record_audit_event(
                test_db_session,
                actor_type=ActorType.user,
                audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
                audit_hmac_key=invalid_key,
                action="test.audit.denied",
                resource="camera:test",
            )
        except AuditLogError as exc:
            assert str(exc) == "audit-hmac-key-invalid"
        else:
            raise AssertionError("record_audit_event accepted an invalid audit HMAC key")

    rows = test_db_session.execute(select(AuditLog)).scalars().all()
    assert rows == []


def test_audit_chain_verification_returns_structured_failure_for_invalid_key(
    test_db_session: DbSession,
) -> None:
    audit_log = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action="test.audit.created",
        resource="camera:test",
    )

    result = verify_audit_chain([audit_log], audit_hmac_key="replace-me")

    assert result.valid is False
    assert result.checked == 1
    assert result.error == "audit-hmac-key-invalid"


def test_audit_payload_scrubbing_redacts_sensitive_values() -> None:
    payload = {
        "token": "livekit-token",
        "Authorization": "Bearer secret",
        "nested": {
            "api_key": "key",
            "safe": "value",
            "items": [{"password": "pw"}, {"room": "camera_a"}],
        },
    }

    scrubbed = scrub_audit_payload(payload)

    assert scrubbed == {
        "token": REDACTED_VALUE,
        "Authorization": REDACTED_VALUE,
        "nested": {
            "api_key": REDACTED_VALUE,
            "safe": "value",
            "items": [{"password": REDACTED_VALUE}, {"room": "camera_a"}],
        },
    }


def test_record_audit_event_hashes_scrubbed_payload(test_db_session: DbSession) -> None:
    audit_log = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action="test.audit.redacted",
        resource="camera:test",
        payload={"token": "secret-token", "safe": "value"},
    )

    assert audit_log.payload == {"token": REDACTED_VALUE, "safe": "value"}
    result = verify_audit_chain([audit_log], audit_hmac_key=AUDIT_HMAC_KEY)
    assert result.valid is True


def test_session_revoke_success_writes_audit_row(test_db_session: DbSession) -> None:
    user = get_or_create_user(test_db_session, email="viewer@example.test", idp_subject="viewer@example.test")
    session_row = create_session(test_db_session, user_id=user.id)
    client = _client_with_db(test_db_session)

    response = client.post(
        "/api/v1/sessions/revoke",
        headers=_auth_headers(),
        json={"session_id": str(session_row.id)},
    )

    assert response.status_code == 200
    assert response.json()["revoked"] is True
    audit_rows = test_db_session.execute(select(AuditLog)).scalars().all()
    assert [row.action for row in audit_rows] == ["session.revoke.succeeded"]
    assert audit_rows[0].payload == {"session_id": str(session_row.id), "revoked": True}


def test_session_revoke_denied_writes_audit_row(test_db_session: DbSession) -> None:
    other_user = get_or_create_user(test_db_session, email="other@example.test", idp_subject="other@example.test")
    other_session = create_session(test_db_session, user_id=other_user.id)
    client = _client_with_db(test_db_session)

    response = client.post(
        "/api/v1/sessions/revoke",
        headers=_auth_headers(),
        json={"session_id": str(other_session.id)},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "session-not-owned"
    audit_rows = test_db_session.execute(select(AuditLog)).scalars().all()
    assert [row.action for row in audit_rows] == ["session.revoke.denied.not_owned"]
    assert audit_rows[0].payload == {"session_id": str(other_session.id)}


def test_admin_session_revoke_not_found_writes_audit_row(test_db_session: DbSession) -> None:
    missing_session_id = uuid.uuid4()
    client = _client_with_db(test_db_session)

    response = client.post(
        "/api/v1/sessions/revoke",
        headers=_admin_headers(),
        json={"session_id": str(missing_session_id)},
    )

    assert response.status_code == 200
    assert response.json()["revoked"] is False
    audit_rows = test_db_session.execute(select(AuditLog)).scalars().all()
    assert [row.action for row in audit_rows] == ["session.revoke.not_found"]
    assert audit_rows[0].payload == {"session_id": str(missing_session_id), "revoked": False}


def test_admin_audit_export_requires_authentication(test_db_session: DbSession) -> None:
    client = _client_with_db(test_db_session)

    response = client.get("/api/v1/admin/audit/export")

    assert response.status_code == 401


def test_admin_audit_export_requires_admin_role(test_db_session: DbSession) -> None:
    client = _client_with_db(test_db_session)

    response = client.get("/api/v1/admin/audit/export", headers=_auth_headers())

    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_admin_audit_export_empty_returns_empty_body(test_db_session: DbSession) -> None:
    client = _client_with_db(test_db_session)

    response = client.get("/api/v1/admin/audit/export", headers=_admin_headers())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert response.headers["content-disposition"] == 'attachment; filename="audit-export.jsonl"'
    assert response.text == ""


def test_admin_audit_export_returns_jsonl_rows(test_db_session: DbSession) -> None:
    _record_test_audit_row(test_db_session, "test.export.first")
    _record_test_audit_row(test_db_session, "test.export.second")
    client = _client_with_db(test_db_session)

    response = client.get("/api/v1/admin/audit/export", headers=_admin_headers())

    assert response.status_code == 200
    lines = [line for line in response.text.strip().split("\n") if line]
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    expected_keys = {"id", "ts", "actor_id", "actor_type", "action", "resource", "payload", "ip", "ua"}
    for row in (first, second):
        assert set(row.keys()) == expected_keys
        assert "hash" not in row
        assert "prev_hash" not in row
        assert "hmac_key_version" not in row
    assert first["action"] == "test.export.first"
    assert second["action"] == "test.export.second"


def test_admin_audit_export_respects_id_bounds(test_db_session: DbSession) -> None:
    _record_test_audit_row(test_db_session, "test.export.first")
    second = _record_test_audit_row(test_db_session, "test.export.second")
    _record_test_audit_row(test_db_session, "test.export.third")
    client = _client_with_db(test_db_session)

    response = client.get(
        f"/api/v1/admin/audit/export?start_id={second.id}&end_id={second.id}",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    lines = [line for line in response.text.strip().split("\n") if line]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["action"] == "test.export.second"


def test_admin_audit_export_rejects_invalid_bounds(test_db_session: DbSession) -> None:
    client = _client_with_db(test_db_session)

    for query in ("start_id=0", "end_id=0", "start_id=3&end_id=2"):
        response = client.get(f"/api/v1/admin/audit/export?{query}", headers=_admin_headers())
        assert response.status_code == 422


def test_admin_audit_export_fails_closed_with_placeholder_key(test_db_session: DbSession) -> None:
    client = _client_with_db(test_db_session, audit_hmac_key="replace-me")

    response = client.get("/api/v1/admin/audit/export", headers=_admin_headers())

    assert response.status_code == 503
    assert response.json()["detail"] == "audit-hmac-key-invalid"


def test_admin_audit_export_returns_scrubbed_payload(test_db_session: DbSession) -> None:
    record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action="test.export.scrubbed",
        resource="camera:test",
        payload={"token": "secret-value", "safe": "visible"},
    )
    client = _client_with_db(test_db_session)

    response = client.get("/api/v1/admin/audit/export", headers=_admin_headers())

    assert response.status_code == 200
    lines = [line for line in response.text.strip().split("\n") if line]
    row = json.loads(lines[0])
    assert row["payload"]["token"] == REDACTED_VALUE
    assert row["payload"]["safe"] == "visible"
