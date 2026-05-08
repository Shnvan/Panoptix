from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from cctv_api.models.base import Base
from cctv_api.models import tables as _tables  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _load_env() -> None:
    # Prefer a repo-root `.env` (common in this repo) then fall back to local.
    # This is only for developer convenience; Railway/CI should use real env vars.
    here = Path(__file__).resolve()
    repo_root_env = here.parents[3] / ".env"
    if repo_root_env.exists():
        load_dotenv(repo_root_env, override=False)
    load_dotenv(override=False)


def _normalize_database_url(url: str) -> str:
    # Prefer psycopg3 driver if user supplied a generic postgres URL.
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def get_url() -> str:
    _load_env()
    raw = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError("MIGRATION_DATABASE_URL (or DATABASE_URL) is required for migrations")
    return _normalize_database_url(raw)


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
