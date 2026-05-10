from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession, sessionmaker

import cctv_api.gateway.command_queue as command_queue_module
from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.gateway.command_queue import (
    create_ack_sink,
    create_command_provider,
    db_ack_sink,
    db_command_provider,
    enqueue_command,
    expire_stale_commands,
)
from cctv_api.gateway.models import GatewayCommandAck
from cctv_api.main import create_app
from cctv_api.models.enums import CommandStatus
from cctv_api.models.tables import AuditLog, EdgeGateway


def _create_gateway(db: DbSession) -> EdgeGateway:
    gw = EdgeGateway(id=uuid.uuid4(), name="test-gw")
    db.add(gw)
    db.flush()
    return gw


@pytest.fixture()
def db(_test_db: sessionmaker[DbSession]):
    session = _test_db()
    try:
        yield session
    finally:
        session.close()


def test_enqueue_command_creates_pending_row(db: DbSession) -> None:
    gw = _create_gateway(db)
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    row = enqueue_command(db, gateway_id=gw.id, kind="reload_config", payload={"a": 1}, expires_at=expires)
    assert row.id is not None
    assert row.status == CommandStatus.pending
    assert row.kind == "reload_config"
    assert row.payload == {"a": 1}
    assert row.gateway_id == gw.id


def test_db_command_provider_returns_pending_unexpired_commands(db: DbSession) -> None:
    gw = _create_gateway(db)
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    enqueue_command(db, gateway_id=gw.id, kind="cmd_a", payload={}, expires_at=future)
    provider = db_command_provider(db)
    cmds = provider(str(gw.id))
    assert len(cmds) == 1
    assert cmds[0].kind == "cmd_a"
    assert cmds[0].gateway_id == str(gw.id)
    assert cmds[0].signature == ""


def test_db_command_provider_filters_by_gateway_id(db: DbSession) -> None:
    gw1 = _create_gateway(db)
    gw2 = _create_gateway(db)
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    enqueue_command(db, gateway_id=gw1.id, kind="for_gw1", payload={}, expires_at=future)
    enqueue_command(db, gateway_id=gw2.id, kind="for_gw2", payload={}, expires_at=future)
    provider = db_command_provider(db)
    cmds = provider(str(gw1.id))
    assert len(cmds) == 1
    assert cmds[0].kind == "for_gw1"


def test_db_command_provider_excludes_accepted_commands(db: DbSession) -> None:
    gw = _create_gateway(db)
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    row = enqueue_command(db, gateway_id=gw.id, kind="done", payload={}, expires_at=future)
    row.status = CommandStatus.accepted
    db.flush()
    provider = db_command_provider(db)
    cmds = provider(str(gw.id))
    assert len(cmds) == 0


def test_db_ack_sink_marks_command_accepted(db: DbSession) -> None:
    gw = _create_gateway(db)
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    row = enqueue_command(db, gateway_id=gw.id, kind="restart", payload={}, expires_at=future)
    sink = db_ack_sink(db)
    ack = GatewayCommandAck(command_id=str(row.id), gateway_id=str(gw.id), status="accepted")
    result = sink(str(gw.id), ack)
    db.refresh(row)
    assert result.applied is True
    assert result.command_id == str(row.id)
    assert row.status == CommandStatus.accepted
    assert row.acked_at is not None
    assert row.error is None


def test_db_ack_sink_marks_command_rejected_with_error(db: DbSession) -> None:
    gw = _create_gateway(db)
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    row = enqueue_command(db, gateway_id=gw.id, kind="restart", payload={}, expires_at=future)
    sink = db_ack_sink(db)
    ack = GatewayCommandAck(
        command_id=str(row.id), gateway_id=str(gw.id), status="rejected", error="not ready"
    )
    result = sink(str(gw.id), ack)
    db.refresh(row)
    assert result.applied is True
    assert result.command_id == str(row.id)
    assert row.status == CommandStatus.rejected
    assert row.error == "not ready"
    assert row.acked_at is not None


def test_db_ack_sink_ignores_unknown_command_id(db: DbSession) -> None:
    gw = _create_gateway(db)
    sink = db_ack_sink(db)
    command_id = str(uuid.uuid4())
    ack = GatewayCommandAck(command_id=command_id, gateway_id=str(gw.id), status="accepted")
    result = sink(str(gw.id), ack)
    assert result.applied is False
    assert result.reason == "command-not-found"
    assert result.command_id == command_id


def test_db_ack_sink_ignores_none_command_id(db: DbSession) -> None:
    gw = _create_gateway(db)
    sink = db_ack_sink(db)
    ack = GatewayCommandAck(command_id=None, gateway_id=str(gw.id), status="accepted")
    result = sink(str(gw.id), ack)
    assert result.applied is False
    assert result.reason == "command-id-missing"
    assert result.command_id is None


def test_db_ack_sink_reports_invalid_command_id(db: DbSession) -> None:
    gw = _create_gateway(db)
    sink = db_ack_sink(db)
    ack = GatewayCommandAck(command_id="not-a-uuid", gateway_id=str(gw.id), status="accepted")
    result = sink(str(gw.id), ack)
    assert result.applied is False
    assert result.reason == "command-id-invalid"
    assert result.command_id == "not-a-uuid"


def test_db_command_provider_returns_commands_in_fifo_order(db: DbSession) -> None:
    gw = _create_gateway(db)
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    t1 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2024, 1, 1, 0, 1, 0, tzinfo=timezone.utc)
    t3 = datetime(2024, 1, 1, 0, 2, 0, tzinfo=timezone.utc)

    row_c = enqueue_command(db, gateway_id=gw.id, kind="third", payload={}, expires_at=future)
    row_c.issued_at = t3
    row_a = enqueue_command(db, gateway_id=gw.id, kind="first", payload={}, expires_at=future)
    row_a.issued_at = t1
    row_b = enqueue_command(db, gateway_id=gw.id, kind="second", payload={}, expires_at=future)
    row_b.issued_at = t2
    db.flush()

    provider = db_command_provider(db)
    cmds = provider(str(gw.id))
    assert [c.kind for c in cmds] == ["first", "second", "third"]


def test_create_command_provider_returns_commands_via_own_session(
    _test_db: sessionmaker[DbSession], db: DbSession
) -> None:
    gw = _create_gateway(db)
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    enqueue_command(db, gateway_id=gw.id, kind="wired_test", payload={}, expires_at=future)
    db.commit()

    with patch.object(command_queue_module, "get_sessionmaker", return_value=_test_db):
        provider = create_command_provider()
        cmds = provider(str(gw.id))
    assert len(cmds) == 1
    assert cmds[0].kind == "wired_test"


def test_create_ack_sink_commits_via_own_session(
    _test_db: sessionmaker[DbSession], db: DbSession
) -> None:
    gw = _create_gateway(db)
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    row = enqueue_command(db, gateway_id=gw.id, kind="ack_wired", payload={}, expires_at=future)
    db.commit()

    with patch.object(command_queue_module, "get_sessionmaker", return_value=_test_db):
        sink = create_ack_sink()
        ack = GatewayCommandAck(command_id=str(row.id), gateway_id=str(gw.id), status="accepted")
        sink(str(gw.id), ack)

    db.expire(row)
    db.refresh(row)
    assert row.status == CommandStatus.accepted


# ── Endpoint tests ──


def _endpoint_client(test_db_session: DbSession) -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            AUDIT_HMAC_KEY_VERSION=1,
            AUDIT_HMAC_KEY="test-audit-key-with-enough-entropy",
        )
    )

    def _override_db() -> Generator[DbSession, None, None]:
        yield test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


def _admin_headers() -> dict[str, str]:
    return {
        "x-panoptix-dev-auth": "1",
        "x-panoptix-dev-email": "admin@example.test",
        "x-panoptix-dev-subject": "admin@example.test",
        "x-panoptix-dev-roles": "admin",
    }


def _viewer_headers() -> dict[str, str]:
    return {
        "x-panoptix-dev-auth": "1",
        "x-panoptix-dev-email": "viewer@example.test",
        "x-panoptix-dev-subject": "viewer@example.test",
        "x-panoptix-dev-roles": "viewer",
    }


def test_enqueue_endpoint_requires_authentication(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{uuid.uuid4()}/commands",
        json={"kind": "test"},
    )
    assert response.status_code == 401


def test_enqueue_endpoint_requires_admin_role(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{uuid.uuid4()}/commands",
        json={"kind": "test"},
        headers=_viewer_headers(),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_enqueue_endpoint_rejects_invalid_gateway_id(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.post(
        "/api/v1/admin/gateways/not-a-uuid/commands",
        json={"kind": "test"},
        headers=_admin_headers(),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "gateway-id-invalid"


def test_enqueue_endpoint_rejects_missing_gateway(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{uuid.uuid4()}/commands",
        json={"kind": "test"},
        headers=_admin_headers(),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "gateway-not-found"


def test_enqueue_endpoint_creates_pending_command(test_db_session: DbSession) -> None:
    gw = EdgeGateway(id=uuid.uuid4(), name="endpoint-gw")
    test_db_session.add(gw)
    test_db_session.flush()

    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gw.id}/commands",
        json={"kind": "reload_config", "payload": {"key": "value"}},
        headers=_admin_headers(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "reload_config"
    assert body["gateway_id"] == str(gw.id)
    assert body["status"] == "pending"
    assert body["command_id"] is not None
    assert body["expires_at"] is not None


def test_enqueue_endpoint_uses_default_expiry(test_db_session: DbSession) -> None:
    gw = EdgeGateway(id=uuid.uuid4(), name="expiry-gw")
    test_db_session.add(gw)
    test_db_session.flush()

    client = _endpoint_client(test_db_session)
    before = datetime.now(timezone.utc)
    response = client.post(
        f"/api/v1/admin/gateways/{gw.id}/commands",
        json={"kind": "ping"},
        headers=_admin_headers(),
    )
    after = datetime.now(timezone.utc)
    assert response.status_code == 201
    expires_at = datetime.fromisoformat(response.json()["expires_at"])
    assert expires_at >= before + timedelta(seconds=299)
    assert expires_at <= after + timedelta(seconds=301)


def test_enqueue_endpoint_uses_custom_expiry(test_db_session: DbSession) -> None:
    gw = EdgeGateway(id=uuid.uuid4(), name="custom-gw")
    test_db_session.add(gw)
    test_db_session.flush()

    client = _endpoint_client(test_db_session)
    before = datetime.now(timezone.utc)
    response = client.post(
        f"/api/v1/admin/gateways/{gw.id}/commands",
        json={"kind": "restart", "expires_in_seconds": 60},
        headers=_admin_headers(),
    )
    after = datetime.now(timezone.utc)
    assert response.status_code == 201
    expires_at = datetime.fromisoformat(response.json()["expires_at"])
    assert expires_at >= before + timedelta(seconds=59)
    assert expires_at <= after + timedelta(seconds=61)


# ── Expire stale commands tests ──


def test_expire_stale_commands_marks_expired_pending_rows(db: DbSession) -> None:
    gw = _create_gateway(db)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    enqueue_command(db, gateway_id=gw.id, kind="old_a", payload={}, expires_at=past)
    enqueue_command(db, gateway_id=gw.id, kind="old_b", payload={}, expires_at=past)
    db.flush()

    expire_stale_commands(db)

    from sqlalchemy import select
    from cctv_api.models.tables import GatewayCommandQueue

    rows = list(db.execute(select(GatewayCommandQueue)).scalars().all())
    assert all(r.status == CommandStatus.expired for r in rows)


def test_expire_stale_commands_skips_unexpired_commands(db: DbSession) -> None:
    gw = _create_gateway(db)
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    row = enqueue_command(db, gateway_id=gw.id, kind="fresh", payload={}, expires_at=future)
    db.flush()

    expire_stale_commands(db)

    db.refresh(row)
    assert row.status == CommandStatus.pending


def test_expire_stale_commands_skips_already_accepted(db: DbSession) -> None:
    gw = _create_gateway(db)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    row = enqueue_command(db, gateway_id=gw.id, kind="done", payload={}, expires_at=past)
    row.status = CommandStatus.accepted
    db.flush()

    expire_stale_commands(db)

    db.refresh(row)
    assert row.status == CommandStatus.accepted


def test_expire_stale_commands_returns_count(db: DbSession) -> None:
    gw = _create_gateway(db)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    enqueue_command(db, gateway_id=gw.id, kind="stale1", payload={}, expires_at=past)
    enqueue_command(db, gateway_id=gw.id, kind="stale2", payload={}, expires_at=past)
    enqueue_command(db, gateway_id=gw.id, kind="stale3", payload={}, expires_at=past)
    enqueue_command(db, gateway_id=gw.id, kind="fresh", payload={}, expires_at=future)
    db.flush()

    count = expire_stale_commands(db)
    assert count == 3


# ── List commands endpoint tests ──


def test_list_commands_requires_authentication(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.get(f"/api/v1/admin/gateways/{uuid.uuid4()}/commands")
    assert response.status_code == 401


def test_list_commands_requires_admin_role(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.get(
        f"/api/v1/admin/gateways/{uuid.uuid4()}/commands",
        headers=_viewer_headers(),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_list_commands_rejects_invalid_gateway_id(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.get(
        "/api/v1/admin/gateways/not-a-uuid/commands",
        headers=_admin_headers(),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "gateway-id-invalid"


def test_list_commands_rejects_missing_gateway(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.get(
        f"/api/v1/admin/gateways/{uuid.uuid4()}/commands",
        headers=_admin_headers(),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "gateway-not-found"


def test_list_commands_returns_empty_list(test_db_session: DbSession) -> None:
    gw = EdgeGateway(id=uuid.uuid4(), name="empty-gw")
    test_db_session.add(gw)
    test_db_session.flush()

    client = _endpoint_client(test_db_session)
    response = client.get(
        f"/api/v1/admin/gateways/{gw.id}/commands",
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


def test_list_commands_returns_commands_newest_first(test_db_session: DbSession) -> None:
    gw = EdgeGateway(id=uuid.uuid4(), name="order-gw")
    test_db_session.add(gw)
    test_db_session.flush()

    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    t1 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2024, 1, 1, 0, 1, 0, tzinfo=timezone.utc)
    t3 = datetime(2024, 1, 1, 0, 2, 0, tzinfo=timezone.utc)

    row_a = enqueue_command(db=test_db_session, gateway_id=gw.id, kind="first", payload={}, expires_at=future)
    row_a.issued_at = t1
    row_b = enqueue_command(db=test_db_session, gateway_id=gw.id, kind="second", payload={}, expires_at=future)
    row_b.issued_at = t2
    row_c = enqueue_command(db=test_db_session, gateway_id=gw.id, kind="third", payload={}, expires_at=future)
    row_c.issued_at = t3
    test_db_session.flush()

    client = _endpoint_client(test_db_session)
    response = client.get(
        f"/api/v1/admin/gateways/{gw.id}/commands",
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    kinds = [item["kind"] for item in body["items"]]
    assert kinds == ["third", "second", "first"]


def test_list_commands_filters_by_status(test_db_session: DbSession) -> None:
    gw = EdgeGateway(id=uuid.uuid4(), name="filter-gw")
    test_db_session.add(gw)
    test_db_session.flush()

    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    enqueue_command(
        db=test_db_session, gateway_id=gw.id, kind="pending_cmd", payload={}, expires_at=future
    )
    row_accepted = enqueue_command(
        db=test_db_session, gateway_id=gw.id, kind="accepted_cmd", payload={}, expires_at=future
    )
    row_accepted.status = CommandStatus.accepted
    test_db_session.flush()

    client = _endpoint_client(test_db_session)
    response = client.get(
        f"/api/v1/admin/gateways/{gw.id}/commands?status=pending",
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["kind"] == "pending_cmd"
    assert body["items"][0]["status"] == "pending"


# ── Cancel command endpoint tests ──


def test_cancel_command_requires_authentication(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{uuid.uuid4()}/commands/{uuid.uuid4()}/cancel"
    )
    assert response.status_code == 401


def test_cancel_command_requires_admin_role(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{uuid.uuid4()}/commands/{uuid.uuid4()}/cancel",
        headers=_viewer_headers(),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_cancel_command_rejects_invalid_gateway_id(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/not-a-uuid/commands/{uuid.uuid4()}/cancel",
        headers=_admin_headers(),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "gateway-id-invalid"


def test_cancel_command_rejects_invalid_command_id(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{uuid.uuid4()}/commands/not-a-uuid/cancel",
        headers=_admin_headers(),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "command-id-invalid"


def test_cancel_command_rejects_missing_gateway(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{uuid.uuid4()}/commands/{uuid.uuid4()}/cancel",
        headers=_admin_headers(),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "gateway-not-found"


def test_cancel_command_rejects_missing_command(test_db_session: DbSession) -> None:
    gw = EdgeGateway(id=uuid.uuid4(), name="cancel-missing-gw")
    test_db_session.add(gw)
    test_db_session.flush()

    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gw.id}/commands/{uuid.uuid4()}/cancel",
        headers=_admin_headers(),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "command-not-found"


def test_cancel_command_rejects_non_pending(test_db_session: DbSession) -> None:
    gw = EdgeGateway(id=uuid.uuid4(), name="cancel-nonpend-gw")
    test_db_session.add(gw)
    test_db_session.flush()

    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    row = enqueue_command(
        db=test_db_session, gateway_id=gw.id, kind="done_cmd", payload={}, expires_at=future
    )
    row.status = CommandStatus.accepted
    test_db_session.flush()

    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gw.id}/commands/{row.id}/cancel",
        headers=_admin_headers(),
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "command-not-pending"


def test_cancel_command_succeeds_on_pending(test_db_session: DbSession) -> None:
    gw = EdgeGateway(id=uuid.uuid4(), name="cancel-ok-gw")
    test_db_session.add(gw)
    test_db_session.flush()

    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    row = enqueue_command(
        db=test_db_session, gateway_id=gw.id, kind="restart", payload={}, expires_at=future
    )
    test_db_session.flush()

    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gw.id}/commands/{row.id}/cancel",
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["command_id"] == str(row.id)
    assert body["gateway_id"] == str(gw.id)
    assert body["kind"] == "restart"
    assert body["status"] == "cancelled"
    assert body["cancelled_at"] is not None


# ── Expire cleanup endpoint tests ──


def test_expire_cleanup_requires_authentication(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.post("/api/v1/admin/commands/cleanup")
    assert response.status_code == 401


def test_expire_cleanup_requires_admin_role(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.post(
        "/api/v1/admin/commands/cleanup",
        headers=_viewer_headers(),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_expire_cleanup_returns_zero_when_nothing_to_expire(test_db_session: DbSession) -> None:
    client = _endpoint_client(test_db_session)
    response = client.post(
        "/api/v1/admin/commands/cleanup",
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    assert response.json()["expired_count"] == 0


def test_expire_cleanup_expires_stale_commands(test_db_session: DbSession) -> None:
    gw = EdgeGateway(id=uuid.uuid4(), name="cleanup-gw")
    test_db_session.add(gw)
    test_db_session.flush()

    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    enqueue_command(db=test_db_session, gateway_id=gw.id, kind="stale1", payload={}, expires_at=past)
    enqueue_command(db=test_db_session, gateway_id=gw.id, kind="stale2", payload={}, expires_at=past)
    enqueue_command(db=test_db_session, gateway_id=gw.id, kind="fresh", payload={}, expires_at=future)
    test_db_session.flush()

    client = _endpoint_client(test_db_session)
    response = client.post(
        "/api/v1/admin/commands/cleanup",
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    assert response.json()["expired_count"] == 2


# ── Audit logging tests ──


def test_enqueue_command_writes_audit_row(test_db_session: DbSession) -> None:
    gw = EdgeGateway(id=uuid.uuid4(), name="audit-enqueue-gw")
    test_db_session.add(gw)
    test_db_session.flush()

    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gw.id}/commands",
        json={"kind": "reload_config"},
        headers=_admin_headers(),
    )
    assert response.status_code == 201

    from sqlalchemy import select

    audit_rows = list(test_db_session.execute(select(AuditLog)).scalars().all())
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "command.enqueue"
    assert audit_rows[0].payload["kind"] == "reload_config"
    assert audit_rows[0].payload["gateway_id"] == str(gw.id)


def test_cancel_command_writes_audit_row(test_db_session: DbSession) -> None:
    gw = EdgeGateway(id=uuid.uuid4(), name="audit-cancel-gw")
    test_db_session.add(gw)
    test_db_session.flush()

    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    row = enqueue_command(
        db=test_db_session, gateway_id=gw.id, kind="restart", payload={}, expires_at=future
    )
    test_db_session.flush()

    client = _endpoint_client(test_db_session)
    response = client.post(
        f"/api/v1/admin/gateways/{gw.id}/commands/{row.id}/cancel",
        headers=_admin_headers(),
    )
    assert response.status_code == 200

    from sqlalchemy import select

    audit_rows = list(test_db_session.execute(select(AuditLog)).scalars().all())
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "command.cancel"
    assert audit_rows[0].payload["command_id"] == str(row.id)
    assert audit_rows[0].payload["kind"] == "restart"


def test_expire_cleanup_writes_audit_row(test_db_session: DbSession) -> None:
    gw = EdgeGateway(id=uuid.uuid4(), name="audit-cleanup-gw")
    test_db_session.add(gw)
    test_db_session.flush()

    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    enqueue_command(db=test_db_session, gateway_id=gw.id, kind="stale", payload={}, expires_at=past)
    test_db_session.flush()

    client = _endpoint_client(test_db_session)
    response = client.post(
        "/api/v1/admin/commands/cleanup",
        headers=_admin_headers(),
    )
    assert response.status_code == 200

    from sqlalchemy import select

    audit_rows = list(test_db_session.execute(select(AuditLog)).scalars().all())
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "commands.cleanup"
    assert audit_rows[0].payload["expired_count"] == 1
