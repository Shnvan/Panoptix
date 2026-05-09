from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from panoptix_edge_agent.commands import (
    CommandVerificationError,
    GatewayCommand,
    canonical_command_json,
    verify_gateway_command,
)

SIGNING_KEY = "test-command-signing-key-with-enough-entropy"
NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)
VALID_SIGNATURE = "JzWX_J0pZjFozy8jD0NUHXqnuWXPZvwbpfiSmK-XQg0"


def _command_data() -> dict[str, object]:
    return {
        "command_id": "11111111-1111-1111-1111-111111111111",
        "kind": "gateway.command.start_publish",
        "gateway_id": "gateway-1",
        "issued_at": "2026-05-07T12:00:00Z",
        "expires_at": "2026-05-07T12:00:30Z",
        "payload": {"camera_id": "camera-1", "room": "camera_ab12cd34"},
        "signature": VALID_SIGNATURE,
    }


def test_gateway_command_verifies_backend_compatible_signature() -> None:
    command = GatewayCommand.from_dict(_command_data())

    verify_gateway_command(
        command,
        SIGNING_KEY,
        expected_gateway_id="gateway-1",
        now=NOW,
    )


def test_canonical_command_json_excludes_signature() -> None:
    command = GatewayCommand.from_dict(_command_data())

    body = canonical_command_json(command)

    assert "signature" not in body
    assert body.startswith('{"command_id"')
    assert '"expires_at":"2026-05-07T12:00:30Z"' in body


def test_gateway_command_rejects_tampered_payload() -> None:
    data = _command_data()
    data["payload"] = {"camera_id": "camera-2"}
    command = GatewayCommand.from_dict(data)

    with pytest.raises(CommandVerificationError, match="signature-invalid"):
        verify_gateway_command(
            command,
            SIGNING_KEY,
            expected_gateway_id="gateway-1",
            now=NOW,
        )


def test_gateway_command_rejects_tampered_signature() -> None:
    data = _command_data()
    data["signature"] = "invalid-signature"
    command = GatewayCommand.from_dict(data)

    with pytest.raises(CommandVerificationError, match="signature-invalid"):
        verify_gateway_command(
            command,
            SIGNING_KEY,
            expected_gateway_id="gateway-1",
            now=NOW,
        )


def test_gateway_command_rejects_expired_command() -> None:
    command = GatewayCommand.from_dict(_command_data())

    with pytest.raises(CommandVerificationError, match="expired"):
        verify_gateway_command(
            command,
            SIGNING_KEY,
            expected_gateway_id="gateway-1",
            now=NOW + timedelta(seconds=31),
        )


def test_gateway_command_rejects_wrong_gateway() -> None:
    command = GatewayCommand.from_dict(_command_data())

    with pytest.raises(CommandVerificationError, match="target-mismatch"):
        verify_gateway_command(
            command,
            SIGNING_KEY,
            expected_gateway_id="gateway-2",
            now=NOW,
        )


def test_gateway_command_rejects_missing_signing_key() -> None:
    command = GatewayCommand.from_dict(_command_data())

    with pytest.raises(CommandVerificationError, match="signing-key-invalid"):
        verify_gateway_command(
            command,
            "",
            expected_gateway_id="gateway-1",
            now=NOW,
        )
