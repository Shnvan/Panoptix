from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Environment ──
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_PUBLIC_BASE_URL: str = "https://cctv.example.test"
    CLOCK_SKEW_SECONDS: int = Field(default=30, ge=0, le=120)
    BREAK_GLASS_WINDOW_MINUTES: int = Field(default=90, ge=10)

    # ── Cloudflare Access JWT verification ──
    CF_ACCESS_ISSUER: str = "https://example.cloudflareaccess.com"
    CF_ACCESS_AUD_DASHBOARD: str = "replace-me"
    CF_ACCESS_AUD_ADMIN: str = "replace-me"
    CF_ACCESS_AUD_GATEWAY: str = "replace-me"
    CF_ACCESS_JWKS_URL: str = "https://example.cloudflareaccess.com/cdn-cgi/access/certs"

    # ── Local development auth ──
    ALLOW_DEV_AUTH: bool = False
    DEV_CF_JWT_SIGNING_KEY: str = "replace-me-local-only"

    # ── GitHub organization invitations ──
    GITHUB_INVITES_ENABLED: bool = False
    GITHUB_ORG: str = ""
    GITHUB_INVITE_TOKEN: str = "replace-me"
    GITHUB_INVITE_TEAM_IDS: str = ""
    GITHUB_INVITE_TIMEOUT_SECONDS: int = Field(default=10, ge=1, le=60)

    # ── Pilot alert email notifications ──
    ALERT_EMAIL_ENABLED: bool = False
    ALERT_EMAIL_SMTP_HOST: str = ""
    ALERT_EMAIL_SMTP_PORT: int = Field(default=587, ge=1, le=65535)
    ALERT_EMAIL_SMTP_USERNAME: str = ""
    ALERT_EMAIL_SMTP_PASSWORD: str = "replace-me"
    ALERT_EMAIL_FROM: str = ""
    ALERT_EMAIL_TO: str = ""
    ALERT_EMAIL_USE_TLS: bool = True
    ALERT_EMAIL_MIN_SEVERITY: str = "high"
    ALERT_EMAIL_TIMEOUT_SECONDS: int = Field(default=10, ge=1, le=60)

    # ── Session / cookie ──
    SESSION_COOKIE_NAME: str = "panoptix_session"
    SESSION_SIGNING_KEY: str = "replace-me"
    CSRF_SIGNING_KEY: str = "replace-me"
    SESSION_IDLE_TIMEOUT_SECONDS: int = Field(default=900, ge=60)  # 15 min
    SESSION_ABSOLUTE_TIMEOUT_SECONDS: int = Field(default=28800, ge=300)  # 8 h

    # ── Audit HMAC chain ──
    AUDIT_HMAC_KEY_VERSION: int = Field(default=1, ge=1)
    AUDIT_HMAC_KEY: str = "replace-me"

    # ── Database ──
    DATABASE_URL: str = "postgresql+psycopg://cctv_app_runtime:replace-me@localhost:5432/panoptix"
    MIGRATION_DATABASE_URL: str = (
        "postgresql+psycopg://cctv_migrator:replace-me@localhost:5432/panoptix"
    )

    # ── LiveKit ──
    LIVEKIT_MODE: Literal["cloud", "fallback"] = "cloud"
    LIVEKIT_CLOUD_URL: str = "wss://replace-me.livekit.cloud"
    LIVEKIT_CLOUD_API_KEY: str = "replace-me"
    LIVEKIT_CLOUD_API_SECRET: str = "replace-me"
    LIVEKIT_FALLBACK_URL: str = "wss://livekit.example.test"
    LIVEKIT_FALLBACK_API_KEY: str = "replace-me"
    LIVEKIT_FALLBACK_API_SECRET: str = "replace-me"
    LIVEKIT_WEBHOOK_SECRET: str = "replace-me"

    # ── Gateway ──
    GATEWAY_SERVICE_TOKEN: str = "replace-me-gateway-only"
    GATEWAY_CONTROL_WS_PATH: str = "/api/v1/gateway-control/ws"
    GATEWAY_COMMAND_SIGNING_KEY: str = "replace-me"
    GATEWAY_HEARTBEAT_INTERVAL_SECONDS: int = Field(default=10, ge=5)
    GATEWAY_STALE_THRESHOLD_SECONDS: int = Field(default=60, ge=10)

    # ── Maintenance scheduler ──
    ENABLE_MAINTENANCE_SCHEDULER: bool = False
    MAINTENANCE_INTERVAL_SECONDS: int = Field(default=30, ge=5)

    # ── Security headers / CSP ──
    CSP_REPORT_URI: str = ""
    LIVEKIT_CONNECT_SRC: str = "wss://replace-me.livekit.cloud"

    # ── Rate limiting (§16.17) ──
    RATE_LIMIT_VIEWER_TOKEN_MAX: int = Field(default=30, ge=1)
    RATE_LIMIT_VIEWER_TOKEN_WINDOW: int = Field(default=60, ge=10)
    RATE_LIMIT_GATEWAY_INGEST_MAX: int = Field(default=20, ge=1)
    RATE_LIMIT_GATEWAY_INGEST_WINDOW: int = Field(default=60, ge=10)
    RATE_LIMIT_ADMIN_MUTATION_MAX: int = Field(default=10, ge=1)
    RATE_LIMIT_ADMIN_MUTATION_WINDOW: int = Field(default=60, ge=10)

    @property
    def cf_access_browser_audiences(self) -> list[str]:
        return [
            self.CF_ACCESS_AUD_DASHBOARD,
            self.CF_ACCESS_AUD_ADMIN,
        ]

    def validate_production_guardrails(self) -> None:
        if self.APP_ENV == "development":
            return

        unsafe: list[str] = []

        if self.ALLOW_DEV_AUTH:
            unsafe.append("ALLOW_DEV_AUTH")

        _PLACEHOLDER_MARKERS = ("replace-me", "example.cloudflareaccess.com")

        _GUARDED_FIELDS = [
            "CF_ACCESS_ISSUER",
            "CF_ACCESS_AUD_DASHBOARD",
            "CF_ACCESS_AUD_ADMIN",
            "CF_ACCESS_AUD_GATEWAY",
            "CF_ACCESS_JWKS_URL",
            "SESSION_SIGNING_KEY",
            "CSRF_SIGNING_KEY",
            "AUDIT_HMAC_KEY",
            "DATABASE_URL",
            "MIGRATION_DATABASE_URL",
            "GATEWAY_SERVICE_TOKEN",
            "GATEWAY_COMMAND_SIGNING_KEY",
        ]

        if self.GITHUB_INVITES_ENABLED:
            _GUARDED_FIELDS.extend(["GITHUB_ORG", "GITHUB_INVITE_TOKEN"])
            if not self.GITHUB_ORG.strip():
                unsafe.append("GITHUB_ORG")
            if not self.GITHUB_INVITE_TOKEN.strip():
                unsafe.append("GITHUB_INVITE_TOKEN")

        if self.ALERT_EMAIL_ENABLED:
            _GUARDED_FIELDS.extend(
                [
                    "ALERT_EMAIL_SMTP_HOST",
                    "ALERT_EMAIL_SMTP_PASSWORD",
                    "ALERT_EMAIL_FROM",
                    "ALERT_EMAIL_TO",
                ]
            )
            for field_name in (
                "ALERT_EMAIL_SMTP_HOST",
                "ALERT_EMAIL_FROM",
                "ALERT_EMAIL_TO",
            ):
                if not getattr(self, field_name, "").strip():
                    unsafe.append(field_name)

        for field_name in _GUARDED_FIELDS:
            value = getattr(self, field_name, "")
            if any(marker in value for marker in _PLACEHOLDER_MARKERS):
                unsafe.append(field_name)

        if unsafe:
            raise ValueError(
                f"unsafe-production-config: {', '.join(unsafe)}"
            )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
