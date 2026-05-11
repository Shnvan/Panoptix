# Neon Staging Database Checklist

Docs-only checklist for provisioning the Neon Postgres staging database. Do **not** commit real connection strings, passwords, or project IDs to this file.

---

## Project Setup

- [ ] Create a Neon project named `panoptix-staging` (or per team convention).
- [ ] Select the region closest to the Railway staging service.
- [ ] Note the project ID for internal reference (do not commit it).

## Database

- [ ] Create database `panoptix` (or confirm the default database name).
- [ ] Confirm the database uses PostgreSQL 16+ (or the version matching local development).

## Roles

| Role | Purpose | Privileges |
|------|---------|------------|
| `cctv_app_runtime` | Used by the running API for queries | `SELECT`, `INSERT`, `UPDATE`, `DELETE` on application tables. No schema-alter. |
| `cctv_migrator` | Used only for schema migrations | `CREATE`, `ALTER`, `DROP` on schema objects. Used during deploy only. |

- [ ] Create `cctv_app_runtime` role with a strong generated password.
- [ ] Create `cctv_migrator` role with a strong generated password.
- [ ] Grant appropriate privileges to each role.
- [ ] Confirm `cctv_app_runtime` cannot alter schema.

## Connection Strings

- [ ] Copy the **pooled** connection string for `cctv_app_runtime` → Railway `DATABASE_URL`.
- [ ] Copy the **direct** (non-pooled) connection string for `cctv_migrator` → Railway `MIGRATION_DATABASE_URL`.
- [ ] Confirm both use `sslmode=require`.
- [ ] Store both in Railway secret environment variables, not in the repository.

## SSL

- [ ] Verify Neon enforces SSL for all connections (default behavior).
- [ ] Confirm the backend driver (`psycopg`) connects with `sslmode=require`.

## Migrations

- [ ] Run migrations locally against a disposable Postgres first to validate.
- [ ] Apply migrations to Neon staging using the `cctv_migrator` role.
- [ ] Confirm the runtime role can read/write application tables after migration.
- [ ] Record the migration version applied.

## Backup and Recovery

- [ ] Confirm Neon PITR (point-in-time recovery) is available on the staging project.
- [ ] Note the retention window (default: 7 days on free tier, 30 days on paid).
- [ ] Plan a restore drill before promoting to production.
- [ ] See [Backup and Restore](../backup-restore.md) runbook for the full procedure.

## Post-Setup Verification

- [ ] Backend starts without `unsafe-production-config` errors.
- [ ] `/health` returns `{ "status": "ok" }`.
- [ ] A simple query (e.g., list cameras) returns an empty result, not a connection error.
- [ ] `cctv_app_runtime` cannot run DDL statements (e.g., `CREATE TABLE` should fail).

---

## References

| What | Where |
|------|-------|
| Railway staging prep | `docs/runbooks/railway-neon-staging-prep.md` |
| Railway API env template | `docs/runbooks/templates/railway-api.env.example` |
| Backup and restore | `docs/runbooks/backup-restore.md` |
| Deploy and rollback | `docs/runbooks/deploy-rollback.md` |
| Environment variable schema | `.env.example` |
