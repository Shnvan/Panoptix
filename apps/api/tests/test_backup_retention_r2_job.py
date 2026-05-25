from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone

from cctv_api.core.config import Settings
from cctv_api.jobs.backup_retention_r2 import BackupObject, run_backup_retention_job


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "R2_ACCOUNT_ID": "account-id",
        "R2_BUCKET": "panoptix-backups",
        "R2_ACCESS_KEY_ID": "access-key",
        "R2_SECRET_ACCESS_KEY": "secret-key",
        "BACKUP_OBJECT_PREFIX": "database",
    }
    values.update(overrides)
    return Settings(**values)


@dataclass
class FakeObjectStore:
    objects: list[BackupObject]
    listed_prefixes: list[str] = field(default_factory=list)
    deleted_keys: list[str] = field(default_factory=list)

    def list_encrypted_backups(self, *, bucket: str, prefix: str) -> list[BackupObject]:
        self.listed_prefixes.append(prefix)
        return self.objects

    def delete_objects(self, *, bucket: str, keys: Sequence[str]) -> None:
        self.deleted_keys.extend(keys)


def _key(ts: datetime, suffix: str = "00000000-0000-0000-0000-000000000000") -> str:
    return (
        f"database/{ts:%Y/%m/%d}/"
        f"panoptix-{ts:%Y%m%dT%H%M%SZ}-{suffix}.dump.age"
    )


def test_backup_retention_keeps_recent_and_deletes_expired_when_monthly_disabled() -> None:
    now = datetime(2026, 5, 25, 0, 0, tzinfo=timezone.utc)
    recent_key = _key(datetime(2026, 5, 10, 0, 0, tzinfo=timezone.utc))
    expired_key = _key(
        datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
        "00000000-0000-0000-0000-000000000001",
    )
    store = FakeObjectStore(objects=[BackupObject(key=recent_key), BackupObject(key=expired_key)])

    result = run_backup_retention_job(
        settings=_settings(BACKUP_RETENTION_DAYS=30, BACKUP_RETENTION_MONTHLY_KEEP=0),
        object_store=store,
        now=lambda: now,
    )

    assert result.status == "ok"
    assert result.scanned_count == 2
    assert result.retained_recent_count == 1
    assert result.retained_monthly_count == 0
    assert result.planned_delete_count == 1
    assert result.deleted_count == 1
    assert store.deleted_keys == [expired_key]


def test_backup_retention_keeps_twelve_latest_monthly_backups() -> None:
    now = datetime(2026, 5, 25, 0, 0, tzinfo=timezone.utc)
    objects: list[BackupObject] = []
    keys_by_month: list[str] = []
    for index in range(14):
        ts = _minus_months(datetime(2026, 4, 15, 0, 0, tzinfo=timezone.utc), index)
        key = _key(ts, f"00000000-0000-0000-0000-{index:012d}")
        keys_by_month.append(key)
        objects.append(BackupObject(key=key))
    store = FakeObjectStore(objects=objects)

    result = run_backup_retention_job(
        settings=_settings(BACKUP_RETENTION_DAYS=30, BACKUP_RETENTION_MONTHLY_KEEP=12),
        object_store=store,
        now=lambda: now,
    )

    assert result.status == "ok"
    assert result.retained_recent_count == 0
    assert result.retained_monthly_count == 12
    assert result.planned_delete_count == 2
    assert result.deleted_count == 2
    assert store.deleted_keys == sorted(keys_by_month[12:])


def test_backup_retention_dry_run_deletes_nothing() -> None:
    now = datetime(2026, 5, 25, 0, 0, tzinfo=timezone.utc)
    expired_key = _key(datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc))
    store = FakeObjectStore(objects=[BackupObject(key=expired_key)])

    result = run_backup_retention_job(
        settings=_settings(BACKUP_RETENTION_DAYS=30, BACKUP_RETENTION_MONTHLY_KEEP=0),
        object_store=store,
        dry_run=True,
        now=lambda: now,
    )

    assert result.status == "ok"
    assert result.planned_delete_count == 1
    assert result.deleted_count == 0
    assert store.deleted_keys == []


def _minus_months(ts: datetime, months: int) -> datetime:
    month_index = ts.year * 12 + (ts.month - 1) - months
    year = month_index // 12
    month = (month_index % 12) + 1
    return ts.replace(year=year, month=month)


def test_backup_retention_missing_config_fails_without_delete() -> None:
    now = datetime(2026, 5, 25, 0, 0, tzinfo=timezone.utc)
    expired_key = _key(datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc))
    store = FakeObjectStore(objects=[BackupObject(key=expired_key)])

    result = run_backup_retention_job(
        settings=_settings(R2_BUCKET=""),
        object_store=store,
        now=lambda: now,
    )

    assert result.status == "failed"
    assert result.error == "retention-config-missing: R2_BUCKET"
    assert result.deleted_count == 0
    assert store.deleted_keys == []


def test_backup_retention_preserves_unparseable_keys() -> None:
    now = datetime(2026, 5, 25, 0, 0, tzinfo=timezone.utc)
    unparseable_key = "database/manual/backup.dump.age"
    store = FakeObjectStore(objects=[BackupObject(key=unparseable_key)])

    result = run_backup_retention_job(
        settings=_settings(BACKUP_RETENTION_DAYS=30, BACKUP_RETENTION_MONTHLY_KEEP=0),
        object_store=store,
        now=lambda: now,
    )

    assert result.status == "ok"
    assert result.retained_unparseable_count == 1
    assert result.planned_delete_count == 0
    assert result.deleted_count == 0
    assert store.deleted_keys == []
