from __future__ import annotations

from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


AppEnv = Literal["development", "staging", "production"]


class Settings(BaseSettings):
    app_env: AppEnv = "development"

    app_public_base_url: str = "https://cctv.example.test"
    clock_skew_seconds: int = 30

    # Cloudflare Access JWT verification
    cf_access_issuer: str = "https://example.cloudflareaccess.com"
    cf_access_aud_dashboard: str = "replace-me"
    cf_access_aud_admin: str = "replace-me"
    cf_access_aud_gateway: str = "replace-me"
    cf_access_jwks_url: AnyUrl = "https://example.cloudflareaccess.com/cdn-cgi/access/certs"

    # Local development auth only (see docs/implementation/development-setup.md)
    allow_dev_auth: bool = False
    dev_cf_jwt_signing_key: str | None = None

    # Session/cookie secrets
    session_cookie_name: str = "panoptix_session"
    session_signing_key: str = "replace-me"
    csrf_signing_key: str = "replace-me"

    # Database
    # Note: the repository `.env` uses `DATABASE_URL` (uppercase) per Neon/Railway convention.
    # We explicitly map to that env var to avoid case-sensitivity surprises.
    database_url: str = "postgresql+psycopg://cctv_app_runtime:replace-me@localhost:5432/panoptix"
    migration_database_url: str = (
        "postgresql+psycopg://cctv_migrator:replace-me@localhost:5432/panoptix"
    )
    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=True,
        fields={
            "database_url": {"env": "DATABASE_URL"},
            "migration_database_url": {"env": "MIGRATION_DATABASE_URL"},
        },
    )

    # Gateway identity and command channel
    gateway_service_token: str = "replace-me-gateway-only"
    gateway_control_ws_path: str = "/api/v1/gateway-control/ws"
    gateway_command_signing_key: str = "replace-me"
    gateway_heartbeat_interval_seconds: int = 10


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        # Developer convenience: load repo-root `.env` if present.
        # Railway/CI should provide real environment variables.
        here = Path(__file__).resolve()
        repo_root_env = here.parents[4] / ".env"
        if repo_root_env.exists():
            load_dotenv(repo_root_env, override=False)
        load_dotenv(override=False)
        _settings = Settings()
    return _settings
