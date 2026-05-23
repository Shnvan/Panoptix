# Runbook: Backup and Restore

<!-- PE-FIX: Added standalone backup/restore runbook required by council audit -->

## Backup objective

- MVP RPO: ≤24 hours.
- MVP RTO: ≤4 hours.
- Pilot RPO: ≤1 hour with PITR.
- Pilot RTO: ≤1 hour.

## Current implementation status

As of the 2026-05-24 production evidence pass:

- The `backup_runs` table and `BackupRun` model exist for backup metadata.
- Cloudflare R2 bucket `panoptix-backups` is provisioned.
- Production Railway has the required R2 env vars present; values were not printed or recorded during verification.
- Direct production R2 bucket listing succeeded without exposing object keys.
- The production bucket currently reports no objects, and production `backup_runs` currently has `0` rows.
- `python -m cctv_api.jobs.backup_r2` exists for an operator-run encrypted R2 backup from the Railway backend runtime.
- `scripts/restore-drill.sh` exists for an operator-run restore drill against R2 and a target database.
- `GET /api/v1/admin/backups/status` reports database-known backup readiness from `backup_runs`.
- A real restore drill has not yet been recorded in repository evidence.

Do not treat backups as production-operational until a backup artifact is produced and restore-drill evidence is recorded.
The immediate next step is to deploy and run the first real production backup job, not a restore drill.

## Backup status API

`GET /api/v1/admin/backups/status` is admin-only and returns a compact readiness summary:

- `status`: `missing`, `degraded`, or `ok`.
- `latest_backup`: latest `backup_runs` record, or `null`.
- `latest_restore_drill`: latest row with `restore_schema_ok` recorded, or `null`.
- `checks`: booleans for upload success, backup completion, restore-format check, restore-drill presence, schema-restore result, and latest backup age in hours.

The endpoint does not call R2 and does not expose credentials, object paths, database URLs, backup artifacts, or decryption material.

## Daily backup

1. Operator-run backup job runs outside the web request path with `python -m cctv_api.jobs.backup_r2`.
2. `pg_dump` creates logical backup.
3. Backup is encrypted with `age`.
4. Encrypted object is uploaded to Cloudflare R2.
5. SHA-256 and size are recorded in `backup_runs`.
6. `pg_restore --list` validates archive readability.
7. `restore_format_ok` is recorded.

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

Do not store the `age` private identity on Railway production. Keep the private restore key offline or in a separate controlled restore environment.

## Weekly restore drill

1. Fetch latest encrypted backup.
2. Decrypt in controlled test environment.
3. Restore to ephemeral Postgres.
4. Run integration query:
   - audit chain verification,
   - camera/gateway row counts,
   - user/session sanity checks.
5. Record `restore_schema_ok`.
6. Alert on failure or stale drill.

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
| Restore drill (automated) | Quarterly | On-call / DevOps | — | 2026-08-01 |
| Full DR test (manual) | Annually | Engineering lead | — | 2027-05-20 |

## Infrastructure status

- Cloudflare R2 bucket `panoptix-backups` is provisioned and active.
- Terraform Cloud workspace `panoptix-backup-r2` manages bucket state remotely.
- R2 API tokens with Object Read & Write scope (bucket-only) are configured in Railway production.
- Production R2 bucket access was verified on 2026-05-24; no backup objects existed at that time.
- `python -m cctv_api.jobs.backup_r2` is available for operator-run encrypted backups.
- `scripts/restore-drill.sh` is available for automated quarterly drills.

Record completion dates and any anomalies found as a DPA/security artifact alongside the standard restore evidence.
