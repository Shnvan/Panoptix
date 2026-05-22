# Railway / Neon Production Deployment Prep

Docs-only production deployment preparation checklist for Railway (compute) and Neon (Postgres). This runbook captures the required accounts, services, environment variables, migration safety, and release gates for the production environment.

**Prerequisite:** The 7-day staging uptime gate must clear before production deploy. Started: 2026-05-13. Clears: 2026-05-20.

## Non-Goals

- This runbook does **not** create Railway services, Neon databases, or Cloudflare policies.
- It does **not** contain real secrets, account IDs, project IDs, or connection strings.
- It does **not** replace the existing [Deploy and Rollback](deploy-rollback.md) or [Cloudflare Production Setup](cloudflare-production-setup.md) runbooks.

---

## Required Accounts and Access

Before production setup begins, confirm:

- [ ] Railway team/org account created with billing enabled.
- [ ] Neon **production** project created (paid tier recommended for PITR + branch support).
- [ ] Cloudflare team configured with production Access policies ready to provision (see [Cloudflare Production Setup](cloudflare-production-setup.md)).
- [ ] GitHub repo linked to Railway for deploy-on-push or manual deploy.
- [ ] At least two team members have admin access to Railway and Neon dashboards.
- [ ] Break-glass hardware key procured and registered (see [Break-Glass Runbook](break-glass-runbook.md)).

---

## Railway Service Plan

### `cctv-api` (FastAPI backend)

| Setting | Value |
|---------|-------|
| Source | `apps/api` (Dockerfile build) |
| Start command | `uvicorn cctv_api.main:app --host 0.0.0.0 --port 8080` |
| Port | `8080` |
| Region | Choose region closest to expected users (APAC recommended) |
| Environment | `production` |
| Health check path | `/health` |
| Deploy trigger | Manual only (require explicit approval for production) |

### `cctv-web` (React + Vite frontend)

| Setting | Value |
|---------|-------|
| Source | `apps/cctv-web` |
| Start command | `npm start` |
| Port | `3000` |
| Environment | `production` |
| Deploy trigger | Manual only |

> **Note:** `cctv-web` is owned by the frontend coworker. Deploy only after frontend code review and QA sign-off.

---

## Neon Production Database

### Database and Roles

| Item | Value |
|------|-------|
| Neon project name | `panoptix-production` (or team convention) |
| Database name | `panoptix` |
| Runtime role | `cctv_app_runtime` — used by the running API for queries |
| Migration role | `cctv_migrator` — used only for schema migrations |
| Backup | Enable Neon automated daily backups + PITR |

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
- Do **not** reuse staging database credentials for production.

See also: [Neon staging checklist](templates/neon-staging-checklist.md) (adapt for production).

---

## Required Environment Variables

All production environment variables are listed in the placeholder template:

```text
docs/runbooks/templates/railway-api.env.example
```

Key groups (values must be distinct from staging):

- **Environment**: `APP_ENV=production`, `ALLOW_DEV_AUTH=0`
- **Cloudflare Access**: production issuer, audience IDs, JWKS URL, and trusted client-IP flag (distinct from staging where applicable)
- **Session/CSRF**: signing keys (distinct from staging)
- **Audit**: HMAC key and version (distinct from staging)
- **Actor IP enrichment**: Ipregistry enable flag and API key
- **Visitor collector**: disabled-by-default public entry flag, cookie key/domain, retention, and collector rate limit after the narrow `/entry` Cloudflare bypass is approved
- **Database**: production runtime and migration connection strings
- **LiveKit**: cloud URL (can be same project; API key/secret may be same or production-specific)
- **R2 Backup**: account ID (same), bucket name (`panoptix-backups`), access key/secret (production-specific recommended)
- **Gateway**: command signing key (distinct from staging)
- **Security headers**: CSP report URI, LiveKit connect-src

The backend [production auth guardrails](../runbooks/cloudflare-production-setup.md) will reject startup if any guarded value still contains `replace-me` or `example.cloudflareaccess.com`.

---

## Actor IP Enrichment Pilot

Production enablement follows a successful staging validation for the same backend contract and Ipregistry response subset.

Production rollout:

1. Create or select the production Ipregistry API key for backend-only use.
2. Set the production Railway backend variables:

```text
ACTOR_IP_ENRICHMENT_ENABLED=true
ACTOR_IP_IPREGISTRY_API_KEY=<ipregistry-api-key>
TRUST_CF_CONNECTING_IP=true
```

3. Redeploy the production backend.
4. Validate one admin user actor profile through Cloudflare Access and record the deployment date, returned `ip_details.status`, and rollback path in release notes.

Provider handling for the first rollout:

- Keep the Ipregistry API key in Railway backend variables only.
- Set `TRUST_CF_CONNECTING_IP=true` only when Cloudflare origin-binding keeps direct clients from supplying trusted-header values to the backend.
- Do not capture raw provider payloads or API keys in frontend config, screenshots, or release notes.
- Actor profile reads send only the backend-selected bounded recent-session IPs for admin investigation context.
- If a legacy `/data/maxmind` pilot volume exists from the replaced rollout path, detach/remove it after the Ipregistry rollout no longer needs a rollback comparison.

---

## Public Visitor Collector Pilot

The first collector rollout uses the existing frontend service on same-domain public path `https://panoptix.site/entry`. Keep the protected app root behind Cloudflare Access and enable the backend collector only after Cloudflare bypasses exactly `/entry`, `/api/v1/visitor/notice`, and `/api/v1/visitor/collect`. Do not bypass broad `/api/v1/*`. The entry page shows the visible notice before its explicit Continue action posts browser-side signals. Collector failure should still redirect the visitor into secure sign-in.

```text
VISITOR_COLLECTOR_ENABLED=true
VISITOR_COOKIE_SIGNING_KEY=<new-random-backend-secret>
VISITOR_COOKIE_DOMAIN=panoptix.site
VISITOR_RETENTION_DAYS=30
RATE_LIMIT_VISITOR_COLLECT_MAX=20
RATE_LIMIT_VISITOR_COLLECT_WINDOW=60
```

Apply migration `0010_visitor_visits` before enabling this flag. Use the existing Ipregistry actor-enrichment key path for stored normalized IP context; never send raw provider payloads to frontend config or rollout evidence.

---

## Production-Specific Considerations

### Rate limits and thresholds

Production should use stricter defaults than staging:

| Setting | Staging | Production | Note |
|---------|---------|------------|------|
| `RATE_LIMIT_VIEWER_TOKEN_MAX` | 30/min | 30/min | Same; user-facing |
| `RATE_LIMIT_ADMIN_MUTATION_MAX` | 10/min | 10/min | Same; admin-facing |
| `GATEWAY_STALE_THRESHOLD_SECONDS` | 60 | 60 | Same |
| `SESSION_IDLE_TIMEOUT_SECONDS` | 900 | 900 | Same |
| `SESSION_ABSOLUTE_TIMEOUT_SECONDS` | 28800 | 28800 | Same |

### Neon paid tier features

- **Point-in-time recovery (PITR)**: Enable before first production deploy.
- **Branching**: Create a `staging` branch from production for testing migrations.
- **Read replicas**: Evaluate after pilot launch if query load increases.

### R2 backup in production

- Use the same `panoptix-backups` bucket with a production-specific prefix or path.
- Create a separate R2 API token for production with Object Read & Write scope.
- Test restore drill from production backup before go-live.

### Domain and routing

- Production domain: `panoptix.site` (root) or `app.panoptix.site`
- Staging domain: `staging.panoptix.site` (already live)
- Cloudflare Access app: "Panoptix Production" (distinct from "Panoptix Staging")

---

## Migration Safety

- Database migrations must follow the expand/contract pattern.
- Never run destructive migrations (DROP COLUMN, DROP TABLE) in the same release as the code change that removes usage.
- The migration role (`cctv_migrator`) must have schema-alter privileges; the runtime role (`cctv_app_runtime`) must not.
- Test migrations locally against a disposable Postgres before applying to Neon production.
- Record migration version and hash in the deployment audit event.
- If a migration fails, do **not** retry automatically — follow the [Deploy and Rollback](deploy-rollback.md) runbook.

---

## Production Smoke Validation

After first production deploy, verify:

- [ ] `/health` returns `{ "status": "ok" }`.
- [ ] `APP_ENV` is `production` (visible in logs).
- [ ] Production auth guardrails passed (app started without `unsafe-production-config`).
- [ ] `ALLOW_DEV_AUTH` is rejected (dev auth disabled in production).
- [ ] Cloudflare Access JWT verification works for a test browser session.
- [ ] `/api/v1/me` returns valid principal for authenticated user.
- [ ] Direct Railway URL returns fail-closed for protected routes.
- [ ] Database connection works (health or `/api/v1/cameras` returns empty list, not 500).
- [ ] Security headers present on all responses.
- [ ] R2 backup connectivity verified (write a test object, verify, delete).
- [ ] Deep health returns `livekit: connected` and `db: connected`.
- [ ] After creating a fresh Cloudflare browser session with `TRUST_CF_CONNECTING_IP=true`, admin user actor profile smoke confirms a new recent session IP is not an origin/proxy hop such as `100.64.0.x` and Ipregistry-backed `ip_details.available = true`, `provider = "ipregistry"`, and `status = "ok"` after enrichment enablement.
- [ ] Break-glass window can be opened and closed by an admin.
- [ ] Audit export returns signed data.

---

## Release Gates

Promotion from staging → production (clears 2026-05-20):

- [ ] 7-day staging uptime gate cleared (staging health cron green since 2026-05-13).
- [ ] CI green (lint, typecheck, tests, Docker build, secret scan, Semgrep, Trivy, osv-scanner).
- [ ] All `replace-me` values replaced with real secrets in Railway production env.
- [ ] Neon production database provisioned and migrations applied.
- [ ] Cloudflare Access policies provisioned for production domain.
- [ ] R2 backup token configured and connectivity tested.
- [ ] Break-glass hardware key procured and tested.
- [ ] Frontend coworker QA sign-off (if applicable).
- [ ] Bus-factor recovery docs verified (see [Bus Factor Recovery](bus-factor.md)).

---

## Rollback

- Railway: redeploy previous known-good commit or image.
- Actor IP enrichment only: set `ACTOR_IP_ENRICHMENT_ENABLED=false` or remove `ACTOR_IP_IPREGISTRY_API_KEY`, redeploy `cctv-api`, and confirm user actor profiles return a degraded IP enrichment state instead of failing.
- Neon: use point-in-time recovery (PITR) if available, or restore from R2 backup.
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
| Break-glass runbook | `docs/runbooks/break-glass-runbook.md` |
| Bus factor recovery | `docs/runbooks/bus-factor.md` |
