from __future__ import annotations

from cctv_api.core.config import Settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.APP_ENV == "development"
    assert settings.CLOCK_SKEW_SECONDS == 30
    assert settings.SESSION_COOKIE_NAME == "panoptix_session"
    assert settings.LIVEKIT_MODE == "cloud"
    assert settings.GATEWAY_HEARTBEAT_INTERVAL_SECONDS == 10


def test_settings_override_via_env(monkeypatch: object) -> None:
    import pytest

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("CLOCK_SKEW_SECONDS", "60")
    settings = Settings()
    assert settings.APP_ENV == "staging"
    assert settings.CLOCK_SKEW_SECONDS == 60
    monkeypatch.undo()
