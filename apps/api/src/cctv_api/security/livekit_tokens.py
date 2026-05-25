from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from jwt import encode

from cctv_api.core.config import Settings

MAX_LIVEKIT_TOKEN_TTL_SECONDS = 60


class LiveKitTokenConfigError(Exception):
    pass


@dataclass(frozen=True)
class LiveKitTokenResult:
    token: str
    livekit_url: str
    room: str
    issued_at: datetime
    expires_at: datetime
    jti: str


def mint_viewer_subscribe_token(
    settings: Settings,
    *,
    user_id: uuid.UUID,
    camera_id: uuid.UUID,
    room: str,
    ttl_seconds: int = MAX_LIVEKIT_TOKEN_TTL_SECONDS,
) -> LiveKitTokenResult:
    identity = f"viewer:{user_id}:{camera_id}"
    return _mint_livekit_token(
        settings,
        identity=identity,
        room=room,
        video_grants={
            "roomJoin": True,
            "room": room,
            "canSubscribe": True,
            "canPublish": False,
        },
        ttl_seconds=ttl_seconds,
    )


def mint_gateway_publish_token(
    settings: Settings,
    *,
    gateway_id: uuid.UUID,
    camera_id: uuid.UUID,
    room: str,
    ttl_seconds: int = MAX_LIVEKIT_TOKEN_TTL_SECONDS,
) -> LiveKitTokenResult:
    identity = f"gateway:{gateway_id}:{camera_id}"
    return _mint_livekit_token(
        settings,
        identity=identity,
        room=room,
        video_grants={
            "roomJoin": True,
            "room": room,
            "canSubscribe": False,
            "canPublish": True,
        },
        ttl_seconds=ttl_seconds,
    )


def _mint_livekit_token(
    settings: Settings,
    *,
    identity: str,
    room: str,
    video_grants: dict[str, object],
    ttl_seconds: int,
) -> LiveKitTokenResult:
    livekit_url, api_key, api_secret = _livekit_credentials(settings)
    now = datetime.now(timezone.utc)
    ttl = min(ttl_seconds, MAX_LIVEKIT_TOKEN_TTL_SECONDS)
    expires_at = now + timedelta(seconds=ttl)
    jti = uuid.uuid4().hex
    claims: dict[str, object] = {
        "iss": api_key,
        "sub": identity,
        "nbf": int(now.timestamp()),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": jti,
        "video": video_grants,
    }
    token = encode(claims, api_secret, algorithm="HS256")
    return LiveKitTokenResult(
        token=token,
        livekit_url=livekit_url,
        room=room,
        issued_at=now,
        expires_at=expires_at,
        jti=jti,
    )


def _livekit_credentials(settings: Settings) -> tuple[str, str, str]:
    if settings.LIVEKIT_MODE == "fallback":
        values = (
            settings.LIVEKIT_FALLBACK_URL,
            settings.LIVEKIT_FALLBACK_API_KEY,
            settings.LIVEKIT_FALLBACK_API_SECRET,
        )
    else:
        values = (
            settings.LIVEKIT_CLOUD_URL,
            settings.LIVEKIT_CLOUD_API_KEY,
            settings.LIVEKIT_CLOUD_API_SECRET,
        )

    if any(_is_placeholder(value) for value in values):
        raise LiveKitTokenConfigError("livekit-token-config-invalid")

    return values


def _is_placeholder(value: str) -> bool:
    stripped = value.strip()
    return not stripped or stripped == "replace-me" or "replace-me" in stripped
