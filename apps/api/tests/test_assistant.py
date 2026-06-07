from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.assistant import AssistantMessage, build_operations_snapshot, complete_chat
from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import (
    AlertCategory,
    AlertSeverity,
    AlertStatus,
    BackupUploadStatus,
    CameraPublishStatus,
    CameraSourceType,
    GatewayStatus,
)
from cctv_api.models.tables import (
    Alert,
    AuditLog,
    BackupRun,
    Camera,
    CameraPublishState,
    EdgeGateway,
)
from cctv_api.security.rate_limit import get_rate_limiter

_ADMIN_HEADERS = {
    "x-panoptix-dev-auth": "1",
    "x-panoptix-dev-subject": "assistant-admin",
    "x-panoptix-dev-email": "assistant-admin@example.test",
    "x-panoptix-dev-roles": "admin",
}
_VIEWER_HEADERS = {
    **_ADMIN_HEADERS,
    "x-panoptix-dev-roles": "viewer",
}


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "APP_ENV": "development",
        "ALLOW_DEV_AUTH": True,
        "AUDIT_HMAC_KEY_VERSION": 1,
        "AUDIT_HMAC_KEY": "assistant-test-audit-key-with-enough-entropy",
        "AI_ASSISTANT_ENABLED": True,
        "AI_ASSISTANT_API_KEY": "server-only-provider-key",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _client(test_db_session: DbSession, **settings: object) -> TestClient:
    app = create_app(settings=_settings(**settings))

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


def _body(content: str = "Is the pilot healthy?") -> dict[str, object]:
    return {"messages": [{"role": "user", "content": content}]}


def test_assistant_status_requires_admin_and_reports_configuration(
    test_db_session: DbSession,
) -> None:
    client = _client(test_db_session)
    denied = client.get("/api/v1/admin/assistant/status", headers=_VIEWER_HEADERS)
    allowed = client.get("/api/v1/admin/assistant/status", headers=_ADMIN_HEADERS)

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json() == {
        "enabled": True,
        "provider": "openai-compatible",
        "model": "llama-3.3-70b-versatile",
        "max_history_messages": 20,
        "page_session_limit": 50,
    }


def test_assistant_chat_disabled_fails_closed(test_db_session: DbSession) -> None:
    client = _client(test_db_session, AI_ASSISTANT_ENABLED=False)
    response = client.post(
        "/api/v1/admin/assistant/chat",
        headers=_ADMIN_HEADERS,
        json=_body(),
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "assistant-disabled"


@patch("cctv_api.api.assistant.complete_chat")
@patch("cctv_api.api.health.httpx.post")
def test_assistant_chat_returns_answer_and_audits_without_content(
    mock_health_post: MagicMock,
    mock_complete: MagicMock,
    test_db_session: DbSession,
) -> None:
    mock_health_post.return_value = MagicMock(status_code=200)
    mock_complete.return_value = "The current sanitized snapshot is healthy."
    client = _client(
        test_db_session,
        LIVEKIT_CLOUD_API_KEY="configured-key",
        LIVEKIT_CLOUD_API_SECRET="configured-secret-with-enough-entropy",
    )

    response = client.post(
        "/api/v1/admin/assistant/chat",
        headers=_ADMIN_HEADERS,
        json=_body("Do not store this prompt."),
    )

    assert response.status_code == 200
    assert response.json()["message"] == "The current sanitized snapshot is healthy."
    rows = list(
        test_db_session.execute(
            select(AuditLog).where(AuditLog.action.like("admin.assistant.%")).order_by(AuditLog.id)
        ).scalars()
    )
    assert [row.action for row in rows] == [
        "admin.assistant.requested",
        "admin.assistant.completed",
    ]
    serialized = repr([row.payload for row in rows])
    assert "Do not store this prompt." not in serialized
    assert "The current sanitized snapshot is healthy." not in serialized
    assert "server-only-provider-key" not in serialized


@patch("cctv_api.api.assistant.complete_chat")
@patch("cctv_api.api.assistant.record_audit_event")
def test_assistant_does_not_contact_provider_when_required_audit_fails(
    mock_audit: MagicMock,
    mock_complete: MagicMock,
    test_db_session: DbSession,
) -> None:
    mock_audit.side_effect = RuntimeError("audit unavailable")
    client = _client(test_db_session)

    response = client.post(
        "/api/v1/admin/assistant/chat",
        headers=_ADMIN_HEADERS,
        json=_body(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "audit-log-write-failed"
    mock_complete.assert_not_called()


def test_assistant_validates_history_order_and_total_size(test_db_session: DbSession) -> None:
    client = _client(test_db_session)
    bad_order = client.post(
        "/api/v1/admin/assistant/chat",
        headers=_ADMIN_HEADERS,
        json={
            "messages": [
                {"role": "user", "content": "one"},
                {"role": "user", "content": "two"},
            ]
        },
    )
    too_large = client.post(
        "/api/v1/admin/assistant/chat",
        headers=_ADMIN_HEADERS,
        json={
            "messages": [
                {"role": "user", "content": "x" * 2000},
                {"role": "assistant", "content": "x" * 2000},
                {"role": "user", "content": "x" * 2000},
                {"role": "assistant", "content": "x" * 2000},
                {"role": "user", "content": "x" * 2000},
                {"role": "assistant", "content": "x" * 2000},
                {"role": "user", "content": "x" * 2000},
            ]
        },
    )
    assert bad_order.status_code == 422
    assert too_large.status_code == 422


@patch("cctv_api.api.assistant.complete_chat", return_value="ok")
def test_assistant_server_rate_limit_sets_retry_after(
    _mock_complete: MagicMock,
    test_db_session: DbSession,
) -> None:
    get_rate_limiter().reset()
    client = _client(
        test_db_session,
        RATE_LIMIT_AI_ASSISTANT_MAX=1,
        RATE_LIMIT_AI_ASSISTANT_WINDOW=300,
    )
    first = client.post(
        "/api/v1/admin/assistant/chat",
        headers=_ADMIN_HEADERS,
        json=_body(),
    )
    second = client.post(
        "/api/v1/admin/assistant/chat",
        headers=_ADMIN_HEADERS,
        json=_body(),
    )
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"]


@patch("cctv_api.api.health.httpx.post")
def test_operations_snapshot_excludes_identifiers_and_sensitive_fields(
    mock_health_post: MagicMock,
    test_db_session: DbSession,
) -> None:
    mock_health_post.return_value = MagicMock(status_code=200)
    now = datetime.now(timezone.utc)
    gateway = EdgeGateway(
        id=uuid.uuid4(),
        name="secret-gateway-name",
        status=GatewayStatus.enabled,
        service_token_hash="secret-token-hash",
        last_seen_at=now,
    )
    camera = Camera(
        id=uuid.uuid4(),
        display_name="private-camera-name",
        source_type=CameraSourceType.rtsp,
        room_uuid=uuid.uuid4(),
        livekit_room_name="private-room",
    )
    test_db_session.add_all(
        [
            gateway,
            camera,
            CameraPublishState(
                camera_id=camera.id,
                gateway_id=gateway.id,
                room="private-room",
                status=CameraPublishStatus.publishing,
            ),
            Alert(
                severity=AlertSeverity.high,
                category=AlertCategory.operations,
                title="Gateway admin@example.test at 203.0.113.10",
                message="contains-secret-message",
                status=AlertStatus.open,
                source="test",
                metadata_json={"token": "secret"},
            ),
            BackupRun(
                id=uuid.uuid4(),
                started_at=now - timedelta(hours=1),
                finished_at=now,
                upload_status=BackupUploadStatus.uploaded,
                restore_format_ok=True,
                notes="private backup note",
            ),
            BackupRun(
                id=uuid.uuid4(),
                started_at=now - timedelta(days=1),
                finished_at=now - timedelta(days=1),
                upload_status=BackupUploadStatus.uploaded,
                restore_schema_ok=True,
            ),
        ]
    )
    test_db_session.commit()

    snapshot = build_operations_snapshot(
        test_db_session,
        _settings(
            LIVEKIT_CLOUD_API_KEY="configured-key",
            LIVEKIT_CLOUD_API_SECRET="configured-secret-with-enough-entropy",
        ),
    )
    serialized = repr(snapshot)
    for forbidden in (
        str(gateway.id),
        str(camera.id),
        "secret-gateway-name",
        "secret-token-hash",
        "private-camera-name",
        "private-room",
        "admin@example.test",
        "203.0.113.10",
        "contains-secret-message",
        "private backup note",
    ):
        assert forbidden not in serialized
    assert "[redacted]" in serialized


def test_provider_retries_429_then_returns_content() -> None:
    responses = [
        httpx.Response(429),
        httpx.Response(429),
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Recovered response"}}]},
        ),
    ]
    post = MagicMock(side_effect=responses)
    sleep = MagicMock()

    result = complete_chat(
        _settings(),
        [AssistantMessage(role="user", content="status")],
        {"health": {"gateway": "connected"}},
        post=post,
        sleep=sleep,
    )

    assert result == "Recovered response"
    assert post.call_count == 3
    assert [call.args[0] for call in sleep.call_args_list] == [3, 6]
    sent = post.call_args.kwargs["json"]
    assert sent["messages"][0]["role"] == "system"
    assert "server-only-provider-key" not in repr(sent)


def test_provider_redacts_sensitive_conversation_content() -> None:
    post = MagicMock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Contact admin@example.test from 203.0.113.10"
                        }
                    }
                ]
            },
        )
    )

    result = complete_chat(
        _settings(),
        [
            AssistantMessage(
                role="user",
                content=(
                    "Check admin@example.test at 203.0.113.10 "
                    "token=provider-secret-value"
                ),
            )
        ],
        {"health": {"gateway": "connected"}},
        post=post,
    )

    sent = repr(post.call_args.kwargs["json"])
    assert "admin@example.test" not in sent
    assert "203.0.113.10" not in sent
    assert "provider-secret-value" not in sent
    assert result == "Contact [redacted] from [redacted]"
