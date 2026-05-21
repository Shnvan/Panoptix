# Current Document Review Status

<!-- PE-FIX: Added current non-stale review status after council audit execution -->

The earlier `document-review-report.md` is historical. This current status records the implementation-readiness fixes applied after the council audit.

## Completed Fixes

- Critical gateway contradiction resolved with outbound WebSocket command channel plus heartbeat fallback.
- Same-domain Cloudflare/Railway routing clarified for `cctv-web` and `cctv-api`.
- Break-glass scope clarified; broad Cloudflare Access failure uses provider-console rollback.
- API contract added in `docs/implementation/api-reference.md`.
- Development setup added in `docs/implementation/development-setup.md`.
- Deployment guide added in `docs/implementation/deployment-guide.md`.
- Test plan added in `docs/implementation/test-plan.md`.
- UX/product spec added in `docs/frontend/ux-product-spec.md`.
- Team RACI added in `docs/implementation/team-raci-checklist.md`.
- Compliance readiness checklist added in `docs/privacy/compliance-readiness-checklist.md`.
- Camera procurement spec added in `docs/procurement/camera-spec.md`.
- Runbooks added in `docs/runbooks/`.
- Environment schema added in `.env.example`.
- Security, contribution, and proprietary license files added at repository root.

## Production Readiness Evidence Pass - 2026-05-19

Current evidence branch: `fullstack-integration`.

Latest verified commits:

- `545dcd3 docs: record gateway command publish smoke`
- `4050d38 fix: add gateway command queue migration`
- `83b56db docs: add frontend production integration roadmap`

Repository and quality checks:

- Working tree clean on `fullstack-integration`.
- `fullstack-integration` aligned with `origin/fullstack-integration` at `545dcd3`.
- Backend lint passed: `python -m ruff check src/ tests/`.
- Backend type check passed: `python -m mypy src/cctv_api/ --ignore-missing-imports`.
- Targeted backend tests passed: `python -m pytest tests/test_gateway_command_queue.py tests/test_livekit_tokens.py -q` -> `53 passed`.
- Frontend lint passed with one existing Fast Refresh warning in `apps/web/src/lib/theme.tsx`.
- Frontend production build passed with the existing Vite large chunk warning.
- Gitleaks passed: `108 commits scanned`, `no leaks found`.
- Tracked-file sensitive artifact scan found no tracked `.env`, `.env.example`, `CLAUDE.md`, Terraform state, tfvars, or private key/certificate files.

Database and gateway publish evidence:

- Migration `0007_gateway_command_tables` was added for `gateway_command_queue` and `camera_publish_states`.
- Operator-verified active database state showed `alembic_version: 0007_gateway_command_tables`.
- Operator-verified active database tables: `gateway_command_queue exists` and `camera_publish_states exists`.
- Direct LiveKit Cloud synthetic RTSP smoke passed with `smoke: PASSED` and `cleanup_ok: True`.
- Backend-controlled gateway command publish smoke passed after minting a fresh ingest token and command.
- Latest successful gateway command status was `accepted` with `acked_at`.
- Earlier rejected command was caused by an invalid or expired LiveKit token and was resolved by generating a fresh command payload.

Security and public-readiness notes:

- No real LiveKit credentials, generated JWTs, gateway service tokens, Railway secrets, or screenshots were added to repository files.
- Gateway publish tokens remain backend-to-gateway only and are not browser-facing.
- Branch protection and ruleset restoration remain a GitHub console check; GitHub CLI is not installed in this local environment.

Current production blockers:

- Frontend LiveKit subscriber playback still needs implementation and browser smoke testing.
- Real CCTV hardware validation is still pending; synthetic RTSP is verified.
- Production deployment remains gated by staging uptime, Cloudflare/Railway/Neon production settings, and hardware/procurement readiness.

## Backup Restore Readiness Pass - 2026-05-19

Verified implementation state:

- `BackupRun` model exists and maps to `backup_runs`.
- Initial Alembic schema creates `backup_runs` and the `backup_upload_status` enum.
- `scripts/restore-drill.sh` exists for R2-backed restore drill execution.
- `docs/runbooks/backup-restore.md` documents daily backup, weekly restore drill, emergency restore, and DR cadence.
- R2 backup bucket `panoptix-backups` and scoped R2 staging credentials are documented as provisioned in Railway secrets.
- `GET /api/v1/admin/backups/status` now reports database-known backup readiness from `backup_runs`.

Known gaps:

- Backup worker automation and direct R2 object verification remain outside the web API.
- No fresh restore drill was executed in this pass.
- No backup artifact, database dump, R2 object metadata, database URL, R2 key, or decryption key was added to the repository.

Next backup/restore task:

- Run an isolated restore drill against a disposable database and record the evidence without storing secrets or backup contents in Git.

## Production Readiness Evidence Pass - 2026-05-21

Current evidence branch: `fullstack-integration`.

Latest verified commits:

- `11734bd feat: add frontend production proxy server`
- `26815fc docs: add frontend coworker handoff`
- `63aac23 feat: add alert email pilot`

Repository and quality checks:

- Working tree clean on `fullstack-integration`.
- Backend lint passed: `python -m ruff check src/ tests/` → `All checks passed`.
- Backend type check passed: `python -m mypy src/cctv_api/ --ignore-missing-imports` → `no issues found in 48 source files`.
- Backend tests: `python -m pytest tests/ -q --tb=no` → `569 passed, 23 known local-environment failures` (the 23 failures are tests that require production guardrails to be active, i.e. `ALLOW_DEV_AUTH=false` and `APP_ENV=production`, which conflict with the local dev `.env`; they pass in CI with correct env vars).
- Frontend lint passed with one existing Fast Refresh warning in `apps/web/src/lib/theme.tsx` (0 errors).
- Frontend production build passed with the existing Vite large chunk warning: `✓ built in 7.55s`.
- Frontend security scan: no `getUserMedia`, `MediaRecorder`, `publishTrack`, `LIVEKIT_API_SECRET`, auth tokens in `localStorage`/`sessionStorage`, or RTSP URLs found in frontend source. Only safe uses found: `localStorage` for UI theme preference, `service_token` as a React display-only state variable for the one-time rotate-credential response.

New milestones completed since 2026-05-19 pass:

- Migration `0008_alerts_email` added `alerts` and `alert_notifications` tables. Local migration head is now `0008_alerts_email`.
- `GET /api/v1/admin/backups/status` implemented: DB-known backup readiness (`ok`, `degraded`, `missing`).
- `PATCH` and `/enable` lifecycle endpoints added for cameras and gateways.
- `POST /api/v1/admin/users/invite` implemented: GitHub organization invite flow.
- `GET/POST/PATCH /api/v1/admin/dsr-requests` implemented: DSR compliance workflow tracking.
- Alert pilot: alert auto-detection, lifecycle API, SMTP email foundation (backend-only, disabled by default).
- Frontend production proxy server (`apps/web/server.mjs`) added: serves Vite `dist/` and proxies `/api/v1/` and `/health` to `PANOPTIX_API_ORIGIN`.
- Frontend coworker handoff doc added: `docs/frontend/FRONTEND_HANDOFF.md`.
- Staging 7-day uptime gate cleared (started 2026-05-13, cleared 2026-05-20).

Security and public-readiness notes:

- No real credentials, generated JWTs, gateway service tokens, Railway secrets, or screenshots were added to repository files.
- Gateway publish tokens remain backend-to-gateway only and are not browser-facing.
- Branch protection and ruleset restoration remain a GitHub console check.

Current production blockers:

- Frontend LiveKit subscriber playback still needs implementation and browser smoke testing.
- Real CCTV hardware validation is still pending; synthetic RTSP is verified.
- Staging/deployed frontend browser smoke evidence is still pending (requires authenticated browser session against `staging.panoptix.site`).
- Production deployment: Neon production DB, Cloudflare Access production policies, R2 production token, and break-glass hardware key are still pending.

## Current Human Decisions

- Legal/privacy owner naming is **not a current blocker** for the prototype.
- First deployment site type is **not a current blocker** for the prototype.
- Camera/NVR SKU selection is deferred until hardware testing/procurement.
- Railway/Cloudflare/account-owner details are deferred.
- Prototype uses free tiers first wherever available.
- Team is three people: frontend coworker owns frontend, database coworker owns database, and the system owner owns backend, security, gateway, DevOps, QA, procurement, and compliance-related coordination.

## Authoritative Navigation

Use `docs/index.md` as the project documentation map.
