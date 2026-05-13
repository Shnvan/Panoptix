# Runbook: Backup and Restore

<!-- PE-FIX: Added standalone backup/restore runbook required by council audit -->

## Backup objective

- MVP RPO: ≤24 hours.
- MVP RTO: ≤4 hours.
- Pilot RPO: ≤1 hour with PITR.
- Pilot RTO: ≤1 hour.

## Daily backup

1. Scheduled backup job runs outside the web process.
2. `pg_dump` creates logical backup.
3. Backup is encrypted with `age`.
4. Encrypted object is uploaded to Cloudflare R2 with object lock.
5. SHA-256 and size are recorded in `backup_runs`.
6. `pg_restore --list` validates archive readability.
7. `restore_format_ok` is recorded.

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
- R2 API tokens with Object Read & Write scope (bucket-only) are configured in Railway staging.
- `scripts/restore-drill.sh` is available for automated quarterly drills.

Record completion dates and any anomalies found as a DPA/security artifact alongside the standard restore evidence.
