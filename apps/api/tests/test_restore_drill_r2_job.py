from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session as DbSession

import cctv_api.jobs.restore_drill_r2 as restore_drill
from cctv_api.core.config import Settings
from cctv_api.jobs.restore_drill_r2 import BackupObject, run_restore_drill
from cctv_api.models.enums import BackupUploadStatus
from cctv_api.models.tables import BackupRun


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "DATABASE_URL": "postgresql+psycopg://user:secret@db.example/panoptix",
        "R2_ACCOUNT_ID": "account-id",
        "R2_BUCKET": "panoptix-backups",
        "R2_ACCESS_KEY_ID": "access-key",
        "R2_SECRET_ACCESS_KEY": "secret-key",
    }
    values.update(overrides)
    return Settings(**values)


@dataclass
class FakeObjectStore:
    latest: BackupObject | None = BackupObject(key="database/backup.dump.age", size_bytes=20)
    downloads: list[tuple[str, str, Path]] = field(default_factory=list)

    def latest_encrypted_backup(self, *, bucket: str) -> BackupObject | None:
        return self.latest

    def download_file(self, *, bucket: str, key: str, destination: Path) -> None:
        self.downloads.append((bucket, key, destination))
        destination.write_bytes(b"encrypted backup bytes")


@dataclass
class FakeCommandRunner:
    fail_command: str | None = None
    commands: list[list[str]] = field(default_factory=list)

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        cmd = list(command)
        self.commands.append(cmd)
        if self.fail_command and cmd[0] == self.fail_command:
            raise subprocess.CalledProcessError(1, cmd, stderr="simulated failure")

        if cmd[0] == "age":
            Path(cmd[cmd.index("-o") + 1]).write_bytes(b"postgres custom dump")

        return subprocess.CompletedProcess(cmd, 0, "", "")


def test_restore_drill_dry_run_downloads_decrypts_and_validates_without_evidence_row(
    test_db_session: DbSession,
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity.txt"
    identity.write_text("AGE-SECRET-KEY-test", encoding="utf-8")
    object_store = FakeObjectStore()
    runner = FakeCommandRunner()

    result = run_restore_drill(
        test_db_session,
        settings=_settings(),
        age_identity_file=identity,
        object_store=object_store,
        command_runner=runner,
    )

    assert result.dry_run is True
    assert result.restore_format_ok is True
    assert result.restore_schema_ok is None
    assert result.backup_run_id is None
    assert result.size_bytes == len(b"encrypted backup bytes")
    assert result.sha256 == "170e627590bc7a874e031d7ceb3f254163eeab845d9a9176a3012d427492e99e"
    assert [command[0] for command in runner.commands] == ["age", "pg_restore"]
    assert len(object_store.downloads) == 1
    assert test_db_session.query(BackupRun).count() == 0


def test_restore_drill_with_target_records_restore_evidence_row(
    test_db_session: DbSession,
    tmp_path: Path,
    monkeypatch,
) -> None:
    identity = tmp_path / "identity.txt"
    identity.write_text("AGE-SECRET-KEY-test", encoding="utf-8")
    runner = FakeCommandRunner()
    monkeypatch.setattr(restore_drill, "_target_row_count", lambda _url: 7)

    result = run_restore_drill(
        test_db_session,
        settings=_settings(),
        age_identity_file=identity,
        target_database_url="postgresql+psycopg://restore:secret@localhost/restore_db",
        object_store=FakeObjectStore(),
        command_runner=runner,
        now=lambda: datetime(2026, 5, 25, 1, 2, 3, tzinfo=timezone.utc),
    )

    assert result.dry_run is False
    assert result.restore_format_ok is True
    assert result.restore_schema_ok is True
    assert result.backup_run_id is not None
    assert [command[0] for command in runner.commands] == ["age", "pg_restore", "pg_restore"]
    restore_command = runner.commands[-1]
    assert "--exit-on-error" in restore_command
    assert "--clean" in restore_command
    assert "--if-exists" in restore_command
    assert restore_command[-2].startswith("postgresql://")
    assert "postgresql+psycopg://" not in restore_command[-2]

    row = test_db_session.get(BackupRun, result.backup_run_id)
    assert row is not None
    assert row.upload_status == BackupUploadStatus.uploaded
    assert row.restore_format_ok is True
    assert row.restore_schema_ok is True
    assert row.row_count_estimate == 7
    assert row.notes == "operator restore drill passed; source object key withheld from API output"


def test_restore_drill_missing_identity_file_fails_without_row(test_db_session: DbSession) -> None:
    result = run_restore_drill(
        test_db_session,
        settings=_settings(),
        age_identity_file=Path("missing-age-identity.txt"),
        object_store=FakeObjectStore(),
        command_runner=FakeCommandRunner(),
    )

    assert result.error == "age-identity-file-missing"
    assert result.restore_format_ok is False
    assert test_db_session.query(BackupRun).count() == 0


def test_restore_drill_no_backup_object_fails_without_row(
    test_db_session: DbSession,
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity.txt"
    identity.write_text("AGE-SECRET-KEY-test", encoding="utf-8")

    result = run_restore_drill(
        test_db_session,
        settings=_settings(),
        age_identity_file=identity,
        object_store=FakeObjectStore(latest=None),
        command_runner=FakeCommandRunner(),
    )

    assert result.error == "backup-object-not-found"
    assert result.restore_format_ok is False
    assert test_db_session.query(BackupRun).count() == 0


def test_restore_drill_decryption_failure_fails_without_row(
    test_db_session: DbSession,
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity.txt"
    identity.write_text("AGE-SECRET-KEY-test", encoding="utf-8")

    result = run_restore_drill(
        test_db_session,
        settings=_settings(),
        age_identity_file=identity,
        object_store=FakeObjectStore(),
        command_runner=FakeCommandRunner(fail_command="age"),
    )

    assert result.error == "age-decryption-failed"
    assert result.restore_format_ok is False
    assert test_db_session.query(BackupRun).count() == 0
