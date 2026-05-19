from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

from cctv_api.gateway.models import GatewayCommandEnvelope


class CommandSigningError(ValueError):
    pass


class CommandVerificationError(ValueError):
    pass


def sign_command_envelope(
    envelope: GatewayCommandEnvelope,
    signing_key: str,
) -> GatewayCommandEnvelope:
    key_bytes = _validated_key(signing_key)
    signature = _signature_for_payload(_signed_payload(envelope), key_bytes)
    return envelope.model_copy(update={"signature": signature})


def verify_command_envelope(
    envelope: GatewayCommandEnvelope,
    signing_key: str,
    *,
    expected_gateway_id: str,
    now: datetime | None = None,
) -> None:
    key_bytes = _validated_key(signing_key)
    if envelope.gateway_id != expected_gateway_id:
        raise CommandVerificationError("gateway-command-target-mismatch")

    current_time = datetime.now(timezone.utc) if now is None else _normalize_datetime(now)
    expires_at = _normalize_datetime(envelope.expires_at)
    if expires_at <= current_time:
        raise CommandVerificationError("gateway-command-expired")

    expected_signature = _signature_for_payload(_signed_payload(envelope), key_bytes)
    if not hmac.compare_digest(envelope.signature, expected_signature):
        raise CommandVerificationError("gateway-command-signature-invalid")


def canonical_command_json(envelope: GatewayCommandEnvelope) -> str:
    return json.dumps(
        _signed_payload(envelope),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _signature_for_payload(payload: dict[str, Any], key_bytes: bytes) -> str:
    body = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    digest = hmac.new(key_bytes, body, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _signed_payload(envelope: GatewayCommandEnvelope) -> dict[str, Any]:
    payload = envelope.model_dump(mode="python", exclude={"signature"})
    return _normalize_value(payload)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return _format_datetime(value)
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    return value


def _format_datetime(value: datetime) -> str:
    normalized = _normalize_datetime(value)
    return normalized.isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _validated_key(signing_key: str) -> bytes:
    key = signing_key.strip()
    if not key or key == "replace-me":
        raise CommandSigningError("gateway-command-signing-key-invalid")
    return key.encode("utf-8")
