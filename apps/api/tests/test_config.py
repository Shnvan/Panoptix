from __future__ import annotations

from cctv_api.core.config import Settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.APP_ENV == "development"
    assert settings.CLOCK_SKEW_SECONDS == 30
    assert settings.SESSION_COOKIE_NAME == "panoptix_session"
    assert settings.AUDIT_HMAC_KEY_VERSION == 1
    assert settings.AUDIT_HMAC_KEY == "replace-me"
    assert settings.LIVEKIT_MODE == "cloud"
    assert settings.GATEWAY_HEARTBEAT_INTERVAL_SECONDS == 10


def test_settings_override_via_env(monkeypatch: object) -> None:
    import pytest

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("CLOCK_SKEW_SECONDS", "60")
    monkeypatch.setenv("AUDIT_HMAC_KEY_VERSION", "2")
    monkeypatch.setenv("AUDIT_HMAC_KEY", "test-audit-key")
    settings = Settings()
    assert settings.APP_ENV == "staging"
    assert settings.CLOCK_SKEW_SECONDS == 60
    assert settings.AUDIT_HMAC_KEY_VERSION == 2
    assert settings.AUDIT_HMAC_KEY == "test-audit-key"
    monkeypatch.undo()
