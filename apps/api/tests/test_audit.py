from __future__ import annotations

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


def _client_with_db(test_db_session: DbSession) -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            AUDIT_HMAC_KEY_VERSION=AUDIT_HMAC_KEY_VERSION,
            AUDIT_HMAC_KEY=AUDIT_HMAC_KEY,
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
        headers=_auth_headers(email="admin@example.test", roles="admin"),
        json={"session_id": str(missing_session_id)},
    )

    assert response.status_code == 200
    assert response.json()["revoked"] is False
    audit_rows = test_db_session.execute(select(AuditLog)).scalars().all()
    assert [row.action for row in audit_rows] == ["session.revoke.not_found"]
    assert audit_rows[0].payload == {"session_id": str(missing_session_id), "revoked": False}
