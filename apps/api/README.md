# Panoptix API

FastAPI control-plane service owned by the system owner.

## Scope

This service is responsible for:

- Cloudflare Access JWT verification
- session and authorization control
- backend API endpoints
- LiveKit token minting
- gateway identity and command/control coordination
- audit/control-plane logic

## Out of scope

- frontend UI implementation
- database schema and migration ownership

Frontend and database implementation remain assigned to the respective coworkers in `docs/implementation/team-raci-checklist.md`.

## Migrations

Alembic migrations live in `apps/api/alembic/`.

Environment variables:

- `MIGRATION_DATABASE_URL` (preferred) — privileged role/user for running Alembic migrations.
- `DATABASE_URL` — runtime app role/user.

If `MIGRATION_DATABASE_URL` is not set, migrations fall back to `DATABASE_URL` (dev convenience only).
