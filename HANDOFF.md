# Panoptix Project Handoff

This handoff gives a new IDE/LLM enough project context, development rules, and navigation instructions to continue Panoptix without starting from scratch.

## First Instructions For The New IDE/LLM

Before making any changes, read this file completely, then read these files in order:

1. `PROGRESS.md`
2. `IMPLEMENTATION_GUIDE.md`
3. `MANUAL_TESTING.md`
4. `README.md`
5. `CLAUDE.md`
6. `docs/index.md`
7. `docs/implementation/api-reference.md`
8. `docs/implementation/development-setup.md`
9. `docs/implementation/test-plan.md`
10. `docs/runbooks/gateway-control-channel.md`

For frontend coordination, start with `docs/frontend/FRONTEND_HANDOFF.md`, then follow the read order in that file.

After that, inspect the source files related to the active task. Do not assume the whole repository has been loaded into context. Search and read files on demand.

## Repository

- Path: `C:\Users\Ivan\Downloads\panoptix-main\Panoptix`
- Current branch: `fullstack-integration`
- Remote: `https://github.com/Shnvan/Panoptix`
- Current development mode: combined backend/frontend integration and production-readiness hardening

Latest full-stack integration commits:

- `f2bda6a fix: harden restore drill smoke check`
- `545a9d4 feat: add encrypted R2 restore drill`
- `bbbde73 fix: configure R2 backup region`
- `cf516e1 feat: add operator R2 backup runner`
- `f5023e4 docs: fix progress summary table`

## Current Objective

Maintain the combined backend/frontend integration branch as the production-candidate review branch. The backend/control plane and edge-agent synthetic publish path are implemented; production is live at `panoptix.site` behind Cloudflare Access, with a working same-domain `/entry` visitor notice flow and expanded admin visitor detail API smoke verified. Local same-origin smoke through Vite passes for the main admin/viewer surfaces with a local FastAPI backend using ignored `apps/api/.env` configuration and dev auth. The first encrypted R2 backup artifact exists, dry-run decrypt/`pg_restore --list` validation passed, the first isolated restore drill completed successfully against a temporary Neon branch, the temporary branch was deleted, and backup status now reports `ok`. The next system-owner implementation milestone is recurring backup automation and retention rules. The remaining product gates are real LiveKit browser subscriber playback, real CCTV hardware validation, Alerts page backend API wiring, actor investigation UI, and admin visitor investigation UI.

The system is Panoptix, a secure live-view CCTV web monitoring system with three planes:

- Control plane: FastAPI backend and React/Vite frontend
- Media plane: LiveKit Cloud primary, self-hosted LiveKit fallback later
- Camera plane: on-site edge gateway/NUC, mediamtx, isolated camera network

Permanent product constraint: browsers are viewers only. No browser, phone, or laptop camera publishing.

## High-Level Architecture

### Control Plane

Location: `apps/api/`

FastAPI backend currently implements:

- app factory
- configuration loading
- health endpoints
- RFC 9457-style problem details
- local development auth
- Cloudflare Access JWT verification scaffolding
- session cookie helpers
- RBAC/policy placeholders
- gateway heartbeat endpoint
- gateway camera status endpoint
- LiveKit viewer token endpoint
- LiveKit gateway ingest token endpoint
- gateway control WebSocket skeleton
- gateway command signing helpers
- in-memory/test-scaffolded WebSocket command dispatch + ACK handling
- in-memory/test-scaffolded heartbeat command fallback
- persistent gateway command queue model with DB-backed provider and ACK sink
- command queue wired into app factory (auto-activates when DATABASE_URL is configured)
- admin command enqueue endpoint (`POST /admin/gateways/{gateway_id}/commands`)
- admin command listing endpoint (`GET /admin/gateways/{gateway_id}/commands`)
- admin command cancellation endpoint (`POST /admin/gateways/{gateway_id}/commands/{command_id}/cancel`)
- admin expired-command cleanup endpoint (`POST /admin/commands/cleanup`)
- HMAC-SHA-256 audit hash chain writer and verifier helpers
- read-only admin audit verification endpoint with optional ID ranges and key-version handling
- admin audit export endpoint returning scrubbed JSONL rows
- admin audit row listing endpoint with cursor pagination
- admin actor investigation profile endpoint (`GET /api/v1/admin/actors/{actor_type}/{actor_id}/profile`)
- admin actor investigation activity endpoint (`GET /api/v1/admin/actors/{actor_type}/{actor_id}/activity`)
- LiveKit webhook receiver with Authorization JWT validation, replay cache, audit, and camera event persistence
- room-presence-driven gateway publish command enqueue from LiveKit webhooks
- break-glass emergency access (open/close/status endpoints + request-time enforcement gate)
- admin camera search/filter (`search`, `source_type`, `gateway_id` params)
- admin gateway search (`search` param)
- admin camera list enrichment (`gateway_id`, `acl_count`)
- admin gateway list enrichment (`camera_count`)
- LiveKit fallback toggle (`POST /admin/livekit/fallback` with `SystemConfig` DB flag)
- DPA artifact export (`POST /admin/dpa/export` with kind filter)
- bystander signage attestation (`POST /admin/sites/:id/signage-attest`)
- admin-mediated MFA reset (`POST /admin/users/:id/mfa/reset` with self-reset prevention)
- GitHub organization invite flow (`POST /admin/users/invite`)
- camera and gateway update/re-enable lifecycle routes
- DSR request workflow APIs (`/api/v1/admin/dsr-requests`)
- backup status reporting from `backup_runs`

### Edge / Camera Plane

Location: `apps/cctv-edge/`

Current implemented code is in `apps/cctv-edge/agent/`:

- environment-driven agent config
- HTTP client for backend heartbeat/status calls
- one-shot and continuous heartbeat runner
- command envelope verifier
- gateway control WebSocket client skeleton
- heartbeat pending-command verifier
- command execution dispatcher for verified `start_publish` / `stop_publish`
- in-memory edge publish-state tracker
- stub media controller for safe local execution tests
- `--once` CLI for heartbeat
- `--control-once` CLI for one-shot WebSocket control check
- `--control-loop-once` CLI for bounded reconnect/backoff control check

Remaining edge/camera gaps:

- real CCTV hardware validation is still pending
- production service deployment is still pending
- mediamtx runtime generation remains future hardening

### Media Plane

Location: `apps/media-fallback/` and docs

Current state:

- LiveKit token minting exists in backend tests/source
- LiveKit Cloud account is provisioned and direct synthetic FFmpeg-to-LiveKit smoke has passed
- backend-controlled gateway command publish smoke has passed with accepted ACK
- frontend browser playback still needs real subscriber-only LiveKit integration
- fallback LiveKit app remains operational future work

### Frontend

Location: `apps/web/`

Current state:

- `origin/integratedCompleteFrontend` has been merged into `fullstack-integration`
- React/Vite frontend includes the login shell, viewer dashboard, camera modal, admin dashboard, users, cameras, gateways, audit/compliance, DSR, break-glass, health, settings, dev-auth headers, and same-origin API client
- frontend lint/build passed after merge and after local smoke cleanup
- local same-origin smoke has passed through the Vite proxy for dashboard/bootstrap, live-camera camera list, users, camera management, gateways, audit logs/verify, DSR list, break-glass status, backup status, deep health, sessions, and health
- local API configuration uses `apps/api/.env`, which is ignored by Git; do not commit database URLs, audit keys, LiveKit keys, GitHub tokens, R2 secrets, or gateway service tokens
- production backend migration state is at Alembic head `0011_visitor_expanded_signals` for expanded visitor context
- `github-invites-not-configured` is expected locally while `GITHUB_INVITES_ENABLED=false`
- one-time gateway service tokens must never be screenshotted or committed; the exposed local test gateway named `what` was disabled during smoke cleanup

## Repository

- Path: `C:\Users\Ivan\Downloads\panoptix-main\Panoptix`
- Current branch: `fullstack-integration`
- Remote: `https://github.com/Shnvan/Panoptix`
- Current development mode: combined backend/frontend integration and production-readiness hardening

Latest full-stack integration commits:

- `f2bda6a fix: harden restore drill smoke check`
- `545a9d4 feat: add encrypted R2 restore drill`
- `bbbde73 fix: configure R2 backup region`
- `cf516e1 feat: add operator R2 backup runner`
- `f5023e4 docs: fix progress summary table`

## Current Objective

Maintain the combined backend/frontend integration branch as the production-candidate review branch. The backend/control plane and edge-agent synthetic publish path are implemented; production is live at `panoptix.site` behind Cloudflare Access, with a working same-domain `/entry` visitor notice flow and expanded admin visitor detail API smoke verified. Local same-origin smoke through Vite passes for the main admin/viewer surfaces with a local FastAPI backend using ignored `apps/api/.env` configuration and dev auth. The first encrypted R2 backup artifact exists, dry-run decrypt/`pg_restore --list` validation passed, the first isolated restore drill completed successfully against a temporary Neon branch, the temporary branch was deleted, and backup status now reports `ok`. The next system-owner implementation milestone is recurring backup automation and retention rules. The remaining product gates are real LiveKit browser subscriber playback, real CCTV hardware validation, Alerts page backend API wiring, actor investigation UI, and admin visitor investigation UI.

The system is Panoptix, a secure live-view CCTV web monitoring system with three planes:

- Control plane: FastAPI backend and React/Vite frontend
- Media plane: LiveKit Cloud primary, self-hosted LiveKit fallback later
- Camera plane: on-site edge gateway/NUC, mediamtx, isolated camera network

Permanent product constraint: browsers are viewers only. No browser, phone, or laptop camera publishing.

## High-Level Architecture

### Control Plane

Location: `apps/api/`

FastAPI backend currently implements:

- app factory
- configuration loading
- health endpoints
- RFC 9457-style problem details
- local development auth
- Cloudflare Access JWT verification scaffolding
- session cookie helpers
- RBAC/policy placeholders
- gateway heartbeat endpoint
- gateway camera status endpoint
- LiveKit viewer token endpoint
- LiveKit gateway ingest token endpoint
- gateway control WebSocket skeleton
- gateway command signing helpers
- in-memory/test-scaffolded WebSocket command dispatch + ACK handling
- in-memory/test-scaffolded heartbeat command fallback
- persistent gateway command queue model with DB-backed provider and ACK sink
- command queue wired into app factory (auto-activates when DATABASE_URL is configured)
- admin command enqueue endpoint (`POST /admin/gateways/{gateway_id}/commands`)
- admin command listing endpoint (`GET /admin/gateways/{gateway_id}/commands`)
- admin command cancellation endpoint (`POST /admin/gateways/{gateway_id}/commands/{command_id}/cancel`)
- admin expired-command cleanup endpoint (`POST /admin/commands/cleanup`)
- HMAC-SHA-256 audit hash chain writer and verifier helpers
- read-only admin audit verification endpoint with optional ID ranges and key-version handling
- admin audit export endpoint returning scrubbed JSONL rows
- admin audit row listing endpoint with cursor pagination
- admin actor investigation profile endpoint (`GET /api/v1/admin/actors/{actor_type}/{actor_id}/profile`)
- admin actor investigation activity endpoint (`GET /api/v1/admin/actors/{actor_type}/{actor_id}/activity`)
- LiveKit webhook receiver with Authorization JWT validation, replay cache, audit, and camera event persistence
- room-presence-driven gateway publish command enqueue from LiveKit webhooks
- break-glass emergency access (open/close/status endpoints + request-time enforcement gate)
- admin camera search/filter (`search`, `source_type`, `gateway_id` params)
- admin gateway search (`search` param)
- admin camera list enrichment (`gateway_id`, `acl_count`)
- admin gateway list enrichment (`camera_count`)
- LiveKit fallback toggle (`POST /admin/livekit/fallback` with `SystemConfig` DB flag)
- DPA artifact export (`POST /admin/dpa/export` with kind filter)
- bystander signage attestation (`POST /admin/sites/:id/signage-attest`)
- admin-mediated MFA reset (`POST /admin/users/:id/mfa/reset` with self-reset prevention)
- GitHub organization invite flow (`POST /admin/users/invite`)
- camera and gateway update/re-enable lifecycle routes
- DSR request workflow APIs (`/api/v1/admin/dsr-requests`)
- backup status reporting from `backup_runs`

### Edge / Camera Plane

Location: `apps/cctv-edge/`

Current implemented code is in `apps/cctv-edge/agent/`:

- environment-driven agent config
- HTTP client for backend heartbeat/status calls
- one-shot and continuous heartbeat runner
- command envelope verifier
- gateway control WebSocket client skeleton
- heartbeat pending-command verifier
- command execution dispatcher for verified `start_publish` / `stop_publish`
- in-memory edge publish-state tracker
- stub media controller for safe local execution tests
- `--once` CLI for heartbeat
- `--control-once` CLI for one-shot WebSocket control check
- `--control-loop-once` CLI for bounded reconnect/backoff control check

Remaining edge/camera gaps:

- real CCTV hardware validation is still pending
- production service deployment is still pending
- mediamtx runtime generation remains future hardening
- gateway local network discovery is planned core pilot scope only; no scanner/API/UI exists yet, and any future implementation must run only on the on-site gateway against approved camera VLAN/subnet ranges

### Media Plane

Location: `apps/media-fallback/` and docs

Current state:

- LiveKit token minting exists in backend tests/source
- LiveKit Cloud account is provisioned and direct synthetic FFmpeg-to-LiveKit smoke has passed
- backend-controlled gateway command publish smoke has passed with accepted ACK
- frontend browser playback still needs real subscriber-only LiveKit integration
- fallback LiveKit app remains operational future work

### Frontend

Location: `apps/web/`

Current state:

- `origin/integratedCompleteFrontend` has been merged into `fullstack-integration`
- React/Vite frontend includes the login shell, viewer dashboard, camera modal, admin dashboard, users, cameras, gateways, audit/compliance, DSR, break-glass, health, settings, dev-auth headers, and same-origin API client
- frontend lint/build passed after merge and after local smoke cleanup
- local same-origin smoke has passed through the Vite proxy for dashboard/bootstrap, live-camera camera list, users, camera management, gateways, audit logs/verify, DSR list, break-glass status, backup status, deep health, sessions, and health
- local API configuration uses `apps/api/.env`, which is ignored by Git; do not commit database URLs, audit keys, LiveKit keys, GitHub tokens, R2 secrets, or gateway service tokens
- production backend migration state is at Alembic head `0011_visitor_expanded_signals` for expanded visitor context
- `github-invites-not-configured` is expected locally while `GITHUB_INVITES_ENABLED=false`
- one-time gateway service tokens must never be screenshotted or committed; the exposed local test gateway named `what` was disabled during smoke cleanup
- camera modal can request a short-lived viewer token, but real LiveKit subscriber playback is still pending
- do not add backend/security logic here; browsers remain viewers only

### Database

Location: `database/`, `apps/api/alembic/`, `apps/api/src/cctv_api/models/`
Current state:

- Alembic migrations exist
- SQLAlchemy models exist
- command queue model and migration exist (`GatewayCommandQueue`, `0007_gateway_command_tables`)
- camera publish-state model and migration exist (`CameraPublishState`, `0007_gateway_command_tables`)
- alert and alert notification models and migration exist (`Alert`, `AlertNotification`, `0008_alerts_email`)
- suspicious login detection model and migration exist (`LoginBaseline`, `0009_login_baselines`) — applied on staging and production Neon branches (2026-05-22)
- DB coworker ownership is documented, but backend tests use database helpers where needed

## Recently Completed Milestones

### Production Go-Live (2026-05-22)

Completed in this milestone:

- **Cloudflare Access**: Created "Panoptix Production" app for `panoptix.site` with GitHub org (`panoptix-site`) policy. AUD tag configured in Railway.
- **Railway production variables**: New `SESSION_SIGNING_KEY`, `CSRF_SIGNING_KEY`, `AUDIT_HMAC_KEY` (version 2), `GATEWAY_COMMAND_SIGNING_KEY`. `APP_ENV=production`, `ALLOW_DEV_AUTH=false`, `APP_PUBLIC_BASE_URL=https://panoptix.site`.
- **Production Neon branch**: `0009_login_baselines` migration applied — production DB at head.
- **DNS**: Promoted `staging.panoptix.site` → `panoptix.site` as frontend custom domain.
- **Admin seeding**: `ivanlia041@gmail.com` assigned `admin` role. Coworker accounts seeded via Users & Access dashboard.
- **AUDIT_HMAC_KEY_VERSION=2**: Fixed unique constraint conflict where production DB already had version 1 key from staging data.
- **Suspicious login detection**: `SUSPICIOUS_LOGIN_DETECTION_ENABLED=true` set in production Railway variables.
- **Smoke test passed**: Database CONNECTED, LiveKit CONNECTED, Audit Logs 50 events with valid HMAC chain, Administrator role confirmed at `panoptix.site`.

### Public Visitor Entry and Collector Rollout (2026-05-23)

Completed in this milestone:

- **Same-domain entry**: `https://panoptix.site/entry` is operational on the existing frontend service.
- **First-visit redirect**: Cloudflare redirects `https://panoptix.site/` to `/entry` only when the signed `panoptix_visitor` cookie is absent. Returning visitors go directly to the protected app/Access flow.
- **Public bypass scope**: Only `/entry`, `/assets/*`, `/logo.png`, `/api/v1/visitor/notice`, and `/api/v1/visitor/collect` bypass Cloudflare Access.
- **Protected scope**: `/`, `/api/v1/me`, `/api/v1/admin/*`, `/api/v1/cameras/*`, and `/api/v1/sessions/*` remain protected. Never make broad `/api/v1/*` public.
- **Backend collector**: Visitor notice/collect APIs, `0010_visitor_visits`, `0011_visitor_expanded_signals`, signed visitor cookie correlation, admin visitor visit list/detail APIs, and maintenance retention cleanup are implemented.
- **Expanded signal boundary**: `/entry` collection starts only after explicit Continue and stores approved browser/network/WebRTC summary signals. Raw WebRTC SDP/candidate strings, raw Ipregistry payloads, reverse geocoding, coordinates, canvas/audio/WebGL/font fingerprints, and broad fingerprint dumps remain out of scope.
- **Frontend handoff**: Admin visitor investigation UI is still coworker-owned frontend work; backend responses now expose `ip_details`, `browser_context`, `network_context`, `webrtc_details`, `timing`, `server_context`, `risk_context`, and login correlation fields for that future UI.
- **Production smoke**: Admin visitor list/detail API smoke passed on 2026-05-24 with expanded sections present.

### Frontend Capability Documentation Refresh (2026-05-24)

Completed in this milestone:

- Updated `docs/frontend/*` as the current backend-to-frontend handoff source of truth.
- Documented backend-ready but frontend-missing UI work: Alerts API wiring, actor profile/activity UI, admin visitor investigation UI, LiveKit subscriber playback, and full audit filters.
- Documented frontend references to unavailable backend routes: `GET /api/v1/admin/sites` and planned security-check endpoints.
- Documented backend/gateway-only routes that must stay out of browser code: gateway heartbeat, ingest-token, camera status, gateway control WebSocket, LiveKit webhook, and gateway service-token use beyond one-time admin display.
- Documented disabled-user behavior for UI handling: disabled users receive `403 user-disabled`, and invites for existing disabled users receive `409 user-disabled`.

### Suspicious Login Detection (2026-05-21)

Completed in this milestone:

- `apps/api/src/cctv_api/models/tables.py`: Added `LoginBaseline` model for per-user IP/country/UA fingerprint baselines.
- `apps/api/src/cctv_api/core/config.py`: Added `SUSPICIOUS_LOGIN_DETECTION_ENABLED`, `LOGIN_BASELINE_MIN_LOGINS`, `LOGIN_BASELINE_SUSPICION_THRESHOLD_DAYS` settings.
- `apps/api/alembic/versions/0009_login_baselines.py`: Migration adding `login_baselines` table.
- `apps/api/src/cctv_api/security/suspicious_login.py`: Detection engine with IP/country/UA fingerprinting and alert integration.
- `apps/api/src/cctv_api/security/dependencies.py`: Hooked `check_login_suspicion` into session creation (never blocks auth on detection failure).
- `apps/api/tests/test_suspicious_login.py`: 25 unit tests — all passing.
- Applied `0009_login_baselines` on staging and production Neon branches.

### Alert System & Email Notification Pilot (2026-05-21)

Completed in this milestone:

- `apps/api/src/cctv_api/api/router.py`: added endpoints for alert list, details, acknowledge, and resolve.
- `apps/api/src/cctv_api/security/alerts.py`: business logic for alert detection, deduplication, and lifecycle transitions.
- `apps/api/src/cctv_api/integrations/email_alerts.py`: SMTP-based email alert notification sender helper.
- Applied migration `0008_alerts_email` on the active local database, adding `alerts` and `alert_notifications` tables. Apply separately in staging/production before deployed alert testing.
- Auto-triggered alerts for critical security and operational events (break-glass open, tampered audit check, admin role grant, gateway disable, rejected commands, and degraded backups).
- Redact-safe secrets validation ensuring no sensitive settings leak.
- Added focused alert API, detection, and email-notification tests.
- Added DSR request workflow endpoints (`GET/POST/PATCH /api/v1/admin/dsr-requests`) to track compliance cases.
- Supports status transitions, requester contact, subject/request type, site/artifact links, camera scope notes, due/verified dates, and outcome tracking.
- Audit logged DSR events (`admin.dsr.created`, `admin.dsr.viewed`, `admin.dsr.updated`).
- Added comprehensive unit tests in `apps/api/tests/test_dsr_requests.py`.

### GitHub Organization Invite Flow (2026-05-20)

Completed in this milestone:

- Implemented GitHub API integration in `github_invites.py` for inviting users to the organization (`POST /api/v1/admin/users/invite`).
- Added config toggles and invite failure handles (`github-invites-not-configured`).
- Audit logged the invite transactions and added unit tests in `test_stub_endpoints.py`.

### Camera and Gateway Lifecycle Endpoints (2026-05-19)

Completed in this milestone:

- Added `PATCH` endpoints for metadata modifications and `POST /enable` endpoints to support re-enabling previously disabled gateways and cameras.
- Ensured state transitions correctly update supported metadata fields and audit logged modifications.
- Handled viewer/publisher participant cleanup on gateway/camera disablement.

### Backup Status Reporting (2026-05-19)

Completed in this milestone:

- Implemented `GET /api/v1/admin/backups/status` returning JSON containing `status` (`ok`, `degraded`, `missing`) and latest backup age.
- Reads backup run history from database without exposing object paths or credentials.
- Added unit tests in `tests/test_backup_status.py` verifying status transitions.

Production evidence as of 2026-05-25:

- Production R2 env-var presence was confirmed without recording values.
- Direct R2 bucket listing succeeded using production Railway credentials without exposing object keys.
- Operator-run backup job is implemented as `python -m cctv_api.jobs.backup_r2`; it creates a `pg_dump` custom archive, validates it with `pg_restore --list`, encrypts with `age`, uploads to R2, and records `backup_runs`.
- The production R2 bucket contains one encrypted `.dump.age` backup artifact; object keys are intentionally not recorded in docs or screenshots.
- Production `backup_runs` contains four evidence rows: two earlier diagnostic failures, one successful uploaded/finished backup row, and one isolated restore-drill row.
- Latest successful `backup_run_id`: `78901812-df12-4a32-b91f-9975772fdca2`; `restore_format_ok=true`; `size_bytes=119112`; `sha256=98ad13944da3705b79b51ce35db30e5f7524daa8577a2387553bf2a760fd3336`.
- Isolated restore drill completed against a temporary Neon branch on 2026-05-25; restore evidence row `564e2bfd-b449-4c9f-b46d-a0366856a7e0` has `restore_schema_ok=true`.
- The temporary Neon restore branch was deleted after validation.
- Backup status returned `ok` after restore-drill evidence was recorded.
- Restore-drill tooling supports the real encrypted `.dump.age` format through `python -m cctv_api.jobs.restore_drill_r2` and `scripts/restore-drill.sh`: latest R2 object selection, local temp download, `age` decrypt, `pg_restore --list`, optional isolated target restore, and evidence-row recording.
- Dry-run restore validation passed: the encrypted production artifact decrypted locally and `pg_restore --list` succeeded.
- Next system-owner backup task is recurring backup automation and retention rules. Never restore into production Neon.

### Actor Investigation Profile and Activity API (2026-05-14)

Completed in this milestone:

- `apps/api/src/cctv_api/api/actor_profile.py`: new admin-only actor investigation router.
- `apps/api/src/cctv_api/security/actor_investigation.py`: service layer aggregating identity, roles, sessions, camera access, stream grants, audit activity summaries, risk indicators, containment status, direct actor-linked alert summaries, and safe user login-baseline summaries.
- `GET /api/v1/admin/actors/{actor_type}/{actor_id}/profile`: composite actor profile for `user`, `gateway`, `system`, `break_glass`, and `service_token_monitor` actors.
- `GET /api/v1/admin/actors/{actor_type}/{actor_id}/activity`: actor-scoped audit timeline with cursor pagination and filters for action, severity, category, outcome, resource, session, and timestamp range.
- System-like actors accept the literal path segment `none` for null `actor_id`.
- Profile and activity views write audit-of-audit events: `admin.actor.profile.viewed` and `admin.actor.activity.viewed`.
- `apps/api/tests/test_actor_profile.py`: 21 tests covering auth/RBAC, validation, user/gateway/system/break-glass profiles, direct actor-linked alert isolation, safe login-baseline summaries, activity pagination/filtering, stream-grant actor isolation, and audit-of-view rows.

Verification:

```text
backend pytest: 606 passed
ruff: all checks passed
mypy: no issues found in 44 source files
```

---

### Rounds 1–4: Security Hardening, CI/CD, Infrastructure & Docs (2026-05-13)

Completed in this batch:

**Round 1 — Rate limiting + edge backoff + CI hardening:**

- `config.py`: Added `RATE_LIMIT_ADMIN_MUTATION_MAX=10` and `RATE_LIMIT_ADMIN_MUTATION_WINDOW=60`
- `api/router.py`: Sliding-window rate limiting on admin mutations (`rotate-credential`, `user-role`, `break-glass-open`, `enqueue-commands`) — returns 429 + Retry-After; key format `admin-mutation:{actor_id}`
- `tests/test_rate_limit_admin.py`: 6 new tests for admin rate limiting
- `control.py`: Exponential backoff + jitter for WebSocket reconnect (`base * 2^attempt + jitter`)
- `tests/test_control.py`: 3 new backoff tests (27 total)
- `.github/workflows/ci.yml`: Pinned action versions and added edge-agent CI job (ruff, mypy, pytest, compileall, osv-scanner)
- `.github/dependabot.yml`: Added pip scope for `apps/cctv-edge/agent`

**Round 2 — Threat models + runbooks:**

- `docs/security/mediamtx-threat-model.md`: New mediamtx threat model (6 threats)
- `scripts/check_mediamtx_config.py`: CI script to validate mediamtx YAML configs
- `docs/runbooks/uptime-monitoring.md`: New runbook for staging monitoring alert response
- `docs/runbooks/backup-restore.md`: DR testing schedule section appended
- `docs/runbooks/cloudflare-production-setup.md`: WARP device posture checklist appended
- `infra/terraform/STATE_SECURITY.md`: New doc on Terraform state security requirements

**Round 3 — Infrastructure + mTLS scaffold:**

- `infra/terraform/modules/backup-r2/`: New Terraform module for Cloudflare R2 backup bucket (main.tf, variables.tf, outputs.tf)
- `scripts/restore-drill.sh`: New DR restore drill automation script
- `scripts/ct-log-check.sh`: New CT-log monitoring script
- `apps/cctv-edge/agent/src/panoptix_edge_agent/mtls_bootstrap.py`: New mTLS cert bootstrap scaffold
- `apps/cctv-edge/agent/pyproject.toml`: Added `cryptography>=42.0` dependency

**Round 4 — Staging deploy + Dependabot automation:**

- `.github/workflows/deploy-staging.yml`: New staging auto-deploy workflow with post-push health checks
- `.github/workflows/dependabot-auto-merge.yml`: New Dependabot auto-merge workflow (minor/patch auto, major requires manual approval)

Verification after Rounds 1–4:

```text
backend pytest: 466 passed (was 460; +6 admin rate-limit tests)
edge agent pytest: 245 passed (was 242; +3 backoff tests)
ruff: all checks passed
mypy: no issues found
```

---

### CI Pipeline Finalization, External Service Provisioning & Security Tooling (2026-05-13)

Completed in this session.

**CI pipeline hardening (runs #4–#10):**

- `.github/workflows/ci.yml`: Migrated osv-scanner from v1 to v2.3.8 (`--recursive` instead of `--lockfile`); removed nonexistent `--skip-git` flag
- `.github/workflows/ci.yml`: Updated trivy-action from 0.28.0 to v0.36.0; added `ignore-unfixed: true` and `trivyignores: apps/api/.trivyignore` for Debian 12 CVEs with no available patch
- `.github/workflows/ci.yml`: Updated semgrep-action from `returntocorp` to `semgrep` org
- `.github/workflows/ci.yml` + `deploy-staging.yml` + `deploy-production.yml`: Fixed Semgrep shell injection findings — moved all `${{ github.* }}` expressions from `run:` blocks to `env:` intermediary variables
- `apps/api/Dockerfile`: Upgraded base image to `python:3.12-slim-bookworm` + `apt-get upgrade` to reduce OS-level CVEs
- `apps/api/.trivyignore`: Created with 13 Debian 12 CVE IDs (zlib1g, libcap2, libsystemd0, ncurses, libgcrypt20, libc-bin/libc6, libgnutls30 x5, libsqlite3-0)
- `.semgrepignore`: Created to suppress urllib false positive in `apps/cctv-edge/agent/src/panoptix_edge_agent/client.py`
- `deploy-staging.yml`: Changed post-deploy health check from hard-fail to informational (Cloudflare Access returns 302 for unauthenticated probes)

**External service provisioning:**

- LiveKit Cloud account created at livekit.io (APAC region)
- Project `panoptix` provisioned with WebSocket URL, API key, API secret, and webhook secret
- All 4 LiveKit values set as Railway staging env vars (`LIVEKIT_CLOUD_URL`, `LIVEKIT_CLOUD_API_KEY`, `LIVEKIT_CLOUD_API_SECRET`, `LIVEKIT_WEBHOOK_SECRET`)
- Semgrep CI token (`SEMGREP_APP_TOKEN`) configured as GitHub repository secret
- Cloudflare R2 backup bucket `panoptix-backups` provisioned via Terraform Cloud workspace `panoptix-backup-r2`
- Terraform Cloud backend added to `infra/terraform/modules/backup-r2/main.tf`
- R2 scoped API token created (Object Read & Write, `panoptix-backups` bucket only)
- R2 env vars set in Railway staging (`R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`)
- Staging health verified: `https://staging.panoptix.site/health` returns `{"status":"ok"}` behind Cloudflare Access

Verification:

```text
CI run #10: ALL 8 JOBS GREEN
- Lint & Test
- Secret Scan
- Semgrep SAST
- Dependency Vulnerability Scan
- Edge Agent Lint & Test
- Docker Build Check
- Container Image Scan
- Deploy-Staging
```

Not included:

- Gitleaks license (optional; public repo gets free license, but CI passes without it)
- Production Cloudflare Access apps (waits for 7-day gate)
- Production Railway/Neon environments (waits for 7-day gate)
- Break-glass hardware key procurement

---

### LiveKit Fallback, DPA Export, Signage Attestation & Bus-Factor Doc

Completed in this milestone.

Implemented:

- `POST /api/v1/admin/livekit/fallback` — flips `system_config.media_plane_mode` between `cloud` and `fallback`; audit-logged
- `security/media_plane.py` helper module with `get_media_plane_mode`, `set_media_plane_mode`
- `POST /api/v1/admin/dpa/export` — returns DPA artifact bundle with optional `kinds` filter; audit-logged
- `POST /api/v1/admin/sites/{site_id}/signage-attest` — records bystander signage attestation as `DpaArtifact`; audit-logged
- `docs/runbooks/bus-factor.md` — emergency recovery runbook for sole-operator unavailability
- `POST /api/v1/admin/users/{user_id}/mfa/reset` — admin-mediated MFA reset with self-reset prevention; audit-logged
- 21 new tests (`test_livekit_fallback.py` + `test_dpa.py` + `test_mfa_reset.py`)
- All 454 backend tests passing; ruff, mypy clean

Not included:

- Dynamic CSP middleware reading `media_plane_mode` (frontend/middleware work)
- Automated failover (deferred to pilot+ per ADR 0004)
- R2 upload for DPA artifacts (requires Cloudflare R2 provisioning)

Verification:

- `python -m pytest tests/ -v`: 454 passed
- `python -m ruff check src/ tests/`: all checks passed
- `python -m mypy src/cctv_api/ --ignore-missing-imports`: no issues found

### Operational Runbooks, SCA/SAST CI, Search/Filter & Enrichment

Completed in this milestone.

Implemented:

- 3 operational runbooks: `break-glass-runbook.md`, `lost-mfa-recovery.md`, `idp-outage-recovery.md`
- SCA/SAST CI: Semgrep SAST, osv-scanner dependency scan, Trivy container image scan added to GitHub Actions
- Admin gateway list: `search` (name substring) param + `camera_count` enrichment
- Admin camera list: `search` (display_name), `source_type` (validated enum), `gateway_id` filter params + `gateway_id`, `acl_count` enrichment
- 12 new tests in `test_admin_search_enrichment.py`
- All 428 backend tests passing; ruff, mypy clean

Not included:

- Full-text search (deferred — substring ilike is sufficient for current scale)
- Sorting params (deferred — default `created_at DESC` is sufficient)

Verification:

- `python -m pytest tests/ -v`: 428 passed
- `python -m ruff check src/ tests/`: all checks passed
- `python -m mypy src/cctv_api/ --ignore-missing-imports`: no issues found

### Break-Glass Emergency Access

Completed in this milestone.

Implemented:

- `POST /api/v1/admin/break-glass/open` — opens a 90-minute emergency admin window; rejects if active window already exists (409)
- `POST /api/v1/admin/break-glass/close` — closes an active or expired-but-unclosed window; returns mandatory rotation checklist
- `GET /api/v1/admin/internal/break-glass-status` — unauthenticated external-monitor endpoint; returns `{"active": false}` or `{"active": true, "auto_disable_at": "..."}`
- `security/break_glass.py` helper module: `open_break_glass_window`, `close_break_glass_window`, `get_break_glass_status`, `assert_break_glass_active`, `get_active_window`
- Request-time enforcement per ADR 0005 — no scheduler, no cron; `now >= auto_disable_at` is the authoritative gate
- Audit events: `system.break_glass.opened` and `system.break_glass.closed` (fail-closed via `_record_user_audit_required`)
- T-52 simulated clock advance test: access denied after 91 minutes
- 12 new tests in `test_break_glass.py`
- All 416 backend tests passing; ruff, mypy clean

Not included:

- CF Access App C (Cloudflare infra config, not application code)
- Post-close rotation automation (operational runbook, not automated)
- Rate limiting on break-glass open (deferred to rate-limit milestone)

Verification:

- `python -m pytest tests/ -v`: 416 passed
- `python -m ruff check src/ tests/`: all checks passed
- `python -m mypy src/cctv_api/ --ignore-missing-imports`: no issues found

### Admin Health Probes

Completed in this milestone.

Implemented:

- `GET /api/v1/admin/health/deep` now returns real LiveKit connectivity and gateway heartbeat-age status instead of hardcoded `"not_connected"`
- `_probe_livekit(settings)` calls `POST /twirp/livekit.RoomService/ListRooms` with 5s timeout; returns `connected`, `not_configured` (placeholder creds), or `error`
- `_probe_gateways(db, settings)` queries enabled gateways and checks `last_seen_at` against `GATEWAY_STALE_THRESHOLD_SECONDS` (default 60s, 6× heartbeat interval)
- Gateway probe returns `connected` (recent heartbeat), `no_gateways` (none enabled), `stale` (all old/null `last_seen_at`), or `error`
- Overall status: `"ok"` only when DB connected AND (LiveKit connected/not_configured) AND (gateway connected/no_gateways); otherwise `"degraded"`
- Added `GATEWAY_STALE_THRESHOLD_SECONDS` to `Settings` with `Field(default=60, ge=10)`
- Fixed gap: gateway heartbeat endpoint now updates `EdgeGateway.last_seen_at` via `_update_gateway_last_seen()` (fail-open)
- Fixed SQLite/PostgreSQL datetime comparison: `_as_naive_utc()` normalizes timezone-aware/naive datetimes for cross-DB compatibility
- 8 new health tests in `test_health.py` + 1 new gateway test in `test_gateway.py`
- All 404 backend tests passing; ruff, mypy clean

Not included:

- Auth requirement for deep health (monitoring systems need unauthenticated access)
- Gateway mTLS certificate expiry checks
- Historical health status tracking

Verification:

- `python -m pytest tests/ -v`: 404 passed
- `python -m ruff check src/ tests/`: all checks passed
- `python -m mypy src/cctv_api/ --ignore-missing-imports`: no issues found

### Admin Dashboard Summary Endpoint

Completed in this milestone.

Implemented:

- `GET /api/v1/admin/dashboard` returns aggregated system counts in a single admin call
- Response shape: `{ "cameras": { "total", "active", "retired" }, "gateways": { "total", "enabled", "disabled" }, "users": { "total", "active", "disabled" }, "commands": { "pending" }, "publishing": { "active" } }`
- Admin-role enforcement via `require_role(principal, "admin")`
- Uses `select(func.count()).select_from(Model).where(...)` for efficient DB aggregation
- Added `CameraPublishState` and `CameraPublishStatus` imports to router
- 6 new tests in `test_admin_dashboard.py` covering auth, empty counts, cameras, gateways, users, and commands/publishing
- All 395 backend tests passing; ruff, mypy clean

Not included:

- Historical trend data or time-series counts
- Real-time streaming dashboard updates
- Per-gateway or per-camera breakdown endpoints

Verification:

- `python -m pytest tests/ -v`: 395 passed
- `python -m ruff check src/ tests/`: all checks passed
- `python -m mypy src/cctv_api/ --ignore-missing-imports`: no issues found

### Admin Camera & Gateway Listing Endpoints

Completed in previous milestone.

Implemented:

- `GET /api/v1/admin/gateways` — list all gateways (enabled + disabled) with cursor pagination, optional `status` filter (validated against `GatewayStatus` enum)
- `GET /api/v1/admin/gateways/{gateway_id}` — gateway detail with `camera_count` from active `GatewayCameraAssignment` rows, plus `mtls_fingerprint` and `cert_expires_at`
- `GET /api/v1/admin/cameras` — list all cameras with cursor pagination, optional `include_retired` filter (default excludes retired)
- `GET /api/v1/admin/cameras/{camera_id}` — camera detail with `acl_count` from active `CameraAcl` rows, plus `room_uuid`, `gateway_id`, `site_id`
- All four endpoints require admin role and use cursor-based pagination on `created_at DESC, id DESC`
- Sensitive fields (`service_token_hash`) excluded from gateway responses
- 8 new gateway list+detail tests in `test_admin_gateways.py`
- 8 new camera list+detail tests in `test_cameras.py`
- All 389 backend tests passing; ruff, mypy clean

Not included:

- admin camera/gateway search or full-text filtering
- admin camera/gateway update/rename endpoints
- bulk operations

Verification:

- `python -m pytest tests/ -v`: 389 passed
- `python -m ruff check src/ tests/`: all checks passed
- `python -m mypy src/cctv_api/ --ignore-missing-imports`: no issues found

### Camera Disable → Kill Viewer Participants

Completed in this milestone.

Implemented:

- `remove_room_viewers()` added to `security/livekit_rooms.py` — removes all `viewer:*` participants from a camera's single LiveKit room when it is retired
- Unlike user/gateway removal (which filter by entity prefix across multiple rooms), this removes all viewers from one room
- Same fail-open pattern: errors collected, never raised; placeholder credential skip
- `DisableCameraResponse` Pydantic model with `participants_removed` and `participant_errors` fields
- `disable_camera()` handler calls `remove_room_viewers()` with `camera.livekit_room_name`
- Audit event `camera.disable` payload includes `participants_removed` and `participant_errors`
- 7 new unit tests in `test_livekit_rooms.py`, 3 new integration tests + 1 updated test in `test_cameras.py`
- All 373 backend tests passing; ruff, mypy clean

Not included:

- camera re-enable/un-retire flow
- bulk camera disable

Verification:

- `python -m pytest tests/ -v`: 373 passed
- `python -m ruff check src/ tests/`: all checks passed
- `python -m mypy src/cctv_api/ --ignore-missing-imports`: no issues found

### Gateway Disable → Kill Publisher Participants

Completed in previous milestone.

Implemented:

- `remove_gateway_participants()` added to `security/livekit_rooms.py` — mirrors `remove_user_participants()` for gateway publisher identity prefix `gateway:{gateway_id}:`
- Same fail-open pattern: errors collected, never raised; placeholder credential skip
- `DisableGatewayResponse` Pydantic model with `participants_removed` and `participant_errors` fields
- `disable_gateway()` handler queries assigned camera rooms via `GatewayCameraAssignment` join and calls `remove_gateway_participants()`
- Audit event `gateway.disable` payload includes `participants_removed` and `participant_errors`
- 7 new unit tests in `test_livekit_rooms.py`, 3 new integration tests + 1 updated test in `test_admin_gateways.py`
- All 363 backend tests passing; ruff, mypy clean

Not included:

- gateway re-enable flow
- bulk gateway disable
- WebSocket connection termination on disable (only LiveKit participants removed)

Verification:

- `python -m pytest tests/ -v`: 363 passed
- `python -m ruff check src/ tests/`: all checks passed
- `python -m mypy src/cctv_api/ --ignore-missing-imports`: no issues found

### Per-Camera RTSP Credential Handling

Completed in previous milestone.

Implemented:

- `camera_credentials.py` with `CameraCredential`, `CameraCredentialStore`, `load_camera_credentials()`, `build_rtsp_url()`, `build_authenticated_rtsp_url()`, `check_credential_file_permissions()`, and `CredentialFileError`
- `PANOPTIX_CAMERA_CREDENTIALS_PATH` env var in `AgentConfig` (empty = backward compatible)
- `MediaController` protocol extended with optional `source_url`, `rtsp_username`, `rtsp_password`, `rtsp_transport` params
- `CommandExecutor` resolves per-camera credential store before calling media controller; missing camera rejects with `camera-credentials-not-found`
- `FfmpegRtspFrameSourceConfig` composes authenticated URL only in `args()` subprocess boundary
- Credentials wired through `LiveKitPublishRequest`, `LiveKitMediaController`, and `FfmpegVideoTrackMediaSessionFactory`
- CLI loads and validates credential file at startup (fail-closed)
- `__repr__` redacts passwords in `CameraCredential`, `FfmpegRtspFrameSourceConfig`, and `LiveKitPublishRequest`
- File permission check (0600 on Linux, skip on Windows)
- `cameras.json.example` template, `gateway.env.example` updated, agent README updated
- 28 new tests in `test_camera_credentials.py`, 3 new tests in `test_executor.py`
- All 239 edge-agent tests passing; ruff, mypy, and compileall clean

Not included:

- real camera onboarding
- credential rotation tooling
- encrypted credential file at rest

Verification:

- `python -m pytest tests/ -v`: 239 passed, 2 skipped
- `python -m ruff check src tests`: all checks passed
- `python -m mypy src/panoptix_edge_agent --ignore-missing-imports`: no issues found in 22 source files
- `python -m compileall src tests`: passed

### Production Gateway Supervision

Completed in this milestone.

Implemented:

- Added edge-agent `--supervise` CLI mode
- Added `GatewayRuntimeSupervisor` for a long-running gateway runtime loop
- Supervisor coordinates heartbeat fallback, outbound gateway-control supervision, optional local `mediamtx` process startup, and cleanup on shutdown
- Added config toggles for `PANOPTIX_SUPERVISE_MEDIAMTX`, `PANOPTIX_MEDIAMTX_BINARY`, and `PANOPTIX_MEDIAMTX_CONFIG_PATH`
- Preserved default `PANOPTIX_MEDIA_PUBLISHER_MODE=stub`; real FFmpeg/LiveKit publishing remains opt-in
- Added fake-based tests for supervisor success/failure paths, mediamtx start/stop cleanup, config parsing, and CLI dispatch
- Updated `.env.example`, manual testing docs, edge README, and mediamtx README with safe local-only usage

Verification:

- `python -m pytest tests/ -v`: 210 passed
- `python -m ruff check src tests`: all checks passed
- `python -m mypy src/panoptix_edge_agent --ignore-missing-imports`: no issues found in 21 source files
- `python -m compileall src tests`: passed

Not included:

- Installing systemd units, Windows services, or Docker production deployment
- Exposing RTSP, HLS, WebRTC, RTMP, mediamtx API, or backend ports to WAN
- Making real media publishing the default
- Storing LiveKit API credentials or RTSP camera credentials in committed files

### Real LiveKit Cloud Smoke Execution

Completed in this milestone.

Result:

- Ran `python -m panoptix_edge_agent.cli --smoke-ffmpeg-livekit` against LiveKit Cloud
- LiveKit host only: `panoptix-4feff0dr.livekit.cloud`
- Room: `panoptix-smoke-test`
- RTSP source: `rtsp://127.0.0.1:8554/synthetic-camera-1`
- Camera ID: `synthetic-smoke-camera`
- Requested duration: 10s
- Result: `smoke: PASSED`, `frames_published: 1`, `duration: 38.84s`, `cleanup_ok: True`
- Transient LiveKit signal retry/timeout logs occurred, but final result passed and cleanup succeeded
- LiveKit Cloud smoke secrets were cleared from the shell after the run

Not included:

- API key, API secret, generated JWT, or credential material in committed files
- Production deployment readiness
- Making FFmpeg-backed publishing the default edge-agent runtime path

### Backend-Controlled Gateway Publish Smoke

Completed in this milestone.

Result:

- Added Alembic migration `0007_gateway_command_tables` for `gateway_command_queue` and `camera_publish_states`
- Applied the migration on the active database and verified both tables exist
- Ran backend-controlled synthetic RTSP publish through the real control flow:
  - admin registered gateway and camera
  - gateway-camera assignment was active
  - gateway ingest token was minted by the backend
  - admin enqueued `gateway.command.start_publish`
  - edge agent received the command over gateway control WebSocket
  - edge agent published to LiveKit Cloud with `PANOPTIX_MEDIA_PUBLISHER_MODE=livekit-ffmpeg`
  - edge agent ACKed the command back to the backend
- Latest command verification: `status=accepted`, `acked_at` present, `error` empty
- Edge one-shot result included `accepted_commands=1`, `rejected_commands=0`
- A prior command rejected with LiveKit `invalid token`; re-minting a fresh short-lived ingest token and command resolved it

Not included:

- Real CCTV hardware validation
- Browser/frontend LiveKit subscriber playback
- Committed LiveKit API keys, API secrets, generated JWTs, or gateway-publish tokens

### Real LiveKit Cloud Smoke Checklist

Completed in prior milestone.

Implemented:

- Added LiveKit Cloud-specific manual smoke checklist to `MANUAL_TESTING.md`
- Documented preflight checks for optional LiveKit SDK, FFmpeg, mediamtx, and synthetic RTSP source
- Documented session-only PowerShell environment variables for real LiveKit Cloud URL/key/secret
- Added explicit secret-handling rules and post-run environment cleanup commands
- Added smoke result template that records only non-secret result metadata

Not included:

- Real credentials, `.env` changes, screenshots, or committed smoke results
- Making FFmpeg-backed publishing the default edge-agent runtime path

### User Disable → LiveKit Participant Kill

Completed in prior milestone.

Implemented:

- `security/livekit_rooms.py`: `remove_user_participants()` calls LiveKit Twirp API via httpx
- Wired into `admin_disable_user` — after session revocation, removes viewer participants from active rooms
- Fail-open: errors collected and audited but don't block the disable
- Graceful placeholder detection — skips when LiveKit creds are `replace-me`
- `DisableUserResponse` now includes `participants_removed` and `participant_errors`
- tests cover LiveKit room API behavior and router ACL-room integration; 373 total backend tests passing

Not included:

- Proactive participant scan (only checks rooms the user has ACL for)
- Gateway participant kill on gateway disable (separate future milestone)

### App-Level Rate Limiting

Completed in prior milestone.

Implemented:

- In-memory sliding-window rate limiter (`security/rate_limit.py`) — per-key, thread-safe
- Viewer token endpoint rate-limited per user (30/min default)
- Gateway ingest token endpoint rate-limited per gateway (20/min default)
- 429 responses include `Retry-After` header
- Audit events on rate limit denial: `viewer.token.rate_limited`, `gateway.ingest.rate_limited`
- 9 new tests (7 unit + 2 integration); 329 total backend tests passing

Not included:

- Redis/Memcached backend (in-process only — CF is the primary enforcement layer)
- Rate limiting on non-token endpoints (heartbeat, etc.)

### Session Idle/Absolute TTL Enforcement

Completed in prior milestone.

Implemented:

- `is_session_expired()` helper checks both idle (15 min) and absolute (8 h) timeouts
- Wired into `require_authenticated_user` — expired sessions auto-revoked and return 401
- `touch_session()` resets idle timer on each request; absolute is non-resettable
- `SESSION_IDLE_TIMEOUT_SECONDS` and `SESSION_ABSOLUTE_TIMEOUT_SECONDS` settings added
- 5 new tests; 320 total backend tests passing

Not included:

- Admin re-auth window (≤5 min) — requires frontend integration
- Session listing/active-count admin API

### CSP, CORS, and Security Headers Hardening

Completed in prior milestone.

Implemented:

- Full v4-plan security headers per sections 16.5 and 16.13
- HSTS preload, COOP `same-origin`, CORP `same-origin`
- Dynamic CSP `connect-src` that includes the active LiveKit origin based on `LIVEKIT_MODE`
- `media-src blob:` for LiveKit SDK video playback
- Expanded `Permissions-Policy` with all five directives (Inv 5 defence in depth)
- Per-route CORS policy: browser routes get exact origin, gateway/webhook routes denied
- Server/X-Powered-By banner stripping
- 8 new security tests; 315 total backend tests passing

Not included:

- CSP nonces (requires React + Vite frontend integration — frontend coworker)
- Trusted Types (requires frontend integration)
- COEP `require-corp` (deferred until LiveKit SDK compatibility is verified)

### Live Media Controller Wiring

Completed in prior milestone.

Implemented:

- `media_factory.py` provides `build_media_controller(config)` that selects `StubMediaController` or `LiveKitMediaController` based on `PANOPTIX_MEDIA_PUBLISHER_MODE`
- `AgentConfig` now includes `media_publisher_mode`, `media_source_url`, `media_width`, `media_height`, `media_frame_rate`, and `media_ffmpeg_binary`
- `cli.py` builds the media controller once and passes a shared `CommandExecutor` to both `HeartbeatRunner` and `GatewayControlClient`
- when `livekit-ffmpeg` mode is set, the factory builds the real `LiveKitMediaController` backed by `LiveKitSdkPublisherClient` and `FfmpegVideoTrackMediaSessionFactory`
- when the LiveKit SDK is unavailable, the factory falls back to `StubMediaController` with an error marker
- default behavior is unchanged: `stub` mode, no real services required

### Real Local FFmpeg/LiveKit Smoke Scaffold

Completed in prior milestone.

Implemented:

- `smoke_config.py` provides fail-closed environment variable validation for manual smoke tests
- `smoke_ffmpeg_livekit.py` provides an async smoke runner that mints a short-lived LiveKit publish token locally, builds the real FFmpeg-to-LiveKit pipeline, runs for a bounded duration, and reports structured results
- `--smoke-ffmpeg-livekit` CLI flag bypasses backend config requirements and runs the real media path against explicit local services
- standalone HS256 JWT token minting avoids requiring PyJWT on the edge agent
- smoke config validates LiveKit URL scheme, RTSP URL scheme/credentials, API secret minimum length, FFmpeg binary PATH presence, and duration bounds
- 20 smoke config validation tests and 9 smoke runner tests use fake SDK/FFmpeg objects
- no real credentials, real LiveKit Cloud accounts, or real cameras are committed to the repo

Not included:

- making FFmpeg-backed publishing the default edge-agent controller path
- real LiveKit Cloud smoke testing
- real RTSP camera credentials
- production Docker/systemd gateway supervision
- browser, webcam, phone, or frontend publishing
- external account setup

### Synthetic FFmpeg-to-LiveKit Local Smoke Wiring

Completed in prior milestone.

Implemented:

- `ffmpeg_livekit_smoke.py` provides opt-in factory helpers that compose `FfmpegRtspFrameSource` with `LiveKitVideoTrackMediaSession`
- the factory builds `FfmpegRtspFrameSourceConfig` from the validated `LiveKitPublishRequest.source_url`
- synthetic smoke helper composes signed start/stop commands, `LiveKitSdkPublisherClient`, fake SDK room/track objects, and fake FFmpeg stdout
- tests prove fake RTSP frames flow into the fake LiveKit video source and stop cleanup disconnects/unpublishes/closes the fake process
- start failures remain token-safe and do not require real LiveKit, real FFmpeg, real cameras, or credentials

Not included:

- making FFmpeg-backed publishing the default edge-agent controller path
- real FFmpeg execution
- real RTSP camera credentials
- real LiveKit Cloud smoke testing
- browser, webcam, phone, or frontend publishing
- external account setup

### FFmpeg RTSP Frame Source

Completed in this milestone.

Implemented:

- `ffmpeg_rtsp_frame_source.py` provides `FfmpegRtspFrameSource` behind the existing `LiveKitVideoFrameSource` protocol
- safe FFmpeg argument builder reads RTSP/RTSPS input and writes raw RGBA video frames to stdout
- validation rejects invalid URL schemes, RTSP URLs with credentials, invalid dimensions, invalid frame rates, invalid binary names, and invalid stop timeouts
- async frame iteration reads exact `width * height * 4` byte frames and assigns timestamps from configured FPS
- cleanup is idempotent and terminates or timeout-kills the fake/real process
- fake-process tests cover command args, validation, frame reads, EOF, short reads, missing stdout, close, and timeout kill without launching FFmpeg

Not included:

- wiring this frame source into `LiveKitSdkPublisherClient` by default
- real FFmpeg execution
- real RTSP camera credentials
- real LiveKit Cloud smoke testing
- browser, webcam, phone, or frontend publishing
- external account setup

### Frame-to-LiveKit Track Bridge

Completed in this milestone.

Implemented:

- `LiveKitVideoFrame` and fakeable video frame-source abstractions for CCTV media frames
- `LiveKitVideoTrackMediaSession` creates a LiveKit video source, local video track, and publish options
- async frame pump captures injected frames into the SDK video source
- stop cleanup cancels frame pumping, unpublishes the local track when available, closes the video source, and closes the frame source
- fake SDK/frame-source tests cover track publishing, frame capture, source URL handoff, cleanup, failure containment, and token non-disclosure

Not included:

- real RTSP camera credentials
- real LiveKit Cloud smoke testing
- real FFmpeg, mediamtx, WHIP, RTMP, or LiveKit Ingress execution
- browser, webcam, phone, or frontend publishing
- external account setup

### Real LiveKit SDK Media Adapter

Completed in this milestone.

Implemented:

- `LiveKitSdkPublisherClient` provides an optional LiveKit Python SDK adapter behind `LiveKitPublisherClient`
- SDK import remains lazy and optional; missing SDK returns `livekit-sdk-unavailable`
- adapter connects `rtc.Room()` with `RoomOptions(auto_subscribe=False)` and disconnects on stop
- active SDK sessions are tracked by camera ID, start failures do not store sessions, and stop failures keep sessions for retry
- injectable media-session seam receives the validated CCTV `source_url` for future RTSP frame publishing work
- fake SDK/session tests cover missing SDK, connect/disconnect, cleanup, failure behavior, unknown-stop idempotency, and token non-disclosure

Not included:

- real RTSP camera credentials
- real FFmpeg, mediamtx, WHIP, RTMP, or LiveKit Ingress execution
- browser, webcam, phone, or frontend publishing
- external account setup

### Synthetic End-to-End Publish Dry Run

Completed in this milestone.

Implemented:

- `publish_dry_run.py` builds signed synthetic `start_publish` and `stop_publish` commands
- dry-run execution verifies command signatures before calling `CommandExecutor`
- `CommandExecutor` drives `LiveKitMediaController` using the synthetic RTSP source URL
- fake LiveKit publisher records safe call metadata without logging token values
- optional fake mediamtx lifecycle hooks prove start/stop ordering without launching mediamtx
- tests cover happy path, custom config, duplicate start idempotency, stop-only safety, tampered command rejection, wrong-gateway rejection, publisher failures, and mediamtx lifecycle failures

Not included:

- RTSP-to-LiveKit frame/track publishing
- real RTSP camera credentials
- real FFmpeg or mediamtx process execution
- browser, webcam, phone, or frontend publishing

### LiveKit Publisher Foundation

Completed in prior milestone.

Implemented:

- `livekit_publisher.py` defines a fakeable LiveKit publisher client protocol and publish request/result models
- `LiveKitMediaController` implements the existing `MediaController` boundary
- start-publish validates camera ID, room, LiveKit URL, token, and source RTSP URL before calling the publisher adapter
- duplicate starts for the same camera and room are idempotent at the controller boundary
- stop-publish calls the injected publisher adapter and keeps session state on stop failures
- `SdkUnavailableLiveKitPublisherClient` fails clearly without requiring a LiveKit package or real credentials
- tests cover validation, success, failure, idempotency, SDK-unavailable behavior, and command-executor integration

Not included:

- hard dependency on the real LiveKit SDK package
- real media packet publishing
- browser, webcam, phone, or frontend publishing
- real RTSP camera credentials

### mediamtx Process Management

Completed in prior milestone.

Implemented:

- `mediamtx_process.py` builds safe argument lists for local mediamtx startup
- `MediamtxProcessManager` tracks an injected process and supports start, stop, status, double-start rejection, timeout kill, and failure reporting
- fake-process tests cover lifecycle behavior without requiring mediamtx to be installed
- process management remains independent of the media-controller implementation
- production Docker/systemd supervision remains out of scope

Not included:

- real RTSP camera credentials
- RTSP-to-LiveKit frame/track publishing
- production Docker/systemd unit management

### mediamtx Runtime Configuration

Completed in prior milestone.

Implemented:

- `apps/cctv-edge/mediamtx/mediamtx.local.yml` provides local-only mediamtx defaults for the synthetic RTSP source
- `mediamtx_config.py` generates and validates the safe local mediamtx config
- RTSP/API bindings are constrained to loopback
- tests reject wildcard, WAN, and camera-VLAN API bindings
- tests verify the checked-in YAML matches generated defaults without launching mediamtx

Not included:

- production Docker/systemd supervision
- real RTSP camera credentials
- RTSP-to-LiveKit frame/track publishing

### Synthetic RTSP Test Source

Completed in prior milestone.

Implemented:

- edge-agent config now includes synthetic RTSP URL, video size, frame rate, and audio frequency
- `synthetic_rtsp.py` builds a safe FFmpeg argument list for `testsrc` video and `sine` audio
- validation rejects non-RTSP URLs, RTSP URLs containing credentials, invalid dimensions, and invalid rates
- tests cover command construction and validation without requiring FFmpeg or mediamtx to be installed
- `.env.example` and mediamtx docs include local synthetic-source defaults and security expectations

Not included:

- production Docker/systemd supervision
- real RTSP camera credentials
- RTSP-to-LiveKit frame/track publishing

### Gateway Reconnect Supervision

Completed in prior milestone.

Implemented:

- `ControlReconnectResult` now reports retryable failure count, sleep delays, and stopped reason
- `GatewayControlSupervisor` runs bounded repeated reconnect cycles
- supervisor tracks connected cycles, failed cycles, consecutive failures, and final result
- non-retryable control errors stop supervision without weakening command validation
- `--control-loop-once` now uses the supervisor path for bounded local smoke testing
- edge-agent tests cover reconnect telemetry, repeated cycles, stop-after-success, non-retryable stop, consecutive failures, invalid cycle counts, and cancellation propagation

Not included:

- real mediamtx runtime control
- real RTSP camera publishing
- external monitoring service integration

### Production Maintenance Scheduler

Completed in prior milestone.

Implemented:

- reusable one-shot maintenance job logic now powers both admin-triggered and scheduled maintenance
- disabled-by-default in-process scheduler loop is controlled by `ENABLE_MAINTENANCE_SCHEDULER`
- scheduler interval is controlled by `MAINTENANCE_INTERVAL_SECONDS`
- scheduler starts only when enabled and `DATABASE_URL` is not a placeholder
- scheduled maintenance expires stale gateway commands and enqueues due publish-stop commands
- scheduled runs write `system.maintenance.run` audit events; admin-triggered runs keep `admin.maintenance.run`
- scheduler tests cover stale command expiry, due publish stops, system audit rows, startup gating, and cancellation

Not included:

- distributed scheduler locking for multi-instance deployments
- external Railway/cron configuration
- production database setup

### Browser/Admin Security Hardening

Completed in prior milestone.

Implemented:

- signed CSRF tokens are now bound to non-dev browser sessions
- unsafe browser/admin routes require both `panoptix_csrf` cookie and matching `x-panoptix-csrf-token` header
- CSRF enforcement covers admin mutations, privacy notice acceptance, and session revoke
- safe methods, dev auth, gateway HTTP APIs, gateway WebSocket, LiveKit webhook, and health checks remain outside browser CSRF enforcement
- baseline API security headers are added to success and problem-detail responses
- 11 tests added across `apps/api/tests/test_security.py` and `apps/api/tests/test_sessions.py`

Not included:

- frontend client implementation for sending the CSRF header
- Cloudflare Access production setup
- dynamic frontend CSP for served frontend assets

### Audit Export Signing

Completed in prior milestone.

Implemented:

- `GET /api/v1/admin/audit/export` now returns a self-contained signed JSON response
- response shape is `{ "format": "audit-export-v1", "manifest": {...}, "items": [...] }`
- manifest includes row count, start/end row IDs, canonical content SHA-256, signature algorithm, signature key version, and HMAC-SHA256 signature
- signature covers a canonical unsigned manifest that includes the exported item digest
- exported items continue to exclude internal audit-chain fields (`hash`, `prev_hash`, `hmac_key_version`)
- existing audit export tests now verify digest/signature, range bounds, empty exports, scrubbed payloads, and invalid-key fail-closed behavior

Not included:

- downloadable JSONL/ZIP bundle
- offline verifier CLI
- production key custody/KMS integration

### Command Denial Audit Logging

Completed in prior milestone.

Implemented:

- heartbeat gateway mismatch and command-signing failures now write best-effort gateway audit events
- camera status disabled, missing-camera, and unassigned denials now write best-effort gateway audit events
- gateway control WebSocket unauthenticated, command-signing failure, invalid ACK, ACK gateway mismatch, and not-applied ACK paths now write best-effort gateway audit events
- `db_ack_sink` now returns `AckSinkResult` so ignored ACKs are observable instead of silent
- ACK sink outcomes cover applied, missing command ID, invalid command ID, and command-not-found
- 11 tests added/expanded across `apps/api/tests/test_gateway.py` and `apps/api/tests/test_gateway_command_queue.py`

Not included:

- production SIEM/log forwarding
- edge-agent local persistence for rejected commands

### Gateway Token Verification

Completed in prior milestone.

Implemented:

- gateway API requests can authenticate with `x-panoptix-gateway-id` plus `Authorization: Bearer <service_token>`
- backend looks up `EdgeGateway` and verifies the bearer token against `service_token_hash`
- disabled gateway requests fail with 403 `gateway-disabled`
- invalid, unknown, missing-token, missing-hash, and wrong-token requests fail closed with 401 errors
- valid service token creates a gateway `Principal` with `roles={"gateway"}`
- dev gateway header auth remains unchanged for local-first tests
- 9 production-style gateway auth tests added to `apps/api/tests/test_gateway_credentials.py`

Not included:

- WebSocket service-token authentication
- mTLS certificate authentication
- token grace period / dual-token rotation window

### Gateway Credential Rotation

Completed in prior milestone.

Implemented:

- `POST /api/v1/admin/gateways` now returns a one-time plaintext `service_token`
- gateway rows store only `service_token_hash`
- `POST /api/v1/admin/gateways/{gateway_id}/rotate-credential` issues a new one-time token and overwrites the stored hash
- old service tokens are invalidated immediately after rotation
- credential-sensitive audit payload fields are scrubbed/redacted by existing audit scrubbing
- audit event: `gateway.credential.rotated`
- `apps/api/src/cctv_api/security/service_tokens.py` provides token generation, hashing, and constant-time verification
- 9 tests added in `apps/api/tests/test_gateway_credentials.py`

Not included:

- overlapping grace period for old/new credentials
- mTLS certificate issuance/rotation

### Admin User Management

Completed in prior milestone.

Implemented:

- `POST /api/v1/admin/users/{user_id}/role` grants or revokes a role (`grant`/`revoke` action with `role_name`)
- `POST /api/v1/admin/users/{user_id}/disable` disables user and bulk-revokes all active sessions
- audit events: `admin.user.role.granted`, `admin.user.role.revoked`, `admin.user.disabled`
- error handling: `user-not-found`, `role-not-found`, `role-already-granted`, `role-not-granted`, `user-already-disabled`
- `revoke_all_user_sessions` bulk helper in `sessions.py`
- 13 tests added in `apps/api/tests/test_admin_user_management.py`

Not included:

- MFA reset endpoint
- IdP invite flow
- user re-enable endpoint

### Scheduler Jobs: Admin Maintenance Endpoint

Completed in prior milestone.

Implemented:

- `POST /api/v1/admin/jobs/run-maintenance` runs both `expire_stale_commands` and `enqueue_due_publish_stops` in one admin call
- returns `{ "expired_commands": N, "stops_enqueued": N }`
- writes `admin.maintenance.run` audit event with both counts
- existing `POST /api/v1/admin/commands/cleanup` kept for backward compat
- 6 tests added in `apps/api/tests/test_maintenance.py`

Not included:

- automatic background loop / cron
- production scheduler wiring
- Railway / external cron integration

### Privacy Notice And Admin User Listing APIs

Completed in prior milestone.

Implemented:

- `GET /api/v1/privacy/notice` returns current operator notice text and caller acceptance state
- `POST /api/v1/privacy/notice/accept` records current-version acceptance in `PrivacyNoticeAcceptance`
- acceptance is idempotent and only the first current-version acceptance writes audit
- successful first acceptance audits `privacy.notice.accepted`
- wrong notice versions return 409 `privacy-notice-version-mismatch`
- `GET /api/v1/admin/users` lists safe user fields for admins only
- admin user list supports `limit`, `cursor`, and exact `email` filter
- admin user list returns role names without exposing IdP subject, session rows, or tokens
- 11 tests added in `apps/api/tests/test_privacy_admin_users.py`

Not included:

- role assignment endpoint
- user disable endpoint
- MFA reset endpoint
- IdP invite flow
- production-configured notice content management

### Backend Publish State And Stop Grace Timers

Completed in prior milestone.

Implemented:

- `CameraPublishStatus` enum and `CameraPublishState` SQLAlchemy model
- `cctv_api.gateway.publish_state` helper module for start, schedule-stop, cancel-stop, immediate-stop, and due-stop transitions
- `participant_joined` cancels pending stops or enqueues a start command only if not already starting/publishing
- duplicate `participant_joined` does not enqueue duplicate start commands
- `participant_left` with `participant_count == 0` schedules a delayed stop with a 10-second grace window
- `room_finished` immediately enqueues `gateway.command.stop_publish` and resets publish state
- deterministic `enqueue_due_publish_stops()` helper for future scheduler/cron integration
- new audit actions: `livekit.publish.stop_scheduled`, `livekit.publish.stop_cancelled`
- LiveKit webhook tests expanded to 23 cases

Not included:

- production scheduler/cron wiring for due stops
- Alembic migration; DB-owner coordination still required
- production Docker/systemd gateway supervision
- RTSP-to-LiveKit frame/track publishing

### Room-Presence-Driven Gateway Publish Commands

Completed in prior milestone.

Implemented:

- LiveKit `participant_joined` webhooks enqueue `gateway.command.start_publish` for known camera rooms with enabled gateway assignments
- Start commands mint short-lived gateway publish tokens and record `StreamGrant` rows
- LiveKit `participant_left` with `participant_count == 0` and `room_finished` enqueue `gateway.command.stop_publish`
- Unknown rooms, nonzero participant counts, disabled gateways, and revoked/missing assignments do not enqueue commands
- Publish command audit actions: `livekit.publish.start_enqueued`, `livekit.publish.stop_enqueued`, `livekit.publish.command_skipped`
- Enqueued commands flow through the existing signed WebSocket and heartbeat fallback command provider path
- 10 new tests covering start/stop enqueue, stream grants, skip paths, signed heartbeat fallback, and fail-closed token minting

Not included:

- 10-second grace timers
- backend publish-state tracking
- direct WebSocket push outside the existing queue/provider path
- LiveKit REST calls
- mediamtx process control or real media publishing

### Edge Command Executor

Completed in this milestone.

Implemented:

- `CommandExecutor` dispatches verified gateway commands by kind
- `gateway.command.start_publish` validates camera, room, LiveKit URL, publish token, and token expiry payload fields
- `gateway.command.stop_publish` validates camera and room payload fields
- `MediaController` protocol defines async `start_publish` / `stop_publish`
- `StubMediaController` safely records calls without controlling real media processes
- `FailingMediaController` covers error-path tests
- `PublishState` tracks active per-camera publish sessions in memory
- Duplicate `start_publish` is idempotent and accepted without a duplicate controller call
- `stop_publish` for a non-publishing camera is idempotent and accepted
- WebSocket control path executes verified commands before ACKing
- Heartbeat pending-command fallback executes verified commands before counting them accepted
- 14 new executor tests plus updated control/runner tests

Not included:

- production Docker/systemd gateway supervision
- RTSP-to-LiveKit frame/track publishing
- token refresh or expiry-driven stop
- publish-state persistence across restarts
- backend publish-state tracking or stop grace timers

### LiveKit Webhook Receiver Foundation

Completed in prior milestone.

Implemented:

- `POST /api/v1/webhooks/livekit` accepts signed LiveKit webhook events
- Authorization JWT validation using active LiveKit API key/secret and raw-body SHA-256 claim
- 60-second `createdAt` freshness window
- duplicate webhook JWT signature rejection through `webhook_replay_cache`
- status-relevant room event mapping into `CameraEvent` rows with `source=livekit_webhook`
- system audit actions: `livekit.webhook.received`, `livekit.webhook.replay_rejected`
- SSE visibility for ACL viewers through the existing camera events endpoint
- 9 tests covering auth, signature/hash validation, replay, audit, event persistence, SSE visibility, unknown rooms, and preflight rejection

Not included:

- Gateway start/stop publish orchestration
- Grace timers for last-participant-left
- LiveKit REST calls
- mediamtx process control
- Real CCTV hardware integration

### Admin Gateway Registry And Assignment Endpoints

Completed in prior milestone.

Implemented:

- `POST /api/v1/admin/gateways` creates enabled gateway registry rows
- `POST /api/v1/admin/gateways/{gateway_id}/disable` disables gateways
- `POST /api/v1/admin/gateways/{gateway_id}/cameras` grants/revokes gateway-camera assignments
- Successful mutations audit actions: `gateway.create`, `gateway.disable`, `gateway.camera.grant`, `gateway.camera.revoke`
- Assignment grants enable gateway ingest-token and camera status authorization
- 20 tests covering auth, validation, conflicts, audit, disable, assignment, and downstream authorization

Not included:

- Real service-token or mTLS credential bootstrap
- Gateway credential rotation
- LiveKit publish start/stop control
- Database migrations

### Gateway Camera Status Persistence

Completed in prior milestone.

Implemented:

- `POST /api/v1/gateways/{gateway_id}/cameras/{camera_id}/status` persists `CameraEvent` rows
- Requires matching gateway identity, valid UUIDs, enabled gateway, active camera, and active assignment
- Maps gateway status `online`, `offline`, `degraded` to camera event kind
- Uses `observed_at` if supplied, otherwise server time
- Events use `EventSource.heartbeat` and are visible through `GET /api/v1/cameras/events`
- 13 tests covering auth, validation, authorization, event persistence, observed_at, and SSE visibility

Not included:

- LiveKit room-presence publish orchestration
- Event broker/subscriber integration
- Real camera/media process control
- Persisting status `detail` text

### Camera Events SSE Endpoint

Completed in prior milestone.

Implemented:

- `GET /api/v1/cameras/events` returns persisted camera events as `text/event-stream`
- Filters through Camera + CameraAcl so users only receive events for active ACL cameras
- Excludes retired cameras and revoked ACL grants
- Supports exclusive `since` ISO timestamp filtering and `limit` (default 100, max 500)
- Emits `event: camera_event` frames with event_id, camera_id, gateway_id, kind, source, and at
- 7 tests covering auth, empty stream, ACL filtering, retired/revoked exclusions, since filtering, and invalid since

Not included:

- Infinite live polling loop
- Event broker/subscriber integration
- Gateway publish-command orchestration from LiveKit room presence
- Frontend SSE client wiring

### Admin Camera CRUD Endpoints

Completed in prior milestone.

Implemented:

- `POST /api/v1/admin/cameras` — create camera (display_name, source_type, livekit_room_name)
- `POST /api/v1/admin/cameras/{id}/acl` — grant or revoke user camera ACL
- `POST /api/v1/admin/cameras/{id}/disable` — retire camera (soft delete)
- Source type validated against CCTV-only enum
- Room name uniqueness enforced
- One active ACL grant per user/camera enforced
- All three audit-logged via `_record_user_audit_required` (fail-closed)
- 15 tests covering auth, validation, conflict, and success

Not included:

- Camera update/rename
- Gateway assignment management
- Viewer session termination on disable
- Admin camera listing (all cameras)
- LiveKit room-presence publish orchestration

### Real Camera List Endpoint

Completed in prior milestone.

Implemented:

- `GET /api/v1/cameras` wired to real DB query with Camera + CameraAcl join
- Returns only cameras where the authenticated user has a non-revoked ACL entry
- Excludes retired cameras
- Cursor pagination using `created_at` (newest first, limit+1 pattern)
- 7 tests: auth, empty, accessible, retired, revoked, pagination, user isolation

### Deep Health Check Implementation

Completed in prior milestone, updated by Admin Health Probes milestone.

Implemented:

- `/api/v1/admin/health/deep` wired to real `SELECT 1` database connectivity probe
- Real LiveKit probe via `ListRooms` Twirp API (5s timeout)
- Real gateway probe checking `last_seen_at` freshness against configurable threshold
- Overall status `"ok"` when all subsystems healthy, `"degraded"` otherwise
- No auth required — monitoring systems need unauthenticated access
- 11 tests covering DB, LiveKit, gateway, and overall status combinations

### Gateway Command Audit Logging

Completed in prior milestone.

Implemented:

- `command.enqueue` audit action on enqueue endpoint success
- `command.cancel` audit action on cancel endpoint success
- `commands.cleanup` audit action on cleanup endpoint success
- All three use `_record_user_audit_required` (fail-closed)
- Actor resolved via `get_or_create_user` for UUID actor_id
- `request: Request` and `settings: Settings` added to endpoint signatures
- 3 tests verifying audit rows are written

Not included:

- Denial path audit logging
- Periodic background scheduler/cron
- Real camera/media actions

### Expired-Command Cleanup Admin Endpoint

Completed in prior milestone.

Implemented:

- `POST /api/v1/admin/commands/cleanup` admin-only endpoint
- Calls existing `expire_stale_commands(db)` to bulk-expire stale pending commands across all gateways
- Returns `expired_count` with the number of commands expired
- Idempotent — returns 0 when nothing to expire
- 4 tests covering auth, zero-count, and successful expiry

Not included:

- Periodic background scheduler/cron
- Real camera/media actions

### Command Cancellation Admin Endpoint

Completed in prior milestone.

Implemented:

- `POST /api/v1/admin/gateways/{gateway_id}/commands/{command_id}/cancel` admin-only endpoint
- `cancelled` value added to `CommandStatus` enum
- Only `pending` commands can be cancelled; non-pending returns 409 `command-not-pending`
- Gateway and command existence checks with appropriate 404 errors
- Listing endpoint status filter updated to accept `cancelled`
- 8 tests covering auth, validation, conflict, and success

Not included:

- Audit logging of the cancel action
- Real camera/media actions

### Command Listing Admin Endpoint

Completed in prior milestone.

Implemented:

- `GET /api/v1/admin/gateways/{gateway_id}/commands` admin-only endpoint
- Cursor pagination using `issued_at` (newest first, descending)
- Optional `status` filter (pending, accepted, rejected, expired, cancelled)
- Gateway existence check with 404 `gateway-not-found`
- Response shape `{"items": [...], "next_cursor": "<uuid>" | null}`
- 7 tests covering auth, validation, empty list, ordering, and status filter

Not included:

- Scheduler/cron for cleanup
- Audit logging of the listing call
- Real camera/media actions

### Background Expired-Command Cleanup

Completed in prior milestone.

Implemented:

- `expire_stale_commands(db) -> int` utility function in `gateway/command_queue.py`
- Bulk UPDATE marks pending commands past `expires_at` as `expired`
- Returns count of updated rows; idempotent (only touches pending rows)
- 4 tests covering marking, skip unexpired, skip accepted, return count

Not included:

- Scheduler/cron integration
- Admin endpoint to trigger cleanup
- Notification/alerting

### Command Enqueue API Endpoint

Completed in prior milestone.

Implemented:

- `POST /api/v1/admin/gateways/{gateway_id}/commands` admin-only endpoint
- Request body: `kind` (required), `payload` (optional), `expires_in_seconds` (default 300, 10–3600)
- Gateway existence check with 404 `gateway-not-found`
- Returns 201 with command_id, gateway_id, kind, status, expires_at
- 7 tests covering auth, validation, and success

Not included:

- Command listing/cancellation endpoints
- Background expired-command cleanup job
- Audit logging of command enqueue
- Real camera/media actions

### Command Queue App Factory Wiring

Completed in prior milestone.

Implemented:

- Session-per-call `create_command_provider()` and `create_ack_sink()` wrappers in `gateway/command_queue.py`
- `create_app()` wires hooks automatically when `DATABASE_URL` is configured (no `replace-me`)
- Tests remain isolated — placeholder URL skips wiring; test overrides take precedence
- 2 integration tests verifying session-per-call behavior

Not included:

- Background expired-command cleanup job
- Command enqueue API endpoint
- Real camera/media actions

### Backend Command Queue Persistence

Completed in prior milestone.

Implemented:

- `CommandStatus` enum (pending, accepted, rejected, expired) in `models/enums.py`
- `GatewayCommandQueue` SQLAlchemy model in `models/tables.py` with FK to `edge_gateways`
- `gateway/command_queue.py` with `enqueue_command`, `db_command_provider`, and `db_ack_sink`
- Provider/sink match the existing `app.state` hook protocol
- Alembic migration `0007_gateway_command_tables` creates `gateway_command_queue` and `camera_publish_states`
- 9 tests covering enqueue, provider filtering/FIFO, ack acceptance/rejection, idempotency

Not included:

- Background expired-command cleanup job
- Real CCTV hardware execution

### Audit Row Listing Endpoint

Completed in this milestone.

Implemented:

- `GET /api/v1/admin/audit` admin-only endpoint
- cursor pagination using `AuditLog.id` (newest first, descending)
- configurable `limit` (default 50, max 200)
- optional `action` exact-match filter
- response shape `{"items": [...], "next_cursor": "id" | null}`
- internal chain fields excluded from response
- fail-closed 503 when HMAC key is placeholder or empty

Not included:

- broad filters (actor_type, ts range, resource)
- export signing
- key rotation UI/workflow
- database migrations
- self-auditing the listing call

### Audit Export Skeleton

Completed in this milestone.

Implemented:

- `GET /api/v1/admin/audit/export` admin-only endpoint
- scrubbed audit rows returned as newline-delimited JSON (JSONL)
- optional inclusive `start_id` and `end_id` range filtering
- `application/x-ndjson` content type with `Content-Disposition: attachment` header
- internal chain fields excluded from export
- fail-closed 503 when HMAC key is placeholder or empty

Not included:

- export signing
- key rotation UI/workflow
- broad browsing filters
- database migrations
- self-auditing the export call

### Audit Verification Range/Key-Version Support

Completed in this milestone.

Implemented:

- optional inclusive `start_id` and `end_id` query params on `GET /api/v1/admin/audit/verify`
- full-chain verification remains the default
- open-ended ranges when only one bound is provided
- continuity checks against the latest row before `start_id`
- per-row key lookup using `audit_log.hmac_key_version` and local `audit_hmac_keys.key_enc`
- structured failures for missing or invalid stored key versions

Not included:

- audit row listing
- audit export signing
- key rotation UI/workflow
- database migrations
- self-auditing the verification call

### Admin Audit Verification Endpoint Skeleton

Completed and pushed in commit:

```text
5003679 Add admin audit verification endpoint
```

Implemented:

- `GET /api/v1/admin/audit/verify`
- admin-role enforcement through existing browser/user auth and policy helpers
- full audit-chain verification in `audit_log.id` order
- structured `valid`, `checked`, and `error` response
- `503 audit-hmac-key-invalid` when the configured audit HMAC key is blank or `replace-me`

Not included:

- audit row listing
- audit export signing
- key rotation UI/workflow
- database migrations
- self-auditing the verification call

### Audit HMAC Chain Foundation

Completed in this milestone.

Implemented:

- `AUDIT_HMAC_KEY_VERSION`
- `AUDIT_HMAC_KEY`
- fail-closed audit writes when the HMAC key is blank or left as `replace-me`
- HMAC-SHA-256 audit hashes over canonical scrubbed audit material
- `prev_hash` continuity for newly written audit rows
- active audit HMAC key row handling using `audit_hmac_keys.key_enc` as local placeholder storage
- single-row and sequence verifier helpers for future admin verification surfaces

Not included:

- admin audit list/export/verify endpoints
- export signing
- KMS/envelope encryption
- key rotation UI/workflow
- database migrations

### Edge Gateway Control Reconnect/Backoff Skeleton

Completed and pushed in commit:

```text
b4a4262 Add gateway control reconnect backoff
```

Implemented:

- `PANOPTIX_GATEWAY_CONTROL_RECONNECT_ATTEMPTS`
- `PANOPTIX_GATEWAY_CONTROL_RECONNECT_BACKOFF_SECONDS`
- bounded `GatewayControlClient.run_with_reconnect()`
- `--control-loop-once` local CLI check
- retry for temporary connection/run failures
- no retry for malformed fail-closed control messages
- no inbound gateway listener, command execution, mediamtx control, or LiveKit publishing

Verification:

```text
edge agent pytest: 43 passed
edge agent mypy: no issues found
edge agent ruff: all checks passed
edge agent compileall: passed
```

### Gateway WebSocket Command Dispatch + ACK Skeleton

Completed and pushed in commit:

```text
97f00e7 Add gateway command dispatch ACK skeleton
```

Implemented:

- backend sends signed in-memory/test-scaffolded command envelopes over the existing gateway WebSocket
- edge agent receives and verifies command envelopes
- edge agent sends `command_ack` for valid commands
- edge agent sends rejected ACKs for invalid/tampered/wrong-gateway commands
- backend receives ACK/reject messages through an app-state test hook
- no DB command queue, mediamtx action, LiveKit publishing, or real camera action

### Gateway Heartbeat Command Fallback Skeleton

Completed and pushed in commit:

```text
8c96180 Add gateway heartbeat command fallback
```

Implemented:

- backend heartbeat response can return signed in-memory/test-scaffolded `pending_commands`
- backend fails closed instead of returning unsigned heartbeat commands when signing is misconfigured
- edge heartbeat runner verifies pending commands
- edge heartbeat runner records accepted/rejected command counts and local verifier errors
- no DB command queue, heartbeat ACK persistence, mediamtx action, LiveKit publishing, or real camera action

### Gateway Command Signing + Agent Verifier

Completed and pushed.

Backend:

- `apps/api/src/cctv_api/gateway/command_signing.py`
- `apps/api/src/cctv_api/gateway/models.py`
- `apps/api/tests/test_gateway_command_signing.py`

Edge agent:

- `apps/cctv-edge/agent/src/panoptix_edge_agent/commands.py`
- `apps/cctv-edge/agent/tests/test_commands.py`

Implemented:

- canonical JSON signing payload
- HMAC-SHA-256 signatures
- base64url signatures
- command expiry validation
- gateway target validation
- constant-time signature compare
- fail-closed verifier behavior

### Edge Gateway Control WebSocket Client

Completed and pushed in commit:

```text
2a641d6 Add edge gateway control websocket client
```

Implemented:

- `apps/cctv-edge/agent/src/panoptix_edge_agent/control.py`
- `apps/cctv-edge/agent/tests/test_control.py`
- `--control-once` in `apps/cctv-edge/agent/src/panoptix_edge_agent/cli.py`
- `PANOPTIX_GATEWAY_CONTROL_WS_PATH` config
- `websockets>=15.0` dependency
- docs/manual testing updates

Behavior:

- agent builds `ws://` or `wss://` URL from `PANOPTIX_API_BASE_URL`
- agent connects outbound to `/api/v1/gateway-control/ws`
- agent sends dev gateway identity header when enabled
- agent receives backend connected hello
- agent validates hello gateway ID
- agent can parse future command envelopes
- agent verifies command signatures
- invalid JSON raises client error
- unsigned/tampered/wrong-gateway commands are rejected
- no command execution yet

## Latest Known Verification Status

Backend from `apps/api/`:

```powershell
$env:PYTHONPATH = "src"; python -m pytest tests/ -v
$env:PYTHONPATH = "src"; python -m ruff check src tests alembic scripts
$env:PYTHONPATH = "src"; python -m mypy src/cctv_api/ --ignore-missing-imports
$env:PYTHONPATH = "src"; python -m compileall src alembic scripts
```

Latest result:

```text
pytest: 606 passed
ruff: all checks passed
mypy: no issues found in 44 source files
compileall: passed
```

Edge agent from `apps/cctv-edge/agent/`:

```powershell
$env:PYTHONPATH = "src"; python -m pytest tests/ -v
$env:PYTHONPATH = "src"; python -m ruff check src tests
$env:PYTHONPATH = "src"; python -m mypy src/panoptix_edge_agent --ignore-missing-imports
$env:PYTHONPATH = "src"; python -m compileall src tests
```

Latest result:

```text
pytest: 245 passed, 2 skipped (includes 3 real FFmpeg integration tests)
ruff: all checks passed
mypy: no issues found in 22 source files
compileall: passed
```

## Next Recommended Milestone

Recommended next task:

```text
Recurring Backup Automation And Retention Rules
```

Turn the proven operator-run R2 backup and isolated restore-drill path into a scheduled, monitored production backup workflow. The first encrypted backup artifact and restore-drill evidence already exist, so the next system-owner task is automation: cadence, failure alerting, retention policy, and runbook evidence.

**Note**: Production is already live at `panoptix.site`; the old staging-gate/procurement wording below is historical context only. Do not restore into production Neon. Keep private `age` identities outside Railway and outside the repo.

## Not Implemented Yet

- real camera onboarding (credential file exists, needs real hardware + LiveKit Cloud)
- real LiveKit browser subscriber playback (frontend/system-owner integration path; browser must subscribe only)
- Alerts page wiring to real backend alert APIs (frontend coworker)
- actor investigation UI (frontend coworker)
- admin visitor investigation UI (frontend coworker)
- full audit filter UI (frontend coworker)
- recurring backup automation and retention policy (system owner)
- gateway local network discovery scanner/API/UI (planned core pilot; gateway/backend first, frontend later)
- production Docker/systemd gateway supervision (runbook templates exist)
- Google Workspace IdP setup (GitHub OAuth currently deployed)
- WARP device posture production activation (checklist done in `cloudflare-production-setup.md`)

The proven manual backup/restore path is complete; automation, retention, hardware validation, and coworker-owned UI gaps remain.

## 7-Day Staging Gate

The 7-day staging uptime gate started 2026-05-13. Expected clear date: 2026-05-20.
Staging health check cron runs every 15 minutes at `.github/workflows/staging-healthcheck.yml`.
Production deployment is gated on 7-day uptime >= 99% (v4 plan T-20).
The production deploy workflow is at `.github/workflows/deploy-production.yml`.

## External Accounts Status

### Active
- **Cloudflare** — `panoptix.site` domain active, Zero Trust org `panoptix-netad`, GitHub OAuth IdP, Access application for `staging.panoptix.site`
- **Railway** — `panoptix-control` service deployed from `backend` branch, custom domain `staging.panoptix.site`
- **Neon** — staging database `neondb` (ap-southeast-1), 23 tables, migrations at `0004_constraints_and_indexes`

### Not Yet Required
- Google Workspace
- R2
- Sentry/Better Stack/UptimeRobot

LiveKit Cloud was used for a bounded smoke test only. No LiveKit API key, API secret, generated JWT, or credential material should be committed.

Use local/dev placeholders and fail-closed behavior for services not yet active.

## Development Rules

### Mandatory Rules

- Always update `MANUAL_TESTING.md` when behavior or local manual testing steps change.
- Always update `PROGRESS.md` when a milestone is completed or next step changes.
- Update `IMPLEMENTATION_GUIDE.md` for meaningful implementation milestones.
- Add or update tests for every backend or edge behavior change.
- Run backend and edge verification before declaring completion.
- Keep gateway control fail-closed.
- Reject invalid, unsigned, expired, tampered, or wrong-gateway commands.
- Edge gateway must connect outbound to cloud/backend; do not add inbound WAN listeners.
- Do not execute real camera/media actions until protocol skeletons are proven.
- Do not replace the stub media controller with real mediamtx/LiveKit control until runtime config, process supervision, and rollback behavior are planned and tested.
- Do not hardcode real secrets, API keys, database passwords, school/user data, or production credentials.
- Use dev auth only for local development.
- Preserve the CCTV-only invariant: browser viewers never publish media.
- Keep gateway publish tokens away from browser responses.
- Prefer small, testable milestones over large invasive changes.
- Preserve existing code style and avoid unrelated edits.

### Command Safety Rules

- On Windows PowerShell, use the command working directory instead of putting `cd` inside commands.
- Safe read-only commands can run directly.
- Be careful with destructive commands, dependency installs, migrations, process kills, and network calls.
- If starting a dev server, check for existing servers/processes first.

### Git / Handoff Rules

- Work on branch `backend` unless user explicitly says otherwise.
- After completing a milestone, show `git status --short --branch` and `git diff --stat`.
- Commit message style used recently:
  - `Add gateway command signing and agent verifier`
  - `Add edge gateway control websocket client`

## Important Files And What They Do

### Root Docs

- `README.md`: high-level architecture, invariants, project structure
- `PROGRESS.md`: current completion status and next steps
- `IMPLEMENTATION_GUIDE.md`: implementation history and verification status
- `MANUAL_TESTING.md`: local manual test guide; must be updated with behavior changes
- `CLAUDE.md`: AI coding/development guidance and security invariants
- `.env.example`: environment variable schema; contains placeholders only
- `.gitignore`: ignores local envs, caches, build outputs, and local-only AI/process instructions

### Backend Source

- `apps/api/src/cctv_api/main.py`: FastAPI app factory
- `apps/api/src/cctv_api/core/config.py`: backend settings/env parsing
- `apps/api/src/cctv_api/api/router.py`: versioned API router
- `apps/api/src/cctv_api/api/errors.py`: problem detail errors
- `apps/api/src/cctv_api/api/health.py`: health endpoints
- `apps/api/src/cctv_api/api/gateways.py`: gateway heartbeat, camera status, LiveKit token endpoints, gateway control WebSocket
- `apps/api/src/cctv_api/api/livekit_webhooks.py`: LiveKit webhook receiver, replay cache, audit, and camera event persistence
- `apps/api/src/cctv_api/db.py`: database/session setup
- `apps/api/src/cctv_api/gateway/models.py`: gateway API and command envelope Pydantic models
- `apps/api/src/cctv_api/gateway/command_signing.py`: backend command signing/verifying
- `apps/api/src/cctv_api/gateway/command_queue.py`: persistent command queue provider/sink
- `apps/api/src/cctv_api/gateway/publish_state.py`: backend camera publish-state and stop-grace helpers
- `apps/api/src/cctv_api/models/tables.py`: SQLAlchemy table models
- `apps/api/src/cctv_api/models/enums.py`: DB/domain enums
- `apps/api/src/cctv_api/security/cloudflare_access.py`: CF Access JWT handling
- `apps/api/src/cctv_api/security/dependencies.py`: auth dependencies
- `apps/api/src/cctv_api/security/identity.py`: principal identity model
- `apps/api/src/cctv_api/security/livekit_tokens.py`: LiveKit token helpers
- `apps/api/src/cctv_api/security/livekit_rooms.py`: LiveKit participant removal helper for user disable
- `apps/api/src/cctv_api/security/livekit_webhooks.py`: LiveKit webhook Authorization JWT and body-hash verifier
- `apps/api/src/cctv_api/security/policy.py`: RBAC policy helpers
- `apps/api/src/cctv_api/security/session_cookie.py`: signed session cookie helpers
- `apps/api/src/cctv_api/security/sessions.py`: session management
- `apps/api/src/cctv_api/security/stream_access.py`: stream access checks
- `apps/api/src/cctv_api/security/audit.py`: audit writer, scrubbing, HMAC chain, and verifier helpers

### Backend Tests

- `apps/api/tests/conftest.py`: backend pytest setup
- `apps/api/tests/test_gateway.py`: heartbeat, camera status, gateway control WebSocket tests
- `apps/api/tests/test_gateway_command_signing.py`: command signing tests
- `apps/api/tests/test_gateway_command_queue.py`: command queue persistence tests
- `apps/api/tests/test_livekit_webhooks.py`: LiveKit webhook receiver tests
- `apps/api/tests/test_livekit_rooms.py`: LiveKit room participant removal tests
- `apps/api/tests/test_livekit_tokens.py`: viewer/gateway LiveKit token tests
- `apps/api/tests/test_privacy_admin_users.py`: privacy notice and admin user list tests
- `apps/api/tests/test_maintenance.py`: admin maintenance endpoint tests
- `apps/api/tests/test_admin_user_management.py`: admin role assignment and user disable tests
- `apps/api/tests/test_gateway_credentials.py`: gateway service-token issuance and rotation tests
- `apps/api/tests/test_security.py`: auth/dev-auth tests
- `apps/api/tests/test_sessions.py`: session tests
- `apps/api/tests/test_audit.py`: audit tests
- `apps/api/tests/test_policy.py`: RBAC tests
- `apps/api/tests/test_config.py`: config tests
- `apps/api/tests/test_health.py`: health tests

### Edge Agent Source

- `apps/cctv-edge/agent/src/panoptix_edge_agent/config.py`: agent env config
- `apps/cctv-edge/agent/src/panoptix_edge_agent/client.py`: HTTP JSON client to backend
- `apps/cctv-edge/agent/src/panoptix_edge_agent/runner.py`: heartbeat runner
- `apps/cctv-edge/agent/src/panoptix_edge_agent/commands.py`: command envelope parser/verifier
- `apps/cctv-edge/agent/src/panoptix_edge_agent/control.py`: gateway control WebSocket client
- `apps/cctv-edge/agent/src/panoptix_edge_agent/executor.py`: verified command dispatcher
- `apps/cctv-edge/agent/src/panoptix_edge_agent/media.py`: media controller protocol and stub/failing controllers
- `apps/cctv-edge/agent/src/panoptix_edge_agent/livekit_publisher.py`: fakeable LiveKit publisher controller boundary
- `apps/cctv-edge/agent/src/panoptix_edge_agent/ffmpeg_rtsp_frame_source.py`: fakeable FFmpeg RTSP raw-frame source
- `apps/cctv-edge/agent/src/panoptix_edge_agent/ffmpeg_livekit_smoke.py`: opt-in synthetic FFmpeg-to-LiveKit smoke wiring
- `apps/cctv-edge/agent/src/panoptix_edge_agent/publish_dry_run.py`: fake-only synthetic publish dry-run harness
- `apps/cctv-edge/agent/src/panoptix_edge_agent/mediamtx_process.py`: local mediamtx process command/lifecycle scaffold
- `apps/cctv-edge/agent/src/panoptix_edge_agent/publish_state.py`: in-memory publish session tracker
- `apps/cctv-edge/agent/src/panoptix_edge_agent/camera_credentials.py`: per-camera RTSP credential store, loader, URL builders, and permission checks
- `apps/cctv-edge/agent/src/panoptix_edge_agent/cli.py`: CLI entrypoint for heartbeat/control checks

### Edge Agent Tests

- `apps/cctv-edge/agent/tests/test_config.py`: agent config tests
- `apps/cctv-edge/agent/tests/test_client.py`: HTTP client tests
- `apps/cctv-edge/agent/tests/test_runner.py`: heartbeat runner tests
- `apps/cctv-edge/agent/tests/test_commands.py`: command verifier tests
- `apps/cctv-edge/agent/tests/test_control.py`: WebSocket control client tests
- `apps/cctv-edge/agent/tests/test_executor.py`: command executor tests
- `apps/cctv-edge/agent/tests/test_livekit_publisher.py`: fakeable LiveKit publisher controller tests
- `apps/cctv-edge/agent/tests/test_ffmpeg_rtsp_frame_source.py`: FFmpeg frame-source command/process/frame tests
- `apps/cctv-edge/agent/tests/test_ffmpeg_livekit_smoke.py`: synthetic FFmpeg-to-LiveKit smoke wiring tests
- `apps/cctv-edge/agent/tests/test_camera_credentials.py`: per-camera credential loader, URL builder, validation, and permission tests
- `apps/cctv-edge/agent/tests/test_publish_dry_run.py`: synthetic publish dry-run tests
- `apps/cctv-edge/agent/tests/test_mediamtx_process.py`: mediamtx process lifecycle tests

### Migrations / Database

- `apps/api/alembic/versions/0001_initial_schema.py`: initial schema
- `apps/api/alembic/versions/0002_camera_display_name.py`: camera display name
- `apps/api/alembic/versions/0003_roles_and_grants.py`: roles and grants
- `apps/api/alembic/versions/0004_constraints_and_indexes.py`: constraints/indexes
- `apps/api/alembic/versions/0005_seed_roles.py`: seed roles
- `apps/api/alembic/versions/0006_audit_log_metadata.py`: audit severity/outcome/category/session metadata
- `apps/api/alembic/versions/0007_gateway_command_tables.py`: gateway command queue and camera publish-state tables

### Planning / Architecture Docs

- `docs/index.md`: documentation map
- `docs/planning/secure-cctv-monitoring-system-v4.md`: full system plan
- `docs/planning/cctv-core-functionality-features.md`: core feature list
- `docs/planning/cctv-future-functionality-features.md`: future features
- `docs/planning/tech-stack-simple.md`: simple tech stack explanation
- `docs/implementation/api-reference.md`: API contract
- `docs/implementation/development-setup.md`: local setup
- `docs/implementation/deployment-guide.md`: deployment model
- `docs/implementation/test-plan.md`: QA/test plan
- `docs/implementation/team-raci-checklist.md`: ownership boundaries
- `docs/runbooks/gateway-control-channel.md`: gateway control operations guidance
- `docs/security/threat-model-stride.md`: STRIDE threat model
- `docs/frontend/ux-product-spec.md`: frontend UX/product spec
- `docs/database/database-guardrails.md`: database guardrails

## Project Tree Summary

```text
Panoptix/
  .env.example
  .gitignore
  CLAUDE.md
  CONTRIBUTING.md
  IMPLEMENTATION_GUIDE.md
  MANUAL_TESTING.md
  PROGRESS.md
  README.md
  SECURITY.md
  apps/
    api/
      Dockerfile
      README.md
      pyproject.toml
      alembic/
        versions/
          0001_initial_schema.py
          0002_camera_display_name.py
          0003_roles_and_grants.py
          0004_constraints_and_indexes.py
          0005_seed_roles.py
      scripts/
        db_validate.py
      src/cctv_api/
        main.py
        db.py
        api/
          errors.py
          gateways.py
          health.py
          livekit_webhooks.py
          router.py
        core/
          config.py
        gateway/
          command_queue.py
          command_signing.py
          models.py
          publish_state.py
        models/
          base.py
          enums.py
          tables.py
        security/
          audit.py
          cloudflare_access.py
          dependencies.py
          identity.py
          livekit_webhooks.py
          livekit_tokens.py
          policy.py
          session_cookie.py
          sessions.py
          stream_access.py
          users.py
      tests/
        conftest.py
        test_audit.py
        test_cloudflare_access.py
        test_config.py
        test_gateway.py
        test_gateway_command_queue.py
        test_gateway_command_signing.py
        test_health.py
        test_livekit_webhooks.py
        test_livekit_tokens.py
        test_policy.py
        test_security.py
        test_sessions.py
    cctv-edge/
      README.md
      agent/
        README.md
        pyproject.toml
        src/panoptix_edge_agent/
          cli.py
          client.py
          commands.py
          config.py
          control.py
          executor.py
          media.py
          publish_state.py
          runner.py
        tests/
          test_client.py
          test_commands.py
          test_config.py
          test_control.py
          test_executor.py
          test_runner.py
      mediamtx/
        README.md
    media-fallback/
      README.md
    web/
      README.md
  database/
    README.md
  docs/
    index.md
    adrs/
      0001-plane-separation.md
      0002-idp-selection.md
      0003-postgres-tier.md
      0004-livekit-fallback.md
      0005-break-glass.md
      0006-reserved.md
      0007-version-pinning.md
      0008-gateway-identity.md
      0009-cctv-only-ingest.md
      0010-origin-binding.md
      0011-bystander-signage-policy.md
      0012-camera-network-design.md
      0013-gateway-hardware-standard.md
      0014-railway-python-control-plane.md
    architecture/
      data-flow.mmd
      erd.mmd
      network-security.mmd
      request-flow.mmd
      sequence-admin-actions.mmd
      sequence-camera-stream.mmd
      sequence-viewer-login.mmd
      system-overview.mmd
    database/
      database-guardrails.md
      README.md
    frontend/
      frontend-guardrails.md
      README.md
      ux-product-spec.md
    implementation/
      api-reference.md
      deployment-guide.md
      development-setup.md
      team-raci-checklist.md
      test-plan.md
    planning/
      cctv-core-functionality-features.md
      cctv-future-functionality-features.md
      secure-cctv-monitoring-system-v4.md
      tech-stack.md
      tech-stack-simple.md
    privacy/
      bystander-signage-template.md
      compliance-readiness-checklist.md
      pia-template.md
      vendor-dpa-template.md
    procurement/
      camera-spec.md
      procurement-guide.md
    reference/
      glossary.md
    review/
      document-review-report-current.md
    runbooks/
      backup-restore.md
      cf-access-rollback.md
      deploy-rollback.md
      gateway-control-channel.md
    security/
      threat-model-stride.md
  infra/
    README.md
    terraform/
      README.md
  scripts/
    README.md
```

## Manual Local Testing Pointers

Use `MANUAL_TESTING.md` as the authoritative local testing guide.

Important local checks currently include:

- backend health
- dev auth behavior
- gateway heartbeat
- gateway camera status
- LiveKit token local/fail-closed checks
- LiveKit webhook receiver local signed webhook check
- room-presence publish command enqueue checks
- gateway command signing local check
- admin audit listing
- admin audit export
- camera list endpoint
- admin camera CRUD endpoints
- camera events SSE endpoint
- gateway camera status persistence
- admin gateway registry and assignments
- backend gateway control WebSocket hello check
- backend gateway control WebSocket dispatch/ACK test
- gateway heartbeat command fallback test
- edge-agent heartbeat `--once`
- edge-agent gateway control `--control-once`
- edge-agent gateway control `--control-loop-once`

## Suggested Prompt For The New IDE/LLM

```text
Read HANDOFF.md and follow its instructions. Then read PROGRESS.md, IMPLEMENTATION_GUIDE.md, MANUAL_TESTING.md, README.md, CLAUDE.md, docs/runbooks/backup-restore.md, and the source files related to the next milestone. Confirm the current state and development rules before making changes. Current production facts: panoptix.site is live, /entry works, expanded visitor detail APIs work, the first encrypted R2 backup exists, isolated restore-drill evidence row 564e2bfd-b449-4c9f-b46d-a0366856a7e0 passed, backup status is ok, and the temporary Neon restore branch was deleted. The next recommended system-owner milestone is recurring backup automation and retention rules. Do not take coworker-owned frontend tasks unless explicitly reassigned.
```

## Final Notes

The new IDE/LLM will not automatically know every file's full contents. This handoff gives it the map, rules, current state, and read-first order. It should still search and read files on demand before editing.
