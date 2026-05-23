| **Frontend** | 80% | 🟡 Integrated, staging smoke passed | `integratedCompleteFrontend` is merged into `fullstack-integration`. The React/Vite app now has the login shell, viewer dashboard, camera detail modal, admin dashboard, users, cameras, gateways, audit/compliance, DSR, break-glass, health, settings, dev-auth headers, same-origin API client, and same-domain public `/entry` visitor notice flow. Local same-origin smoke through the Vite proxy passes. Staging deployed browser smoke passed 2026-05-21: all 10 sidebar pages loaded through Cloudflare Access at `staging.panoptix.site` with no 500/502 errors. Production expanded visitor collector API smoke passed 2026-05-24. Frontend production proxy server (`server.mjs`) serves Vite dist and proxies API calls. Missing: real LiveKit subscriber playback, Alerts page wiring to real backend APIs, admin visitor investigation UI, actor investigation UI, Playwright coverage, and production polish. |
| **Database** | 100% | 🟢 Strong | Core schema plus `0007_gateway_command_tables`, `0008_alerts_email`, `0009_login_baselines`, `0010_visitor_visits`, and expanded visitor signal migration `0011_visitor_expanded_signals` are part of the production migration path. `alerts`, `alert_notifications`, `gateway_command_queue`, `camera_publish_states`, `backup_runs`, `login_baselines`, and `visitor_visits` model/schema verified. Missing: recorded restore drill evidence, backup worker automation, retention policy tables (pilot+). |
| **Infrastructure** | 100% | 🟢 Strong | **Production live at `panoptix.site` (2026-05-22).** Cloudflare Access "Panoptix Production" app protects the app root and protected API paths with GitHub org policy. First-time root visits without `panoptix_visitor` redirect to the public `/entry` notice flow; only `/entry`, `/assets/*`, `/logo.png`, `/api/v1/visitor/notice`, and `/api/v1/visitor/collect` are bypassed for the visitor pilot. Railway production backend + frontend deployed with new cryptographic keys. Neon production branch fully migrated. DNS promoted from `staging.panoptix.site` to `panoptix.site`. `SUSPICIOUS_LOGIN_DETECTION_ENABLED=true` in production. Staging health check cron running. R2 backup bucket provisioned. LiveKit Cloud (APAC) live. Missing: break-glass YubiKey hardware, physical gateways, first R2 backup run. |
| **Security** | 90% | 🟢 Strong | CF Access JWT, CSRF, HMAC audit chain, classified audit events with session/IP/UA metadata, audit-of-audit for profile/activity views, rate limiting (including admin mutations), security headers, service tokens, RBAC, break-glass, SCA/SAST CI, mediamtx threat model, mTLS cert bootstrap scaffold, CT-log monitoring all done. Missing: device posture enforcement production activation and browser security smoke evidence. |
| **Documentation** | 96% | 🟢 Strong | Full system plan, API reference, 51+ docs, all runbooks done (incl. break-glass, lost-MFA, IdP-outage, bus-factor, uptime monitoring, backup-restore DR schedule, Cloudflare WARP posture), mediamtx threat model, Terraform state security doc, frontend design guidance, and current full-stack status docs. |
| **DevOps/CI** | 98% | 🟢 Strong | GitHub Actions CI covers both `main` and `backend` branches. Edge agent CI added (ruff, mypy, pytest, compileall, osv-scanner). Staging health check cron active. Production deploy workflow (manual) ready. Staging auto-deploy workflow added. Dependabot auto-merge workflow added (minor/patch auto, major manual). |

### Critical Path to MVP

| # | Blocker | Owner | Depends On |
|---|---------|-------|------------|
| 1 | Real LiveKit browser subscriber playback | Frontend/system owner | Backend viewer token endpoint done; frontend modal currently token-only |
| 2 | ~~Complete staging/deployed browser smoke test~~ | System owner + Frontend | ✅ Done — all 10 sidebar pages pass on `staging.panoptix.site` (2026-05-21) |
| 3 | Real camera → LiveKit publishing from edge agent | System owner | Synthetic backend path ✅, needs real camera hardware |
| 4 | ~~Production deployment hardening~~ | System owner | ✅ Done — `panoptix.site` live (2026-05-22), Cloudflare Access, Railway, Neon, signing keys, migration all complete |
| 5 | ~~LiveKit Cloud provisioning (APAC region)~~ | System owner | ✅ Done |
| 6 | ~~Break-glass emergency access~~ | System owner | ✅ Done |
| 7 | ~~Production deployment pipeline~~ | System owner | ✅ Done (manual workflow ready, 7-day staging clock running) |

### What We Control vs What's Blocked

**Can do now (no external dependencies):**
- Keep static checks green, document operational changes, and run the first production R2 backup before any restore drill. Production is live; the main product-path blockers are real LiveKit browser playback, real camera hardware validation, first backup artifact/restore evidence, Alerts page API wiring, actor investigation UI, and admin visitor investigation UI.
- GitHub organization invites are now live on staging (`panoptix-site` org). `GITHUB_INVITES_ENABLED=true`, `GITHUB_ORG=panoptix-site`, and `GITHUB_INVITE_TOKEN` are set in Railway. Staging smoke confirmed invite endpoint works — invited users appear in Users & Access with assigned roles (2026-05-21).
- Pilot alert records now exist for high-value backend events, and SMTP email notification support is available but disabled by default. Real email delivery should only be tested after placeholder SMTP settings are replaced with approved provider credentials in local/staging secrets.
- Any one-time gateway service token displayed by the frontend must be treated as sensitive. Do not screenshot it; rotate exposed test credentials or disable the test gateway. The exposed local test gateway named `what` was disabled during local smoke cleanup.

**Blocked on external dependencies:**
- Real CCTV hardware onboarding → hardware procurement
- Paid Neon tier → procurement (post-pilot)

---

## Ownership Boundary

- **Frontend implementation** (`apps/web/`) → owned by frontend coworker; `fullstack-integration` now contains the merged V1 frontend for combined testing
- **Database implementation** (`database/`) → owned by database coworker
- **Everything else** → owned by system owner (us)

See `docs/implementation/team-raci-checklist.md` for full RACI details.

---

## Completed

### Documentation
- [x] All docs reorganized into category folders under `docs/`
- [x] `docs/index.md` central navigation map created and validated
- [x] All internal Markdown links validated — 0 broken links
- [x] Architecture diagrams created (8 `.mmd` files in `docs/architecture/`)
- [x] Frontend/database role README guides created
- [x] RACI ownership boundary documented in `docs/implementation/team-raci-checklist.md`

### Repo Setup
- [x] `.gitignore` added (ignores `.env`, `__pycache__`, `node_modules`, `COUNCIL.md`, `execute.md`)
- [x] `.env.example` verified — placeholder values only, safe to share
- [x] Monorepo skeleton created: `apps/`, `database/`, `infra/`, `scripts/`
- [x] FastAPI backend starter created and validated (`apps/api/`)
- [x] Gateway/edge placeholder created (`apps/cctv-edge/`)
- [x] Media fallback placeholder created (`apps/media-fallback/`)
- [x] Infrastructure placeholder created (`infra/`, `infra/terraform/`)
- [x] Scripts placeholder created (`scripts/`)
- [x] Frontend V1 integration merged into `fullstack-integration` and build/lint verified
- [x] Local full-stack admin smoke partially verified: Users & Access, Camera Management, and Gateways load and perform core admin actions against the local backend with dev auth
- [x] Database ownership placeholder created (`database/README.md`)
- [x] `README.md` project structure diagram updated

### Backend App Foundation
- [x] Pydantic Settings config loader (`apps/api/src/cctv_api/core/config.py`)
- [x] App factory pattern (`create_app()` in `main.py`)
- [x] RFC 9457 Problem Details error handling (`api/errors.py`)
- [x] Health endpoint (`/health`) and deep health placeholder (`/api/v1/admin/health/deep`)
- [x] API v1 router with placeholder endpoints (`/api/v1/me`, `/api/v1/cameras`)
- [x] Test suite: 4 tests passing (health + config)
- [x] `httpx` added as dev dependency for TestClient

### DevOps Foundation
- [x] Dockerfile for `apps/api/` — pinned Python 3.12.7-slim, non-root user, read-only FS
- [x] `.dockerignore` for `apps/api/`
- [x] GitHub Actions CI workflow (`.github/workflows/ci.yml`) — lint, mypy, pytest, Docker build, secret scan
- [x] Dependabot config (`.github/dependabot.yml`) — pip + GitHub Actions weekly updates

### Security Foundation
- [x] Request principal model (`apps/api/src/cctv_api/security/identity.py`)
- [x] Cloudflare Access verifier interface with fail-closed behavior
- [x] Development auth path restricted to `APP_ENV=development` and `ALLOW_DEV_AUTH=true`
- [x] Authentication dependencies for browser users and gateways
- [x] Deny-by-default RBAC helper placeholders
- [x] `/api/v1/me` and `/api/v1/cameras` protected by auth dependency
- [x] Tests for unauthenticated access, disabled dev-auth, allowed dev-auth, forbidden non-dev dev-auth, and RBAC helpers
- [x] Production Cloudflare Access browser JWT verification with PyJWT, JWKS key lookup, issuer/audience validation, clock-skew handling, and fail-closed tests

### Gateway Foundation
- [x] Gateway Pydantic models for heartbeat, camera status, ingest-token request, and command envelopes
- [x] Gateway heartbeat endpoint placeholder (`POST /api/v1/gateways/{gateway_id}/heartbeat`)
- [x] Gateway ingest-token endpoint fail-closed placeholder (`POST /api/v1/gateways/{gateway_id}/ingest-token`)
- [x] Gateway camera status endpoint placeholder (`POST /api/v1/gateways/{gateway_id}/cameras/{camera_id}/status`)
- [x] Gateway control channel placeholder (`GET /api/v1/gateway-control/ws`)
- [x] Gateway ID path matching enforced against authenticated gateway principal
- [x] Tests for gateway auth requirement, dev gateway identity, ID mismatch, fail-closed token minting, status acceptance, and control-channel placeholder

### Database Foundation
- [x] Safely integrated database-owned Alembic setup from `origin/dev-phase` without replacing backend/security/gateway code
- [x] SQLAlchemy model package added for users, sessions, RBAC, cameras, gateways, stream grants, audit, privacy, and ops tables
- [x] Alembic migrations added for initial schema, camera display-name alignment, DB roles/grants, constraints, and indexes
- [x] Database settings added to existing backend `Settings` class
- [x] Database validation script integrated with backend config

### Backend Session Foundation
- [x] Role model simplified to `admin` and `viewer`
- [x] Alembic seed migration added for `admin` and `viewer` roles
- [x] Session cookie signing and verification added
- [x] Database-backed user lookup and session creation added to browser auth flow
- [x] Active session listing and session revocation endpoints added
- [x] Test database fixture added for backend tests without requiring local PostgreSQL

### LiveKit Token Minting Foundation
- [x] Viewer subscribe-token endpoint added with active camera ACL checks
- [x] Gateway publish-token endpoint added with active gateway-camera assignment checks
- [x] LiveKit JWT minting added with ≤60s TTL and strict viewer/gateway grant separation
- [x] Stream grants recorded for successful viewer and gateway token mints

### Audit Foundation
- [x] Minimal audit writer added for append-only `audit_log` inserts
- [x] Sensitive audit payload scrubbing added
- [x] Viewer, gateway ingest-token, and session revoke events audited
- [x] Real HMAC-SHA-256 audit hash chain added for newly written audit rows
- [x] Previous-hash continuity, active key row handling, and verifier helpers added
- [x] Placeholder audit keys now fail closed for audit writes
- [x] Admin audit verification endpoint skeleton added for full-chain read-only verification
- [x] Audit verification range and key-version support added

### Gateway Agent Foundation
- [x] Minimal Python gateway agent package added under `apps/cctv-edge/agent`
- [x] Environment-driven gateway agent configuration added
- [x] Outbound heartbeat and camera status API client added
- [x] One-shot and continuous heartbeat runner added
- [x] Agent tests added for config, client, and runner behavior

### Gateway Control Channel Foundation
- [x] Backend WebSocket skeleton added at `/api/v1/gateway-control/ws`
- [x] Gateway-only WebSocket identity checks added
- [x] Valid gateways receive a connected hello message
- [x] Missing or browser/user identities are rejected with WebSocket close code `1008`
- [x] Backend command signing helpers added
- [x] Edge-agent command verifier added
- [x] Edge-agent one-shot gateway control WebSocket client added
- [x] Backend WebSocket command dispatch scaffold added with signed in-memory commands
- [x] Edge-agent WebSocket command ACK/reject scaffold added
- [x] Gateway heartbeat command fallback scaffold added with signed in-memory commands
- [x] Edge-agent heartbeat pending-command verifier added
- [x] Edge gateway control reconnect/backoff skeleton added
- [x] Command queues, persistence, command execution, and production reconnect policy remain deferred

### Audit Export Skeleton
- [x] Admin audit export endpoint added at `GET /api/v1/admin/audit/export`
- [x] Admin-role enforcement through existing user auth and policy helpers
- [x] Scrubbed audit rows returned as newline-delimited JSON (JSONL)
- [x] Optional inclusive `start_id` and `end_id` range filtering
- [x] `application/x-ndjson` content type with file download disposition
- [x] Fail-closed 503 when HMAC key is placeholder or empty
- [x] Internal chain fields (`hash`, `prev_hash`, `hmac_key_version`) excluded from export
- [x] Export signing, key rotation UI, broad browsing filters, and migrations remain deferred

### Audit Row Listing Endpoint
- [x] Admin audit listing endpoint added at `GET /api/v1/admin/audit`
- [x] Cursor pagination using `AuditLog.id` (newest first, descending)
- [x] Configurable page size via `limit` param (default 50, max 200)
- [x] Optional `action` exact-match filter
- [x] Fail-closed 503 when HMAC key is placeholder or empty
- [x] Internal chain fields excluded from response
- [x] Broad filters, export signing, key rotation UI, and migrations remain deferred

### Backend Command Queue Persistence
- [x] `CommandStatus` enum added (pending, accepted, rejected, expired)
- [x] `GatewayCommandQueue` SQLAlchemy model added with FK to `edge_gateways`
- [x] `enqueue_command` helper creates pending command rows
- [x] `db_command_provider` returns pending/unexpired commands in FIFO order matching hook protocol
- [x] `db_ack_sink` marks commands accepted/rejected with error and timestamp, matching hook protocol
- [x] 9 tests passing for enqueue, provider filtering, ack acceptance/rejection, idempotency, and FIFO ordering
- [x] Alembic migration `0007_gateway_command_tables` creates `gateway_command_queue` and `camera_publish_states`
- [x] Active DB verified at `0007_gateway_command_tables`
- [x] Cleanup job and real CCTV hardware validation remain deferred

### Command Queue App Factory Wiring
- [x] Session-per-call `create_command_provider()` and `create_ack_sink()` wrappers added
- [x] `create_app()` wires hooks automatically when `DATABASE_URL` is configured (not placeholder)
- [x] Tests remain isolated — placeholder URL skips wiring; test overrides take precedence
- [x] 2 integration tests verifying session-per-call provider and sink behavior
- [x] Background cleanup job and real actions remain deferred

### Command Enqueue API Endpoint
- [x] `POST /api/v1/admin/gateways/{gateway_id}/commands` admin-only endpoint added
- [x] Request body: `kind` (required), `payload` (optional dict), `expires_in_seconds` (default 300, 10–3600)
- [x] Gateway existence check with friendly 404
- [x] Returns 201 with command_id, gateway_id, kind, status, expires_at
- [x] 7 tests covering auth (401/403), validation (400/404), and success cases (201 with correct expiry)
- [x] Command listing, cancellation, and real actions remain deferred

### Background Expired-Command Cleanup
- [x] `expire_stale_commands(db)` bulk-updates pending commands past their `expires_at` to `expired`
- [x] Returns count of rows updated
- [x] Idempotent — only touches `pending` rows, skips accepted/rejected/already-expired
- [x] 4 tests covering expired marking, skip unexpired, skip accepted, return count
- [x] Scheduler/cron integration, admin trigger endpoint, and real actions remain deferred

### Command Listing Admin Endpoint
- [x] Admin-only `GET /api/v1/admin/gateways/{gateway_id}/commands` endpoint added
- [x] Cursor pagination using command `issued_at` (newest first, descending)
- [x] Optional `status` filter (pending, accepted, rejected, expired)
- [x] Gateway existence check with 404 `gateway-not-found`
- [x] Returns command details: command_id, gateway_id, kind, payload, status, issued_at, expires_at, acked_at, error
- [x] Response shape: `{"items": [...], "next_cursor": "<uuid>" | null}`
- [x] 7 tests covering auth (401/403), validation (400/404), empty list, ordering, and status filter
- [x] Command cancellation, scheduler/cron, and real actions remain deferred

### Command Cancellation Admin Endpoint
- [x] `cancelled` value added to `CommandStatus` enum
- [x] Admin-only `POST /api/v1/admin/gateways/{gateway_id}/commands/{command_id}/cancel` endpoint added
- [x] Only `pending` commands can be cancelled; non-pending returns 409 `command-not-pending`
- [x] Gateway existence check with 404 `gateway-not-found`
- [x] Command existence check (scoped to gateway) with 404 `command-not-found`
- [x] Returns cancelled command: command_id, gateway_id, kind, status, cancelled_at
- [x] Listing endpoint status filter updated to accept `cancelled`
- [x] 8 tests covering auth (401/403), validation (400/404), conflict (409), and success (200)
- [x] Scheduler/cron, audit logging of cancel, and real actions remain deferred

### Expired-Command Cleanup Admin Endpoint
- [x] Admin-only `POST /api/v1/admin/commands/cleanup` endpoint added
- [x] Calls `expire_stale_commands(db)` to bulk-expire stale pending commands across all gateways
- [x] Returns `expired_count` with the number of commands expired
- [x] Idempotent — returns 0 when nothing to expire
- [x] 4 tests covering auth (401/403), zero-count, and successful expiry
- [x] Periodic background scheduler/cron and audit logging remain deferred

### Gateway Command Audit Logging
- [x] `command.enqueue` audit action added to enqueue endpoint
- [x] `command.cancel` audit action added to cancel endpoint
- [x] `commands.cleanup` audit action added to cleanup endpoint
- [x] All three endpoints use `_record_user_audit_required` (fail-closed)
- [x] Actor resolved via `get_or_create_user` for UUID actor_id
- [x] `request: Request` and `settings: Settings` added to endpoint signatures
- [x] 3 tests verifying audit rows are written on success
- [x] Denial path audit logging remains deferred

### Deep Health Check Implementation
- [x] `/api/v1/admin/health/deep` wired to real `SELECT 1` database connectivity probe
- [x] Returns `"connected"` when DB is reachable, `"error"` on failure
- [x] Overall status `"ok"` when DB connected, `"degraded"` otherwise
- [x] LiveKit and gateway probes now return real status (see Admin Health Probes milestone)
- [x] 11 tests: DB connected/error, LiveKit connected/network-error/non-200, gateway connected/stale/null/disabled, overall degraded

### Real Camera List Endpoint
- [x] `GET /api/v1/cameras` wired to real DB query with Camera + CameraAcl join
- [x] Returns only cameras where the authenticated user has a non-revoked ACL entry
- [x] Excludes retired cameras (`retired_at IS NOT NULL`)
- [x] Cursor pagination using `created_at` (newest first, limit+1 pattern)
- [x] Response includes `camera_id`, `display_name`, `source_type`, `livekit_room_name`, `created_at`
- [x] 7 tests: auth, empty, accessible, retired, revoked, pagination, isolation

### Break-Glass Emergency Access
- [x] `POST /api/v1/admin/break-glass/open` opens a 90-minute emergency admin window
- [x] `POST /api/v1/admin/break-glass/close` closes an active window and returns rotation checklist
- [x] `GET /api/v1/admin/internal/break-glass-status` unauthenticated monitoring endpoint
- [x] `break_glass.py` helper module with `open_break_glass_window`, `close_break_glass_window`, `get_break_glass_status`, `assert_break_glass_active`, `get_active_window`
- [x] Request-time enforcement gate per ADR 0005 — no scheduler, no cron, just `now >= auto_disable_at`
- [x] Open rejects if active window already exists (409)
- [x] Close works on expired-but-unclosed windows (cleanup)
- [x] Audit events: `system.break_glass.opened` and `system.break_glass.closed` with mandatory rotation checklist
- [x] T-52 simulated: clock advance past 90 minutes → access denied
- [x] 12 tests in `test_break_glass.py` covering auth, lifecycle, conflict, status, and T-52
- [x] All 416 backend tests passing; ruff, mypy clean

### Operational Runbooks
- [x] `docs/runbooks/break-glass-runbook.md` — full break-glass lifecycle: open, recover, close, mandatory rotation checklist
- [x] `docs/runbooks/lost-mfa-recovery.md` — admin-mediated MFA reset with optional break-glass path
- [x] `docs/runbooks/idp-outage-recovery.md` — IdP outage detection, break-glass, monitor, close, post-incident review

### SCA/SAST CI Additions
- [x] Semgrep SAST job added (`p/python`, `p/security-audit`, `p/owasp-top-ten` rulesets)
- [x] osv-scanner dependency vulnerability scan job added
- [x] Trivy container image scan job added (CRITICAL + HIGH severity, fail build)
- [x] All three jobs run in parallel; Trivy depends on Docker build

### Admin Camera/Gateway Search & Filter
- [x] `GET /api/v1/admin/gateways` — added `search` param (case-insensitive name substring)
- [x] `GET /api/v1/admin/cameras` — added `search` (display_name), `source_type` (validated enum), `gateway_id` params
- [x] Invalid `source_type` returns 400 `source-type-invalid`
- [x] Combined search + filter works correctly
- [x] 7 search/filter tests in `test_admin_search_enrichment.py`

### Admin List Enrichment
- [x] Gateway list now includes `camera_count` (active assignment count per gateway)
- [x] Camera list now includes `gateway_id` and `acl_count` (active ACL count per camera)
- [x] 5 enrichment tests in `test_admin_search_enrichment.py`
- [x] All 428 backend tests passing; ruff, mypy clean

### LiveKit Fallback Toggle
- [x] `POST /api/v1/admin/livekit/fallback` flips `system_config.media_plane_mode` between `cloud` and `fallback`
- [x] `security/media_plane.py` helper: `get_media_plane_mode`, `set_media_plane_mode`
- [x] Uses existing `SystemConfig` model (key-value store)
- [x] Validates mode enum, rejects no-op same-mode (409)
- [x] Audit events: `system.media_plane.switched_to_fallback` / `system.media_plane.switched_to_primary`
- [x] 6 tests in `test_livekit_fallback.py` covering auth, lifecycle, no-op, and validation

### DPA Export & Signage Attestation
- [x] `POST /api/v1/admin/dpa/export` returns DPA artifact bundle with optional `kinds` filter
- [x] `POST /api/v1/admin/sites/{site_id}/signage-attest` records bystander signage attestation
- [x] Validates `DpaKind` enum (400 on invalid kind)
- [x] Signage creates `DpaArtifact` with `bystander_signage_attestation` kind + SHA-256 hash
- [x] Audit events: `admin.dpa.export`, `admin.signage.attest`
- [x] 10 tests in `test_dpa.py` covering auth, empty, filtered, invalid, and signage lifecycle

### Bus-Factor Documentation
- [x] `docs/runbooks/bus-factor.md` — emergency recovery if sole system owner unavailable
- [x] Covers: sealed-envelope access, password manager delegation, critical env vars, knowledge transfer
- [x] Prevention checklist for proactive bus-factor risk reduction

### User MFA Reset
- [x] `POST /api/v1/admin/users/{user_id}/mfa/reset` records admin-mediated MFA reset
- [x] Self-reset blocked (409 `cannot-reset-own-mfa`)
- [x] Audit event: `admin.user.mfa_reset` with verification evidence
- [x] 5 tests in `test_mfa_reset.py`

- [x] All 454 backend tests passing; ruff, mypy clean

### Admin Camera CRUD Endpoints
- [x] `POST /api/v1/admin/cameras` creates camera with display_name, source_type, livekit_room_name
- [x] Source type validated against `CameraSourceType` enum (CCTV-only)
- [x] Room name uniqueness enforced (409 `room-name-taken`)
- [x] `POST /api/v1/admin/cameras/{id}/acl` grants or revokes user camera ACL
- [x] One active grant per user/camera enforced (409 `acl-already-active`)
- [x] `POST /api/v1/admin/cameras/{id}/disable` soft-deletes camera via `retired_at`
- [x] Already-retired cameras return 409 `camera-already-retired`
- [x] All three endpoints audit-logged via `_record_user_audit_required` (fail-closed)
- [x] 15 tests: auth, validation, conflict, success for all three endpoints

### Camera Events SSE Endpoint
- [x] `GET /api/v1/cameras/events` returns persisted camera events as `text/event-stream`
- [x] Uses Camera + CameraAcl joins so users only receive events for active ACL cameras
- [x] Excludes retired cameras and revoked ACL grants
- [x] Supports exclusive `since` ISO timestamp filtering and `limit` (default 100, max 500)
- [x] Emits `event: camera_event` frames with event_id, camera_id, gateway_id, kind, source, and at
- [x] Invalid `since` returns 400 `since-invalid`
- [x] 7 tests: auth, empty, accessible event, user isolation, revoked/retired exclusions, since filter, invalid since

### Gateway Camera Status Persistence
- [x] `POST /api/v1/gateways/{gateway_id}/cameras/{camera_id}/status` writes `CameraEvent` rows
- [x] Gateway identity must match route gateway ID
- [x] Gateway and camera IDs validated as UUIDs
- [x] Requires enabled gateway, active camera, and active gateway-camera assignment
- [x] Maps status `online`, `offline`, `degraded` to `CameraEventKind`
- [x] Uses `observed_at` when supplied, otherwise server time
- [x] Events use `EventSource.heartbeat` and are visible through the camera events SSE endpoint
- [x] 13 tests: auth, validation, authorization, success persistence, observed_at, SSE visibility

### Admin Gateway Registry And Assignment Endpoints
- [x] `POST /api/v1/admin/gateways` creates enabled gateway registry rows
- [x] `POST /api/v1/admin/gateways/{gateway_id}/disable` disables gateways with `disabled_at`
- [x] `POST /api/v1/admin/gateways/{gateway_id}/cameras` grants/revokes gateway-camera assignments
- [x] Duplicate active assignments return 409 `gateway-camera-assignment-already-active`
- [x] Missing active assignment revoke returns 404 `gateway-camera-assignment-not-found`
- [x] All successful mutations audit-logged: `gateway.create`, `gateway.disable`, `gateway.camera.grant`, `gateway.camera.revoke`
- [x] Assignment grants enable gateway ingest-token and camera status authorization
- [x] 20 tests covering auth, validation, conflicts, audit, disable, assignment, and downstream authorization

### LiveKit Webhook Receiver Foundation
- [x] `POST /api/v1/webhooks/livekit` accepts signed LiveKit webhook events
- [x] Verifies Authorization JWT with active LiveKit API key/secret and raw-body SHA-256 claim
- [x] Enforces a 60-second `createdAt` timestamp window
- [x] Rejects duplicate webhook JWT signatures through `webhook_replay_cache`
- [x] Maps `track_published`, `track_unpublished`, `room_finished`, and `participant_connection_aborted` to persisted `CameraEvent` rows
- [x] Webhook-created events use `EventSource.livekit_webhook` and are visible through camera events SSE for ACL viewers
- [x] Writes system audit rows for accepted webhooks and stale/duplicate replay rejections
- [x] 9 tests covering authorization, signature/hash validation, replay, audit, event persistence, SSE visibility, unknown room handling, and preflight rejection

### Room-Presence-Driven Gateway Publish Commands
- [x] LiveKit `participant_joined` webhooks enqueue `gateway.command.start_publish` for known camera rooms with enabled gateway assignments
- [x] Start commands mint short-lived gateway publish tokens and record `StreamGrant` rows
- [x] LiveKit `participant_left` with `participant_count == 0` and `room_finished` enqueue `gateway.command.stop_publish`
- [x] Unknown rooms, nonzero participant counts, disabled gateways, and revoked/missing assignments do not enqueue commands
- [x] Publish command audit actions added: `livekit.publish.start_enqueued`, `livekit.publish.stop_enqueued`, `livekit.publish.command_skipped`
- [x] Enqueued commands flow through the existing signed heartbeat/WebSocket command provider path
- [x] 10 new tests covering start/stop enqueue, stream grants, skip paths, signed heartbeat fallback, and fail-closed token minting

### Edge Command Executor
- [x] `CommandExecutor` added to dispatch verified commands by kind (`start_publish`, `stop_publish`)
- [x] `MediaController` protocol defined with async `start_publish` / `stop_publish` methods
- [x] `StubMediaController` added for testing (logs calls, returns success, no real process management)
- [x] `FailingMediaController` added for testing error paths
- [x] `PublishState` tracker added for in-memory camera publish session tracking (start, stop, idempotency)
- [x] `GatewayControlClient` wired to execute commands after verification via async `handle_message`
- [x] `HeartbeatRunner` wired to execute commands after verification via `asyncio.run()`
- [x] Executor rejects unknown command kinds, incomplete payloads, and media controller failures
- [x] Idempotent: duplicate `start_publish` accepted without re-calling controller; `stop_publish` for non-publishing camera accepted silently
- [x] 14 new tests in `test_executor.py` covering start/stop, idempotency, validation, unknown kinds, and controller failures
- [x] Existing control and runner tests updated with full command payloads and async `handle_message`
- [x] All 57 edge-agent tests passing; mypy, ruff, and compileall clean

### Backend Publish State And Stop Grace Timers
- [x] `CameraPublishStatus` enum added (`idle`, `starting`, `publishing`, `stop_pending`)
- [x] `CameraPublishState` SQLAlchemy model added for per-camera publish lifecycle tracking
- [x] `gateway.publish_state` helper module added for start, schedule-stop, cancel-stop, immediate-stop, and due-stop processing
- [x] `participant_joined` now cancels pending stops or enqueues `start_publish` only when not already starting/publishing
- [x] Duplicate `participant_joined` events no longer enqueue duplicate start commands
- [x] `participant_left` with zero viewers now schedules a delayed stop instead of immediately enqueueing `stop_publish`
- [x] `room_finished` still enqueues immediate `stop_publish` and resets publish state
- [x] Deterministic `enqueue_due_publish_stops()` helper added for scheduler/cron integration later
- [x] Audit actions added for `livekit.publish.stop_scheduled` and `livekit.publish.stop_cancelled`
- [x] LiveKit webhook tests expanded to 23 cases covering start idempotency, stop scheduling, stop cancellation, due-stop processing, and immediate room-finished stop
- [x] Backend verification clean: 232 tests passing; mypy, ruff, and compileall clean

### Privacy Notice And Admin User Listing APIs
- [x] `GET /api/v1/privacy/notice` returns the current operator privacy notice and the caller's acceptance state
- [x] `POST /api/v1/privacy/notice/accept` records the current notice acceptance using `PrivacyNoticeAcceptance`
- [x] Privacy notice acceptance is idempotent for the current version
- [x] Successful first acceptance writes `privacy.notice.accepted` audit rows and fails closed on audit write failure
- [x] Wrong notice versions return 409 `privacy-notice-version-mismatch`
- [x] `GET /api/v1/admin/users` lists safe user fields for admins only
- [x] Admin user listing supports `limit`, `cursor`, and exact `email` filtering
- [x] Admin user listing returns role names via `UserRole`/`Role` without exposing IdP subject, sessions, or tokens
- [x] 11 tests added for auth, response shape, acceptance recording, idempotency, audit, filtering, and pagination
- [x] Backend verification clean: 243 tests passing; mypy, ruff, and compileall clean

### Scheduler Jobs: Admin Maintenance Endpoint
- [x] `POST /api/v1/admin/jobs/run-maintenance` runs both `expire_stale_commands` and `enqueue_due_publish_stops` in a single admin call
- [x] Returns `{ "expired_commands": N, "stops_enqueued": N }`
- [x] Writes `admin.maintenance.run` audit event with both counts
- [x] Existing `POST /api/v1/admin/commands/cleanup` kept for backward compat
- [x] 6 tests added for auth, role, empty run, expired commands, due publish stops, and audit

### Admin User Management
- [x] `POST /api/v1/admin/users/{user_id}/role` grants or revokes a role for a user
- [x] `POST /api/v1/admin/users/{user_id}/disable` disables a user and revokes all active sessions
- [x] Both endpoints write audit events (`admin.user.role.granted`, `admin.user.role.revoked`, `admin.user.disabled`)
- [x] Error handling for user-not-found, role-not-found, role-already-granted, role-not-granted, user-already-disabled
- [x] `revoke_all_user_sessions` bulk helper added to `sessions.py`
- [x] 13 tests added for auth, role, grant/revoke, disable, session revocation, and audit

### Gateway Credential Rotation
- [x] `POST /api/v1/admin/gateways` now issues a one-time `service_token` and stores only its SHA-256 hash
- [x] `POST /api/v1/admin/gateways/{gateway_id}/rotate-credential` rotates the gateway service token and immediately invalidates the old token
- [x] Plaintext service tokens are returned only in create/rotate responses and are never stored or audited
- [x] `service_tokens.py` added for generation, hashing, and constant-time verification
- [x] `gateway.credential.rotated` audit event added with redacted credential-sensitive fields
- [x] 9 tests added for token utilities, one-time create issuance, rotation, disabled/missing gateway errors, audit, and invalidation

### Gateway Token Verification
- [x] Gateway API requests can authenticate with `x-panoptix-gateway-id` and `Authorization: Bearer <service_token>`
- [x] Backend verifies bearer tokens against `EdgeGateway.service_token_hash`
- [x] Disabled, unknown, invalid, missing-token, missing-hash, and wrong-token cases fail closed
- [x] Valid service token resolves to a gateway `Principal`
- [x] Dev gateway header auth remains unchanged for local-first tests
- [x] 9 tests added for production-style gateway service-token authentication

### Command Denial Audit Logging
- [x] Heartbeat gateway mismatch and command-signing failures write best-effort audit events
- [x] Camera status disabled, missing-camera, and unassigned denial paths write best-effort audit events
- [x] Gateway control WebSocket unauthenticated, signing-failure, invalid-ACK, ACK gateway-mismatch, and not-applied ACK paths write best-effort audit events
- [x] `db_ack_sink` now returns explicit `AckSinkResult` outcomes for applied, missing command ID, invalid command ID, and command-not-found cases
- [x] 11 tests added/expanded for denial audit coverage and observable ACK sink ignored outcomes

### Audit Export Signing
- [x] `GET /api/v1/admin/audit/export` now returns a self-contained signed JSON response
- [x] Export response includes `format`, `manifest`, and exported audit `items`
- [x] Manifest includes row count, first/last row IDs, canonical content SHA-256, signature algorithm, key version, and HMAC-SHA256 signature
- [x] Signature covers a canonical unsigned manifest containing the exported item digest
- [x] Exported items omit internal audit-chain fields (`hash`, `prev_hash`, `hmac_key_version`)
- [x] Existing audit export tests updated to verify digest/signature, bounds, empty exports, scrubbed payloads, and fail-closed invalid key behavior

### Browser/Admin Security Hardening
- [x] Added signed CSRF tokens bound to non-dev browser sessions
- [x] Unsafe browser/admin routes now require matching CSRF cookie and `x-panoptix-csrf-token` header
- [x] Gateway HTTP APIs, gateway WebSocket, LiveKit webhook, health checks, safe methods, and dev auth remain outside browser CSRF enforcement
- [x] Added baseline API security headers on success and problem-detail responses
- [x] Added 11 tests covering CSRF helpers, browser CSRF enforcement, dev-auth compatibility, and security headers

### Production Maintenance Scheduler
- [x] Added reusable one-shot maintenance job logic shared by admin-triggered and scheduled maintenance
- [x] Added disabled-by-default in-process scheduler loop controlled by `ENABLE_MAINTENANCE_SCHEDULER`
- [x] Added `MAINTENANCE_INTERVAL_SECONDS` setting with safe lower bound
- [x] Scheduler starts only with an enabled flag and non-placeholder database URL
- [x] Scheduled runs write system audit events while admin-triggered runs keep `admin.maintenance.run`
- [x] Added scheduler tests for stale command expiry, due publish stops, audit rows, startup gating, and cancellation

### Gateway Reconnect Supervision
- [x] Added reconnect telemetry for retryable failures, sleep delays, and stopped reason
- [x] Added bounded gateway control supervisor cycles for repeated reconnect attempts
- [x] Preserved fail-closed command validation during reconnect/supervision
- [x] Updated `--control-loop-once` to use the supervisor path
- [x] Added edge-agent tests for retry telemetry, repeated cycles, stop-after-success, non-retryable stop, consecutive failures, invalid cycles, and cancellation

### Synthetic RTSP Test Source
- [x] Added edge-agent synthetic RTSP settings for RTSP URL, video size, frame rate, and audio frequency
- [x] Added safe FFmpeg argument-list builder for `testsrc` video and `sine` audio
- [x] Added validation that rejects non-RTSP URLs, URL credentials, invalid dimensions, and invalid rates
- [x] Added tests that do not require FFmpeg or mediamtx to be installed
- [x] Documented local synthetic source expectations and preserved the CCTV-only invariant

### mediamtx Runtime Configuration
- [x] Added local-only `mediamtx.local.yml` scaffold for the synthetic RTSP source
- [x] Added edge-agent helper for generating and validating safe mediamtx local defaults
- [x] Enforced loopback-only RTSP/API bindings and rejected wildcard, WAN, and camera-VLAN API bindings
- [x] Added tests that validate the checked-in config without launching mediamtx
- [x] Documented that real mediamtx process supervision remains a later milestone

### mediamtx Process Management
- [x] Added safe mediamtx process argument-list builder
- [x] Added injectable lifecycle manager for start, stop, status, double-start, timeout, and failure behavior
- [x] Added fake-process tests that do not require mediamtx to be installed
- [x] Preserved the stub media controller boundary; real LiveKit publishing remains future work
- [x] Documented that production Docker/systemd supervision remains a later milestone

### LiveKit Publisher Foundation
- [x] Added fakeable edge-agent LiveKit publisher/client protocol and request model
- [x] Added `LiveKitMediaController` implementing the existing media-controller boundary
- [x] Validates LiveKit URL, source RTSP URL, token, camera ID, and room before adapter calls
- [x] Added SDK-unavailable default client that fails clearly without requiring LiveKit credentials or packages
- [x] Added tests for start/stop, idempotency, validation, adapter failures, and command-executor integration

### Synthetic End-to-End Publish Dry Run
- [x] Added fake-only edge-agent dry-run harness for signed start/stop publish commands
- [x] Proved `CommandExecutor` drives `LiveKitMediaController` with the synthetic RTSP source URL
- [x] Added optional fake mediamtx lifecycle hooks without launching mediamtx
- [x] Added tests for happy path, duplicate start idempotency, stop-only safety, tampered/wrong-gateway rejection, publisher failures, and mediamtx lifecycle failures
- [x] Preserved no-real-services invariant: no LiveKit SDK, real camera, FFmpeg, mediamtx process, browser publisher, or external account required

### Real LiveKit SDK Media Adapter
- [x] Added optional `LiveKitSdkPublisherClient` behind the existing edge-agent publisher boundary
- [x] Kept the LiveKit SDK lazy/optional with a `livekit` package extra and `livekit-sdk-unavailable` missing-SDK failure
- [x] Added SDK room connect/disconnect lifecycle tracking by camera ID with fixed, token-safe error codes
- [x] Added injectable media-session seam that receives the validated CCTV `source_url` without implementing RTSP frame decode yet
- [x] Added fake SDK/session tests for start, stop, cleanup, failure, idempotent unknown stop, and token non-disclosure
- [x] Preserved CCTV-only invariant: no browser, webcam, phone, frontend, real camera, or external-account publishing path was introduced

### Frame-to-LiveKit Track Bridge
- [x] Added `LiveKitVideoFrame` and fakeable video frame-source abstractions for CCTV media frames
- [x] Added `LiveKitVideoTrackMediaSession` that creates a LiveKit video source, local video track, and publish options
- [x] Added async frame pumping from injected frame sources into the SDK video source
- [x] Added cleanup for frame-pump cancellation, track unpublish, video-source close, and frame-source close
- [x] Added fake SDK/frame-source tests for track publish, frame capture, source URL handoff, cleanup, failure containment, and token non-disclosure
- [x] Preserved no-real-services invariant: FFmpeg RTSP decoding, real LiveKit Cloud smoke testing, real cameras, and credentials remain future work

### FFmpeg RTSP Frame Source
- [x] Added `FfmpegRtspFrameSource` behind the existing `LiveKitVideoFrameSource` protocol
- [x] Added safe FFmpeg argument builder for RTSP/RTSPS input to raw RGBA stdout output
- [x] Validates source URL scheme, URL credentials, dimensions, frame rate, binary name, and stop timeout
- [x] Added async frame iteration that reads exact RGBA frames and assigns timestamps from configured FPS
- [x] Added idempotent cleanup with terminate and timeout-kill behavior
- [x] Added fake-process tests for args, validation, frame yield, EOF, short reads, missing stdout, close, and timeout kill
- [x] Preserved no-real-services invariant: no real FFmpeg, camera, LiveKit SDK, credentials, or browser publishing required

### Synthetic FFmpeg-to-LiveKit Local Smoke Wiring
- [x] Added opt-in factory wiring from validated `LiveKitPublishRequest.source_url` to `FfmpegRtspFrameSourceConfig`
- [x] Added helper that builds a `FfmpegRtspFrameSource` and `LiveKitVideoTrackMediaSession` for the SDK publisher media-session seam
- [x] Added fake-only synthetic smoke helper composing signed start/stop commands, `LiveKitSdkPublisherClient`, fake SDK room/track objects, and fake FFmpeg stdout
- [x] Added tests for config handoff, opt-in publisher construction, fake frame publish, cleanup, and token-safe start failure
- [x] Preserved opt-in behavior: default controller/publisher behavior still does not launch FFmpeg or require LiveKit credentials

### Real Local FFmpeg/LiveKit Smoke Scaffold
- [x] Added `smoke_config.py` with fail-closed environment variable validation for manual smoke tests
- [x] Added `smoke_ffmpeg_livekit.py` with async smoke runner, standalone HS256 JWT token minting, and structured result reporting
- [x] Added `--smoke-ffmpeg-livekit` CLI flag that bypasses backend config requirements and runs against real local FFmpeg/LiveKit
- [x] Smoke config validates LiveKit URL scheme, RTSP URL scheme/credentials, API secret minimum length, FFmpeg binary PATH presence, and duration bounds
- [x] Smoke runner mints a short-lived publish-only LiveKit token locally without requiring the backend API
- [x] Token minting uses a standalone HS256 JWT encoder to avoid requiring PyJWT on the edge agent
- [x] Added 20 smoke config validation tests and 9 smoke runner tests using fake SDK/FFmpeg objects
- [x] No real credentials, real LiveKit Cloud accounts, or real cameras are committed to the repo
- [x] Existing 159 tests remain unchanged and passing; total test count is now 187
- [x] Preserved CCTV-only invariant: browser/viewer clients still never publish media

### Live Media Controller Wiring
- [x] Added `media_factory.py` with `build_media_controller(config)` factory that selects `StubMediaController` or `LiveKitMediaController` based on `PANOPTIX_MEDIA_PUBLISHER_MODE`
- [x] Added `media_publisher_mode`, `media_source_url`, `media_width`, `media_height`, `media_frame_rate`, and `media_ffmpeg_binary` to `AgentConfig`
- [x] Updated `cli.py` to build the media controller once and pass a shared `CommandExecutor` to both `HeartbeatRunner` and `GatewayControlClient`
- [x] When `livekit-ffmpeg` mode is set, the factory builds the real `LiveKitMediaController` backed by `LiveKitSdkPublisherClient` and `FfmpegVideoTrackMediaSessionFactory`
- [x] When the LiveKit SDK is unavailable, the factory falls back to `StubMediaController` with an error marker (no crash)
- [x] `PANOPTIX_MEDIA_SOURCE_URL` validation only applies when mode is `livekit-ffmpeg` (stub mode skips it)
- [x] Added 12 media factory tests covering stub default, livekit-ffmpeg wiring with fakes, SDK fallback, config validation
- [x] Existing 187 tests remain unchanged and passing; total test count is now 199
- [x] Default behavior unchanged: `stub` mode is the default, no real services required
- [x] Preserved CCTV-only invariant: browser/viewer clients still never publish media

### CSP, CORS, and Security Headers Hardening
- [x] Expanded `headers.py` with full v4-plan security headers per sections 16.5 and 16.13
- [x] Added `Strict-Transport-Security` with HSTS preload (2-year max-age, includeSubDomains)
- [x] Added `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Resource-Policy: same-origin`
- [x] Expanded `Permissions-Policy` to include all five directives: `camera=(), microphone=(), geolocation=(), autoplay=(self), display-capture=()`
- [x] Added dynamic CSP `connect-src` that includes the active LiveKit origin based on `LIVEKIT_MODE` (cloud or fallback)
- [x] CSP includes `media-src blob:` for LiveKit SDK, `form-action 'self'`, and omits placeholder LiveKit URLs
- [x] Added per-route CORS policy: browser routes get exact origin + credentials; gateway and webhook routes get NO CORS headers
- [x] Server and X-Powered-By banners stripped from all responses
- [x] Added 8 new security tests for HSTS, COOP/CORP, dynamic CSP, CORS per-route policy, and media-src
- [x] All 315 backend tests passing; existing tests updated for expanded header assertions
- [x] Preserved CCTV-only invariant: `Permissions-Policy: camera=(), microphone=()` is the technical enforcement of Inv 5

### Session Idle/Absolute TTL Enforcement
- [x] Added `SESSION_IDLE_TIMEOUT_SECONDS` (default 900 = 15 min) and `SESSION_ABSOLUTE_TIMEOUT_SECONDS` (default 28800 = 8 h) to `Settings`
- [x] Added `is_session_expired()` helper to `sessions.py` that checks both idle and absolute TTLs
- [x] Absolute timeout checked first (takes precedence) — session older than 8 h is always expired
- [x] Idle timeout uses `last_seen_at` (falls back to `created_at`) — 15 min inactivity expires the session
- [x] Wired TTL enforcement into `require_authenticated_user` dependency — expired sessions auto-revoked and return 401
- [x] `touch_session()` already updates `last_seen_at` on each authenticated request, resetting the idle timer
- [x] Expired sessions are revoked in DB before returning 401 (fail-closed)
- [x] Added 5 new TTL tests: valid session, idle expiry, absolute expiry, idle timer reset via touch, absolute precedence
- [x] All 320 backend tests passing; existing tests unchanged
- [x] Ruff and mypy clean

### App-Level Rate Limiting
- [x] Created `security/rate_limit.py` with in-memory sliding-window `RateLimiter` (per-key, thread-safe)
- [x] Added `RateLimitConfig` dataclass and singleton `get_rate_limiter()` for shared state
- [x] Added `ProblemDetail` support for response headers (enables `Retry-After` on 429)
- [x] Wired rate limit into viewer token endpoint (`GET /cameras/{id}/view-token`) — keyed by `viewer-token:{user_id}`
- [x] Wired rate limit into gateway ingest token endpoint (`POST /gateways/{id}/ingest-token`) — keyed by `gateway-ingest:{gateway_id}`
- [x] Rate-limited requests return `429 Too Many Requests` with `Retry-After` header
- [x] Rate-limited requests write audit events: `viewer.token.rate_limited` and `gateway.ingest.rate_limited`
- [x] Added 4 configurable settings: `RATE_LIMIT_VIEWER_TOKEN_MAX` (30/min), `RATE_LIMIT_VIEWER_TOKEN_WINDOW` (60s), `RATE_LIMIT_GATEWAY_INGEST_MAX` (20/min), `RATE_LIMIT_GATEWAY_INGEST_WINDOW` (60s)
- [x] Added 7 unit tests for limiter core (allow, block, independent keys, reset, window expiry, remaining, retry-after)
- [x] Added 2 integration tests for viewer token rate limiting with full DB setup
- [x] All 329 backend tests passing; existing tests unchanged
- [x] Ruff and mypy clean

### User Disable → LiveKit Participant Kill
- [x] Created `security/livekit_rooms.py` with `remove_user_participants()` — calls LiveKit Twirp API via httpx
- [x] Mints short-lived admin JWT for LiveKit server authentication
- [x] Derives HTTP URL from configured WSS URL (wss:// → https://)
- [x] Lists participants per room, matches `viewer:{user_id}:*` identities, removes them
- [x] Fail-open design: errors are collected and audited but do not block the disable flow
- [x] Gracefully skips when LiveKit credentials are placeholders
- [x] Wired into `admin_disable_user`: after session revocation, queries user's camera ACLs → room names → removes participants
- [x] Response includes `participants_removed` and `participant_errors` fields
- [x] Audit event `admin.user.disabled` payload includes participant removal results
- [x] Added 12 tests: URL derivation, admin token, placeholder skip, success, multi-room, non-viewer filtering, error handling, and router ACL-room integration
- [x] Updated existing disable test to assert new response fields
- [x] All 341 backend tests passing
- [x] Ruff, mypy, and compileall clean

### Real LiveKit Cloud Smoke Checklist
- [x] Added LiveKit Cloud-specific manual smoke checklist to `MANUAL_TESTING.md`
- [x] Documented preflight checks for optional LiveKit SDK, FFmpeg, mediamtx, and synthetic RTSP source
- [x] Documented session-only PowerShell environment variable usage for real LiveKit Cloud values
- [x] Added explicit secret-handling rules and post-run environment cleanup commands
- [x] Added smoke result template that captures host/room/result metadata without credentials
- [x] Clarified this is a runbook/checklist milestone; real cloud smoke is not marked passed until manually run with real temporary credentials

### Real LiveKit Cloud Smoke Execution
- [x] Ran `python -m panoptix_edge_agent.cli --smoke-ffmpeg-livekit` against LiveKit Cloud
- [x] Used synthetic RTSP source `rtsp://127.0.0.1:8554/synthetic-camera-1`
- [x] Published to LiveKit host `panoptix-4feff0dr.livekit.cloud`, room `panoptix-smoke-test`
- [x] Smoke result: `smoke: PASSED`, `frames_published: 1`, `duration: 38.84s`, `cleanup_ok: True`
- [x] Observed transient LiveKit signal retry/timeout logs, but final smoke result passed and cleanup succeeded
- [x] Cleared LiveKit Cloud smoke secrets from the shell after the run
- [x] No API key, API secret, generated JWT, or credential material committed

### Backend-Controlled Gateway Publish Smoke
- [x] Applied `0007_gateway_command_tables` and verified `gateway_command_queue` and `camera_publish_states`
- [x] Created a gateway, synthetic camera, and active gateway-camera assignment through backend admin APIs
- [x] Minted a backend gateway ingest token and enqueued `gateway.command.start_publish`
- [x] Edge agent received the command over the gateway control WebSocket and ran in `livekit-ffmpeg` mode
- [x] Latest command status verified as `accepted` with `acked_at` populated and no error
- [x] First command rejected due to LiveKit `invalid token`; a fresh short-lived token/command resolved the issue
- [x] No LiveKit secrets, generated JWTs, or gateway publish tokens committed

### Production Gateway Supervision
- [x] Added `python -m panoptix_edge_agent.cli --supervise` supervisor entrypoint
- [x] Added `GatewayRuntimeSupervisor` to coordinate heartbeat, outbound gateway-control supervision, optional local `mediamtx` startup, and cleanup
- [x] Added safe config toggles: `PANOPTIX_SUPERVISE_MEDIAMTX`, `PANOPTIX_MEDIAMTX_BINARY`, and `PANOPTIX_MEDIAMTX_CONFIG_PATH`
- [x] Preserved safe defaults: media publisher mode remains `stub`, and `mediamtx` supervision remains disabled unless explicitly enabled
- [x] Added fake-based tests for supervisor success/failure, mediamtx cleanup, config parsing, and CLI dispatch
- [x] Edge verification passed: `210 passed`, ruff clean, mypy clean, compileall passed

### Production Host/Service Runbooks
- [x] Added docs-only `docs/runbooks/edge-gateway-service.md`
- [x] Covered Docker, Linux systemd, and Windows/NSSM service operation shapes
- [x] Documented environment-file, startup, shutdown, restart, logging, health verification, rollback, and incident-response checklists
- [x] Preserved zero-inbound-WAN-port invariant and banned WAN exposure for RTSP, HLS, WebRTC, RTMP, and mediamtx API listeners
- [x] Linked the runbook from the docs index and manual testing docs

### Linux Systemd Service Templates
- [x] Added `docs/runbooks/templates/cctv-gateway.service.example` systemd unit file with hardening settings
- [x] Added `docs/runbooks/templates/gateway.env.example` environment file with placeholder-only values
- [x] Added `docs/runbooks/templates/README.md` with usage, security rules, and scope
- [x] Linked templates from `docs/runbooks/edge-gateway-service.md` Linux systemd section
- [x] Added template review section to `MANUAL_TESTING.md`
- [x] Templates contain only placeholder values; no real secrets committed
- [x] Docker Compose, Dockerfile, and Windows/NSSM templates remain deferred

### Docker And Windows Service Templates
- [x] Added `docs/runbooks/templates/Dockerfile.edge-agent.example` with non-root user and no EXPOSE
- [x] Added `docs/runbooks/templates/docker-compose.edge-agent.example.yml` with no ports, external env, read-only FS
- [x] Added `docs/runbooks/templates/nssm-install.example.ps1` Windows/NSSM service install script with placeholder values
- [x] Linked Docker templates from `docs/runbooks/edge-gateway-service.md` Docker section
- [x] Linked Windows templates from `docs/runbooks/edge-gateway-service.md` Windows/NSSM section
- [x] Updated `docs/runbooks/templates/README.md` with all template files
- [x] Updated template review section in `MANUAL_TESTING.md` with Docker and Windows verification checks
- [x] All templates contain only placeholder values; no real secrets committed

### Cloudflare Production Setup Prep
- [x] Added docs-only `docs/runbooks/cloudflare-production-setup.md`
- [x] Documented required Access application boundaries for dashboard, admin, and gateway audiences
- [x] Documented required production environment variables and placeholder-only secret handling
- [x] Captured JWT verification expectations for issuer, audiences, JWKS, required claims, and clock skew
- [x] Preserved browser/admin versus gateway identity split and fail-closed gateway credential rules
- [x] Documented origin-binding, trusted-header, same-domain routing, manual validation, approval, and rollback gates
- [x] Linked the runbook from `docs/index.md`
- [x] Added Cloudflare prep review checks to `MANUAL_TESTING.md`

### Production Auth Guardrail Validation
- [x] Added `Settings.validate_production_guardrails()` for staging/production fail-fast validation
- [x] App startup now rejects unsafe staging/production config before FastAPI starts
- [x] Guardrails reject `ALLOW_DEV_AUTH=True` outside development
- [x] Guardrails reject placeholder Cloudflare Access, session, audit, database, gateway token, and command signing values
- [x] Added focused config tests for development defaults, unsafe production/staging defaults, safe populated config, and app startup failure
- [x] Updated existing auth/security tests to supply safe non-placeholder production settings where needed
- [x] Updated Cloudflare setup and manual testing docs with guardrail validation expectations
- [x] Verified focused tests, ruff, and mypy pass

### Railway/Neon Staging Deployment Prep
- [x] Created `docs/runbooks/railway-neon-staging-prep.md` with full staging prep runbook
- [x] Documented Railway service plan for `cctv-api` and future `cctv-web`
- [x] Documented Neon staging database setup, role separation, connection strings, and SSL
- [x] Documented required environment variable groups with guardrail cross-references
- [x] Documented migration safety (expand/contract pattern, role separation)
- [x] Documented staging smoke validation checklist and release gates
- [x] Created `docs/runbooks/templates/railway-api.env.example` with placeholder-only staging env
- [x] Created `docs/runbooks/templates/neon-staging-checklist.md` for database provisioning
- [x] Updated `docs/index.md`, `docs/implementation/deployment-guide.md`, `docs/runbooks/deploy-rollback.md`, and templates README
- [x] Added staging prep review section to `MANUAL_TESTING.md`

---

## Next Steps (In Order)

### 1. Real camera onboarding
Connect a real CCTV camera to the gateway using the per-camera credential file and test live FFmpeg-to-LiveKit publishing end-to-end.

### 2. Admin dashboard frontend
Work with the frontend coworker to build the admin camera management and user management UI.

---

## Completed Milestones

### Admin Health Probes ✅
- [x] `GET /api/v1/admin/health/deep` now returns real LiveKit connectivity and gateway heartbeat-age status
- [x] LiveKit probe calls `ListRooms` Twirp endpoint with 5s timeout; returns `connected`, `not_configured`, or `error`
- [x] Gateway probe queries enabled gateways and checks `last_seen_at` against `GATEWAY_STALE_THRESHOLD_SECONDS` (default 60s)
- [x] Gateway probe returns `connected`, `no_gateways`, `stale`, or `error`
- [x] Overall status `"ok"` only when DB connected AND (LiveKit connected/not_configured) AND (gateway connected/no_gateways)
- [x] `GATEWAY_STALE_THRESHOLD_SECONDS` setting added to `config.py`
- [x] Gateway heartbeat endpoint now updates `EdgeGateway.last_seen_at` (fail-open)
- [x] 8 new health tests + 1 gateway heartbeat `last_seen_at` test
- [x] All 404 backend tests passing; ruff, mypy clean

### Admin Dashboard Summary Endpoint ✅
- [x] `GET /api/v1/admin/dashboard` — returns aggregated system counts in a single admin call
- [x] Counts: cameras (total/active/retired), gateways (total/enabled/disabled), users (total/active/disabled), commands (pending), publishing (active)
- [x] Admin-role enforcement via `require_role(principal, "admin")`
- [x] Uses `select(func.count()).select_from(Model).where(...)` pattern for efficient DB aggregation
- [x] 6 new tests in `test_admin_dashboard.py`
- [x] All 395 backend tests passing; ruff, mypy clean

### Admin Camera & Gateway Listing Endpoints ✅
- [x] `GET /api/v1/admin/gateways` — list all gateways with cursor pagination and optional `status` filter
- [x] `GET /api/v1/admin/gateways/{gateway_id}` — gateway detail with `camera_count` from active assignments
- [x] `GET /api/v1/admin/cameras` — list all cameras with cursor pagination and optional `include_retired` filter
- [x] `GET /api/v1/admin/cameras/{camera_id}` — camera detail with `acl_count` from active ACLs
- [x] Sensitive fields (`service_token_hash`) excluded from gateway responses
- [x] 8 new gateway list+detail tests in `test_admin_gateways.py`
- [x] 8 new camera list+detail tests in `test_cameras.py`
- [x] All 389 backend tests passing; ruff, mypy clean

### Admin Camera & Gateway Lifecycle Update Endpoints ✅
- [x] `PATCH /api/v1/admin/cameras/{camera_id}` — update camera display/source metadata without accepting RTSP credentials
- [x] `POST /api/v1/admin/cameras/{camera_id}/enable` — re-enable a retired camera while preserving existing ACL enforcement
- [x] `PATCH /api/v1/admin/gateways/{gateway_id}` — update gateway display metadata without rotating credentials
- [x] `POST /api/v1/admin/gateways/{gateway_id}/enable` — re-enable a disabled gateway without automatically restoring revoked assignments
- [x] Successful lifecycle changes write `camera.update`, `camera.enable`, `gateway.update`, and `gateway.enable` audit rows with before/after payloads
- [x] Focused camera/gateway lifecycle tests pass; frontend UI now has V1 wiring and local same-origin smoke evidence

### Camera Disable → Kill Viewer Participants ✅
- [x] Added `remove_room_viewers()` to `security/livekit_rooms.py` — removes all `viewer:*` participants from a camera's single LiveKit room
- [x] Added `DisableCameraResponse` Pydantic model with `participants_removed` and `participant_errors` fields
- [x] Updated `disable_camera()` handler to call `remove_room_viewers()` with the camera's `livekit_room_name`
- [x] Audit event `camera.disable` payload now includes `participants_removed` and `participant_errors`
- [x] 7 new unit tests in `test_livekit_rooms.py` for room viewer removal (placeholder skip, success, gateway filtering, multi-viewer, error handling, non-200, empty room)
- [x] 3 new integration tests in `test_cameras.py` (placeholder creds, mock removal, no viewers)
- [x] Updated existing `test_disable_camera_succeeds` to assert new response fields
- [x] All 373 backend tests passing; ruff, mypy clean

### Gateway Disable → Kill Publisher Participants ✅
- [x] Added `remove_gateway_participants()` to `security/livekit_rooms.py` — mirrors `remove_user_participants()` for gateway publisher identity prefix `gateway:{gateway_id}:`
- [x] Same fail-open pattern: errors collected but do not block the disable flow
- [x] Same placeholder credential skip behavior
- [x] Added `DisableGatewayResponse` Pydantic model with `participants_removed` and `participant_errors` fields
- [x] Updated `disable_gateway()` handler to query assigned camera rooms via `GatewayCameraAssignment` join and call `remove_gateway_participants()`
- [x] Audit event `gateway.disable` payload now includes `participants_removed` and `participant_errors`
- [x] 7 new unit tests in `test_livekit_rooms.py` for gateway participant removal (placeholder skip, success, viewer filtering, multi-room, error handling, non-200, empty rooms)
- [x] 3 new integration tests in `test_admin_gateways.py` (placeholder creds, mock removal with room filtering, no assignments)
- [x] Updated existing `test_disable_gateway_succeeds_and_prevents_enabled_lookup` to assert new response fields
- [x] All 363 backend tests passing; ruff, mypy clean

### Per-Camera RTSP Credential Handling ✅
- [x] Created `camera_credentials.py` with `CameraCredential` frozen dataclass, `CameraCredentialStore`, `load_camera_credentials()`, `build_rtsp_url()`, `build_authenticated_rtsp_url()`, `check_credential_file_permissions()`, and `CredentialFileError`
- [x] Added `PANOPTIX_CAMERA_CREDENTIALS_PATH` env var to `AgentConfig`
- [x] Extended `MediaController` protocol with optional `source_url`, `rtsp_username`, `rtsp_password`, `rtsp_transport` parameters
- [x] Added per-camera credential resolution to `CommandExecutor` — resolves URL from credential store before calling media controller
- [x] Missing camera in credential store rejects with `camera-credentials-not-found`; no credential store = backward compatible
- [x] Extended `FfmpegRtspFrameSourceConfig` with optional `rtsp_username`/`rtsp_password`/`rtsp_transport` — authenticated URL composed only in `args()` subprocess boundary
- [x] Wired credentials through `LiveKitPublishRequest`, `LiveKitMediaController`, and `FfmpegVideoTrackMediaSessionFactory`
- [x] CLI loads and validates credential file at startup (fail-closed: agent refuses to start if file is missing/unreadable/invalid)
- [x] `__repr__` redacts passwords in `CameraCredential`, `FfmpegRtspFrameSourceConfig`, and `LiveKitPublishRequest`
- [x] File permission check (0600 on Linux, skip on Windows)
- [x] Created `cameras.json.example` template, updated `gateway.env.example`, agent README, and project docs
- [x] 28 new tests in `test_camera_credentials.py` covering load, resolve, URL assembly, validation, repr redaction, permissions, and config integration
- [x] 3 new tests in `test_executor.py` for credential store resolution, missing camera rejection, and backward compatibility
- [x] All 239 edge-agent tests passing; ruff, mypy, and compileall clean
- [x] Credential threat model preserved: camera RTSP credentials live ONLY on the gateway and never reach the backend API, browser, or audit logs

### Admin Role Bootstrap ✅
- [x] Seeded `admin` and `viewer` roles into the Neon `roles` table (seed migration `0005` had not been applied)
- [x] Assigned both `admin` and `viewer` roles to `ivanliao41@gmail.com` via `user_roles` table
- [x] Verified `/api/v1/me` returns `"roles":["admin","viewer"]` after fresh GitHub OAuth login
- [x] Verified `/api/v1/admin/health/deep` returns `{"status":"ok","db":"connected"}` (admin access works)

### Cloudflare Access + Custom Domain Setup ✅
- [x] Added `panoptix.site` domain to Cloudflare (Free plan)
- [x] Changed Namecheap nameservers to Cloudflare (`courtney.ns.cloudflare.com`, `hal.ns.cloudflare.com`)
- [x] Domain active and protected by Cloudflare
- [x] Added CNAME `staging` → Railway service (proxied through Cloudflare)
- [x] Configured Railway custom domain `staging.panoptix.site` with DNS verification
- [x] Created Cloudflare Zero Trust organization (`panoptix-netad`)
- [x] Added GitHub OAuth as identity provider (GitHub OAuth App → Cloudflare Access callback)
- [x] Created `Panoptix Staging` Access application covering `staging.panoptix.site`
- [x] Access policy: Allow GitHub Users (GitHub login method)
- [x] Updated Railway CF_ACCESS_* env vars with real Cloudflare values
- [x] Verified `/health` returns `{"status":"ok"}` through `staging.panoptix.site`
- [x] Verified `/api/v1/me` returns authenticated user principal after GitHub OAuth login
- [x] Verified user identity: `ivanliao41@gmail.com`, `is_dev: false`, roles/permissions empty (expected for new user)
- [x] No code changes required — existing Cloudflare Access JWT verification worked out of the box

### Railway/Neon Staging Deployment ✅
- [x] Connected private GitHub repo (`Shnvan/Panoptix`) to Railway via GitHub App
- [x] Configured Railway service to deploy from `backend` branch, `apps/api/` root
- [x] Set Railway Networking custom port to `8080`
- [x] Fixed `ModuleNotFoundError: No module named 'httpx'` by moving `httpx` to main deps in `pyproject.toml`
- [x] Aligned Uvicorn port (`8000` → `8080`) in Dockerfile and updated `PORT` env var
- [x] Set all required staging environment variables (Neon DB URLs, session/CSRF/audit keys, gateway tokens)
- [x] Verified staging deploy: `/health` returns `{"status":"ok"}`
- [x] Verified protected routes fail-closed: `/api/v1/cameras` and `/api/v1/me` return `401 Unauthorized`
- [x] Verified Neon database schema already migrated (23 tables present, alembic_version at `0004_constraints_and_indexes`)
- [x] Updated docs: `railway-neon-staging-prep.md` port reference `8000` → `8080`

### CI Pipeline Finalization ✅
- [x] Fixed Semgrep shell injection findings in `.github/workflows/ci.yml`, `deploy-staging.yml`, and `deploy-production.yml` by moving `${{ github.* }}` expressions to `env:` blocks
- [x] Migrated osv-scanner from v1 to v2.3.8 (`--recursive` instead of `--lockfile`); removed nonexistent `--skip-git` flag
- [x] Updated trivy-action from 0.28.0 to v0.36.0; added `ignore-unfixed: true` + `apps/api/.trivyignore` for Debian 12 CVEs
- [x] Updated semgrep-action org from `returntocorp` to `semgrep`
- [x] Upgraded `apps/api/Dockerfile` to `python:3.12-slim-bookworm` + `apt-get upgrade`
- [x] Created `apps/api/.trivyignore` with 13 Debian 12 will-not-fix CVEs
- [x] Created `.semgrepignore` to suppress urllib false positive in edge agent
- [x] Changed deploy-staging health check from hard-fail to informational (Cloudflare Access 302 handling)
- [x] CI run #10: ALL 8 JOBS GREEN

### LiveKit Cloud Account Provisioning ✅
- [x] Created LiveKit Cloud account at livekit.io (APAC region)
- [x] Project `panoptix` provisioned with WebSocket URL, API key, API secret
- [x] Webhook secret configured (uses API secret as signing key)
- [x] All 4 values set as Railway staging environment variables
- [x] Deep health probe returns `livekit: connected` (previously `not_configured`)

### Semgrep CI Token Configuration ✅
- [x] `SEMGREP_APP_TOKEN` configured as GitHub repository secret
- [x] Semgrep dashboard linked to `Shnvan/Panoptix` repo
- [x] Enables richer SAST scan results and online dashboard viewing

### Cloudflare R2 Backup Bucket Provisioning ✅
- [x] Terraform Cloud workspace `panoptix-backup-r2` created (CLI-driven workflow)
- [x] `infra/terraform/modules/backup-r2/main.tf` updated with Terraform Cloud backend block
- [x] `infra/terraform/modules/backup-r2/outputs.tf` fixed — removed nonexistent `domains` attribute
- [x] Cloudflare R2 activated (free tier: 10 GB + 10M requests/month)
- [x] Bucket `panoptix-backups` created in `WNAM` region
- [x] R2 scoped API token created (Object Read & Write, bucket-only)
- [x] `R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` set in Railway staging

### Staging Health Verification ✅
- [x] Verified `https://staging.panoptix.site/health` returns `{"status":"ok"}` behind Cloudflare Access
- [x] GitHub OAuth login flow working end-to-end
- [x] 7-day uptime gate running (started 2026-05-13, clears 2026-05-20)

### Frontend Integration Package ✅
- [x] Created `docs/frontend/INTEGRATION_GUIDE.md` — auth flow, CSRF handling, LiveKit JS SDK integration, camera grid patterns, SSE events, admin screens, error handling
- [x] Updated `docs/frontend/README.md` and `docs/index.md` with new integration guide reference
- [x] Updated `docs/frontend/BACKEND_STATUS.md` with current LiveKit Cloud, R2, CI, and Cloudflare Access status

### Production Environment Prep ✅
- [x] Created `docs/runbooks/railway-neon-production-prep.md` — production deployment checklist with 7-day gate, release gates, smoke validation, rollback procedure
- [x] Updated `docs/index.md` with production prep runbook reference
- [x] Updated `docs/runbooks/break-glass-runbook.md` with FIDO2 hardware key procurement recommendations
- [x] Updated `docs/procurement/camera-spec.md` with LiveKit Cloud provisioning note

### Academic Manual Crosswalk ✅
- [x] Extracted and analyzed professor's `IP_Camera_Network_Setup_Manual.pdf` (COMP 012)
- [x] Created `docs/reference/academic-manual-crosswalk.md` — maps lab concepts (RTSP, camera brands, FFmpeg, topology) to Panoptix equivalents
- [x] Documented shared foundations, conceptual upgrades, forbidden lab patterns, and quick-reference mapping
- [x] Updated `docs/procurement/camera-spec.md` with crosswalk reference for RTSP URL formats
- [x] Updated `docs/index.md` with crosswalk navigation entry

### Backup Status Reporting ✅
- [x] Implemented `GET /api/v1/admin/backups/status` reporting DB-known backup readiness status from `backup_runs`
- [x] Returns status (`ok`, `degraded`, `missing`) and latest backup age without exposing decryption keys or file paths
- [x] Added unit tests verifying status transitions and DB fallback scenarios

### Camera and Gateway Lifecycle Endpoints ✅
- [x] Added `PATCH` endpoints for gateways and cameras to allow supported metadata updates without credential rotation
- [x] Added `/enable` `POST` endpoints for gateways and cameras to support re-enabling previously disabled resources
- [x] Audit logged all lifecycle events and added unit tests validating state modifications

### GitHub Organization Invite Flow ✅
- [x] Added `POST /api/v1/admin/users/invite` allowing admin-initiated user onboarding via GitHub API integration
- [x] Handled `github-invites-not-configured` gracefully when invites are disabled in settings
- [x] Added audit log recording for successful invites and user creations

### DSR Workflow API ✅
- [x] Added DSR request workflow endpoints (`GET/POST/PATCH /api/v1/admin/dsr-requests`)
- [x] Implemented DSR request CRUD operations, status tracking, camera scope notes, and outcome fields
- [x] Audit logged all actions (`admin.dsr.created`, `admin.dsr.viewed`, `admin.dsr.updated`) and added comprehensive test coverage

### Alert System & Email Notification Pilot ✅
- [x] Applied database migration `0008_alerts_email` locally, adding `alerts` and `alert_notifications` tables
- [x] Implemented auto-detection of alerts from critical events (break-glass open, audit verification failure, admin role grant, gateway disable, command rejection, backup status degraded)
- [x] Added SMTP email alert notification integration with redact-safe configuration and disabled-by-default delivery
- [x] Exposed API endpoints: list, view, acknowledge (`POST /api/v1/admin/alerts/{id}/acknowledge`), and resolve (`POST /api/v1/admin/alerts/{id}/resolve`)
- [x] Added focused backend tests for alert APIs, detection, email-disabled behavior, SMTP success/failure, and token redaction

### Actor Profile Stored-Data Enrichment ✅
- [x] Enriched admin actor profiles with direct actor-linked alert counts and recent alert rows from stored `alerts` data
- [x] Added safe user `behavior_baseline` summaries from `login_baselines` without exposing raw known IP, country, or user-agent history
- [x] Kept external IP intelligence, MFA/device enrichment, incidents, analyst notes, frontend UI, and new schema work out of this backend slice
- [x] Expanded focused actor profile coverage for user/gateway/system alert isolation and baseline privacy summary behavior

### Actor IP and Device Enrichment Pilot
- [x] Added bounded user actor `ip_details` and `device_details` over the latest 10 stored authenticated sessions
- [x] Added optional Ipregistry provider wiring for normalized recent-session location, network, company, carrier, and security context with visible degraded states when enrichment is not configured or unavailable
- [x] Added explicit Cloudflare trusted client-IP capture for fresh browser sessions and user/admin audit writes so public session IPs can feed actor Ipregistry enrichment instead of Railway proxy-hop IPs
- [x] Parsed stored session user agents into browser, OS, and conservative device summaries without new alerts or database schema
- [x] Kept non-user actor enrichment null and left actor investigation frontend work as handoff scope

### Public Visitor Collector Pilot
- [x] Added disabled-by-default public visitor entry notice and collector APIs for approved security-core browser signals
- [x] Added anonymous visitor visit persistence, signed entry cookie correlation to later authenticated sessions, and admin visitor list/detail APIs with detail-view audit
- [x] Expanded `/entry` collection after explicit Continue with approved browser/network/WebRTC summary signals while still excluding raw WebRTC SDP/candidate strings, raw Ipregistry payloads, reverse-geocoded addresses, coordinates, canvas/audio/WebGL/font fingerprints, and broad fingerprint dumps
- [x] Added backend admin visitor response sections for `browser_context`, `network_context`, `webrtc_details`, `timing`, `server_context`, and `risk_context`; admin visitor investigation UI remains frontend handoff work
- [x] Added 30-day default visitor retention cleanup through the existing maintenance path
- [x] Added a same-domain `/entry` frontend entry view on the existing web service that shows the backend notice before explicit Continue collection and redirects into protected Cloudflare Access sign-in
- [x] Production Cloudflare routing verified: first-time `https://panoptix.site/` visits redirect to `/entry` only when the signed `panoptix_visitor` cookie is absent; returning visitors go directly to the protected app/Access flow
- [x] Public bypass scope verified as narrow: `/entry`, `/assets/*`, `/logo.png`, `/api/v1/visitor/notice`, and `/api/v1/visitor/collect`; protected root and protected API paths remain behind Cloudflare Access
- [x] Kept the admin visitor dashboard as frontend handoff work; the collector covers the separate entry flow rather than direct Cloudflare Access challenge visits
- [x] Production admin visitor detail smoke confirmed expanded sections are present and UI-ready: `ip_details`, `browser_context`, `network_context`, `webrtc_details`, `timing`, `server_context`, and `risk_context`

### Frontend Capability Handoff Refresh - 2026-05-24

- [x] Refreshed frontend docs to list backend-ready UI work: Alerts real API UI, actor investigation, admin visitor investigation, full audit filters, and LiveKit subscriber playback
- [x] Documented backend-only/gateway-only routes that must stay out of browser code, including gateway heartbeat, ingest token, camera status, gateway control WebSocket, and LiveKit webhook
- [x] Documented disabled-user behavior for frontend handling: authenticated disabled users get `403 user-disabled`; inviting an existing disabled user returns `409 user-disabled`

### Production Backup Evidence - 2026-05-24

- Production Railway backend has `R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY` present; values were not printed or recorded.
- Direct R2 bucket list check succeeded using production Railway credentials without exposing object keys.
- R2 list returned `has_any_object: False`; no production backup artifact is visible yet.
- Production `backup_runs` contains `0` rows, so `GET /api/v1/admin/backups/status` should report `missing` until the first real backup run records evidence.
- Expanded visitor collector DB smoke found `19` visitor visits, `8` linked visits, and the latest visit has `browser_context`, `network_context`, `webrtc_context`, `timing_context`, and `server_context` populated.
- Next backup action: run the first production backup job, verify one R2 object exists, record a `backup_runs` row, then run an isolated restore drill.

---

## Key References

| What | Where |
|------|-------|
| Full system plan | `docs/planning/secure-cctv-monitoring-system-v4.md` |
| API contract | `docs/implementation/api-reference.md` |
| Team ownership | `docs/implementation/team-raci-checklist.md` |
| Database/frontend coordination gates | `docs/implementation/team-raci-checklist.md#coordination-gates` |
| Environment variables | `.env.example` |
| Doc navigation | `docs/index.md` |
| Frontend guardrails | `docs/frontend/frontend-guardrails.md` |
| Database guardrails | `docs/database/database-guardrails.md` |

---

## Do Not

- Implement frontend UI code — that belongs to the frontend coworker
- Implement database schema/migrations — that belongs to the database coworker
- Push real secrets or `.env` files
- Delete or weaken existing tests
- Skip reading `team-raci-checklist.md` before starting work
