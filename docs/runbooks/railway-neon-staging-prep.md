# Railway / Neon Staging Deployment Prep

Docs-only staging deployment preparation checklist for Railway (compute) and Neon (Postgres). This runbook captures the required accounts, services, environment variables, migration safety, and release gates **before** any external setup begins.

## Non-Goals

- This runbook does **not** create Railway services, Neon databases, or Cloudflare policies.
- It does **not** contain real secrets, account IDs, project IDs, or connection strings.
- It does **not** replace the existing [Deploy and Rollback](deploy-rollback.md) or [Cloudflare Production Setup](cloudflare-production-setup.md) runbooks.

---

## Required Accounts and Access

Before staging setup begins, confirm:

- [ ] Railway team/org account created with billing enabled.
- [ ] Neon project created (free-tier is fine for staging).
- [ ] Cloudflare team configured with Access policies ready to provision (see [Cloudflare Production Setup](cloudflare-production-setup.md)).
- [ ] GitHub repo linked to Railway for deploy-on-push or manual deploy.
- [ ] At least two team members have admin access to Railway and Neon dashboards.

---

## Railway Service Plan

### `cctv-api` (FastAPI backend)

| Setting | Value |
|---------|-------|
| Source | `apps/api` (Dockerfile build) |
| Start command | `uvicorn cctv_api.main:app --host 0.0.0.0 --port 8000` |
| Port | `8000` |
| Region | Choose region closest to expected users |
| Environment | `staging` |
| Health check path | `/health` |
| Deploy trigger | Push to `main` or manual |

### `cctv-web` (Next.js frontend — future)

| Setting | Value |
|---------|-------|
| Source | `apps/cctv-web` |
| Start command | `npm start` |
| Port | `3000` |
| Environment | `staging` |
| Deploy trigger | Push to `main` or manual |

> **Note:** `cctv-web` is owned by the frontend coworker and is not yet ready for deployment. Include it in the Railway project as a placeholder service only.

---

## Neon Staging Database

### Database and Roles

| Item | Value |
|------|-------|
| Neon project name | `panoptix-staging` (or team convention) |
| Database name | `panoptix` |
| Runtime role | `cctv_app_runtime` — used by the running API for queries |
| Migration role | `cctv_migrator` — used only for schema migrations |

### Connection Strings

Railway environment variables must use the Neon-provided pooled connection string:

```text
DATABASE_URL=postgresql+psycopg://<cctv_app_runtime>:<password>@<neon-host>/panoptix?sslmode=require
MIGRATION_DATABASE_URL=postgresql+psycopg://<cctv_migrator>:<password>@<neon-host>/panoptix?sslmode=require
```

Rules:

- Always use `sslmode=require` for Neon connections.
- Use connection pooling (Neon proxy) for the runtime role.
- Use the direct (non-pooled) endpoint for migration runs if needed.
- Do not share credentials between runtime and migration roles.
- Store connection strings in Railway's secret environment variables, never in the repository.

See also: [Neon staging checklist](templates/neon-staging-checklist.md).

---

## Required Environment Variables

All staging environment variables are listed in the placeholder template:

```text
docs/runbooks/templates/railway-api.env.example
```

Key groups:

- **Environment**: `APP_ENV=staging`, `ALLOW_DEV_AUTH=0`
- **Cloudflare Access**: issuer, audience IDs, JWKS URL
- **Session/CSRF**: signing keys (generated, not placeholder)
- **Audit**: HMAC key and version
- **Database**: runtime and migration connection strings
- **LiveKit**: cloud URL, API key, API secret, webhook secret
- **Gateway**: service token, command signing key
- **Security headers**: CSP report URI, LiveKit connect-src

The backend [production auth guardrails](../runbooks/cloudflare-production-setup.md) will reject startup if any guarded value still contains `replace-me` or `example.cloudflareaccess.com`.

---

## Migration Safety

- Database migrations must follow the expand/contract pattern.
- Never run destructive migrations (DROP COLUMN, DROP TABLE) in the same release as the code change that removes usage.
- The migration role (`cctv_migrator`) must have schema-alter privileges; the runtime role (`cctv_app_runtime`) must not.
- Test migrations locally against a disposable Postgres before applying to Neon staging.
- Record migration version and hash in the deployment audit event.
- If a migration fails, do **not** retry automatically — follow the [Deploy and Rollback](deploy-rollback.md) runbook.

---

## Staging Smoke Validation

After first staging deploy, verify:

- [ ] `/health` returns `{ "status": "ok" }`.
- [ ] `APP_ENV` is `staging` (visible in logs or health metadata).
- [ ] Production auth guardrails passed (app started without `unsafe-production-config`).
- [ ] Cloudflare Access JWT verification works for a test browser session.
- [ ] `/api/v1/me` returns valid principal for authenticated user.
- [ ] Direct Railway URL returns fail-closed for protected routes.
- [ ] Database connection works (health or `/api/v1/cameras` returns empty list, not 500).
- [ ] Gateway heartbeat endpoint accepts valid gateway identity.
- [ ] Security headers present on all responses.

---

## Release Gates

Promotion from local → staging:

- CI green (lint, typecheck, tests, Docker build, secret scan).
- All `replace-me` values replaced with real secrets in Railway env.
- Neon database provisioned and migrations applied.
- Cloudflare Access policies provisioned for staging domain.

Promotion from staging → production:

- See [Deploy and Rollback](deploy-rollback.md) and [Deployment Guide](../implementation/deployment-guide.md).

---

## Rollback

- Railway: redeploy previous known-good commit or image.
- Neon: use point-in-time recovery (PITR) if available, or restore from backup.
- Cloudflare: see [CF Access Rollback](cf-access-rollback.md).
- Full procedure: [Deploy and Rollback](deploy-rollback.md).

---

## References

| What | Where |
|------|-------|
| Deployment topology | `docs/implementation/deployment-guide.md` |
| Deploy and rollback | `docs/runbooks/deploy-rollback.md` |
| Cloudflare setup | `docs/runbooks/cloudflare-production-setup.md` |
| CF Access rollback | `docs/runbooks/cf-access-rollback.md` |
| Railway API env template | `docs/runbooks/templates/railway-api.env.example` |
| Neon staging checklist | `docs/runbooks/templates/neon-staging-checklist.md` |
| Environment variable schema | `.env.example` |
