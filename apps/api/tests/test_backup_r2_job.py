from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.jobs.backup_r2 import run_r2_backup_job
from cctv_api.models.enums import BackupUploadStatus
from cctv_api.models.tables import BackupRun


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "DATABASE_URL": "postgresql+psycopg://user:secret@db.example/panoptix",
        "R2_ACCOUNT_ID": "account-id",
        "R2_BUCKET": "panoptix-backups",
        "R2_ACCESS_KEY_ID": "access-key",
        "R2_SECRET_ACCESS_KEY": "secret-key",
        "BACKUP_AGE_RECIPIENT": "age1testrecipient",
    }
    values.update(overrides)
    return Settings(**values)


@dataclass
class FakeCommandRunner:
    fail_command: str | None = None
    commands: list[list[str]] = field(default_factory=list)

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        cmd = list(command)
        self.commands.append(cmd)
        if self.fail_command and cmd[0] == self.fail_command:
            raise subprocess.CalledProcessError(1, cmd, stderr="simulated failure")

        if cmd[0] == "pg_dump":
            Path(cmd[cmd.index("--file") + 1]).write_bytes(b"postgres custom dump")
        elif cmd[0] == "age":
            Path(cmd[cmd.index("-o") + 1]).write_bytes(b"encrypted backup bytes")

        return subprocess.CompletedProcess(cmd, 0, "", "")


@dataclass
class FakeUploader:
    should_fail: bool = False
    uploads: list[tuple[Path, str, str]] = field(default_factory=list)

    def upload_file(self, path: Path, *, bucket: str, key: str) -> None:
        if self.should_fail:
            raise RuntimeError("simulated upload failure")
        self.uploads.append((path, bucket, key))


def test_r2_backup_job_creates_upload_and_backup_run(test_db_session: DbSession) -> None:
    runner = FakeCommandRunner()
    uploader = FakeUploader()

    result = run_r2_backup_job(
        test_db_session,
        settings=_settings(),
        command_runner=runner,
        uploader=uploader,
        now=lambda: datetime(2026, 5, 24, 1, 2, 3, tzinfo=timezone.utc),
    )

    assert result.upload_status == BackupUploadStatus.uploaded
    assert result.restore_format_ok is True
    assert result.size_bytes == len(b"encrypted backup bytes")
    assert result.sha256 == "170e627590bc7a874e031d7ceb3f254163eeab845d9a9176a3012d427492e99e"

    row = test_db_session.get(BackupRun, result.backup_run_id)
    assert row is not None
    assert row.upload_status == BackupUploadStatus.uploaded
    assert row.finished_at is not None
    assert row.restore_format_ok is True
    assert row.notes == "operator-run R2 backup uploaded; object key withheld from API output"

    assert [command[0] for command in runner.commands] == ["pg_dump", "pg_restore", "age"]
    assert runner.commands[0][-1].startswith("postgresql://")
    assert "postgresql+psycopg://" not in runner.commands[0][-1]
    assert len(uploader.uploads) == 1
    assert uploader.uploads[0][1] == "panoptix-backups"
    assert uploader.uploads[0][2].startswith("database/2026/05/24/panoptix-20260524T010203Z-")
    assert uploader.uploads[0][2].endswith(".dump.age")


def test_r2_backup_job_records_missing_config_without_creating_artifact(
    test_db_session: DbSession,
) -> None:
    runner = FakeCommandRunner()
    uploader = FakeUploader()

    result = run_r2_backup_job(
        test_db_session,
        settings=_settings(BACKUP_AGE_RECIPIENT=""),
        command_runner=runner,
        uploader=uploader,
    )

    row = test_db_session.get(BackupRun, result.backup_run_id)
    assert row is not None
    assert result.upload_status == BackupUploadStatus.failed
    assert row.upload_status == BackupUploadStatus.failed
    assert row.notes == "backup-config-missing: BACKUP_AGE_RECIPIENT"
    assert runner.commands == []
    assert uploader.uploads == []


def test_r2_backup_job_records_dump_failure(test_db_session: DbSession) -> None:
    result = run_r2_backup_job(
        test_db_session,
        settings=_settings(),
        command_runner=FakeCommandRunner(fail_command="pg_dump"),
        uploader=FakeUploader(),
    )

    row = test_db_session.get(BackupRun, result.backup_run_id)
    assert row is not None
    assert result.upload_status == BackupUploadStatus.failed
    assert result.error == "pg-dump-failed"
    assert row.notes == "pg-dump-failed"
    assert row.restore_format_ok is False


def test_r2_backup_job_records_restore_validation_failure(test_db_session: DbSession) -> None:
    result = run_r2_backup_job(
        test_db_session,
        settings=_settings(),
        command_runner=FakeCommandRunner(fail_command="pg_restore"),
        uploader=FakeUploader(),
    )

    row = test_db_session.get(BackupRun, result.backup_run_id)
    assert row is not None
    assert result.upload_status == BackupUploadStatus.failed
    assert result.error == "pg-restore-list-failed"
    assert row.notes == "pg-restore-list-failed"


def test_r2_backup_job_records_age_failure(test_db_session: DbSession) -> None:
    result = run_r2_backup_job(
        test_db_session,
        settings=_settings(),
        command_runner=FakeCommandRunner(fail_command="age"),
        uploader=FakeUploader(),
    )

    row = test_db_session.get(BackupRun, result.backup_run_id)
    assert row is not None
    assert result.upload_status == BackupUploadStatus.failed
    assert result.error == "age-encryption-failed"
    assert row.notes == "age-encryption-failed"


def test_r2_backup_job_records_upload_failure(test_db_session: DbSession) -> None:
    result = run_r2_backup_job(
        test_db_session,
        settings=_settings(),
        command_runner=FakeCommandRunner(),
        uploader=FakeUploader(should_fail=True),
    )

    row = test_db_session.get(BackupRun, result.backup_run_id)
    assert row is not None
    assert result.upload_status == BackupUploadStatus.failed
    assert result.error == "r2-upload-or-metadata-failed"
    assert row.notes == "r2-upload-or-metadata-failed"
