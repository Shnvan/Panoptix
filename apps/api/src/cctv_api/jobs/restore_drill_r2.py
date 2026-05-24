from __future__ import annotations

import argparse
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

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings, get_settings
from cctv_api.db import get_sessionmaker, normalize_database_url
from cctv_api.models.enums import BackupUploadStatus
from cctv_api.models.tables import BackupRun


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


class BackupObjectStore(Protocol):
    def latest_encrypted_backup(self, *, bucket: str) -> BackupObject | None: ...

    def download_file(self, *, bucket: str, key: str, destination: Path) -> None: ...


@dataclass(frozen=True)
class BackupObject:
    key: str
    size_bytes: int | None = None


@dataclass(frozen=True)
class RestoreDrillResult:
    restore_format_ok: bool
    restore_schema_ok: bool | None
    size_bytes: int | None
    sha256: str | None
    backup_run_id: uuid.UUID | None = None
    dry_run: bool = True
    error: str | None = None


class RestoreDrillError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class R2BackupObjectStore:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def latest_encrypted_backup(self, *, bucket: str) -> BackupObject | None:
        import boto3  # type: ignore[import-untyped]

        client = boto3.client(
            "s3",
            endpoint_url=_r2_endpoint(self._settings.R2_ACCOUNT_ID),
            region_name="auto",
            aws_access_key_id=self._settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=self._settings.R2_SECRET_ACCESS_KEY,
        )
        paginator = client.get_paginator("list_objects_v2")
        latest: dict[str, object] | None = None
        for page in paginator.paginate(Bucket=bucket):
            for item in page.get("Contents", []):
                key = item.get("Key")
                if not isinstance(key, str) or not key.endswith(".dump.age"):
                    continue
                item_modified = item.get("LastModified")
                latest_modified = latest.get("LastModified") if latest else None
                if latest is None or (
                    isinstance(item_modified, datetime)
                    and isinstance(latest_modified, datetime)
                    and item_modified > latest_modified
                ):
                    latest = item
        if latest is None:
            return None
        size = latest.get("Size")
        return BackupObject(
            key=str(latest["Key"]),
            size_bytes=int(size) if isinstance(size, int) else None,
        )

    def download_file(self, *, bucket: str, key: str, destination: Path) -> None:
        import boto3  # type: ignore[import-untyped]

        client = boto3.client(
            "s3",
            endpoint_url=_r2_endpoint(self._settings.R2_ACCOUNT_ID),
            region_name="auto",
            aws_access_key_id=self._settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=self._settings.R2_SECRET_ACCESS_KEY,
        )
        client.download_file(bucket, key, str(destination))


def run_restore_drill(
    db: DbSession,
    *,
    settings: Settings,
    age_identity_file: Path,
    target_database_url: str | None = None,
    object_store: BackupObjectStore | None = None,
    command_runner: CommandRunner | None = None,
    now: Callable[[], datetime] | None = None,
) -> RestoreDrillResult:
    object_store = object_store or R2BackupObjectStore(settings=settings)
    command_runner = command_runner or _run_command
    now = now or (lambda: datetime.now(timezone.utc))

    try:
        _validate_restore_settings(settings)
        if not age_identity_file.is_file():
            raise RestoreDrillError("age-identity-file-missing")

        backup_object = object_store.latest_encrypted_backup(bucket=settings.R2_BUCKET)
        if backup_object is None:
            raise RestoreDrillError("backup-object-not-found")

        with tempfile.TemporaryDirectory(prefix="panoptix-restore-drill-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            encrypted_path = tmp_path / "backup.dump.age"
            dump_path = tmp_path / "backup.dump"

            object_store.download_file(
                bucket=settings.R2_BUCKET,
                key=backup_object.key,
                destination=encrypted_path,
            )
            encrypted_size = encrypted_path.stat().st_size
            encrypted_sha256 = _sha256(encrypted_path)

            _run_checked(
                command_runner,
                [
                    "age",
                    "-d",
                    "-i",
                    str(age_identity_file),
                    "-o",
                    str(dump_path),
                    str(encrypted_path),
                ],
                error_code="age-decryption-failed",
            )
            _run_checked(
                command_runner,
                ["pg_restore", "--list", str(dump_path)],
                error_code="pg-restore-list-failed",
            )

            if not target_database_url:
                return RestoreDrillResult(
                    restore_format_ok=True,
                    restore_schema_ok=None,
                    size_bytes=encrypted_size,
                    sha256=encrypted_sha256,
                    dry_run=True,
                )

            cli_url = _postgres_cli_url(target_database_url)
            _run_checked(
                command_runner,
                [
                    "pg_restore",
                    "--exit-on-error",
                    "--clean",
                    "--if-exists",
                    "--no-owner",
                    "--no-acl",
                    "-d",
                    cli_url,
                    str(dump_path),
                ],
                error_code="pg-restore-target-failed",
            )
            row_count = _target_row_count(target_database_url)

        drill_row = BackupRun(
            started_at=now(),
            finished_at=now(),
            size_bytes=encrypted_size,
            sha256=encrypted_sha256,
            restore_format_ok=True,
            restore_schema_ok=True,
            row_count_estimate=row_count,
            upload_status=BackupUploadStatus.uploaded,
            notes="operator restore drill passed; source object key withheld from API output",
        )
        db.add(drill_row)
        db.commit()
        db.refresh(drill_row)
        return RestoreDrillResult(
            backup_run_id=drill_row.id,
            restore_format_ok=True,
            restore_schema_ok=True,
            size_bytes=encrypted_size,
            sha256=encrypted_sha256,
            dry_run=False,
        )
    except RestoreDrillError as exc:
        return RestoreDrillResult(
            restore_format_ok=False,
            restore_schema_ok=False if target_database_url else None,
            size_bytes=None,
            sha256=None,
            dry_run=not bool(target_database_url),
            error=exc.code,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Panoptix encrypted R2 restore drill.")
    parser.add_argument("--age-identity-file", required=True)
    parser.add_argument("--target-database-url", default=None)
    args = parser.parse_args(argv)

    settings = get_settings()
    settings.validate_production_guardrails()
    session = get_sessionmaker()()
    try:
        result = run_restore_drill(
            session,
            settings=settings,
            age_identity_file=Path(args.age_identity_file),
            target_database_url=args.target_database_url,
        )
    finally:
        session.close()

    print(
        json.dumps(
            {
                "backup_run_id": str(result.backup_run_id) if result.backup_run_id else None,
                "dry_run": result.dry_run,
                "restore_format_ok": result.restore_format_ok,
                "restore_schema_ok": result.restore_schema_ok,
                "size_bytes": result.size_bytes,
                "sha256": result.sha256,
                "error": result.error,
            },
            sort_keys=True,
        )
    )
    success = result.restore_format_ok and (result.dry_run or result.restore_schema_ok is True)
    return 0 if success else 1


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
        raise RestoreDrillError(error_code) from exc


def _validate_restore_settings(settings: Settings) -> None:
    missing = [
        name
        for name in (
            "R2_ACCOUNT_ID",
            "R2_BUCKET",
            "R2_ACCESS_KEY_ID",
            "R2_SECRET_ACCESS_KEY",
        )
        if not _has_value(getattr(settings, name))
    ]
    if missing:
        raise RestoreDrillError(f"restore-config-missing: {', '.join(missing)}")


def _has_value(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and "replace-me" not in stripped and not stripped.startswith("<")


def _postgres_cli_url(url: str) -> str:
    normalized = normalize_database_url(url)
    return normalized.replace("postgresql+psycopg://", "postgresql://", 1)


def _r2_endpoint(account_id: str) -> str:
    return f"https://{account_id}.r2.cloudflarestorage.com"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _target_row_count(target_database_url: str) -> int | None:
    engine = create_engine(normalize_database_url(target_database_url))
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM public.users"))
            return int(result.scalar_one())
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
