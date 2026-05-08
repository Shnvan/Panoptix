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
    PLACEHOLDER_AUDIT_HMAC_KEY_VERSION,
    REDACTED_VALUE,
    record_audit_event,
    scrub_audit_payload,
)
from cctv_api.security.sessions import create_session
from cctv_api.security.users import get_or_create_user


def _client_with_db(test_db_session: DbSession) -> TestClient:
    app = create_app(settings=Settings(APP_ENV="development", ALLOW_DEV_AUTH=True))

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


def test_record_audit_event_inserts_row_and_placeholder_key(test_db_session: DbSession) -> None:
    actor_id = uuid.uuid4()

    audit_log = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        actor_id=actor_id,
        action="test.audit.created",
        resource="camera:test",
        payload={"camera_id": uuid.uuid4(), "nested": {"ok": True}},
        ip="127.0.0.1",
        ua="pytest",
    )

    key = test_db_session.get(AuditHmacKey, PLACEHOLDER_AUDIT_HMAC_KEY_VERSION)
    rows = test_db_session.execute(select(AuditLog)).scalars().all()
    assert key is not None
    assert audit_log in rows
    assert audit_log.actor_type == ActorType.user
    assert str(audit_log.actor_id) == str(actor_id)
    assert audit_log.action == "test.audit.created"
    assert audit_log.resource == "camera:test"
    assert audit_log.hmac_key_version == PLACEHOLDER_AUDIT_HMAC_KEY_VERSION
    assert audit_log.prev_hash is None
    assert len(audit_log.hash) == 64
    assert audit_log.payload is not None
    assert isinstance(audit_log.payload["camera_id"], str)
    assert audit_log.payload["nested"] == {"ok": True}
    assert audit_log.ip == "127.0.0.1"
    assert audit_log.ua == "pytest"


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
