from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class CommandVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class GatewayCommand:
    command_id: str
    kind: str
    gateway_id: str
    issued_at: datetime
    expires_at: datetime
    payload: dict[str, object] = field(default_factory=dict)
    signature: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GatewayCommand:
        return cls(
            command_id=str(data["command_id"]),
            kind=str(data["kind"]),
            gateway_id=str(data["gateway_id"]),
            issued_at=_parse_datetime(str(data["issued_at"])),
            expires_at=_parse_datetime(str(data["expires_at"])),
            payload=_payload_dict(data.get("payload", {})),
            signature=str(data["signature"]),
        )


def verify_gateway_command(
    command: GatewayCommand,
    signing_key: str,
    *,
    expected_gateway_id: str,
    now: datetime | None = None,
) -> None:
    key_bytes = _validated_key(signing_key)
    if command.gateway_id != expected_gateway_id:
        raise CommandVerificationError("gateway-command-target-mismatch")

    current_time = datetime.now(timezone.utc) if now is None else _normalize_datetime(now)
    expires_at = _normalize_datetime(command.expires_at)
    if expires_at <= current_time:
        raise CommandVerificationError("gateway-command-expired")

    expected_signature = _signature_for_payload(_signed_payload(command), key_bytes)
    if not hmac.compare_digest(command.signature, expected_signature):
        raise CommandVerificationError("gateway-command-signature-invalid")


def canonical_command_json(command: GatewayCommand) -> str:
    return json.dumps(
        _signed_payload(command),
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


def _signed_payload(command: GatewayCommand) -> dict[str, Any]:
    return {
        "command_id": command.command_id,
        "expires_at": _format_datetime(command.expires_at),
        "gateway_id": command.gateway_id,
        "issued_at": _format_datetime(command.issued_at),
        "kind": command.kind,
        "payload": _normalize_value(command.payload),
    }


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


def _payload_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    raise CommandVerificationError("gateway-command-payload-invalid")


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        return _normalize_datetime(datetime.fromisoformat(normalized))
    except ValueError as exc:
        raise CommandVerificationError("gateway-command-datetime-invalid") from exc


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
        raise CommandVerificationError("gateway-command-signing-key-invalid")
    return key.encode("utf-8")
