from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cctv_api.gateway.command_signing import (
    CommandSigningError,
    CommandVerificationError,
    canonical_command_json,
    sign_command_envelope,
    verify_command_envelope,
)
from cctv_api.gateway.models import GatewayCommandEnvelope

SIGNING_KEY = "test-command-signing-key-with-enough-entropy"
NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)


def _command() -> GatewayCommandEnvelope:
    return GatewayCommandEnvelope(
        command_id="11111111-1111-1111-1111-111111111111",
        kind="gateway.command.start_publish",
        gateway_id="gateway-1",
        issued_at=NOW,
        expires_at=NOW + timedelta(seconds=30),
        payload={"camera_id": "camera-1", "room": "camera_ab12cd34"},
        signature="",
    )


def test_sign_command_envelope_generates_verifiable_signature() -> None:
    signed = sign_command_envelope(_command(), SIGNING_KEY)

    assert signed.signature
    verify_command_envelope(
        signed,
        SIGNING_KEY,
        expected_gateway_id="gateway-1",
        now=NOW,
    )


def test_canonical_command_json_excludes_signature_and_sorts_keys() -> None:
    signed = sign_command_envelope(_command(), SIGNING_KEY)

    body = canonical_command_json(signed)

    assert "signature" not in body
    assert body.startswith('{"command_id"')
    assert '"expires_at":"2026-05-07T12:00:30Z"' in body
    assert '"issued_at":"2026-05-07T12:00:00Z"' in body


def test_verify_command_envelope_rejects_tampered_payload() -> None:
    signed = sign_command_envelope(_command(), SIGNING_KEY)
    tampered = signed.model_copy(update={"payload": {"camera_id": "camera-2"}})

    with pytest.raises(CommandVerificationError, match="signature-invalid"):
        verify_command_envelope(
            tampered,
            SIGNING_KEY,
            expected_gateway_id="gateway-1",
            now=NOW,
        )


def test_verify_command_envelope_rejects_tampered_signature() -> None:
    signed = sign_command_envelope(_command(), SIGNING_KEY)
    tampered = signed.model_copy(update={"signature": "invalid-signature"})

    with pytest.raises(CommandVerificationError, match="signature-invalid"):
        verify_command_envelope(
            tampered,
            SIGNING_KEY,
            expected_gateway_id="gateway-1",
            now=NOW,
        )


def test_verify_command_envelope_rejects_expired_command() -> None:
    signed = sign_command_envelope(_command(), SIGNING_KEY)

    with pytest.raises(CommandVerificationError, match="expired"):
        verify_command_envelope(
            signed,
            SIGNING_KEY,
            expected_gateway_id="gateway-1",
            now=NOW + timedelta(seconds=31),
        )


def test_verify_command_envelope_rejects_wrong_gateway() -> None:
    signed = sign_command_envelope(_command(), SIGNING_KEY)

    with pytest.raises(CommandVerificationError, match="target-mismatch"):
        verify_command_envelope(
            signed,
            SIGNING_KEY,
            expected_gateway_id="gateway-2",
            now=NOW,
        )


def test_sign_command_envelope_rejects_placeholder_key() -> None:
    with pytest.raises(CommandSigningError, match="signing-key-invalid"):
        sign_command_envelope(_command(), "replace-me")
