from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import CameraSourceType, GatewayStatus, StreamKind
from cctv_api.models.tables import (
    Camera,
    CameraAcl,
    EdgeGateway,
    GatewayCameraAssignment,
    StreamGrant,
    User,
)

LIVEKIT_SECRET = "test-livekit-secret-with-at-least-32-bytes"


def _settings() -> Settings:
    return Settings(
        APP_ENV="development",
        ALLOW_DEV_AUTH=True,
        LIVEKIT_CLOUD_URL="wss://livekit.example.test",
        LIVEKIT_CLOUD_API_KEY="test-livekit-key",
        LIVEKIT_CLOUD_API_SECRET=LIVEKIT_SECRET,
    )


def _client_with_db(test_db_session: DbSession) -> TestClient:
    app = create_app(settings=_settings())

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


def _auth_headers(email: str = "viewer@example.test") -> dict[str, str]:
    return {
        "x-panoptix-dev-auth": "1",
        "x-panoptix-dev-email": email,
        "x-panoptix-dev-subject": email,
    }


def _gateway_headers(gateway_id: uuid.UUID) -> dict[str, str]:
    return {"x-panoptix-dev-gateway-id": str(gateway_id)}


def _seed_user(db: DbSession, *, email: str = "viewer@example.test") -> User:
    user = User(id=uuid.uuid4(), email=email, idp_subject=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_gateway(db: DbSession, *, status: GatewayStatus = GatewayStatus.enabled) -> EdgeGateway:
    gateway = EdgeGateway(id=uuid.uuid4(), name="Test Gateway", status=status)
    db.add(gateway)
    db.commit()
    db.refresh(gateway)
    return gateway


def _seed_camera(db: DbSession, *, retired: bool = False) -> Camera:
    camera = Camera(
        id=uuid.uuid4(),
        display_name="Front Gate",
        source_type=CameraSourceType.rtsp,
        livekit_room_name=f"camera_{uuid.uuid4().hex[:8]}",
        retired_at=datetime.now(timezone.utc) if retired else None,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


def _grant_camera_acl(db: DbSession, *, user_id: uuid.UUID, camera_id: uuid.UUID) -> None:
    db.add(CameraAcl(user_id=user_id, camera_id=camera_id))
    db.commit()


def _assign_gateway_camera(db: DbSession, *, gateway_id: uuid.UUID, camera_id: uuid.UUID) -> None:
    db.add(GatewayCameraAssignment(gateway_id=gateway_id, camera_id=camera_id))
    db.commit()


def _decode_livekit_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, LIVEKIT_SECRET, algorithms=["HS256"], options={"verify_aud": False})


def test_viewer_token_succeeds_with_active_camera_acl(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    camera = _seed_camera(test_db_session)
    _grant_camera_acl(test_db_session, user_id=user.id, camera_id=camera.id)
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/cameras/{camera.id}/view-token", headers=_auth_headers())

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["camera_id"] == str(camera.id)
    assert body["room"] == camera.livekit_room_name
    assert body["livekit_url"] == "wss://livekit.example.test"
    claims = _decode_livekit_token(body["token"])
    assert claims["iss"] == "test-livekit-key"
    assert claims["sub"] == f"viewer:{user.id}:{camera.id}"
    assert claims["video"] == {
        "roomJoin": True,
        "room": camera.livekit_room_name,
        "canSubscribe": True,
        "canPublish": False,
    }
    assert claims["exp"] - claims["iat"] <= 60
    grants = test_db_session.execute(select(StreamGrant)).scalars().all()
    assert len(grants) == 1
    assert grants[0].kind == StreamKind.viewer_subscribe


def test_viewer_token_denied_without_camera_acl(test_db_session: DbSession) -> None:
    _seed_user(test_db_session)
    camera = _seed_camera(test_db_session)
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/cameras/{camera.id}/view-token", headers=_auth_headers())

    assert response.status_code == 403
    assert response.json()["detail"] == "camera-access-denied"


def test_viewer_token_denied_for_retired_camera(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    camera = _seed_camera(test_db_session, retired=True)
    _grant_camera_acl(test_db_session, user_id=user.id, camera_id=camera.id)
    client = _client_with_db(test_db_session)

    response = client.get(f"/api/v1/cameras/{camera.id}/view-token", headers=_auth_headers())

    assert response.status_code == 404
    assert response.json()["detail"] == "camera-not-found"


def test_gateway_ingest_token_succeeds_with_active_assignment(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client_with_db(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/ingest-token",
        headers=_gateway_headers(gateway.id),
        json={"camera_id": str(camera.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["camera_id"] == str(camera.id)
    assert body["room"] == camera.livekit_room_name
    assert body["livekit_url"] == "wss://livekit.example.test"
    claims = _decode_livekit_token(body["token"])
    assert claims["sub"] == f"gateway:{gateway.id}:{camera.id}"
    assert claims["video"] == {
        "roomJoin": True,
        "room": camera.livekit_room_name,
        "canSubscribe": False,
        "canPublish": True,
    }
    assert claims["exp"] - claims["iat"] <= 60
    grants = test_db_session.execute(select(StreamGrant)).scalars().all()
    assert len(grants) == 1
    assert grants[0].kind == StreamKind.gateway_publish


def test_gateway_ingest_token_denied_without_assignment(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    client = _client_with_db(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/ingest-token",
        headers=_gateway_headers(gateway.id),
        json={"camera_id": str(camera.id)},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gateway-camera-assignment-denied"


def test_gateway_ingest_token_denied_for_disabled_gateway(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session, status=GatewayStatus.disabled)
    camera = _seed_camera(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client_with_db(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/ingest-token",
        headers=_gateway_headers(gateway.id),
        json={"camera_id": str(camera.id)},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gateway-disabled-or-not-found"


def test_gateway_ingest_token_denied_for_gateway_id_mismatch(test_db_session: DbSession) -> None:
    gateway = _seed_gateway(test_db_session)
    other_gateway = _seed_gateway(test_db_session)
    camera = _seed_camera(test_db_session)
    _assign_gateway_camera(test_db_session, gateway_id=gateway.id, camera_id=camera.id)
    client = _client_with_db(test_db_session)

    response = client.post(
        f"/api/v1/gateways/{gateway.id}/ingest-token",
        headers=_gateway_headers(other_gateway.id),
        json={"camera_id": str(camera.id)},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gateway-id-mismatch"


def test_livekit_config_placeholders_fail_closed_for_viewer(test_db_session: DbSession) -> None:
    user = _seed_user(test_db_session)
    camera = _seed_camera(test_db_session)
    _grant_camera_acl(test_db_session, user_id=user.id, camera_id=camera.id)
    app = create_app(settings=Settings(APP_ENV="development", ALLOW_DEV_AUTH=True))

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    client = TestClient(app)

    response = client.get(f"/api/v1/cameras/{camera.id}/view-token", headers=_auth_headers())

    assert response.status_code == 503
    assert response.json()["detail"] == "livekit-token-config-invalid"
