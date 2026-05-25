from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from cctv_api.core.config import Settings, get_settings


@dataclass(frozen=True)
class BackupObject:
    key: str
    last_modified: datetime | None = None
    size_bytes: int | None = None


class BackupRetentionObjectStore(Protocol):
    def list_encrypted_backups(self, *, bucket: str, prefix: str) -> list[BackupObject]: ...

    def delete_objects(self, *, bucket: str, keys: Sequence[str]) -> None: ...


@dataclass(frozen=True)
class BackupRetentionResult:
    status: str
    dry_run: bool
    scanned_count: int
    retained_recent_count: int
    retained_monthly_count: int
    retained_unparseable_count: int
    planned_delete_count: int
    deleted_count: int
    error: str | None = None


@dataclass(frozen=True)
class _RetentionPlan:
    recent_keys: set[str]
    monthly_keys: set[str]
    unparseable_keys: set[str]
    delete_keys: list[str]


class BackupRetentionError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class R2BackupRetentionObjectStore:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def list_encrypted_backups(self, *, bucket: str, prefix: str) -> list[BackupObject]:
        import boto3  # type: ignore[import-untyped]

        client = boto3.client(
            "s3",
            endpoint_url=_r2_endpoint(self._settings.R2_ACCOUNT_ID),
            region_name="auto",
            aws_access_key_id=self._settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=self._settings.R2_SECRET_ACCESS_KEY,
        )
        paginator = client.get_paginator("list_objects_v2")
        objects: list[BackupObject] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item.get("Key")
                if not isinstance(key, str) or not key.endswith(".dump.age"):
                    continue
                last_modified = item.get("LastModified")
                size = item.get("Size")
                objects.append(
                    BackupObject(
                        key=key,
                        last_modified=last_modified if isinstance(last_modified, datetime) else None,
                        size_bytes=int(size) if isinstance(size, int) else None,
                    )
                )
        return objects

    def delete_objects(self, *, bucket: str, keys: Sequence[str]) -> None:
        import boto3  # type: ignore[import-untyped]

        client = boto3.client(
            "s3",
            endpoint_url=_r2_endpoint(self._settings.R2_ACCOUNT_ID),
            region_name="auto",
            aws_access_key_id=self._settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=self._settings.R2_SECRET_ACCESS_KEY,
        )
        for key in keys:
            client.delete_object(Bucket=bucket, Key=key)


def run_backup_retention_job(
    *,
    settings: Settings,
    object_store: BackupRetentionObjectStore | None = None,
    dry_run: bool = False,
    now: Callable[[], datetime] | None = None,
) -> BackupRetentionResult:
    object_store = object_store or R2BackupRetentionObjectStore(settings=settings)
    now = now or (lambda: datetime.now(timezone.utc))

    try:
        _validate_retention_settings(settings)
        prefix = _object_prefix(settings.BACKUP_OBJECT_PREFIX)
        objects = object_store.list_encrypted_backups(bucket=settings.R2_BUCKET, prefix=prefix)
        plan = _retention_plan(
            objects,
            retention_days=settings.BACKUP_RETENTION_DAYS,
            monthly_keep=settings.BACKUP_RETENTION_MONTHLY_KEEP,
            now=now(),
        )

        deleted_count = 0
        if plan.delete_keys and not dry_run:
            object_store.delete_objects(bucket=settings.R2_BUCKET, keys=plan.delete_keys)
            deleted_count = len(plan.delete_keys)

        return BackupRetentionResult(
            status="ok",
            dry_run=dry_run,
            scanned_count=len(objects),
            retained_recent_count=len(plan.recent_keys),
            retained_monthly_count=len(plan.monthly_keys),
            retained_unparseable_count=len(plan.unparseable_keys),
            planned_delete_count=len(plan.delete_keys),
            deleted_count=deleted_count,
        )
    except BackupRetentionError as exc:
        return _failed_result(dry_run=dry_run, error=exc.code)
    except Exception:
        return _failed_result(dry_run=dry_run, error="r2-retention-failed")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply Panoptix encrypted R2 backup retention.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    settings = get_settings()
    settings.validate_production_guardrails()
    result = run_backup_retention_job(settings=settings, dry_run=args.dry_run)
    print(json.dumps(_result_to_json(result), sort_keys=True))
    return 0 if result.status == "ok" else 1


def _retention_plan(
    objects: Sequence[BackupObject],
    *,
    retention_days: int,
    monthly_keep: int,
    now: datetime,
) -> _RetentionPlan:
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    cutoff = current - timedelta(days=retention_days)

    parsed: list[tuple[BackupObject, datetime]] = []
    unparseable_keys: set[str] = set()
    for backup_object in objects:
        parsed_at = _parse_object_timestamp(backup_object.key)
        if parsed_at is None:
            unparseable_keys.add(backup_object.key)
        else:
            parsed.append((backup_object, parsed_at))

    recent_keys = {backup_object.key for backup_object, ts in parsed if ts >= cutoff}
    monthly_candidates = [
        (backup_object, ts) for backup_object, ts in parsed if backup_object.key not in recent_keys
    ]

    latest_by_month: dict[str, tuple[BackupObject, datetime]] = {}
    for backup_object, ts in monthly_candidates:
        month = ts.strftime("%Y-%m")
        existing = latest_by_month.get(month)
        if existing is None or ts > existing[1]:
            latest_by_month[month] = (backup_object, ts)

    retained_months = sorted(latest_by_month.keys(), reverse=True)[:monthly_keep]
    monthly_keys = {latest_by_month[month][0].key for month in retained_months}
    keep_keys = recent_keys | monthly_keys | unparseable_keys
    delete_keys = sorted(backup_object.key for backup_object in objects if backup_object.key not in keep_keys)

    return _RetentionPlan(
        recent_keys=recent_keys,
        monthly_keys=monthly_keys,
        unparseable_keys=unparseable_keys,
        delete_keys=delete_keys,
    )


def _validate_retention_settings(settings: Settings) -> None:
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
        raise BackupRetentionError(f"retention-config-missing: {', '.join(missing)}")


def _has_value(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and "replace-me" not in stripped and not stripped.startswith("<")


def _object_prefix(prefix: str) -> str:
    return prefix.strip().strip("/") or "database"


def _r2_endpoint(account_id: str) -> str:
    return f"https://{account_id}.r2.cloudflarestorage.com"


def _parse_object_timestamp(key: str) -> datetime | None:
    filename = Path(key).name
    match = re.match(r"^panoptix-(\d{8}T\d{6}Z)-.+\.dump\.age$", filename)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _failed_result(*, dry_run: bool, error: str) -> BackupRetentionResult:
    return BackupRetentionResult(
        status="failed",
        dry_run=dry_run,
        scanned_count=0,
        retained_recent_count=0,
        retained_monthly_count=0,
        retained_unparseable_count=0,
        planned_delete_count=0,
        deleted_count=0,
        error=error,
    )


def _result_to_json(result: BackupRetentionResult) -> dict[str, object]:
    return {
        "status": result.status,
        "dry_run": result.dry_run,
        "scanned_count": result.scanned_count,
        "retained_recent_count": result.retained_recent_count,
        "retained_monthly_count": result.retained_monthly_count,
        "retained_unparseable_count": result.retained_unparseable_count,
        "planned_delete_count": result.planned_delete_count,
        "deleted_count": result.deleted_count,
        "error": result.error,
    }


if __name__ == "__main__":
    raise SystemExit(main())
