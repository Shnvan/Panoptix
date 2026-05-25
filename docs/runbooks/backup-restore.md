# Runbook: Backup and Restore

<!-- PE-FIX: Added standalone backup/restore runbook required by council audit -->

## Backup objective

- MVP RPO: ≤24 hours.
- MVP RTO: ≤4 hours.
- Pilot RPO: ≤1 hour with PITR.
- Pilot RTO: ≤1 hour.

## Current implementation status

As of the 2026-05-25 production evidence pass:

- The `backup_runs` table and `BackupRun` model exist for backup metadata.
- Cloudflare R2 bucket `panoptix-backups` is provisioned.
- Production Railway has the required R2 env vars present; values were not printed or recorded during verification.
- Direct production R2 bucket listing succeeded without exposing object keys.
- The production bucket contains one encrypted `.dump.age` database backup object. Object keys are intentionally not recorded in docs or screenshots.
- Production `backup_runs` contains four evidence rows: two earlier diagnostic failures, one successful uploaded/finished backup row, and one isolated restore-drill row.
- Latest successful production backup: `78901812-df12-4a32-b91f-9975772fdca2`; `restore_format_ok=true`; `size_bytes=119112`; `sha256=98ad13944da3705b79b51ce35db30e5f7524daa8577a2387553bf2a760fd3336`.
- Dry-run restore validation passed against the encrypted production artifact: local `age` decrypt plus `pg_restore --list` succeeded.
- Isolated restore drill completed against a temporary Neon branch on 2026-05-25; restore evidence row `564e2bfd-b449-4c9f-b46d-a0366856a7e0` has `restore_schema_ok=true`.
- The temporary Neon restore branch was deleted after validation.
- `python -m cctv_api.jobs.backup_r2` exists for an operator-run encrypted R2 backup from the Railway backend runtime.
- `.github/workflows/production-backup.yml` schedules the encrypted production backup daily at 18:15 UTC / 02:15 Asia/Manila after the workflow is present on the repository default branch.
- `python -m cctv_api.jobs.backup_retention_r2` applies encrypted R2 object retention without deleting `backup_runs` evidence rows.
- `python -m cctv_api.jobs.restore_drill_r2` and `scripts/restore-drill.sh` support the real encrypted `.dump.age` backup format.
- `GET /api/v1/admin/backups/status` reports database-known backup readiness from `backup_runs`.

Backup status returned `ok` after the isolated restore-drill evidence was recorded. The next backup action is to merge the scheduled workflow to the default branch and confirm the first successful scheduled backup/retention run.

## Backup status API

`GET /api/v1/admin/backups/status` is admin-only and returns a compact readiness summary:

- `status`: `missing`, `degraded`, or `ok`.
- `latest_backup`: latest `backup_runs` record, or `null`.
- `latest_restore_drill`: latest row with `restore_schema_ok` recorded, or `null`.
- `checks`: booleans for upload success, backup completion, restore-format check, restore-drill presence, schema-restore result, and latest backup age in hours.

The endpoint does not call R2 and does not expose credentials, object paths, database URLs, backup artifacts, or decryption material.

## Daily backup

1. The scheduled GitHub Actions workflow runs outside the web request path and injects production Railway environment variables with `RAILWAY_TOKEN`.
2. `pg_dump` creates logical backup.
3. Backup is encrypted with `age`.
4. Encrypted object is uploaded to Cloudflare R2.
5. SHA-256 and size are recorded in `backup_runs`.
6. `pg_restore --list` validates archive readability.
7. `restore_format_ok` is recorded.
8. Retention removes expired encrypted R2 objects after a successful backup.

Schedule:

- Workflow: `.github/workflows/production-backup.yml`
- Cron: `15 18 * * *` (18:15 UTC / 02:15 Asia/Manila)
- Manual run: GitHub Actions `workflow_dispatch`
- Activation rule: GitHub scheduled workflows run from the default branch, so this cron starts only after the workflow exists on `main`.

Required GitHub secret:

- `RAILWAY_TOKEN` - Railway project token scoped to production.

Production command:

```powershell
cd C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
railway run --service panoptix-control --environment production --no-local -- python -m cctv_api.jobs.backup_r2
```

Required production variables:

- `R2_ACCOUNT_ID`
- `R2_BUCKET`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `BACKUP_AGE_RECIPIENT`
- `BACKUP_OBJECT_PREFIX` (default: `database`)
- `BACKUP_DATABASE_URL` (optional; defaults to `DATABASE_URL`)
- `BACKUP_RETENTION_DAYS` (default: `30`)
- `BACKUP_RETENTION_MONTHLY_KEEP` (default: `12`)

Do not store the `age` private identity on Railway production. Keep the private restore key offline or in a separate controlled restore environment.

## Retention policy

Retention runs only after a successful encrypted backup in the scheduled workflow.

- Keep every encrypted `.dump.age` backup newer than `BACKUP_RETENTION_DAYS` (default 30 days).
- Keep one monthly encrypted backup for the latest `BACKUP_RETENTION_MONTHLY_KEEP` months (default 12).
- Keep object keys that do not match the expected `panoptix-YYYYMMDDTHHMMSSZ-<uuid>.dump.age` format.
- Delete only expired encrypted R2 objects; do not delete `backup_runs` rows or restore-drill evidence.
- Emit sanitized JSON counts only. Do not print object keys, database URLs, R2 secrets, private keys, or decrypted backup contents.

Dry-run retention check:

```powershell
cd C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
railway run --service panoptix-control --environment production --no-local -- python -m cctv_api.jobs.backup_retention_r2 --dry-run
```

Apply retention manually, normally only after confirming the latest backup succeeded:

```powershell
cd C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
railway run --service panoptix-control --environment production --no-local -- python -m cctv_api.jobs.backup_retention_r2
```

## Restore drill

The restore drill job fetches the latest encrypted `.dump.age` object, downloads it to a temporary directory, decrypts it with a local `age` private identity, validates it with `pg_restore --list`, and optionally restores into an isolated target database.

Dry-run format validation, without restoring or writing restore evidence:

```powershell
$env:PATH = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\FiloSottile.age_Microsoft.Winget.Source_8wekyb3d8bbwe\age;$env:PATH"
cd C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
railway run --service panoptix-control --environment production --no-local -- python -m cctv_api.jobs.restore_drill_r2 --age-identity-file "C:\Users\Ivan\Documents\Panoptix-Backup-Keys\panoptix-prod-age-20260524-165042.txt"
```

Isolated restore drill, after creating a non-production target database:

```powershell
$env:PATH = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\FiloSottile.age_Microsoft.Winget.Source_8wekyb3d8bbwe\age;$env:PATH"
cd C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
railway run --service panoptix-control --environment production --no-local -- python -m cctv_api.jobs.restore_drill_r2 --age-identity-file "C:\Users\Ivan\Documents\Panoptix-Backup-Keys\panoptix-prod-age-20260524-165042.txt" --target-database-url "<isolated-postgres-url>"
```

Rules:

- Never use production `DATABASE_URL` as `--target-database-url`.
- Never print, screenshot, commit, or upload the `AGE-SECRET-KEY-...` identity.
- Do not record object keys, database URLs, R2 secrets, private keys, or decrypted backup contents in docs, logs, screenshots, or tickets.
- `restore_schema_ok=true` should be recorded only after a successful isolated restore and smoke query.

## Emergency restore

1. Declare incident and freeze writes where possible.
2. Select restore point.
3. Restore provider PITR if pilot+; otherwise restore latest encrypted R2 backup.
4. Run audit-chain verifier.
5. Run application smoke tests.
6. Re-enable traffic.
7. Record incident and recovery evidence.

## Security rules

- Production decryption key is not stored on the backup job host.
- Backup logs must not include data contents.
- Restore evidence is stored as a DPA/security artifact.

## DR Testing Schedule

Two levels of DR validation are required:

**Quarterly restore drill** — run `scripts/restore-drill.sh` against a copy of the latest encrypted R2 backup in an isolated environment. Confirms the full decrypt → restore → integration-query path works end-to-end. Target completion: within the first two weeks of each quarter.

**Annual full DR test** — bring up a staging-equivalent environment from scratch using only backup data and Terraform. Validates both the infrastructure rebuild path and the data restore path against a clean slate. Target completion: once per calendar year.

The `scripts/restore-drill.sh` script (created in Round 3A) automates the quarterly drill steps. If the script does not yet exist, the drill must be performed manually following the _Weekly restore drill_ section above.

| Drill Type | Frequency | Owner | Last Completed | Next Due |
| --- | --- | --- | --- | --- |
| Restore drill (automated) | Quarterly | On-call / DevOps | 2026-05-25 | 2026-08-01 |
| Full DR test (manual) | Annually | Engineering lead | — | 2027-05-20 |

## Infrastructure status

- Cloudflare R2 bucket `panoptix-backups` is provisioned and active.
- Terraform Cloud workspace `panoptix-backup-r2` manages bucket state remotely.
- R2 API tokens with Object Read & Write scope (bucket-only) are configured in Railway production.
- Production R2 bucket access was verified on 2026-05-25; one encrypted `.dump.age` backup artifact exists.
- Isolated restore drill completed on 2026-05-25 against a temporary Neon branch, which was deleted after validation.
- `python -m cctv_api.jobs.backup_r2` is available for operator-run encrypted backups.
- `.github/workflows/production-backup.yml` is available for recurring daily backup and retention automation after merge to `main`.
- `python -m cctv_api.jobs.backup_retention_r2` is available for 30-day plus 12-month encrypted object retention.
- `python -m cctv_api.jobs.restore_drill_r2` and `scripts/restore-drill.sh` are available for encrypted artifact validation and isolated restore drills.

Record completion dates and any anomalies found as a DPA/security artifact alongside the standard restore evidence.
