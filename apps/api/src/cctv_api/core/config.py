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

    # ── Session / cookie ──
    SESSION_COOKIE_NAME: str = "panoptix_session"
    SESSION_SIGNING_KEY: str = "replace-me"
    CSRF_SIGNING_KEY: str = "replace-me"

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

    # ── Security headers / CSP ──
    CSP_REPORT_URI: str = ""
    LIVEKIT_CONNECT_SRC: str = "wss://replace-me.livekit.cloud"

    @property
    def cf_access_browser_audiences(self) -> list[str]:
        return [
            self.CF_ACCESS_AUD_DASHBOARD,
            self.CF_ACCESS_AUD_ADMIN,
        ]


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
