"""LiveKit Room Service — server-side participant management (§13.5 rule 11).

Provides ``remove_participant`` to forcibly disconnect a user from a
LiveKit room when their account is disabled.  Uses the LiveKit Twirp
API directly via httpx, avoiding the need for an async event loop in
synchronous FastAPI endpoints.

The service authenticates to LiveKit using the same API key/secret
already configured for token minting.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from jwt import encode as jwt_encode

from cctv_api.core.config import Settings

logger = logging.getLogger(__name__)

# LiveKit Twirp endpoints
_LIST_PARTICIPANTS_PATH = "/twirp/livekit.RoomService/ListParticipants"
_REMOVE_PARTICIPANT_PATH = "/twirp/livekit.RoomService/RemoveParticipant"


class LiveKitRoomServiceError(Exception):
    """Raised when a LiveKit room API call fails."""


@dataclass(frozen=True)
class ParticipantRemovalResult:
    """Result of attempting to remove a user's participants."""

    rooms_checked: int
    participants_removed: int
    errors: list[str]


def _livekit_admin_token(api_key: str, api_secret: str) -> str:
    """Mint a short-lived admin JWT for the LiveKit server API."""
    now = datetime.now(timezone.utc)
    claims = {
        "iss": api_key,
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=30)).timestamp()),
        "video": {"roomAdmin": True, "roomList": True},
    }
    return jwt_encode(claims, api_secret, algorithm="HS256")


def _livekit_http_url(settings: Settings) -> str:
    """Derive the HTTP(S) URL from the WSS URL for API calls."""
    if settings.LIVEKIT_MODE == "fallback":
        wss_url = settings.LIVEKIT_FALLBACK_URL
    else:
        wss_url = settings.LIVEKIT_CLOUD_URL

    # wss://host → https://host, ws://host → http://host
    if wss_url.startswith("wss://"):
        return "https://" + wss_url[6:]
    if wss_url.startswith("ws://"):
        return "http://" + wss_url[5:]
    return wss_url


def _livekit_credentials(settings: Settings) -> tuple[str, str]:
    """Return (api_key, api_secret) for the active LiveKit mode."""
    if settings.LIVEKIT_MODE == "fallback":
        return settings.LIVEKIT_FALLBACK_API_KEY, settings.LIVEKIT_FALLBACK_API_SECRET
    return settings.LIVEKIT_CLOUD_API_KEY, settings.LIVEKIT_CLOUD_API_SECRET


def _is_placeholder(value: str) -> bool:
    stripped = value.strip()
    return not stripped or "replace-me" in stripped


def remove_user_participants(
    settings: Settings,
    *,
    user_id: uuid.UUID,
    room_names: list[str],
) -> ParticipantRemovalResult:
    """Remove all participants belonging to ``user_id`` from the given rooms.

    The viewer identity format is ``viewer:{user_id}:{camera_id}`` so we
    match any identity starting with ``viewer:{user_id}:``.

    This function is fail-open: errors are collected but do not raise.
    The caller can audit the errors without blocking the disable flow.
    """
    api_key, api_secret = _livekit_credentials(settings)

    if _is_placeholder(api_key) or _is_placeholder(api_secret):
        logger.warning("LiveKit credentials are placeholders — skipping participant removal")
        return ParticipantRemovalResult(rooms_checked=0, participants_removed=0, errors=["livekit-credentials-placeholder"])

    base_url = _livekit_http_url(settings)
    token = _livekit_admin_token(api_key, api_secret)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    identity_prefix = f"viewer:{user_id}:"
    rooms_checked = 0
    participants_removed = 0
    errors: list[str] = []

    for room_name in room_names:
        rooms_checked += 1
        try:
            # List participants in the room
            resp = httpx.post(
                f"{base_url}{_LIST_PARTICIPANTS_PATH}",
                headers=headers,
                json={"room": room_name},
                timeout=10.0,
            )
            if resp.status_code != 200:
                errors.append(f"list-participants-failed:{room_name}:{resp.status_code}")
                continue

            data = resp.json()
            participants = data.get("participants", [])

            for participant in participants:
                identity = participant.get("identity", "")
                if identity.startswith(identity_prefix):
                    try:
                        rm_resp = httpx.post(
                            f"{base_url}{_REMOVE_PARTICIPANT_PATH}",
                            headers=headers,
                            json={"room": room_name, "identity": identity},
                            timeout=10.0,
                        )
                        if rm_resp.status_code == 200:
                            participants_removed += 1
                            logger.info(
                                "Removed participant %s from room %s",
                                identity,
                                room_name,
                            )
                        else:
                            errors.append(f"remove-failed:{room_name}:{identity}:{rm_resp.status_code}")
                    except httpx.HTTPError as exc:
                        errors.append(f"remove-error:{room_name}:{identity}:{exc}")
        except httpx.HTTPError as exc:
            errors.append(f"list-error:{room_name}:{exc}")

    return ParticipantRemovalResult(
        rooms_checked=rooms_checked,
        participants_removed=participants_removed,
        errors=errors,
    )
