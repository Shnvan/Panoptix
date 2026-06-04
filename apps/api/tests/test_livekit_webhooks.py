from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
import cctv_api.api.livekit_webhooks as livekit_webhook_module
from cctv_api.db import db_session
from cctv_api.gateway.command_queue import db_command_provider
from cctv_api.gateway.command_signing import verify_command_envelope
from cctv_api.gateway.models import GatewayCommandEnvelope
from cctv_api.gateway.publish_state import enqueue_due_publish_stops
from cctv_api.main import create_app
from cctv_api.models.enums import (
    CameraEventKind,
    CameraPublishStatus,
    CameraSourceType,
    EventSource,
    GatewayStatus,
    StreamKind,
)
from cctv_api.models.tables import (
    AuditLog,
    Camera,
    CameraAcl,
    CameraEvent,
    CameraPublishState,
    EdgeGateway,
    GatewayCameraAssignment,
    GatewayCommandQueue,
    StreamGrant,
    User,
    WebhookReplayCache,
)


LIVEKIT_API_KEY = "test-livekit-key"
LIVEKIT_API_SECRET = "test-livekit-secret-with-at-least-32-bytes"
AUDIT_HMAC_KEY = "test-audit-hmac-key-with-enough-entropy"
COMMAND_SIGNING_KEY = "test-command-signing-key-with-enough-entropy"

_VIEWER_HEADERS = {
    "x-panoptix-dev-auth": "1",
    "x-panoptix-dev-email": "viewer@example.test",
    "x-panoptix-dev-subject": "viewer@example.test",
    "x-panoptix-dev-roles": "viewer",
}


def _client(
    test_db_session: DbSession,
    *,
    enable_maintenance_scheduler: bool = False,
) -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            LIVEKIT_CLOUD_URL="wss://livekit.example.test",
            LIVEKIT_CLOUD_API_KEY=LIVEKIT_API_KEY,
            LIVEKIT_CLOUD_API_SECRET=LIVEKIT_API_SECRET,
            GATEWAY_COMMAND_SIGNING_KEY=COMMAND_SIGNING_KEY,
            AUDIT_HMAC_KEY_VERSION=1,
            AUDIT_HMAC_KEY=AUDIT_HMAC_KEY,
            ENABLE_MAINTENANCE_SCHEDULER=enable_maintenance_scheduler,
        )
    )

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


def _seed_user(db: DbSession, *, email: str = "viewer@example.test") -> User:
    user = User(id=uuid.uuid4(), email=email, idp_subject=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_camera(db: DbSession, *, room: str = "room-front-gate") -> Camera:
    camera = Camera(
        id=uuid.uuid4(),
        display_name="Front Gate",
        source_type=CameraSourceType.rtsp,
        livekit_room_name=room,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


def _seed_gateway(db: DbSession, *, status: GatewayStatus = GatewayStatus.enabled) -> EdgeGateway:
    gateway = EdgeGateway(id=uuid.uuid4(), name="Test Gateway", status=status)
    db.add(gateway)
    db.commit()
    db.refresh(gateway)
    return gateway


def _assign_gateway_camera(
    db: DbSession,
    *,
    gateway_id: uuid.UUID,
    camera_id: uuid.UUID,
    revoked: bool = False,
) -> GatewayCameraAssignment:
    assignment = GatewayCameraAssignment(
        gateway_id=gateway_id,
        camera_id=camera_id,
        granted_at=datetime.now(timezone.utc),
        revoked_at=datetime.now(timezone.utc) if revoked else None,
    )
    db.add(assignment)
    db.commit()
    return assignment


def _grant_camera_acl(db: DbSession, *, user_id: uuid.UUID, camera_id: uuid.UUID) -> None:
    db.add(CameraAcl(user_id=user_id, camera_id=camera_id, granted_at=datetime.now(timezone.utc)))
    db.commit()


def _webhook_payload(
    *,
    event: str = "track_published",
    room: str = "room-front-gate",
    created_at: datetime | None = None,
    participant_count: int | None = None,
) -> dict[str, Any]:
    observed_at = created_at or datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "event": event,
        "createdAt": int(observed_at.timestamp()),
        "room": {"sid": "RM_test", "name": room},
        "participant": {"sid": "PA_test", "identity": "gateway:test"},
        "track": {"sid": "TR_test"},
    }
    if participant_count is not None:
        payload["participant_count"] = participant_count
    return payload


def _raw_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _auth_header(raw_body: bytes, *, secret: str = LIVEKIT_API_SECRET) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "iss": LIVEKIT_API_KEY,
        "nbf": int(now.timestamp()) - 1,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "sha256": base64.b64encode(hashlib.sha256(raw_body).digest()).decode("ascii"),
    }
    return jwt.encode(claims, secret, algorithm="HS256")


def _post_webhook(
    client: TestClient,
    raw_body: bytes,
    *,
    authorization: str | None = None,
) -> Any:
    headers = {"content-type": "application/webhook+json"}
    if authorization is not None:
        headers["authorization"] = authorization
    return client.post("/api/v1/webhooks/livekit", headers=headers, content=raw_body)


def _audit_actions(db: DbSession) -> list[str]:
    return [row.action for row in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars().all()]


def _command_rows(db: DbSession) -> list[GatewayCommandQueue]:
    return list(db.execute(select(GatewayCommandQueue).order_by(GatewayCommandQueue.issued_at)).scalars().all())


def _gateway_headers(gateway_id: uuid.UUID) -> dict[str, str]:
    return {"x-panoptix-dev-gateway-id": str(gateway_id)}


def _parse_sse_events(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for frame in body.strip().split("\n\n"):
        if not frame:
            continue
        lines = frame.splitlines()
        assert lines[0] == "event: camera_event"
        assert lines[1].startswith("data: ")
        events.append(json.loads(lines[1].removeprefix("data: ")))
    return events


def test_livekit_webhook_requires_authorization(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload())

    response = _post_webhook(client, raw_body)

    assert response.status_code == 401
    assert response.json()["detail"] == "livekit-webhook-authorization-required"


def test_livekit_webhook_rejects_invalid_signature(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload())

    response = _post_webhook(
        client,
        raw_body,
        authorization=_auth_header(raw_body, secret="wrong-livekit-secret-with-at-least-32-bytes"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "livekit-webhook-signature-invalid"


def test_livekit_webhook_rejects_body_hash_mismatch(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    signed_body = _raw_body(_webhook_payload(event="track_published"))
    sent_body = _raw_body(_webhook_payload(event="track_unpublished"))

    response = _post_webhook(client, sent_body, authorization=_auth_header(signed_body))

    assert response.status_code == 403
    assert response.json()["detail"] == "livekit-webhook-signature-invalid"


def test_livekit_webhook_rejects_stale_created_at_and_audits(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload(created_at=datetime.now(timezone.utc) - timedelta(minutes=2)))

    response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))

    assert response.status_code == 400
    assert response.json()["detail"] == "livekit-webhook-stale"
    assert _audit_actions(test_db_session) == ["livekit.webhook.replay_rejected"]


def test_livekit_webhook_rejects_duplicate_replay(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload())
    authorization = _auth_header(raw_body)

    first_response = _post_webhook(client, raw_body, authorization=authorization)
    second_response = _post_webhook(client, raw_body, authorization=authorization)

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "livekit-webhook-replay"
    assert _audit_actions(test_db_session) == [
        "livekit.webhook.received",
        "livekit.webhook.replay_rejected",
    ]


def test_livekit_webhook_caches_replay_and_audits_received(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload())

    response = _post_webhook(client, raw_body, authorization=f"Bearer {_auth_header(raw_body)}")

    assert response.status_code == 200
    assert response.json()["accepted"] is True
    replay_rows = test_db_session.execute(select(WebhookReplayCache)).scalars().all()
    assert len(replay_rows) == 1
    assert replay_rows[0].provider == "livekit"
    assert replay_rows[0].expires_at is not None
    assert _audit_actions(test_db_session) == ["livekit.webhook.received"]


def test_livekit_webhook_creates_camera_event_visible_to_sse_viewer(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    camera = _seed_camera(test_db_session)
    _grant_camera_acl(test_db_session, user_id=user.id, camera_id=camera.id)
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload(event="track_published", room=camera.livekit_room_name))

    response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))

    assert response.status_code == 200
    event = test_db_session.execute(select(CameraEvent)).scalar_one()
    assert event.camera_id == camera.id
    assert event.gateway_id is None
    assert event.kind == CameraEventKind.online
    assert event.source == EventSource.livekit_webhook

    events_response = client.get("/api/v1/cameras/events", headers=_VIEWER_HEADERS)
    assert events_response.status_code == 200
    events = _parse_sse_events(events_response.text)
    assert len(events) == 1
    assert events[0]["camera_id"] == str(camera.id)
    assert events[0]["kind"] == "online"
    assert events[0]["source"] == "livekit_webhook"


def test_livekit_webhook_accepts_unknown_room_without_camera_event(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload(room="unknown-room"))

    response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))

    assert response.status_code == 200
    assert test_db_session.execute(select(CameraEvent)).scalars().all() == []
    assert _audit_actions(test_db_session) == ["livekit.webhook.received"]


def test_livekit_webhook_options_preflight_is_not_enabled(test_db_session: DbSession) -> None:
    client = _client(test_db_session)

    response = client.options("/api/v1/webhooks/livekit")

    assert response.status_code == 405


def test_livekit_participant_joined_enqueues_start_publish_command(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    gateway = _seed_gateway(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload(event="participant_joined", room=camera.livekit_room_name))

    response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))

    assert response.status_code == 200
    row = test_db_session.execute(select(GatewayCommandQueue)).scalar_one()
    assert row.gateway_id == gateway.id
    assert row.kind == "gateway.command.start_publish"
    assert row.payload["camera_id"] == str(camera.id)
    assert row.payload["room"] == camera.livekit_room_name
    assert row.payload["livekit_url"] == "wss://livekit.example.test"
    assert row.payload["gateway_publish_token"]
    assert row.payload["token_expires_at"]
    state = test_db_session.get(CameraPublishState, camera.id)
    assert state is not None
    assert state.gateway_id == gateway.id
    assert state.room == camera.livekit_room_name
    assert state.status == CameraPublishStatus.starting
    assert state.last_viewer_count == 1
    assert state.started_at is not None
    assert state.stop_due_at is None
    audit_rows = list(test_db_session.execute(select(AuditLog).order_by(AuditLog.id)).scalars().all())
    assert [row.action for row in audit_rows] == [
        "livekit.publish.start_enqueued",
        "livekit.webhook.received",
    ]
    assert audit_rows[0].payload is not None
    assert "gateway_publish_token" not in audit_rows[0].payload
    assert "token" not in audit_rows[0].payload


def test_livekit_start_command_creates_stream_grant(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    gateway = _seed_gateway(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload(event="participant_joined", room=camera.livekit_room_name))

    response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))

    assert response.status_code == 200
    grant = test_db_session.execute(select(StreamGrant)).scalar_one()
    assert grant.gateway_id == gateway.id
    assert grant.camera_id == camera.id
    assert grant.kind == StreamKind.gateway_publish


def test_livekit_duplicate_participant_joined_does_not_enqueue_duplicate_start(
    test_db_session: DbSession,
) -> None:
    camera = _seed_camera(test_db_session)
    gateway = _seed_gateway(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session)
    first_body = _raw_body(_webhook_payload(event="participant_joined", room=camera.livekit_room_name))
    second_body = _raw_body(_webhook_payload(event="participant_joined", room=camera.livekit_room_name))

    first_response = _post_webhook(client, first_body, authorization=_auth_header(first_body))
    second_response = _post_webhook(client, second_body, authorization=_auth_header(second_body))

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    rows = _command_rows(test_db_session)
    assert len(rows) == 1
    assert rows[0].kind == "gateway.command.start_publish"
    assert _audit_actions(test_db_session) == [
        "livekit.publish.start_enqueued",
        "livekit.webhook.received",
        "livekit.webhook.received",
    ]


def test_livekit_participant_joined_unknown_room_enqueues_no_command(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload(event="participant_joined", room="unknown-room"))

    response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))

    assert response.status_code == 200
    assert _command_rows(test_db_session) == []
    assert _audit_actions(test_db_session) == ["livekit.webhook.received"]


def test_livekit_participant_joined_without_assignment_audits_skip(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload(event="participant_joined", room=camera.livekit_room_name))

    response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))

    assert response.status_code == 200
    assert _command_rows(test_db_session) == []
    assert _audit_actions(test_db_session) == [
        "livekit.publish.command_skipped",
        "livekit.webhook.received",
    ]


def test_livekit_participant_joined_ignores_disabled_gateway_and_revoked_assignment(
    test_db_session: DbSession,
) -> None:
    camera = _seed_camera(test_db_session)
    disabled_gateway = _seed_gateway(test_db_session, status=GatewayStatus.disabled)
    revoked_gateway = _seed_gateway(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=disabled_gateway.id, camera_id=camera.id)
    _assign_gateway_camera(test_db_session, gateway_id=revoked_gateway.id, camera_id=camera.id, revoked=True)
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload(event="participant_joined", room=camera.livekit_room_name))

    response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))

    assert response.status_code == 200
    assert _command_rows(test_db_session) == []
    assert _audit_actions(test_db_session) == [
        "livekit.publish.command_skipped",
        "livekit.webhook.received",
    ]


def test_livekit_participant_left_zero_count_schedules_stop_publish(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    gateway = _seed_gateway(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session, enable_maintenance_scheduler=True)
    start_body = _raw_body(_webhook_payload(event="participant_joined", room=camera.livekit_room_name))
    start_response = _post_webhook(client, start_body, authorization=_auth_header(start_body))
    assert start_response.status_code == 200
    raw_body = _raw_body(
        _webhook_payload(event="participant_left", room=camera.livekit_room_name, participant_count=0)
    )

    response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))

    assert response.status_code == 200
    rows = _command_rows(test_db_session)
    assert len(rows) == 1
    assert rows[0].kind == "gateway.command.start_publish"
    state = test_db_session.get(CameraPublishState, camera.id)
    assert state is not None
    assert state.status == CameraPublishStatus.stop_pending
    assert state.last_viewer_count == 0
    assert state.stop_requested_at is not None
    assert state.stop_due_at is not None
    assert _audit_actions(test_db_session) == [
        "livekit.publish.start_enqueued",
        "livekit.webhook.received",
        "livekit.publish.stop_scheduled",
        "livekit.webhook.received",
    ]


def test_livekit_participant_left_zero_count_enqueues_immediate_stop_when_scheduler_disabled(
    test_db_session: DbSession,
) -> None:
    camera = _seed_camera(test_db_session)
    gateway = _seed_gateway(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session)
    start_body = _raw_body(_webhook_payload(event="participant_joined", room=camera.livekit_room_name))
    start_response = _post_webhook(client, start_body, authorization=_auth_header(start_body))
    assert start_response.status_code == 200
    raw_body = _raw_body(
        _webhook_payload(event="participant_left", room=camera.livekit_room_name, participant_count=0)
    )

    response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))

    assert response.status_code == 200
    rows = _command_rows(test_db_session)
    assert [row.kind for row in rows] == [
        "gateway.command.start_publish",
        "gateway.command.stop_publish",
    ]
    assert rows[1].payload == {"camera_id": str(camera.id), "room": camera.livekit_room_name}
    state = test_db_session.get(CameraPublishState, camera.id)
    assert state is not None
    assert state.status == CameraPublishStatus.idle
    assert state.last_viewer_count == 0
    assert state.stop_due_at is None
    assert _audit_actions(test_db_session) == [
        "livekit.publish.start_enqueued",
        "livekit.webhook.received",
        "livekit.publish.stop_enqueued",
        "livekit.webhook.received",
    ]


def test_livekit_participant_joined_during_grace_cancels_pending_stop(
    test_db_session: DbSession,
) -> None:
    camera = _seed_camera(test_db_session)
    gateway = _seed_gateway(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session, enable_maintenance_scheduler=True)
    start_body = _raw_body(_webhook_payload(event="participant_joined", room=camera.livekit_room_name))
    left_body = _raw_body(
        _webhook_payload(event="participant_left", room=camera.livekit_room_name, participant_count=0)
    )
    rejoin_body = _raw_body(_webhook_payload(event="participant_joined", room=camera.livekit_room_name))

    assert _post_webhook(client, start_body, authorization=_auth_header(start_body)).status_code == 200
    assert _post_webhook(client, left_body, authorization=_auth_header(left_body)).status_code == 200
    assert _post_webhook(client, rejoin_body, authorization=_auth_header(rejoin_body)).status_code == 200

    rows = _command_rows(test_db_session)
    assert len(rows) == 1
    assert rows[0].kind == "gateway.command.start_publish"
    state = test_db_session.get(CameraPublishState, camera.id)
    assert state is not None
    assert state.status == CameraPublishStatus.publishing
    assert state.stop_requested_at is None
    assert state.stop_due_at is None
    assert _audit_actions(test_db_session) == [
        "livekit.publish.start_enqueued",
        "livekit.webhook.received",
        "livekit.publish.stop_scheduled",
        "livekit.webhook.received",
        "livekit.publish.stop_cancelled",
        "livekit.webhook.received",
    ]


def test_livekit_participant_left_nonzero_count_enqueues_no_stop(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    gateway = _seed_gateway(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session)
    raw_body = _raw_body(
        _webhook_payload(event="participant_left", room=camera.livekit_room_name, participant_count=1)
    )

    response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))

    assert response.status_code == 200
    assert _command_rows(test_db_session) == []
    assert _audit_actions(test_db_session) == ["livekit.webhook.received"]


def test_livekit_room_finished_enqueues_stop_publish(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    gateway = _seed_gateway(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload(event="room_finished", room=camera.livekit_room_name))

    response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))

    assert response.status_code == 200
    row = test_db_session.execute(select(GatewayCommandQueue)).scalar_one()
    assert row.kind == "gateway.command.stop_publish"
    assert row.gateway_id == gateway.id
    assert row.payload == {"camera_id": str(camera.id), "room": camera.livekit_room_name}
    state = test_db_session.get(CameraPublishState, camera.id)
    assert state is not None
    assert state.status == CameraPublishStatus.idle
    assert state.stop_due_at is None


def test_due_publish_stop_processor_enqueues_stop_after_grace(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    gateway = _seed_gateway(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session, enable_maintenance_scheduler=True)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start_body = _raw_body(
        _webhook_payload(event="participant_joined", room=camera.livekit_room_name, created_at=now)
    )
    left_body = _raw_body(
        _webhook_payload(
            event="participant_left",
            room=camera.livekit_room_name,
            created_at=now + timedelta(seconds=1),
            participant_count=0,
        )
    )
    audit_events: list[tuple[str, str, dict[str, object | None]]] = []

    assert _post_webhook(client, start_body, authorization=_auth_header(start_body)).status_code == 200
    assert _post_webhook(client, left_body, authorization=_auth_header(left_body)).status_code == 200
    state = test_db_session.get(CameraPublishState, camera.id)
    assert state is not None
    assert state.stop_due_at is not None

    results = enqueue_due_publish_stops(
        test_db_session,
        now=state.stop_due_at + timedelta(seconds=1),
        audit=lambda action, resource, payload: audit_events.append((action, resource, payload)),
    )

    assert len(results) == 1
    rows = _command_rows(test_db_session)
    assert [row.kind for row in rows] == [
        "gateway.command.start_publish",
        "gateway.command.stop_publish",
    ]
    refreshed_state = test_db_session.get(CameraPublishState, camera.id)
    assert refreshed_state is not None
    assert refreshed_state.status == CameraPublishStatus.idle
    assert refreshed_state.stop_due_at is None
    assert audit_events[0][0] == "livekit.publish.stop_enqueued"


def test_due_publish_stop_processor_skips_before_grace_due(test_db_session: DbSession) -> None:
    camera = _seed_camera(test_db_session)
    gateway = _seed_gateway(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session, enable_maintenance_scheduler=True)
    start_body = _raw_body(_webhook_payload(event="participant_joined", room=camera.livekit_room_name))
    left_body = _raw_body(
        _webhook_payload(event="participant_left", room=camera.livekit_room_name, participant_count=0)
    )

    assert _post_webhook(client, start_body, authorization=_auth_header(start_body)).status_code == 200
    assert _post_webhook(client, left_body, authorization=_auth_header(left_body)).status_code == 200
    state = test_db_session.get(CameraPublishState, camera.id)
    assert state is not None
    assert state.stop_due_at is not None

    results = enqueue_due_publish_stops(test_db_session, now=state.stop_due_at - timedelta(seconds=1))

    assert results == []
    rows = _command_rows(test_db_session)
    assert len(rows) == 1
    assert rows[0].kind == "gateway.command.start_publish"


def test_livekit_enqueued_command_is_returned_by_gateway_heartbeat_provider(
    test_db_session: DbSession,
) -> None:
    camera = _seed_camera(test_db_session)
    gateway = _seed_gateway(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session)
    client.app.state.gateway_control_command_provider = db_command_provider(test_db_session)
    raw_body = _raw_body(_webhook_payload(event="participant_joined", room=camera.livekit_room_name))
    webhook_response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))
    assert webhook_response.status_code == 200

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/heartbeat",
        headers=_gateway_headers(gateway.id),
        json={"status": "online", "agent_version": "manual-test", "cameras": []},
    )

    assert response.status_code == 200
    commands = response.json()["pending_commands"]
    assert len(commands) == 1
    command = GatewayCommandEnvelope.model_validate(commands[0])
    assert command.kind == "gateway.command.start_publish"
    assert command.gateway_id == str(gateway.id)
    assert command.signature
    verify_command_envelope(command, COMMAND_SIGNING_KEY, expected_gateway_id=str(gateway.id))


def test_livekit_start_command_fails_closed_with_invalid_livekit_token_config(
    test_db_session: DbSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    camera = _seed_camera(test_db_session)
    gateway = _seed_gateway(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client(test_db_session)
    raw_body = _raw_body(_webhook_payload(event="participant_joined", room=camera.livekit_room_name))

    def _raise_token_config_error(*_args: object, **_kwargs: object) -> object:
        raise livekit_webhook_module.LiveKitTokenConfigError("livekit-token-config-invalid")

    monkeypatch.setattr(livekit_webhook_module, "mint_gateway_publish_token", _raise_token_config_error)

    response = _post_webhook(client, raw_body, authorization=_auth_header(raw_body))

    assert response.status_code == 503
    assert response.json()["detail"] == "livekit-token-config-invalid"
    assert _command_rows(test_db_session) == []
