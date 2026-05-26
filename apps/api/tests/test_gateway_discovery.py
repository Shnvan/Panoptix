from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import GatewayStatus
from cctv_api.models.tables import EdgeGateway, GatewayDiscoveryRun


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


def _gateway_headers(gateway_id: uuid.UUID) -> dict[str, str]:
    return {"x-panoptix-dev-gateway-id": str(gateway_id)}


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


def _seed_gateway(
    db: DbSession,
    *,
    status: GatewayStatus = GatewayStatus.enabled,
) -> EdgeGateway:
    gateway = EdgeGateway(id=uuid.uuid4(), name="Discovery Gateway", status=status)
    db.add(gateway)
    db.commit()
    db.refresh(gateway)
    return gateway


def _report(started_at: datetime | None = None) -> dict[str, object]:
    started = started_at or datetime(2026, 5, 25, 10, 0, 0, tzinfo=timezone.utc)
    return {
        "started_at": started.isoformat(),
        "finished_at": (started + timedelta(seconds=2)).isoformat(),
        "status": "completed",
        "approved_ranges": ["192.168.50.0/30"],
        "ports": [554, 80, 443, 8000, 8080, 8899],
        "scanned_host_count": 2,
        "candidate_count": 1,
        "agent_version": "0.1.0",
        "findings": [
            {
                "ip": "192.168.50.2",
                "hostname": None,
                "hostnames": ["cam-front-door.local"],
                "mac_address": "A4:14:37:91:22:10",
                "mac_vendor": "Hikvision",
                "open_ports": [554],
                "status": "open",
                "candidate_kind": "possible_camera",
                "device_hint": "ip_camera",
                "confidence": "high",
                "observed_protocols": ["RTSP", "HTTP", "ONVIF"],
                "evidence": ["rtsp_port_554", "onvif_service"],
                "raw_banner": "must-not-persist",
                "http_body": "<html>must-not-persist</html>",
                "credentials": "must-not-persist",
            }
        ],
    }


def test_gateway_discovery_requires_matching_gateway_identity(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    client = _client(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/discovery-runs",
        headers=_gateway_headers(uuid.uuid4()),
        json=_report(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gateway-id-mismatch"


def test_gateway_discovery_rejects_missing_gateway(test_db_session: DbSession) -> None:
    gateway_id = uuid.uuid4()
    client = _client(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway_id}/discovery-runs",
        headers=_gateway_headers(gateway_id),
        json=_report(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gateway-disabled-or-not-found"


def test_gateway_discovery_rejects_disabled_gateway(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session, status=GatewayStatus.disabled)
    client = _client(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/discovery-runs",
        headers=_gateway_headers(gateway.id),
        json=_report(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gateway-disabled-or-not-found"


def test_gateway_discovery_valid_report_persists_sanitized_snapshot(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    client = _client(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/discovery-runs",
        headers=_gateway_headers(gateway.id),
        json=_report(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["discovery_run_id"]

    row = test_db_session.execute(select(GatewayDiscoveryRun)).scalar_one()
    assert row.gateway_id == gateway.id
    assert row.status == "completed"
    assert row.scanned_host_count == 2
    assert row.candidate_count == 1
    assert row.approved_ranges == ["192.168.50.0/30"]
    assert row.ports == [554, 80, 443, 8000, 8080, 8899]
    assert row.findings == [
        {
            "ip": "192.168.50.2",
            "hostname": None,
            "hostnames": ["cam-front-door.local"],
            "mac_address": "A4:14:37:91:22:10",
            "mac_vendor": "Hikvision",
            "open_ports": [554],
            "status": "open",
            "candidate_kind": "possible_camera",
            "device_hint": "ip_camera",
            "confidence": "high",
            "observed_protocols": ["RTSP", "HTTP", "ONVIF"],
            "evidence": ["rtsp_port_554", "onvif_service"],
        }
    ]


def test_admin_discovery_runs_require_admin_role(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    client = _client(test_db_session)

    response = client.get(
        f"/api/v1/admin/gateways/{gateway.id}/discovery-runs",
        headers=_viewer_headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "role-required"


def test_admin_discovery_runs_list_and_latest_are_sanitized(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    client = _client(test_db_session)
    old_started = datetime(2026, 5, 24, 10, 0, 0, tzinfo=timezone.utc)
    new_started = datetime(2026, 5, 25, 10, 0, 0, tzinfo=timezone.utc)
    for started in (old_started, new_started):
        response = client.post(
            f"/api/v1/gateways/{gateway.id}/discovery-runs",
            headers=_gateway_headers(gateway.id),
            json=_report(started),
        )
        assert response.status_code == 200

    list_response = client.get(
        f"/api/v1/admin/gateways/{gateway.id}/discovery-runs",
        headers=_admin_headers(),
    )
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 2
    assert items[0]["started_at"] == "2026-05-25T10:00:00Z"
    assert "raw_banner" not in items[0]["findings"][0]

    latest_response = client.get(
        f"/api/v1/admin/gateways/{gateway.id}/discovery-runs/latest",
        headers=_admin_headers(),
    )
    assert latest_response.status_code == 200
    latest = latest_response.json()
    assert latest["started_at"] == "2026-05-25T10:00:00Z"
    assert latest["findings"][0]["candidate_kind"] == "possible_camera"
    assert latest["findings"][0]["device_hint"] == "ip_camera"
    assert latest["findings"][0]["mac_vendor"] == "Hikvision"
    assert "raw_banner" not in latest["findings"][0]
    assert "http_body" not in latest["findings"][0]
    assert "credentials" not in latest["findings"][0]


def test_gateway_discovery_accepts_legacy_v1_finding_shape(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    client = _client(test_db_session)
    report = _report()
    report["findings"] = [
        {
            "ip": "192.168.50.2",
            "hostname": None,
            "open_ports": [554],
            "status": "open",
            "candidate_kind": "possible_camera",
            "confidence": "high",
        }
    ]

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/discovery-runs",
        headers=_gateway_headers(gateway.id),
        json=report,
    )

    assert response.status_code == 200
    row = test_db_session.execute(select(GatewayDiscoveryRun)).scalar_one()
    assert row.findings[0]["device_hint"] == "unknown_network_device"
    assert row.findings[0]["hostnames"] == []
    assert row.findings[0]["observed_protocols"] == []
