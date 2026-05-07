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
