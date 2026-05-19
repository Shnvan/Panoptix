from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import InvalidTokenError

from cctv_api.core.config import Settings


class LiveKitWebhookVerificationError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class LiveKitWebhookVerificationResult:
    token: str
    replay_signature: str
    claims: dict[str, Any]


def verify_livekit_webhook_authorization(
    settings: Settings,
    *,
    authorization_header: str | None,
    raw_body: bytes,
) -> LiveKitWebhookVerificationResult:
    if authorization_header is None or not authorization_header.strip():
        raise LiveKitWebhookVerificationError("livekit-webhook-authorization-required")

    token = _extract_token(authorization_header)
    _, api_key, api_secret = _livekit_credentials(settings)

    try:
        claims = jwt.decode(
            token,
            api_secret,
            algorithms=["HS256"],
            issuer=api_key,
            options={"verify_aud": False},
        )
    except InvalidTokenError as exc:
        raise LiveKitWebhookVerificationError("livekit-webhook-signature-invalid") from exc

    claimed_hash = claims.get("sha256")
    if not isinstance(claimed_hash, str):
        raise LiveKitWebhookVerificationError("livekit-webhook-signature-invalid")

    try:
        expected_body_hash = base64.b64decode(claimed_hash, validate=True)
    except ValueError as exc:
        raise LiveKitWebhookVerificationError("livekit-webhook-signature-invalid") from exc

    actual_body_hash = hashlib.sha256(raw_body).digest()
    if not hmac.compare_digest(actual_body_hash, expected_body_hash):
        raise LiveKitWebhookVerificationError("livekit-webhook-signature-invalid")

    return LiveKitWebhookVerificationResult(
        token=token,
        replay_signature=_jwt_signature(token),
        claims=claims,
    )


def _extract_token(authorization_header: str) -> str:
    value = authorization_header.strip()
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    if not value:
        raise LiveKitWebhookVerificationError("livekit-webhook-authorization-required")
    return value


def _jwt_signature(token: str) -> str:
    parts = token.split(".")
    if len(parts) == 3 and parts[2]:
        return parts[2]
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
        raise LiveKitWebhookVerificationError("livekit-webhook-config-invalid")

    return values


def _is_placeholder(value: str) -> bool:
    stripped = value.strip()
    return not stripped or stripped == "replace-me" or "replace-me" in stripped
