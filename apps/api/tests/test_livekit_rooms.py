"""Tests for LiveKit room service — participant removal (§13.5 rule 11)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from cctv_api.core.config import Settings
from cctv_api.security.livekit_rooms import (
    _livekit_admin_token,
    _livekit_http_url,
    remove_gateway_participants,
    remove_room_viewers,
    remove_user_participants,
)

LIVEKIT_SECRET = "test-livekit-secret-with-at-least-32-bytes"


def _settings(**overrides: object) -> Settings:
    base = dict(
        APP_ENV="development",
        LIVEKIT_CLOUD_URL="wss://livekit.example.test",
        LIVEKIT_CLOUD_API_KEY="test-livekit-key",
        LIVEKIT_CLOUD_API_SECRET=LIVEKIT_SECRET,
        AUDIT_HMAC_KEY="test-audit-hmac-key-do-not-use",
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


# ── URL derivation ──


def test_livekit_http_url_wss_to_https() -> None:
    s = _settings(LIVEKIT_CLOUD_URL="wss://livekit.example.test")
    assert _livekit_http_url(s) == "https://livekit.example.test"


def test_livekit_http_url_ws_to_http() -> None:
    s = _settings(LIVEKIT_CLOUD_URL="ws://localhost:7880")
    assert _livekit_http_url(s) == "http://localhost:7880"


def test_livekit_http_url_fallback_mode() -> None:
    s = _settings(
        LIVEKIT_MODE="fallback",
        LIVEKIT_FALLBACK_URL="wss://fallback.example.test",
    )
    assert _livekit_http_url(s) == "https://fallback.example.test"


# ── Admin token ──


def test_admin_token_is_valid_jwt() -> None:
    import jwt

    token = _livekit_admin_token("test-key", LIVEKIT_SECRET)
    claims = jwt.decode(token, LIVEKIT_SECRET, algorithms=["HS256"])
    assert claims["iss"] == "test-key"
    assert claims["video"]["roomAdmin"] is True
    assert claims["video"]["roomList"] is True


# ── Placeholder credentials ──


def test_remove_skips_with_placeholder_credentials() -> None:
    s = _settings(LIVEKIT_CLOUD_API_KEY="replace-me")
    result = remove_user_participants(s, user_id=uuid.uuid4(), room_names=["room-1"])
    assert result.rooms_checked == 0
    assert result.participants_removed == 0
    assert result.errors == ["livekit-credentials-placeholder"]


# ── Participant removal with mocked httpx ──


def test_remove_participant_success() -> None:
    user_id = uuid.uuid4()
    camera_id = uuid.uuid4()

    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = {
        "participants": [
            {"identity": f"viewer:{user_id}:{camera_id}", "sid": "PA_xxx"},
            {"identity": f"gateway:{uuid.uuid4()}:{camera_id}", "sid": "PA_gw"},
        ]
    }

    remove_response = MagicMock()
    remove_response.status_code = 200

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.side_effect = [list_response, remove_response]

        result = remove_user_participants(
            _settings(),
            user_id=user_id,
            room_names=["room-1"],
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 1
    assert result.errors == []

    # Verify the correct API calls were made
    calls = mock_post.call_args_list
    assert len(calls) == 2
    assert "/ListParticipants" in calls[0].args[0]
    assert "/RemoveParticipant" in calls[1].args[0]
    assert calls[1].kwargs["json"]["identity"] == f"viewer:{user_id}:{camera_id}"


def test_remove_does_not_touch_non_viewer_participants() -> None:
    user_id = uuid.uuid4()

    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = {
        "participants": [
            {"identity": f"gateway:{uuid.uuid4()}:{uuid.uuid4()}", "sid": "PA_gw"},
        ]
    }

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.return_value = list_response

        result = remove_user_participants(
            _settings(),
            user_id=user_id,
            room_names=["room-1"],
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 0
    assert result.errors == []
    # Should only have called ListParticipants, not RemoveParticipant
    assert mock_post.call_count == 1


def test_remove_across_multiple_rooms() -> None:
    user_id = uuid.uuid4()
    cam1, cam2 = uuid.uuid4(), uuid.uuid4()

    list_resp_1 = MagicMock()
    list_resp_1.status_code = 200
    list_resp_1.json.return_value = {
        "participants": [{"identity": f"viewer:{user_id}:{cam1}", "sid": "P1"}]
    }

    list_resp_2 = MagicMock()
    list_resp_2.status_code = 200
    list_resp_2.json.return_value = {
        "participants": [{"identity": f"viewer:{user_id}:{cam2}", "sid": "P2"}]
    }

    remove_resp = MagicMock()
    remove_resp.status_code = 200

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.side_effect = [list_resp_1, remove_resp, list_resp_2, remove_resp]

        result = remove_user_participants(
            _settings(),
            user_id=user_id,
            room_names=["room-a", "room-b"],
        )

    assert result.rooms_checked == 2
    assert result.participants_removed == 2
    assert result.errors == []


def test_remove_handles_list_error_gracefully() -> None:
    import httpx

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("connection refused")

        result = remove_user_participants(
            _settings(),
            user_id=uuid.uuid4(),
            room_names=["room-1"],
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 0
    assert len(result.errors) == 1
    assert "list-error" in result.errors[0]


def test_remove_handles_list_non_200() -> None:
    bad_response = MagicMock()
    bad_response.status_code = 500

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.return_value = bad_response

        result = remove_user_participants(
            _settings(),
            user_id=uuid.uuid4(),
            room_names=["room-1"],
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 0
    assert "list-participants-failed:room-1:500" in result.errors


def test_remove_empty_room_list() -> None:
    result = remove_user_participants(
        _settings(),
        user_id=uuid.uuid4(),
        room_names=[],
    )

    assert result.rooms_checked == 0
    assert result.participants_removed == 0
    assert result.errors == []


# ── Gateway participant removal ──


def test_remove_gateway_placeholder_creds_skips() -> None:
    s = _settings(LIVEKIT_CLOUD_API_KEY="replace-me")
    result = remove_gateway_participants(s, gateway_id=uuid.uuid4(), room_names=["room-1"])
    assert result.rooms_checked == 0
    assert result.participants_removed == 0
    assert result.errors == ["livekit-credentials-placeholder"]


def test_remove_gateway_participant_success() -> None:
    gateway_id = uuid.uuid4()
    camera_id = uuid.uuid4()

    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = {
        "participants": [
            {"identity": f"gateway:{gateway_id}:{camera_id}", "sid": "PA_gw"},
            {"identity": f"viewer:{uuid.uuid4()}:{camera_id}", "sid": "PA_viewer"},
        ]
    }

    remove_response = MagicMock()
    remove_response.status_code = 200

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.side_effect = [list_response, remove_response]

        result = remove_gateway_participants(
            _settings(),
            gateway_id=gateway_id,
            room_names=["room-1"],
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 1
    assert result.errors == []

    calls = mock_post.call_args_list
    assert len(calls) == 2
    assert "/ListParticipants" in calls[0].args[0]
    assert "/RemoveParticipant" in calls[1].args[0]
    assert calls[1].kwargs["json"]["identity"] == f"gateway:{gateway_id}:{camera_id}"


def test_remove_gateway_ignores_viewer_participants() -> None:
    gateway_id = uuid.uuid4()

    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = {
        "participants": [
            {"identity": f"viewer:{uuid.uuid4()}:{uuid.uuid4()}", "sid": "PA_v"},
        ]
    }

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.return_value = list_response

        result = remove_gateway_participants(
            _settings(),
            gateway_id=gateway_id,
            room_names=["room-1"],
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 0
    assert result.errors == []
    assert mock_post.call_count == 1


def test_remove_gateway_across_multiple_rooms() -> None:
    gateway_id = uuid.uuid4()
    cam1, cam2 = uuid.uuid4(), uuid.uuid4()

    list_resp_1 = MagicMock()
    list_resp_1.status_code = 200
    list_resp_1.json.return_value = {
        "participants": [{"identity": f"gateway:{gateway_id}:{cam1}", "sid": "P1"}]
    }

    list_resp_2 = MagicMock()
    list_resp_2.status_code = 200
    list_resp_2.json.return_value = {
        "participants": [{"identity": f"gateway:{gateway_id}:{cam2}", "sid": "P2"}]
    }

    remove_resp = MagicMock()
    remove_resp.status_code = 200

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.side_effect = [list_resp_1, remove_resp, list_resp_2, remove_resp]

        result = remove_gateway_participants(
            _settings(),
            gateway_id=gateway_id,
            room_names=["room-a", "room-b"],
        )

    assert result.rooms_checked == 2
    assert result.participants_removed == 2
    assert result.errors == []


def test_remove_gateway_handles_list_error_gracefully() -> None:
    import httpx

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("connection refused")

        result = remove_gateway_participants(
            _settings(),
            gateway_id=uuid.uuid4(),
            room_names=["room-1"],
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 0
    assert len(result.errors) == 1
    assert "list-error" in result.errors[0]


def test_remove_gateway_handles_list_non_200() -> None:
    bad_response = MagicMock()
    bad_response.status_code = 500

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.return_value = bad_response

        result = remove_gateway_participants(
            _settings(),
            gateway_id=uuid.uuid4(),
            room_names=["room-1"],
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 0
    assert "list-participants-failed:room-1:500" in result.errors


def test_remove_gateway_empty_room_list() -> None:
    result = remove_gateway_participants(
        _settings(),
        gateway_id=uuid.uuid4(),
        room_names=[],
    )

    assert result.rooms_checked == 0
    assert result.participants_removed == 0
    assert result.errors == []


# ── Room viewer removal (camera disable) ──


def test_remove_room_viewers_placeholder_creds_skips() -> None:
    s = _settings(LIVEKIT_CLOUD_API_KEY="replace-me")
    result = remove_room_viewers(s, room_name="camera-room-1")
    assert result.rooms_checked == 0
    assert result.participants_removed == 0
    assert result.errors == ["livekit-credentials-placeholder"]


def test_remove_room_viewers_success() -> None:
    user_id = uuid.uuid4()
    camera_id = uuid.uuid4()

    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = {
        "participants": [
            {"identity": f"viewer:{user_id}:{camera_id}", "sid": "PA_v1"},
            {"identity": f"gateway:{uuid.uuid4()}:{camera_id}", "sid": "PA_gw"},
        ]
    }

    remove_response = MagicMock()
    remove_response.status_code = 200

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.side_effect = [list_response, remove_response]

        result = remove_room_viewers(
            _settings(),
            room_name="camera-room-1",
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 1
    assert result.errors == []

    calls = mock_post.call_args_list
    assert len(calls) == 2
    assert "/ListParticipants" in calls[0].args[0]
    assert "/RemoveParticipant" in calls[1].args[0]
    assert calls[1].kwargs["json"]["identity"] == f"viewer:{user_id}:{camera_id}"


def test_remove_room_viewers_ignores_gateway_participants() -> None:
    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = {
        "participants": [
            {"identity": f"gateway:{uuid.uuid4()}:{uuid.uuid4()}", "sid": "PA_gw"},
        ]
    }

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.return_value = list_response

        result = remove_room_viewers(
            _settings(),
            room_name="camera-room-1",
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 0
    assert result.errors == []
    assert mock_post.call_count == 1


def test_remove_room_viewers_multiple_viewers() -> None:
    camera_id = uuid.uuid4()
    user1, user2 = uuid.uuid4(), uuid.uuid4()

    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = {
        "participants": [
            {"identity": f"viewer:{user1}:{camera_id}", "sid": "P1"},
            {"identity": f"viewer:{user2}:{camera_id}", "sid": "P2"},
        ]
    }

    remove_resp = MagicMock()
    remove_resp.status_code = 200

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.side_effect = [list_response, remove_resp, remove_resp]

        result = remove_room_viewers(
            _settings(),
            room_name="camera-room-1",
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 2
    assert result.errors == []


def test_remove_room_viewers_handles_list_error() -> None:
    import httpx

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("connection refused")

        result = remove_room_viewers(
            _settings(),
            room_name="camera-room-1",
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 0
    assert len(result.errors) == 1
    assert "list-error" in result.errors[0]


def test_remove_room_viewers_handles_list_non_200() -> None:
    bad_response = MagicMock()
    bad_response.status_code = 500

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.return_value = bad_response

        result = remove_room_viewers(
            _settings(),
            room_name="camera-room-1",
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 0
    assert "list-participants-failed:camera-room-1:500" in result.errors


def test_remove_room_viewers_empty_room() -> None:
    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = {"participants": []}

    with patch("cctv_api.security.livekit_rooms.httpx.post") as mock_post:
        mock_post.return_value = list_response

        result = remove_room_viewers(
            _settings(),
            room_name="camera-room-1",
        )

    assert result.rooms_checked == 1
    assert result.participants_removed == 0
    assert result.errors == []
