from __future__ import annotations

import pytest

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
    assert settings.TRUST_CF_CONNECTING_IP is False


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


def _safe_production_settings(**overrides: object) -> Settings:
    defaults = {
        "APP_ENV": "production",
        "ALLOW_DEV_AUTH": False,
        "CF_ACCESS_ISSUER": "https://myteam.cloudflareaccess.com",
        "CF_ACCESS_AUD_DASHBOARD": "aud-dashboard-real",
        "CF_ACCESS_AUD_ADMIN": "aud-admin-real",
        "CF_ACCESS_AUD_GATEWAY": "aud-gateway-real",
        "CF_ACCESS_JWKS_URL": "https://myteam.cloudflareaccess.com/cdn-cgi/access/certs",
        "SESSION_SIGNING_KEY": "real-session-key",
        "CSRF_SIGNING_KEY": "real-csrf-key",
        "AUDIT_HMAC_KEY": "real-audit-key",
        "DATABASE_URL": "postgresql+psycopg://user:pass@db:5432/panoptix",
        "MIGRATION_DATABASE_URL": "postgresql+psycopg://migrator:pass@db:5432/panoptix",
        "GATEWAY_SERVICE_TOKEN": "real-gateway-token",
        "GATEWAY_COMMAND_SIGNING_KEY": "real-signing-key",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def test_guardrails_pass_for_development_defaults() -> None:
    settings = Settings()
    settings.validate_production_guardrails()


def test_guardrails_reject_production_with_placeholder_defaults() -> None:
    settings = Settings(APP_ENV="production")
    with pytest.raises(ValueError, match="unsafe-production-config"):
        settings.validate_production_guardrails()


def test_guardrails_reject_staging_with_placeholder_defaults() -> None:
    settings = Settings(APP_ENV="staging")
    with pytest.raises(ValueError, match="unsafe-production-config"):
        settings.validate_production_guardrails()


def test_guardrails_reject_dev_auth_in_production() -> None:
    settings = _safe_production_settings(ALLOW_DEV_AUTH=True)
    with pytest.raises(ValueError, match="ALLOW_DEV_AUTH"):
        settings.validate_production_guardrails()


def test_guardrails_reject_placeholder_cf_access_issuer() -> None:
    settings = _safe_production_settings(
        CF_ACCESS_ISSUER="https://example.cloudflareaccess.com",
    )
    with pytest.raises(ValueError, match="CF_ACCESS_ISSUER"):
        settings.validate_production_guardrails()


def test_guardrails_reject_placeholder_session_signing_key() -> None:
    settings = _safe_production_settings(SESSION_SIGNING_KEY="replace-me")
    with pytest.raises(ValueError, match="SESSION_SIGNING_KEY"):
        settings.validate_production_guardrails()


def test_guardrails_reject_placeholder_database_url() -> None:
    settings = _safe_production_settings(
        DATABASE_URL="postgresql+psycopg://cctv_app_runtime:replace-me@localhost:5432/panoptix",
    )
    with pytest.raises(ValueError, match="DATABASE_URL"):
        settings.validate_production_guardrails()


def test_guardrails_reject_placeholder_gateway_command_signing_key() -> None:
    settings = _safe_production_settings(GATEWAY_COMMAND_SIGNING_KEY="replace-me")
    with pytest.raises(ValueError, match="GATEWAY_COMMAND_SIGNING_KEY"):
        settings.validate_production_guardrails()


def test_guardrails_pass_for_fully_populated_production() -> None:
    settings = _safe_production_settings()
    settings.validate_production_guardrails()


def test_guardrails_allow_alert_email_admin_recipient_mode_without_static_to() -> None:
    settings = _safe_production_settings(
        ALERT_EMAIL_ENABLED=True,
        ALERT_EMAIL_SMTP_HOST="smtp.example.test",
        ALERT_EMAIL_SMTP_PASSWORD="smtp-password-with-enough-length",
        ALERT_EMAIL_FROM="alerts@example.test",
        ALERT_EMAIL_RECIPIENT_MODE="admins",
        ALERT_EMAIL_TO="",
    )
    settings.validate_production_guardrails()


def test_guardrails_require_alert_email_to_for_static_recipient_mode() -> None:
    settings = _safe_production_settings(
        ALERT_EMAIL_ENABLED=True,
        ALERT_EMAIL_SMTP_HOST="smtp.example.test",
        ALERT_EMAIL_SMTP_PASSWORD="smtp-password-with-enough-length",
        ALERT_EMAIL_FROM="alerts@example.test",
        ALERT_EMAIL_RECIPIENT_MODE="static",
        ALERT_EMAIL_TO="",
    )
    with pytest.raises(ValueError, match="ALERT_EMAIL_TO"):
        settings.validate_production_guardrails()


def test_guardrails_pass_for_fully_populated_staging() -> None:
    settings = _safe_production_settings(APP_ENV="staging")
    settings.validate_production_guardrails()


def test_guardrails_list_multiple_unsafe_fields() -> None:
    settings = Settings(APP_ENV="production", ALLOW_DEV_AUTH=True)
    with pytest.raises(ValueError) as exc_info:
        settings.validate_production_guardrails()
    message = str(exc_info.value)
    assert "ALLOW_DEV_AUTH" in message
    assert "CF_ACCESS_ISSUER" in message
    assert "SESSION_SIGNING_KEY" in message


def test_create_app_fails_fast_for_unsafe_production() -> None:
    from cctv_api.main import create_app

    with pytest.raises(ValueError, match="unsafe-production-config"):
        create_app(settings=Settings(APP_ENV="production"))
