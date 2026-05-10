# Panoptix Implementation Progress

Current status and next steps for any session continuing this project.

---

## Ownership Boundary

- **Frontend implementation** (`apps/web/`) → owned by frontend coworker
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
- [x] Frontend ownership placeholder created (`apps/web/README.md`)
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
- [x] Alembic migration, cleanup job, and real actions remain deferred (DB coworker / future milestone)

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
- [x] `livekit` and `gateway` remain `"not_connected"` (deferred)
- [x] 2 tests: connected state and error state

### Real Camera List Endpoint
- [x] `GET /api/v1/cameras` wired to real DB query with Camera + CameraAcl join
- [x] Returns only cameras where the authenticated user has a non-revoked ACL entry
- [x] Excludes retired cameras (`retired_at IS NOT NULL`)
- [x] Cursor pagination using `created_at` (newest first, limit+1 pattern)
- [x] Response includes `camera_id`, `display_name`, `source_type`, `livekit_room_name`, `created_at`
- [x] 7 tests: auth, empty, accessible, retired, revoked, pagination, isolation

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

---

## Next Steps (In Order)

### 1. TBD — Next milestone to be determined
Review `docs/planning/secure-cctv-monitoring-system-v4.md` and `docs/implementation/api-reference.md` for the next logical milestone.

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
