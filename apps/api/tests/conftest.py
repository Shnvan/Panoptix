# ruff: noqa: E402
from __future__ import annotations

import sqlite3
import uuid
import importlib
from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, event
from sqlalchemy.orm import Session as DbSession, sessionmaker
from sqlalchemy.pool import StaticPool

from cctv_api.core.config import Settings

# Prevent loading of local .env file during testing to ensure isolation
Settings.model_config["env_file"] = None

from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.base import Base

importlib.import_module("cctv_api.models.tables")

sqlite3.register_adapter(uuid.UUID, str)


@pytest.fixture()
def _test_db() -> Generator[sessionmaker[DbSession], None, None]:
    engine = create_engine(
        "sqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_functions(dbapi_conn, _connection_record):  # type: ignore[no-untyped-def]
        dbapi_conn.create_function("now", 0, lambda: datetime.now(timezone.utc).isoformat())

    _remap_pg_types(Base)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def _remap_pg_types(base: type) -> None:
    from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PG_UUID

    for table in base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, INET):
                col.type = String(45)
            elif isinstance(col.type, PG_UUID):
                col.type = String(36)
            elif isinstance(col.type, JSONB):
                from sqlalchemy import JSON

                col.type = JSON()


@pytest.fixture()
def client(_test_db: sessionmaker[DbSession]) -> TestClient:
    app = create_app()

    def _override_db() -> Generator[DbSession, None, None]:
        session = _test_db()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


@pytest.fixture()
def test_db_session(_test_db: sessionmaker[DbSession]) -> Generator[DbSession, None, None]:
    session = _test_db()
    try:
        yield session
    finally:
        session.close()
