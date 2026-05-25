from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings, get_settings
from cctv_api.db import get_sessionmaker, normalize_database_url
from cctv_api.models.enums import BackupUploadStatus
from cctv_api.models.tables import BackupRun


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


class BackupUploader(Protocol):
    def upload_file(self, path: Path, *, bucket: str, key: str) -> None: ...


@dataclass(frozen=True)
class BackupJobResult:
    backup_run_id: uuid.UUID
    upload_status: BackupUploadStatus
    restore_format_ok: bool
    size_bytes: int | None
    sha256: str | None
    error: str | None = None


class BackupJobError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class R2BackupUploader:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def upload_file(self, path: Path, *, bucket: str, key: str) -> None:
        import boto3  # type: ignore[import-untyped]

        client = boto3.client(
            "s3",
            endpoint_url=_r2_endpoint(self._settings.R2_ACCOUNT_ID),
            region_name="auto",
            aws_access_key_id=self._settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=self._settings.R2_SECRET_ACCESS_KEY,
        )
        client.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs={
                "ContentType": "application/octet-stream",
                "Metadata": {"purpose": "panoptix-database-backup"},
            },
        )


def run_r2_backup_job(
    db: DbSession,
    *,
    settings: Settings,
    command_runner: CommandRunner | None = None,
    uploader: BackupUploader | None = None,
    now: Callable[[], datetime] | None = None,
) -> BackupJobResult:
    command_runner = command_runner or _run_command
    uploader = uploader or R2BackupUploader(settings=settings)
    now = now or (lambda: datetime.now(timezone.utc))

    backup_run = BackupRun(
        started_at=now(),
        upload_status=BackupUploadStatus.pending,
        restore_format_ok=False,
        notes="operator-run R2 backup started",
    )
    db.add(backup_run)
    db.commit()
    db.refresh(backup_run)

    try:
        _validate_backup_settings(settings)
        database_url = _backup_database_url(settings)
        timestamp = backup_run.started_at.strftime("%Y%m%dT%H%M%SZ")
        object_key = _object_key(settings.BACKUP_OBJECT_PREFIX, timestamp, backup_run.id)

        with tempfile.TemporaryDirectory(prefix="panoptix-backup-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            dump_path = tmp_path / f"panoptix-{timestamp}-{backup_run.id}.dump"
            encrypted_path = tmp_path / f"{dump_path.name}.age"

            _run_checked(
                command_runner,
                [
                    "pg_dump",
                    "--format=custom",
                    "--no-owner",
                    "--no-acl",
                    "--file",
                    str(dump_path),
                    _postgres_cli_url(database_url),
                ],
                error_code="pg-dump-failed",
            )
            _run_checked(
                command_runner,
                ["pg_restore", "--list", str(dump_path)],
                error_code="pg-restore-list-failed",
            )
            _run_checked(
                command_runner,
                [
                    "age",
                    "-r",
                    settings.BACKUP_AGE_RECIPIENT,
                    "-o",
                    str(encrypted_path),
                    str(dump_path),
                ],
                error_code="age-encryption-failed",
            )

            size_bytes = encrypted_path.stat().st_size
            sha256 = _sha256(encrypted_path)
            uploader.upload_file(encrypted_path, bucket=settings.R2_BUCKET, key=object_key)

        backup_run.finished_at = now()
        backup_run.size_bytes = size_bytes
        backup_run.sha256 = sha256
        backup_run.restore_format_ok = True
        backup_run.row_count_estimate = _row_count_estimate(db)
        backup_run.upload_status = BackupUploadStatus.uploaded
        backup_run.notes = "operator-run R2 backup uploaded; object key withheld from API output"
        db.commit()
        return BackupJobResult(
            backup_run_id=backup_run.id,
            upload_status=backup_run.upload_status,
            restore_format_ok=backup_run.restore_format_ok,
            size_bytes=backup_run.size_bytes,
            sha256=backup_run.sha256,
        )
    except BackupJobError as exc:
        _mark_failed(db, backup_run, now=now, notes=exc.code)
        return _failed_result(backup_run, exc.code)
    except Exception:
        _mark_failed(db, backup_run, now=now, notes="r2-upload-or-metadata-failed")
        return _failed_result(backup_run, "r2-upload-or-metadata-failed")


def main() -> int:
    settings = get_settings()
    settings.validate_production_guardrails()
    session = get_sessionmaker()()
    try:
        result = run_r2_backup_job(session, settings=settings)
    finally:
        session.close()

    print(
        json.dumps(
            {
                "backup_run_id": str(result.backup_run_id),
                "upload_status": result.upload_status.value,
                "restore_format_ok": result.restore_format_ok,
                "size_bytes": result.size_bytes,
                "sha256": result.sha256,
                "error": result.error,
            },
            sort_keys=True,
        )
    )
    return 0 if result.upload_status == BackupUploadStatus.uploaded else 1


def _run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _run_checked(
    runner: CommandRunner,
    command: Sequence[str],
    *,
    error_code: str,
) -> None:
    try:
        runner(command)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise BackupJobError(error_code) from exc


def _validate_backup_settings(settings: Settings) -> None:
    missing = [
        name
        for name in (
            "R2_ACCOUNT_ID",
            "R2_BUCKET",
            "R2_ACCESS_KEY_ID",
            "R2_SECRET_ACCESS_KEY",
            "BACKUP_AGE_RECIPIENT",
        )
        if not _has_value(getattr(settings, name))
    ]
    if missing:
        raise BackupJobError(f"backup-config-missing: {', '.join(missing)}")


def _has_value(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and "replace-me" not in stripped and not stripped.startswith("<")


def _backup_database_url(settings: Settings) -> str:
    return settings.BACKUP_DATABASE_URL.strip() or settings.DATABASE_URL


def _postgres_cli_url(url: str) -> str:
    normalized = normalize_database_url(url)
    return normalized.replace("postgresql+psycopg://", "postgresql://", 1)


def _r2_endpoint(account_id: str) -> str:
    return f"https://{account_id}.r2.cloudflarestorage.com"


def _object_key(prefix: str, timestamp: str, backup_run_id: uuid.UUID) -> str:
    clean_prefix = prefix.strip().strip("/") or "database"
    date_path = f"{timestamp[0:4]}/{timestamp[4:6]}/{timestamp[6:8]}"
    return f"{clean_prefix}/{date_path}/panoptix-{timestamp}-{backup_run_id}.dump.age"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_count_estimate(db: DbSession) -> int | None:
    if db.bind is not None and db.bind.dialect.name != "postgresql":
        return None
    try:
        value = db.execute(
            text("SELECT COALESCE(SUM(n_live_tup), 0)::bigint FROM pg_stat_user_tables")
        ).scalar_one()
    except Exception:
        db.rollback()
        return None
    return int(value) if value is not None else None


def _mark_failed(
    db: DbSession,
    backup_run: BackupRun,
    *,
    now: Callable[[], datetime],
    notes: str,
) -> None:
    db.rollback()
    backup_run.finished_at = now()
    backup_run.upload_status = BackupUploadStatus.failed
    backup_run.restore_format_ok = False
    backup_run.notes = notes
    db.add(backup_run)
    db.commit()


def _failed_result(backup_run: BackupRun, error: str) -> BackupJobResult:
    return BackupJobResult(
        backup_run_id=backup_run.id,
        upload_status=BackupUploadStatus.failed,
        restore_format_ok=False,
        size_bytes=backup_run.size_bytes,
        sha256=backup_run.sha256,
        error=error,
    )


if __name__ == "__main__":
    raise SystemExit(main())
