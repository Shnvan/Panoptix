from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.db import db_session
from cctv_api.main import create_app
from cctv_api.models.enums import BackupUploadStatus
from cctv_api.models.tables import BackupRun


_ADMIN_HEADERS = {
    "x-panoptix-dev-auth": "1",
    "x-panoptix-dev-email": "admin@example.test",
    "x-panoptix-dev-subject": "admin@example.test",
    "x-panoptix-dev-roles": "admin",
}


def _client(test_db_session: DbSession) -> TestClient:
    app = create_app(
        settings=Settings(
            APP_ENV="development",
            ALLOW_DEV_AUTH=True,
            AUDIT_HMAC_KEY_VERSION=1,
            AUDIT_HMAC_KEY="test-audit-key-with-enough-entropy",
        )
    )

    def _override_db() -> DbSession:
        return test_db_session

    app.dependency_overrides[db_session] = _override_db
    return TestClient(app)


def test_backups_status_returns_missing_when_no_backup_runs(
    test_db_session: DbSession,
) -> None:
    client = _client(test_db_session)
    response = client.get("/api/v1/admin/backups/status", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "missing"
    assert data["latest_backup"] is None
    assert data["latest_restore_drill"] is None
    assert data["checks"] == {
        "has_backup": False,
        "latest_upload_uploaded": False,
        "latest_backup_finished": False,
        "latest_restore_format_ok": False,
        "restore_drill_recorded": False,
        "latest_restore_schema_ok": False,
        "latest_backup_age_hours": None,
    }


def test_backups_status_returns_ok_for_uploaded_backup_with_restore_drill(
    test_db_session: DbSession,
) -> None:
    now = datetime.now(timezone.utc)
    backup = BackupRun(
        started_at=now - timedelta(hours=2),
        finished_at=now - timedelta(hours=1, minutes=55),
        size_bytes=123456,
        sha256="a" * 64,
        restore_format_ok=True,
        restore_schema_ok=True,
        row_count_estimate=42,
        upload_status=BackupUploadStatus.uploaded,
        notes="quarterly drill passed",
    )
    test_db_session.add(backup)
    test_db_session.commit()

    client = _client(test_db_session)
    response = client.get("/api/v1/admin/backups/status", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["latest_backup"]["id"] == str(backup.id)
    assert data["latest_backup"]["upload_status"] == "uploaded"
    assert data["latest_backup"]["sha256"] == "a" * 64
    assert data["latest_backup"]["restore_format_ok"] is True
    assert data["latest_backup"]["restore_schema_ok"] is True
    assert data["latest_backup"]["row_count_estimate"] == 42
    assert data["latest_backup"]["notes"] == "quarterly drill passed"
    assert data["latest_restore_drill"]["id"] == str(backup.id)
    assert data["checks"]["has_backup"] is True
    assert data["checks"]["latest_upload_uploaded"] is True
    assert data["checks"]["latest_backup_finished"] is True
    assert data["checks"]["latest_restore_format_ok"] is True
    assert data["checks"]["restore_drill_recorded"] is True
    assert data["checks"]["latest_restore_schema_ok"] is True
    assert isinstance(data["checks"]["latest_backup_age_hours"], float)


def test_backups_status_returns_degraded_for_failed_backup(
    test_db_session: DbSession,
) -> None:
    now = datetime.now(timezone.utc)
    test_db_session.add(
        BackupRun(
            started_at=now - timedelta(minutes=30),
            finished_at=now - timedelta(minutes=25),
            size_bytes=None,
            sha256=None,
            restore_format_ok=False,
            restore_schema_ok=None,
            row_count_estimate=None,
            upload_status=BackupUploadStatus.failed,
            notes="upload failed",
        )
    )
    test_db_session.commit()

    client = _client(test_db_session)
    response = client.get("/api/v1/admin/backups/status", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "degraded"
    assert data["latest_backup"]["upload_status"] == "failed"
    assert data["latest_restore_drill"] is None
    assert data["checks"]["latest_upload_uploaded"] is False
    assert data["checks"]["latest_restore_format_ok"] is False
    assert data["checks"]["restore_drill_recorded"] is False
    assert data["checks"]["latest_restore_schema_ok"] is False


def test_backups_status_returns_degraded_without_restore_drill(
    test_db_session: DbSession,
) -> None:
    now = datetime.now(timezone.utc)
    test_db_session.add(
        BackupRun(
            started_at=now - timedelta(hours=1),
            finished_at=now - timedelta(minutes=55),
            size_bytes=200,
            sha256="c" * 64,
            restore_format_ok=True,
            restore_schema_ok=None,
            row_count_estimate=12,
            upload_status=BackupUploadStatus.uploaded,
            notes="daily backup only",
        )
    )
    test_db_session.commit()

    client = _client(test_db_session)
    response = client.get("/api/v1/admin/backups/status", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "degraded"
    assert data["latest_backup"]["upload_status"] == "uploaded"
    assert data["latest_backup"]["restore_format_ok"] is True
    assert data["latest_restore_drill"] is None
    assert data["checks"]["latest_upload_uploaded"] is True
    assert data["checks"]["restore_drill_recorded"] is False
    assert data["checks"]["latest_restore_schema_ok"] is False


def test_backups_status_returns_ok_when_latest_backup_has_prior_restore_drill(
    test_db_session: DbSession,
) -> None:
    now = datetime.now(timezone.utc)
    older_drill_started_at = now - timedelta(days=7)
    older_drill = BackupRun(
        started_at=older_drill_started_at,
        finished_at=older_drill_started_at + timedelta(minutes=5),
        size_bytes=100,
        sha256="b" * 64,
        restore_format_ok=True,
        restore_schema_ok=True,
        row_count_estimate=10,
        upload_status=BackupUploadStatus.uploaded,
        notes="older schema drill",
    )
    latest_backup = BackupRun(
        started_at=now - timedelta(hours=1),
        finished_at=now - timedelta(minutes=55),
        size_bytes=200,
        sha256="c" * 64,
        restore_format_ok=True,
        restore_schema_ok=None,
        row_count_estimate=12,
        upload_status=BackupUploadStatus.uploaded,
        notes="daily backup only",
    )
    test_db_session.add_all([older_drill, latest_backup])
    test_db_session.commit()

    client = _client(test_db_session)
    response = client.get("/api/v1/admin/backups/status", headers=_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["latest_backup"]["id"] == str(latest_backup.id)
    assert data["latest_restore_drill"]["id"] == str(older_drill.id)
    assert data["checks"]["latest_upload_uploaded"] is True
    assert data["checks"]["latest_restore_format_ok"] is True
    assert data["checks"]["latest_restore_schema_ok"] is True
