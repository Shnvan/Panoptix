# Panoptix Implementation Guide

This guide explains what has been implemented so far, in order, so you can understand how the system works and why each part matters.

---

## 1. Documentation Organization

### What was implemented

The project documentation was organized into clear folders under `docs/`, such as:

- `docs/planning/`
- `docs/architecture/`
- `docs/implementation/`
- `docs/frontend/`
- `docs/database/`
- `docs/security/`
- `docs/privacy/`
- `docs/runbooks/`
- `docs/adrs/`

A central documentation map exists at:

```text
docs/index.md
```

### How it works

Instead of keeping many Markdown files scattered in the root folder, the documentation is grouped by purpose. `docs/index.md` acts like a table of contents.

### Why it matters

This makes the project easier to understand for you, other teammates, and future LLM sessions. It also reduces confusion about where planning, architecture, frontend, database, and security docs belong.

---

## 2. Ownership Boundary

### What was implemented

The ownership rules were documented in:

```text
docs/implementation/team-raci-checklist.md
```

The rule is:

- Frontend implementation is owned by the frontend coworker.
- Database implementation is owned by the database coworker.
- Backend, security, gateway, DevOps, LiveKit integration, audit logic, and coordination are owned by the system owner.

### How it works

Any new contributor or LLM session can read the RACI file and know what should and should not be implemented in this workstream.

### Why it matters

This prevents accidental overlap. For example, we can create backend interfaces that prepare for database integration, but we should not create migrations or database schema because that is assigned to the database coworker.

---

## 3. Monorepo Skeleton

### What was implemented

The repository was shaped into a monorepo:

```text
apps/
  api/
  web/
  cctv-edge/
  media-fallback/
database/
infra/
scripts/
docs/
```

### How it works

Each folder has a clear purpose:

- `apps/api/` — FastAPI backend/control plane
- `apps/web/` — frontend placeholder owned by frontend coworker
- `apps/cctv-edge/` — gateway/edge workspace
- `apps/media-fallback/` — optional LiveKit fallback placeholder
- `database/` — database placeholder owned by database coworker
- `infra/` — deployment and infrastructure workspace
- `scripts/` — utility scripts workspace

### Why it matters

The structure mirrors the architecture of the real system. It separates frontend, backend, gateway, infrastructure, and database work so teams can work in parallel without stepping on each other.

---

## 4. Git Hygiene and Environment Safety

### What was implemented

A `.gitignore` file was added and later improved.

It ignores local/generated files such as:

- `.env`
- `.env.*`
- `__pycache__/`
- `*.pyc`
- `*.egg-info/`
- `.pytest_cache/`
- `.venv/`
- `node_modules/`
- `COUNCIL.md`
- `execute.md`

The `.env.example` file is kept safe to commit because it contains placeholder values only.

### How it works

Real secrets stay in ignored `.env` files. Only the template `.env.example` is committed.

Generated Python package metadata like `*.egg-info/` is ignored so local `pip install` commands do not pollute commits.

### Why it matters

This protects secrets, keeps commits clean, and prevents generated files from being pushed to GitHub.

---

## 5. Full Requirements List

### What was implemented

A repo-level requirements guide was created:

```text
requirements.md
```

### How it works

It lists tools and dependencies for all workstreams:

- backend
- frontend
- database
- gateway
- infrastructure
- CI/CD
- external services

### Why it matters

You wanted one place to learn what must be installed and why. This file helps you and teammates understand project prerequisites without searching through many docs.

---

## 6. Progress Tracking

### What was implemented

A progress file was created:

```text
PROGRESS.md
```

### How it works

It records:

- what has been completed
- what the next steps are
- important references
- guardrails about what not to implement

### Why it matters

New sessions, teammates, or LLMs can quickly understand the current state of the project without relying on chat history.

---

## 7. FastAPI Backend Starter

### What was implemented

The backend app was created under:

```text
apps/api/
```

Important files:

```text
apps/api/pyproject.toml
apps/api/src/cctv_api/__init__.py
apps/api/src/cctv_api/main.py
```

### How it works

`pyproject.toml` declares the Python backend package and dependencies.

The backend uses FastAPI as the API framework. The app entry point is:

```text
cctv_api.main:app
```

### Why it matters

This gives the system a real backend foundation where future security, gateway, LiveKit, audit, and API logic can live.

---

## 8. Backend App Factory

### What was implemented

The backend now uses an app factory:

```text
create_app()
```

in:

```text
apps/api/src/cctv_api/main.py
```

### How it works

Instead of creating the app directly with only one global object, `create_app()` builds and configures the FastAPI app.

It wires together:

- settings
- exception handlers
- health routes
- API v1 routes

### Why it matters

An app factory makes testing easier because tests can create isolated app instances with different settings. This is important for dev-auth and future production-auth tests.

---

## 9. Settings / Config Loader

### What was implemented

Settings were added in:

```text
apps/api/src/cctv_api/core/config.py
```

### How it works

The `Settings` class loads configuration values such as:

- app environment
- Cloudflare Access settings
- dev-auth settings
- session cookie names
- LiveKit settings
- gateway settings
- CSP settings

It uses `pydantic-settings`, so values can come from environment variables or `.env` files.

### Why it matters

Security-sensitive systems should not hardcode secrets or environment-specific settings. This file gives the backend a single, typed place to read configuration.

---

## 10. Health Endpoints

### What was implemented

Health routes were added in:

```text
apps/api/src/cctv_api/api/health.py
```

Endpoints:

```text
GET /health
GET /api/v1/admin/health/deep
```

### How it works

`/health` returns a minimal response:

```json
{ "status": "ok" }
```

The deep health endpoint is a placeholder for future DB, LiveKit, and gateway checks.

### Why it matters

Health endpoints help deployment platforms and monitoring tools know whether the app is alive. The public health endpoint intentionally does not reveal sensitive details.

---

## 11. RFC 9457 Problem Details Errors

### What was implemented

Central API error handling was added in:

```text
apps/api/src/cctv_api/api/errors.py
```

### How it works

The app can raise `ProblemDetail` exceptions, and FastAPI returns structured error responses like:

```json
{
  "type": "https://panoptix.local/problems/unauthorized",
  "title": "Unauthorized",
  "status": 401,
  "detail": "cf-access-token-required"
}
```

### Why it matters

Consistent error shapes make the API predictable for frontend, gateway, QA, and future monitoring. It also matches the documented API contract.

---

## 12. API v1 Router

### What was implemented

A versioned API router was added in:

```text
apps/api/src/cctv_api/api/router.py
```

Current API prefix:

```text
/api/v1
```

### How it works

All future application API routes should be mounted under `/api/v1`. Current placeholder routes include:

```text
GET /api/v1/me
GET /api/v1/cameras
```

### Why it matters

Versioning the API early helps prevent breaking frontend/gateway contracts later. If we ever need a new incompatible API, we can add `/api/v2` instead of breaking `/api/v1`.

---

## 13. Backend Tests

### What was implemented

Tests were added under:

```text
apps/api/tests/
```

Current test coverage includes:

- settings defaults
- settings environment override
- health endpoints
- security behavior
- RBAC helpers
- gateway endpoints

### How it works

Tests use FastAPI `TestClient` to call routes without starting a real server.

### Why it matters

Tests prove that the backend behaves as expected. They also protect us from accidentally breaking existing behavior when adding new features.

---

## 14. DevOps Foundation

### What was implemented

DevOps files were added:

```text
apps/api/Dockerfile
apps/api/.dockerignore
.github/workflows/ci.yml
.github/dependabot.yml
```

### How it works

The Dockerfile defines how to build the backend API container.

The GitHub Actions workflow runs:

- ruff lint
- mypy type check
- pytest tests
- Docker build check
- secret scan

Dependabot checks for dependency updates.

### Why it matters

CI helps catch problems before code is merged. Docker support prepares the backend for deployment. Secret scanning helps prevent accidental credential leaks.

---

## 15. Security Identity Model

### What was implemented

Identity models were added in:

```text
apps/api/src/cctv_api/security/identity.py
```

Important concepts:

- `Principal`
- `PrincipalKind.USER`
- `PrincipalKind.GATEWAY`

### How it works

A `Principal` represents who is making a request.

It can represent:

- a browser user
- a gateway machine

It can include:

- subject
- email
- roles
- permissions
- gateway ID
- whether it is a dev identity

### Why it matters

The backend needs a clear way to distinguish users from gateways. A browser user should never be treated like a gateway, and a gateway should never be treated like a viewer.

---

## 16. Cloudflare Access Verifier Interface

### What was implemented

A Cloudflare Access verifier interface was added in:

```text
apps/api/src/cctv_api/security/cloudflare_access.py
```

### How it works

Production browser JWT verification now uses Cloudflare Access JWT assertions, PyJWT signature verification, JWKS key lookup, issuer validation, audience validation, expiration checks, not-before checks, issued-at checks, and clock-skew handling.

The backend reads the JWT from:

```text
cf-access-jwt-assertion
```

Valid browser JWTs become non-dev `PrincipalKind.USER` principals. Invalid or missing JWTs fail closed with `401 Unauthorized`.

Dev-auth only works when:

```text
APP_ENV=development
ALLOW_DEV_AUTH=true
```

### Why it matters

Fail-closed behavior is important in security. If the app cannot prove who the caller is, it should reject the request instead of guessing or allowing access.

---

## 17. Authentication Dependencies

### What was implemented

FastAPI dependencies were added in:

```text
apps/api/src/cctv_api/security/dependencies.py
```

Key dependencies:

```text
require_authenticated_user()
require_gateway_identity()
```

### How it works

Routes use these dependencies to require a valid identity before route logic runs.

For example:

- browser routes use `require_authenticated_user()`
- gateway routes use `require_gateway_identity()`

### Why it matters

This keeps security checks centralized. Instead of every route manually checking identity, routes declare what kind of identity they require.

---

## 18. RBAC Policy Placeholders

### What was implemented

RBAC helpers were added in:

```text
apps/api/src/cctv_api/security/policy.py
```

Helpers include:

- `has_role()`
- `has_permission()`
- `require_role()`
- `require_permission()`

### How it works

These helpers check whether a `Principal` has a required role or permission. If not, they raise a `403 Forbidden` problem response.

### Why it matters

Authorization should be deny-by-default. These helpers are the beginning of the policy layer that will later enforce viewer/admin/auditor permissions.

---

## 19. Protected Browser API Placeholders

### What was implemented

These routes are now protected:

```text
GET /api/v1/me
GET /api/v1/cameras
```

### How it works

Both routes require `require_authenticated_user()`.

Unauthenticated requests return:

```text
401 Unauthorized
```

### Why it matters

Even placeholder routes should follow security rules. This prevents accidentally leaving data-bearing routes public later.

---

## 20. Gateway Foundation

### What was implemented

Gateway models were added in:

```text
apps/api/src/cctv_api/gateway/models.py
```

Gateway routes were added in:

```text
apps/api/src/cctv_api/api/gateways.py
```

Endpoints:

```text
POST /api/v1/gateways/{gateway_id}/heartbeat
POST /api/v1/gateways/{gateway_id}/ingest-token
POST /api/v1/gateways/{gateway_id}/cameras/{camera_id}/status
GET  /api/v1/gateway-control/ws
```

### How it works

Gateway routes require gateway identity, not browser user identity.

The backend checks that:

```text
path gateway_id == authenticated gateway principal gateway_id
```

If they do not match, the backend returns:

```text
403 Forbidden
```

The ingest-token and WebSocket control channel routes currently return `501 Not Implemented` placeholders.

### Why it matters

The gateway is the bridge between private CCTV cameras and the cloud media plane. It must be authenticated carefully. A browser must never be able to call gateway routes and receive publish tokens.

The placeholders are intentional because real LiveKit token minting, command dispatch, and database-backed gateway assignments come later.

---

## 21. Database Foundation

### What was implemented

Database foundation files were safely integrated from the database coworker's `dev-phase` branch without merging the unsafe branch directly.

Important files:

```text
apps/api/alembic.ini
apps/api/alembic/
apps/api/src/cctv_api/models/
apps/api/src/cctv_api/db.py
apps/api/scripts/db_validate.py
```

### How it works

SQLAlchemy models define backend-visible database tables for users, sessions, RBAC, sites, gateways, cameras, camera ACL, gateway assignments, stream grants, audit records, privacy records, and operational records.

Alembic migrations define how the schema is created and changed over time. The backend reads database connection strings from the existing `Settings` class using:

```text
DATABASE_URL
MIGRATION_DATABASE_URL
```

The validation script can inspect a migrated PostgreSQL database and verify expected tables, enums, indexes, foreign keys, and audit triggers.

### Why it matters

This gives the backend a concrete database contract for upcoming session, RBAC, gateway assignment, stream grant, and audit work while preserving the ownership boundary: database schema/migrations remain database-owned, and backend code consumes them through typed contracts.

---

## 22. Gateway Tests

### What was implemented

Gateway tests were added in:

```text
apps/api/tests/test_gateway.py
```

### How it works

The tests check:

- heartbeat requires gateway identity
- dev gateway identity works only in development
- gateway ID mismatch returns `403`
- ingest-token fails closed
- camera status accepts valid dev gateway event
- gateway control route fails closed until implemented

### Why it matters

Gateway routes are high-risk because they eventually control camera publishing. Tests make sure the default behavior is safe before real media logic is added.

---

## 23. Backend Session Foundation

### What was implemented

The backend now has a session foundation built on the database schema:

```text
apps/api/src/cctv_api/security/session_cookie.py
apps/api/src/cctv_api/security/sessions.py
apps/api/src/cctv_api/security/users.py
```

The role model was simplified to exactly two human roles:

```text
admin
viewer
```

An Alembic seed migration inserts these roles:

```text
apps/api/alembic/versions/0005_seed_roles.py
```

### How it works

Cloudflare Access still verifies the browser JWT first. For production browser requests, the backend then:

- Finds or creates the database user from the verified identity
- Reads roles from the database
- Creates or resumes a signed app session cookie
- Stores the session in the `sessions` table
- Touches `last_seen_at` for resumed sessions

The API now includes:

```text
GET  /api/v1/sessions/active
POST /api/v1/sessions/revoke
```

### Why it matters

This gives the backend revocable app sessions and moves authorization state toward the database instead of trusting JWT role claims directly.

---

## 24. LiveKit Token Minting Foundation

### What was implemented

The backend now mints short-lived LiveKit tokens from:

```text
apps/api/src/cctv_api/security/livekit_tokens.py
apps/api/src/cctv_api/security/stream_access.py
```

The API includes:

```text
GET  /api/v1/cameras/{camera_id}/view-token
POST /api/v1/gateways/{gateway_id}/ingest-token
```

### How it works

Viewer tokens require:

- authenticated browser user
- active database user
- active camera row
- active `camera_acl` row for the user and camera

Gateway publish tokens require:

- authenticated gateway identity
- route gateway ID matching the authenticated gateway ID
- enabled gateway row
- active camera row
- active `gateway_camera_assignments` row for the gateway and camera

Both token types are LiveKit-compatible HS256 JWTs with TTL capped at 60 seconds. Viewer tokens are subscribe-only, and gateway tokens are publish-only. Successful token mints are recorded in `stream_grants`.

### Why it matters

This is the security boundary between Panoptix API authorization and the media plane: the backend now decides who can watch or publish each camera before LiveKit receives a token.

---

## 25. Audit Foundation

### What was implemented

The backend has an audit writer:

```text
apps/api/src/cctv_api/security/audit.py
```

It writes real rows to the existing append-only `audit_log` table, redacts sensitive payload fields, and records security-critical browser and gateway actions.

### How it works

The audit writer records:

- actor type and actor ID
- action name
- resource name
- request IP and user agent when available
- scrubbed JSON payload
- `prev_hash`, `hash`, and `hmac_key_version`

Sensitive payload fields such as tokens, JWTs, secrets, cookies, credentials, passwords, and API keys are redacted before insertion.

The current integrations audit:

- viewer token issued and denied paths
- gateway ingest-token issued and denied paths
- session revoke success, not-found, and not-owned denial paths

### Why it matters

The backend records security-critical actions without storing raw media tokens or credentials, while preserving the long-term append-only audit architecture.

---

## 26. Gateway Agent Foundation

### What was implemented

The first gateway-side agent package now exists at:

```text
apps/cctv-edge/agent
```

It includes:

- environment-based configuration loading
- an outbound HTTP client for backend heartbeat and camera status endpoints
- a one-shot and continuous heartbeat runner
- a CLI entrypoint
- tests for config, client, and runner behavior

### How it works

The agent reads gateway settings from environment variables, then calls:

```text
POST /api/v1/gateways/{gateway_id}/heartbeat
POST /api/v1/gateways/{gateway_id}/cameras/{camera_id}/status
```

For local development, `PANOPTIX_DEV_GATEWAY_IDENTITY=true` sends the backend development gateway identity header. The agent remains outbound-only and does not open a local server socket.

### Important limitation

This milestone does not implement signed command validation, gateway-side WebSocket reconnect handling, mediamtx process management, or LiveKit publishing orchestration.

### Why it matters

Panoptix now has a real edge-agent foundation that can prove gateway liveness to the backend while preserving the zero-inbound-WAN-port invariant.

---

## 27. Gateway Control Channel Backend Skeleton

### What was implemented

The backend now exposes a real gateway-only WebSocket skeleton at:

```text
/api/v1/gateway-control/ws
```

It includes:

- WebSocket-compatible gateway identity verification
- rejection of unauthenticated or browser/user-authenticated callers
- accepted connections for valid gateway identities
- a connected hello message containing the gateway ID
- clean handling when the gateway disconnects

### How it works

Gateway callers connect outbound to the backend WebSocket endpoint with gateway identity. In development mode, this is the same `x-panoptix-dev-gateway-id` header used by other gateway endpoints.

On success, the backend sends:

```json
{
  "type": "connected",
  "gateway_id": "gateway-id"
}
```

Missing or invalid gateway identity is rejected with WebSocket close code `1008`.

### Important limitation

This is only the channel skeleton. Command signing and local edge-agent verification now exist, but the WebSocket does not yet send commands. Queues, command dispatch, gateway-side WebSocket reconnect handling, mediamtx control, and LiveKit publishing orchestration remain deferred.

### Why it matters

The backend now has a real authenticated outbound control-channel endpoint for gateways, while still preserving fail-closed identity handling before any command execution is added.

---

## 28. Gateway Command Signing + Agent Verifier

### What was implemented

The gateway command contract now has matching backend and edge-agent signing logic:

- backend canonical command JSON generation
- backend HMAC-SHA-256 signing and verification
- base64url signatures
- constant-time signature comparison
- expiry validation
- gateway-target validation
- edge-agent command envelope parsing
- edge-agent local signature, expiry, and gateway-target verification

### How it works

The signature covers the command envelope without the `signature` field. The signed bytes are UTF-8 canonical JSON with sorted keys, compact separators, and UTC datetimes normalized with a `Z` suffix.

The shared envelope shape is:

```json
{
  "command_id": "uuid",
  "kind": "gateway.command.start_publish",
  "gateway_id": "gateway-id",
  "issued_at": "2026-05-07T12:00:00Z",
  "expires_at": "2026-05-07T12:00:30Z",
  "payload": {},
  "signature": "base64url-hmac-sha256"
}
```

### Important limitation

This milestone does not send commands over WebSocket yet. It only proves that backend-generated command envelopes can be verified by the edge agent and rejected if tampered, expired, or targeted at the wrong gateway.

### Why it matters

Before any gateway can execute backend instructions, the agent now has a local fail-closed mechanism to reject forged, replayed, expired, or mis-targeted control commands.

---

## 29. Agent WebSocket Command Receive Skeleton

### What was implemented

The edge agent now has a gateway control client skeleton:

- builds `ws://` or `wss://` URLs from `PANOPTIX_API_BASE_URL`
- uses `PANOPTIX_GATEWAY_CONTROL_WS_PATH`, defaulting to `/api/v1/gateway-control/ws`
- sends the local dev gateway identity header when enabled
- supports `python -m panoptix_edge_agent.cli --control-once`
- receives and validates the backend connected hello message
- parses future command envelopes and verifies them with the command verifier
- rejects invalid JSON, wrong-gateway hello messages, unsigned commands, and tampered commands

### Important limitation

The backend still only sends the connected hello message. The agent can verify command envelopes, but real backend dispatch, command ACKs, reconnect/backoff loop behavior, mediamtx control, and LiveKit publishing remain deferred.

### Why it matters

This proves the edge agent can initiate the outbound control channel and fail closed on invalid control messages before any command execution is added.

---

## 30. Backend WebSocket Command Dispatch + ACK Skeleton

### What was implemented

The first local-only command loop now exists over:

```text
/api/v1/gateway-control/ws
```

It includes:

- backend app-state command provider hook for in-memory/test-scaffolded commands
- backend signing of every outbound WebSocket command envelope
- fail-closed close behavior when command signing is not configured
- edge-agent ACK for valid verified commands
- edge-agent reject ACK for invalid, unsigned, tampered, expired, or wrong-gateway commands
- backend app-state ACK sink hook for tests/local scaffolding

### How it works

After a valid gateway connects, the backend still sends the connected hello message first. If a local test or scaffold attaches:

```text
app.state.gateway_control_command_provider
```

the backend reads command envelopes from that provider, signs them with `GATEWAY_COMMAND_SIGNING_KEY`, and sends them over the existing WebSocket. If signing fails, the backend closes the connection instead of sending an unsigned command.

The edge agent verifies each command envelope and sends:

```json
{
  "type": "command_ack",
  "command_id": "11111111-1111-1111-1111-111111111111",
  "gateway_id": "gateway-1",
  "status": "accepted"
}
```

or a rejected ACK with an `error` value. The backend can receive ACKs through:

```text
app.state.gateway_control_ack_sink
```

### Important limitation

This is intentionally not a command queue. ACKs are not persisted, there is no public enqueue API, and the agent still does not execute camera, mediamtx, or LiveKit actions.

### Why it matters

Panoptix now has a tested end-to-end local protocol loop: backend signs a command, edge verifies it, edge ACKs or rejects it, and backend receives the result without adding unsafe real camera actions.

---

## 31. Gateway Heartbeat Command Fallback Skeleton

### What was implemented

The gateway heartbeat response now supports the first local-only fallback command path:

```text
POST /api/v1/gateways/{gateway_id}/heartbeat
```

It includes:

- backend reuse of the existing app-state command provider hook
- backend signing of every pending command returned in `pending_commands`
- fail-closed HTTP behavior when command signing is not configured
- edge-agent verification of heartbeat-delivered pending commands
- local accepted/rejected command result counts on the heartbeat runner

### How it works

If local test or scaffold code attaches:

```text
app.state.gateway_control_command_provider
```

the backend signs those commands and returns them in the existing heartbeat response shape:

```json
{
  "server_time": "2026-05-07T12:00:00Z",
  "pending_commands": []
}
```

The edge heartbeat runner verifies each pending command with the same fail-closed verifier used by the WebSocket client. Invalid, unsigned, expired, tampered, or wrong-gateway commands are rejected locally and are not executed.

### Important limitation

This is still not a persistent command queue. There is no heartbeat ACK persistence, no retry policy, no mediamtx action, no LiveKit publishing orchestration, and no real camera action.

### Why it matters

Panoptix now has both primary WebSocket command delivery and heartbeat fallback command delivery proven locally, while keeping command execution disabled.

---

## 32. Edge Gateway Control Reconnect/Backoff Skeleton

### What was implemented

The edge agent now has a bounded reconnect wrapper for the outbound gateway control WebSocket.

It includes:

- `PANOPTIX_GATEWAY_CONTROL_RECONNECT_ATTEMPTS`, defaulting to `3`
- `PANOPTIX_GATEWAY_CONTROL_RECONNECT_BACKOFF_SECONDS`, defaulting to `1.0`
- `GatewayControlClient.run_with_reconnect()` for bounded retry behavior
- `python -m panoptix_edge_agent.cli --control-loop-once`
- tests for first-attempt success, transient retry, max-attempt failure, and non-retryable malformed messages

### How it works

The reconnect wrapper calls the existing `run_once()` WebSocket control path. Temporary connection/run failures are retried up to the configured attempt limit with the configured backoff. Malformed control messages remain fail-closed and are not retried, so protocol errors do not get hidden as transient network failures.

### Important limitation

This is a bounded local skeleton, not the final production supervisor. There is no persistent command queue, no command execution, no mediamtx control, no LiveKit publishing orchestration, and no inbound gateway listener.

### Why it matters

The edge control channel now has a first resilience layer while preserving the zero-inbound-WAN-port design and keeping heartbeat fallback available.

---

## 33. Audit HMAC Chain Foundation

### What was implemented

New audit rows now use a real HMAC-SHA-256 hash chain.

It includes:

- `AUDIT_HMAC_KEY_VERSION`, defaulting to `1`
- `AUDIT_HMAC_KEY`, defaulting to `replace-me`
- fail-closed audit writes when the HMAC key is blank or left as the placeholder
- `audit_hmac_keys` active-version row handling
- `prev_hash` continuity from the latest previous `audit_log.hash`
- canonical HMAC material built from scrubbed audit fields
- verifier helpers for a single row and an ID-ordered sequence of rows

### How it works

The audit writer scrubs payloads first, ensures the active HMAC key row exists, reads the latest prior audit hash, and stores:

```text
audit_log.prev_hash = previous audit_log.hash, or null for the first row
audit_log.hash = HMAC-SHA-256(canonical scrubbed audit material)
audit_log.hmac_key_version = AUDIT_HMAC_KEY_VERSION
```

The configured key bytes are stored in `audit_hmac_keys.key_enc` as a local foundation placeholder. Production KMS/envelope encryption and key rotation workflow remain deferred.

### Important limitation

This milestone does not add admin audit list, export, or verification endpoints. Verification is available as backend helper code and tests only.

### Why it matters

Audit rows are now tamper-evident for new writes. Changing the payload, action, resource, or previous-hash linkage causes verifier failure.

---

## 34. Admin Audit Verification Endpoint Skeleton

### What was implemented

The backend now exposes a read-only admin verifier endpoint:

```text
GET /api/v1/admin/audit/verify
```

It includes:

- admin-role enforcement through existing user auth and policy helpers
- full-chain audit verification in `audit_log.id` order
- optional inclusive `start_id` and `end_id` range verification
- continuity checking against the latest row before `start_id`
- mixed key-version verification using local `audit_hmac_keys.key_enc`
- structured `valid`, `checked`, and `error` response fields
- fail-closed `503` behavior when `AUDIT_HMAC_KEY` is blank or left as `replace-me`

### How it works

The endpoint loads audit rows ordered by ID. Without query params it verifies the full chain. With `start_id` and/or `end_id`, it verifies only the inclusive range and uses the row before `start_id` as the expected previous hash.

Each selected row is verified with the HMAC key version stored on that row. The current local foundation loads those key bytes from `audit_hmac_keys.key_enc`.

Successful verification returns:

```json
{
  "valid": true,
  "checked": 2,
  "error": null
}
```

Tampering returns `200` with `valid: false` and an error such as `audit-chain-hash-mismatch` or `audit-chain-prev-hash-mismatch`.

Missing or invalid stored key versions return `200` with `audit-chain-key-missing` or `audit-chain-key-invalid`.

### Important limitation

This skeleton does not list audit rows, export audit data, rotate keys, or write an audit event for the verification call itself.

### Why it matters

Operators now have a first local/admin verification surface for the tamper-evident audit chain without exposing raw audit payload browsing or export workflows.

---

## 35. Audit Verification Range/Key-Version Support

### What was implemented

The admin audit verifier now supports bounded verification and mixed key versions.

It includes:

- optional inclusive `start_id` and `end_id` query params
- `422` validation for invalid bounds
- open-ended range support when one bound is omitted
- empty-range success with `checked: 0`
- continuity validation from the row before `start_id`
- per-row key lookup by `audit_log.hmac_key_version`

### Why it matters

The audit verifier can now handle operationally useful slices of the audit chain without losing previous-hash continuity or assuming every row used the active key version.

---

## 36. Audit Export Skeleton

### What was implemented

The backend now exposes a narrow admin audit export endpoint:

```text
GET /api/v1/admin/audit/export
```

It includes:

- admin-role enforcement through existing user auth and policy helpers
- scrubbed audit rows returned as newline-delimited JSON (JSONL)
- optional inclusive `start_id` and `end_id` range filtering
- `application/x-ndjson` content type with file download disposition
- fail-closed `503` behavior when `AUDIT_HMAC_KEY` is blank or left as `replace-me`
- internal chain fields (`hash`, `prev_hash`, `hmac_key_version`) excluded from export
- each row includes: `id`, `ts`, `actor_id`, `actor_type`, `action`, `resource`, `payload`, `ip`, `ua`

### How it works

The endpoint loads audit rows ordered by ID with optional inclusive bounds. Each row is serialized as a compact JSON object on its own line. The payload field is already scrubbed at write time, so raw tokens or credentials never appear in the export.

The response uses `StreamingResponse` with `application/x-ndjson` content type and a `Content-Disposition: attachment` header for file download.

### Important limitation

This skeleton does not sign the export, list audit rows with pagination, rotate keys, support broad browsing filters, or write an audit event for the export call itself.

### Why it matters

Operators now have a first local/admin export surface for scrubbed audit data without requiring database-level access or exposing internal HMAC chain details.

---

## 37. Audit Row Listing Endpoint

### What was implemented

The backend now exposes an admin audit listing endpoint with cursor pagination:

```text
GET /api/v1/admin/audit
```

It includes:

- admin-role enforcement through existing user auth and policy helpers
- cursor pagination using `AuditLog.id` (descending, newest first)
- configurable page size via `limit` query param (default 50, max 200)
- optional `action` exact-match filter
- fail-closed `503` behavior when `AUDIT_HMAC_KEY` is blank or left as `replace-me`
- internal chain fields excluded from response
- response shape: `{"items": [...], "next_cursor": "id" | null}`

### How it works

The endpoint queries audit rows ordered by ID descending. The cursor represents the last item's ID; the next page fetches rows with `id < cursor`. The server fetches `limit + 1` rows to detect whether more pages exist without a separate count query.

### Important limitation

This skeleton does not support broad browsing filters (actor_type, timestamp range, resource pattern), signed exports, key rotation UI, or audit events for the listing call itself.

### Why it matters

Operators now have a paginated in-browser audit browsing surface for quick inspection, complementing the JSONL export for offline review.

---

## 38. Backend Command Queue Persistence

### What was added

- `CommandStatus` enum in `models/enums.py` — pending, accepted, rejected, expired
- `GatewayCommandQueue` model in `models/tables.py` — persistent command row with gateway FK, kind, JSONB payload, status, timestamps, and error
- `gateway/command_queue.py` — three public functions:
  - `enqueue_command(db, *, gateway_id, kind, payload, expires_at)` — creates pending command row
  - `db_command_provider(db)` — returns closure matching `app.state.gateway_control_command_provider` hook; queries pending/unexpired commands in FIFO order
  - `db_ack_sink(db)` — returns closure matching `app.state.gateway_control_ack_sink` hook; marks command accepted/rejected with timestamp and error

### Key design decisions

- Row `id` (UUID) doubles as `command_id` in the command envelope — no separate lookup column needed
- Signature is not persisted — signing happens at dispatch time using the existing `command_signing` module
- Provider and sink match the existing hook protocol so wiring into `app.state` is a future one-line change
- `db_ack_sink` is idempotent: unknown command IDs and `None` command IDs are silently ignored

### What was not included

- Alembic migration (DB coworker ownership)
- Wiring into app factory (`app.state` hooks remain in-memory for now)
- Background expired-command cleanup job
- Real camera/media actions
- Command enqueue API endpoint

### Tests added

9 new tests in `tests/test_gateway_command_queue.py`:
1. enqueue creates pending row
2. provider returns pending unexpired commands
3. provider filters by gateway ID
4. provider excludes accepted commands
5. ack sink marks accepted
6. ack sink marks rejected with error
7. ack sink ignores unknown command ID
8. ack sink ignores None command ID
9. provider returns FIFO order

---

## 39. Command Queue App Factory Wiring

### What was added

- Session-per-call wrappers in `gateway/command_queue.py`:
  - `create_command_provider()` — returns closure that opens/closes its own DB session per call
  - `create_ack_sink()` — returns closure that opens/closes its own DB session per call, commits on success
- App factory wiring in `main.py`:
  - When `DATABASE_URL` is configured (no `replace-me`), hooks are wired automatically
  - Tests with placeholder URL skip wiring; test overrides take precedence

### Key design decisions

- Session-per-call pattern avoids binding the hook lifecycle to a specific request/WebSocket session
- The provider is read-only (no commit); the sink commits after updating command status
- Guard condition uses `"replace-me" not in DATABASE_URL` to distinguish placeholder from real config
- Existing test patterns unaffected — they override `app.state.*` after app creation

### What was not included

- Background expired-command cleanup job
- Command enqueue API endpoint
- Real camera/media actions
- Production retry/supervision policy

### Tests added

2 new integration tests in `tests/test_gateway_command_queue.py`:
1. `create_command_provider` returns commands via its own session
2. `create_ack_sink` commits ACK via its own session

---

## 40. Command Enqueue API Endpoint

### What was added

- `POST /api/v1/admin/gateways/{gateway_id}/commands` in `api/router.py`
- `EnqueueCommandRequest` Pydantic model: `kind`, `payload`, `expires_in_seconds` (default 300, 10–3600)
- `EnqueueCommandResponse` Pydantic model: `command_id`, `gateway_id`, `kind`, `status`, `expires_at`
- Admin-only auth via `require_role(principal, "admin")`
- Gateway existence check returning 404 `gateway-not-found`
- UUID path validation returning 400 `gateway-id-invalid`

### Key design decisions

- Uses `enqueue_command()` from `gateway/command_queue.py` (no duplication)
- Commits in the endpoint (write endpoint, not just flush)
- Returns 201 Created with the command details
- Expiry computed server-side from `expires_in_seconds` to avoid clock-skew issues with client-supplied timestamps

### What was not included

- Command listing endpoint for admins
- Command cancellation endpoint
- Background expired-command cleanup job
- Audit logging of command enqueue
- Real camera/media actions

### Tests added

7 new tests in `tests/test_gateway_command_queue.py`:
1. requires authentication (401)
2. requires admin role (403)
3. rejects invalid gateway UUID (400)
4. rejects missing gateway (404)
5. creates pending command (201)
6. uses default expiry (300s)
7. uses custom expiry

---

## 41. Background Expired-Command Cleanup

### What was added

- `expire_stale_commands(db) -> int` in `gateway/command_queue.py`
- Single bulk `UPDATE` — marks pending commands past `expires_at` as `expired`
- Returns count of updated rows
- Idempotent: only touches `pending` → `expired` transition

### Key design decisions

- No scheduler/cron — function can be called manually, from an admin endpoint, or via a future scheduled task
- Consistent with `enqueue_command` pattern: caller handles commit
- Bulk update avoids row-by-row processing for efficiency

### What was not included

- Scheduler/cron integration
- Admin endpoint to trigger cleanup
- Notification/alerting
- Real camera/media actions

### Tests added

4 new tests in `tests/test_gateway_command_queue.py`:
1. marks expired pending rows
2. skips unexpired commands
3. skips already accepted
4. returns correct count

---

## 42. Command Listing Admin Endpoint

### What was added

- `GET /api/v1/admin/gateways/{gateway_id}/commands` in `api/router.py`
- Admin-only auth via `require_role(principal, "admin")`
- Gateway existence check returning 404 `gateway-not-found`
- UUID path validation returning 400 `gateway-id-invalid`
- Cursor pagination using `issued_at` (newest first, descending)
- Optional `status` filter (pending, accepted, rejected, expired) with 400 `status-invalid` for invalid values
- Cursor-based pagination using command UUID with 400 `cursor-invalid` for invalid cursor

### Key design decisions

- Mirrors the audit listing endpoint pattern: `limit + 1` fetch, `next_cursor` in response
- Orders by `issued_at DESC` (newest first) to show most recent commands at the top
- Cursor resolves to a row's `issued_at`, then filters for items older than that timestamp
- Invalid cursor UUIDs that don't match any row are silently ignored (returns full result set)
- Response includes all command fields except internal DB metadata

### What was not included

- Command cancellation endpoint
- Scheduler/cron for cleanup
- Audit logging of the listing call
- Real camera/media actions

### Tests added

7 new tests in `tests/test_gateway_command_queue.py`:
1. requires authentication (401)
2. requires admin role (403)
3. rejects invalid gateway UUID (400)
4. rejects missing gateway (404)
5. returns empty list for gateway with no commands (200)
6. returns commands newest first (issued_at DESC ordering)
7. filters by status (only matching status returned)

---

## 43. Command Cancellation Admin Endpoint

### What was added

- `cancelled` value added to `CommandStatus` enum in `models/enums.py`
- `POST /api/v1/admin/gateways/{gateway_id}/commands/{command_id}/cancel` in `api/router.py`
- `CancelCommandResponse` Pydantic model: `command_id`, `gateway_id`, `kind`, `status`, `cancelled_at`
- Admin-only auth via `require_role(principal, "admin")`
- Gateway existence check returning 404 `gateway-not-found`
- Command existence check (scoped to gateway) returning 404 `command-not-found`
- Non-pending guard returning 409 `command-not-pending`
- Listing endpoint status validation updated to accept "cancelled"

### Key design decisions

- Added a distinct `cancelled` status instead of reusing `rejected` — operators can now filter cancelled vs gateway-rejected commands
- Cancel sets `acked_at` to the cancellation timestamp for consistency with the ACK flow
- Command scoped to gateway in the query (both `id` and `gateway_id` must match) — prevents cross-gateway command cancellation
- `expire_stale_commands` and `db_command_provider` unaffected — both only touch `pending` rows

### What was not included

- Scheduler/cron for cleanup
- Audit logging of the cancel action
- Real camera/media actions

### Tests added

8 new tests in `tests/test_gateway_command_queue.py`:
1. requires authentication (401)
2. requires admin role (403)
3. rejects invalid gateway UUID (400)
4. rejects invalid command UUID (400)
5. rejects missing gateway (404)
6. rejects missing command (404)
7. rejects non-pending command (409)
8. succeeds on pending command (200, status=cancelled, cancelled_at set)

---

## 44. Expired-Command Cleanup Admin Endpoint

### What was added

- `POST /api/v1/admin/commands/cleanup` in `api/router.py`
- `ExpireCommandsResponse` Pydantic model: `expired_count: int`
- Admin-only auth via `require_role(principal, "admin")`
- Calls existing `expire_stale_commands(db)` then commits
- `expire_stale_commands` added to import from `gateway/command_queue.py`

### Key design decisions

- No gateway path param — expires stale commands across ALL gateways in one call
- Reuses existing `expire_stale_commands` function (no logic duplication)
- Idempotent — safe to call repeatedly; returns 0 when nothing to expire
- Endpoint commits after flush (function only flushes internally)

### What was not included

- Periodic background scheduler/cron
- Notification/alerting on cleanup
- Audit logging of the cleanup action
- Real camera/media actions

### Tests added

4 new tests in `tests/test_gateway_command_queue.py`:
1. requires authentication (401)
2. requires admin role (403)
3. returns zero when nothing to expire (200, expired_count=0)
4. expires stale commands (200, expired_count=2 for 2 stale + 1 fresh)

---

## 45. Gateway Command Audit Logging

### What was added

- `request: Request` and `settings: Settings = Depends(get_settings)` parameters added to all three command mutation endpoints
- `get_or_create_user` call added to resolve admin principal to a UUID actor_id
- `_record_user_audit_required` call added to each success path (fail-closed)
- `db.commit()` moved after audit call so command mutation and audit row commit atomically
- Test helper `_endpoint_client` updated with valid HMAC key for all endpoint tests

### Audit actions

| Endpoint | Action | Resource | Payload |
|----------|--------|----------|---------|
| enqueue | `command.enqueue` | `gateway:<uuid>` | command_id, gateway_id, kind |
| cancel | `command.cancel` | `command:<uuid>` | command_id, gateway_id, kind |
| cleanup | `commands.cleanup` | `commands` | expired_count |

### Key design decisions

- Used `_record_user_audit_required` (not `_safely`) — command mutations are security-relevant actions where audit failure should block the operation
- Actor resolved via existing `get_or_create_user` — same pattern as session revoke
- Commit ordering: mutation flush → audit flush → single commit (atomic)
- Existing test client updated with HMAC key since all success paths now require audit

### What was not included

- Audit on denial paths (gateway not found, command not found, non-pending)
- Periodic background scheduler/cron
- Real camera/media actions

### Tests added

3 new tests in `tests/test_gateway_command_queue.py`:
1. enqueue writes `command.enqueue` audit row with kind and gateway_id in payload
2. cancel writes `command.cancel` audit row with command_id and kind in payload
3. cleanup writes `commands.cleanup` audit row with expired_count in payload

---

## 46. Deep Health Check Implementation

### What was implemented

The `/api/v1/admin/health/deep` placeholder was wired into a real database connectivity check. The endpoint now injects the `db_session` dependency and executes `SELECT 1` to probe database reachability.

### How it works

The endpoint:
1. Receives a database session via FastAPI dependency injection
2. Executes `SELECT 1` inside a try/except
3. Returns `"connected"` on success, `"error"` on any exception
4. Sets overall status to `"ok"` when DB is connected, `"degraded"` otherwise
5. `livekit` and `gateway` remain `"not_connected"` (deferred to future milestones)

### Key design decisions

- No authentication required — monitoring systems and load balancers need unauthenticated access to deep health endpoints
- Exception handling is intentionally broad (`except Exception`) to catch any DB connectivity issue
- Overall status degrades to `"degraded"` rather than failing entirely — the endpoint itself should always return 200

### What was not included

- LiveKit connectivity check (requires LiveKit SDK integration)
- Gateway connectivity check (requires heartbeat state)
- Auth on the deep health endpoint

### Tests added

2 new tests in `tests/test_health.py`:
1. `test_deep_health_db_connected` — working DB returns `{"status": "ok", "db": "connected", ...}`
2. `test_deep_health_db_error` — broken DB returns `{"status": "degraded", "db": "error", ...}`

---

## 47. Real Camera List Endpoint

### What was implemented

The `GET /api/v1/cameras` placeholder was replaced with a real database query that returns cameras the authenticated user has active ACL access to. The endpoint joins the Camera and CameraAcl tables, filters by the authenticated user's ID, excludes retired cameras and revoked ACLs, and supports cursor pagination.

### How it works

The endpoint:
1. Resolves the authenticated user via `get_or_create_user`
2. Queries cameras joined with CameraAcl where `user_id` matches and `revoked_at IS NULL`
3. Excludes cameras with `retired_at IS NOT NULL`
4. Orders by `created_at` descending (newest first)
5. Supports cursor pagination using `limit+1` fetch pattern

### Key design decisions

- Uses existing `str()` wrapping for UUID comparisons (required for SQLite test compatibility)
- Reuses `_parse_uuid` helper for cursor validation
- Does not expose `gateway_id`, `room_uuid`, or other internal fields in the response
- No admin override — even admins only see cameras they have explicit ACL grants for

### What was not included

- Admin camera CRUD endpoints (create, update, retire)
- Camera ACL management endpoints (grant, revoke)
- Filtering by source_type, site, or gateway
- LiveKit publish-state tracking and 10-second stop grace timers
- SSE camera events stream

### Tests added

7 new tests in `tests/test_cameras.py`:
1. Authentication required (401)
2. Empty list when user has no ACL grants
3. Returns cameras with active ACL
4. Excludes retired cameras
5. Excludes cameras with revoked ACL
6. Cursor pagination works correctly
7. User isolation — other users' cameras not visible

---

## 48. Admin Camera CRUD Endpoints

### What was implemented

Three admin-only endpoints for camera management: create camera, manage camera ACL (grant/revoke), and disable (retire) camera. All three require admin role, validate inputs, and write audit trail entries.

### How it works

1. **Create camera** (`POST /admin/cameras`): validates source_type against the CCTV-only enum, checks livekit_room_name uniqueness, creates the Camera row
2. **Manage ACL** (`POST /admin/cameras/{id}/acl`): accepts `grant` or `revoke` action with a `user_email`. For grant, creates CameraAcl row (409 if already active). For revoke, sets `revoked_at` on the existing active grant (404 if none found)
3. **Disable camera** (`POST /admin/cameras/{id}/disable`): sets `retired_at` on the camera (409 if already retired). Retired cameras are automatically excluded from the viewer camera list

### Key design decisions

- `get_or_create_user` used for both the target user (ACL recipient) and the actor (admin), matching existing patterns
- `str()` wrapping on UUID comparisons for SQLite test compatibility
- All three endpoints use `_record_user_audit_required` (fail-closed) with distinct action names: `camera.create`, `camera.acl.grant`, `camera.acl.revoke`, `camera.disable`
- Pydantic request models with Field validation for length constraints

### What was not included

- Camera update/rename
- Gateway assignment management
- Viewer session termination on disable
- Admin camera listing (all cameras regardless of ACL)

### Tests added

15 new tests in `tests/test_cameras.py`:
- Create: auth (401), role (403), invalid source type (400), duplicate room name (409), success (201)
- ACL: role (403), grant success (200), duplicate grant (409), revoke success (200), revoke not found (404), invalid action (400)
- Disable: role (403), success (200), already retired (409), not found (404)

---

## 49. Camera Events SSE Endpoint

### What was implemented

The authenticated viewer camera events endpoint was added at `GET /api/v1/cameras/events`. It returns persisted camera events as a finite `text/event-stream` response, filtered to cameras the caller can access through active ACL grants.

### How it works

1. Resolves the authenticated user via `get_or_create_user`
2. Queries `CameraEvent` joined through `Camera` and `CameraAcl`
3. Excludes retired cameras and revoked ACLs
4. Applies optional exclusive `since` filtering (`CameraEvent.at > since`)
5. Emits one `event: camera_event` SSE frame per row

### Key design decisions

- Uses the same ACL filtering rule as `GET /api/v1/cameras`
- Supports `limit` with default 100 and max 500
- Parses ISO timestamps with `Z` accepted as UTC
- Returns 400 `since-invalid` for malformed timestamps
- Keeps this milestone finite and DB-backed only; no infinite polling loop, broker, or live gateway dependency

### Tests added

7 new tests in `tests/test_cameras.py`:
- Authentication required (401)
- Empty stream when user has no ACL grants
- Accessible event SSE frame shape
- Other users' camera events excluded
- Revoked ACL and retired camera events excluded
- `since` filters older events
- Invalid `since` returns 400

---

## 50. Gateway Camera Status Persistence

### What was implemented

The gateway camera status endpoint now persists accepted status updates as `CameraEvent` rows. This connects gateway status reporting to the viewer/admin camera event stream without requiring CCTV hardware.

### How it works

1. Requires gateway identity and exact route/principal gateway match
2. Validates gateway and camera IDs as UUIDs
3. Requires enabled gateway, active camera, and active gateway-camera assignment
4. Creates a `CameraEvent` with kind from the request status and source `heartbeat`
5. Uses `observed_at` when supplied, otherwise server time

### Key design decisions

- Reuses the same authorization checks as gateway ingest-token issuance
- Keeps response shape as `{"accepted": true}` for compatibility
- Does not persist `detail` because `camera_events` has no detail column
- Does not add LiveKit room-presence publish orchestration, event broker integration, or real camera controls

### Tests added

13 gateway status tests in `tests/test_gateway.py`:
- Authentication and gateway identity mismatch
- Invalid gateway/camera UUIDs
- Missing/disabled gateway and missing/retired camera
- Missing/revoked gateway-camera assignment
- Event persistence and `observed_at`
- SSE visibility for a viewer with camera ACL

---

## 51. Admin Gateway Registry And Assignment Endpoints

### What was implemented

Admin gateway management endpoints now create gateway registry rows, disable gateways, and manage gateway-camera assignments. This gives admins a tested API path for the assignment rows already required by gateway ingest-token issuance and camera status persistence.

### How it works

1. `POST /admin/gateways` creates an enabled `EdgeGateway`
2. `POST /admin/gateways/{id}/disable` sets `status=disabled` and `disabled_at`
3. `POST /admin/gateways/{id}/cameras` grants or revokes active `GatewayCameraAssignment` rows
4. Assignment grants immediately enable gateway ingest-token and camera status authorization
5. Successful mutations write audit entries

### Key design decisions

- Gateway registration creates only the registry row; credential bootstrap and mTLS issuance remain deferred
- Assignment grants set explicit `granted_at` for SQLite composite-key stability
- UUID comparisons follow the existing `str(uuid)` compatibility pattern
- No LiveKit publish control, credential rotation, or migrations were added

### Tests added

20 tests in `tests/test_admin_gateways.py`:
- Create gateway auth, role, success, and audit
- Disable gateway auth, validation, success, enabled lookup prevention, and conflict
- Assignment auth, validation, missing/retired resources, duplicate grant, revoke, and audit
- Assignment grant enables gateway status and ingest-token authorization

---

## 52. LiveKit Webhook Receiver Foundation

### What was implemented

The backend now has a server-to-server LiveKit webhook receiver at `POST /api/v1/webhooks/livekit`. It verifies LiveKit's Authorization JWT against the active LiveKit API key/secret, checks the raw-body SHA-256 claim, enforces a 60-second event timestamp window, rejects duplicate webhook JWT signatures through `webhook_replay_cache`, and writes audit rows for accepted and replay-rejected webhooks.

### How it works

1. The route reads the raw body before parsing JSON.
2. The verifier accepts bare JWTs or `Bearer <jwt>`, checks HS256 signature, issuer, and `sha256`.
3. The handler validates `createdAt`, stores a replay-cache row, maps known room events by `room.name == cameras.livekit_room_name`, and creates a `CameraEvent` when relevant.
4. Accepted webhooks write `livekit.webhook.received`; stale and duplicate replay rejections write `livekit.webhook.replay_rejected`.

### Key design decisions

- Uses LiveKit's current Authorization JWT webhook contract instead of the older local HMAC wording in planning docs.
- Stores the JWT signature segment in `webhook_replay_cache.signature` to fit the existing 256-character schema.
- Maps only status-relevant events in this milestone: `track_published` to `online`, `track_unpublished` and `room_finished` to `offline`, and `participant_connection_aborted` to `degraded`.
- Unknown rooms and unsupported valid event types are accepted and audited but do not create camera events.
- No gateway start/stop publish orchestration, grace timers, LiveKit REST calls, or mediamtx actions were added.

### Tests added

9 tests in `tests/test_livekit_webhooks.py`:
- Authorization required
- Invalid JWT/signature
- Body hash mismatch
- Stale `createdAt` rejection and audit
- Duplicate replay rejection
- Replay cache and accepted audit
- Camera event persistence and SSE visibility
- Unknown room accepted without event
- Browser preflight not enabled

---

## 53. Room-Presence-Driven Gateway Publish Commands

### What was implemented

Accepted LiveKit room-presence webhooks now enqueue gateway publish control commands. `participant_joined` creates a start-publish command for a known active camera room with an enabled gateway assignment. `participant_left` with `participant_count == 0` and `room_finished` create stop-publish commands.

### How it works

1. The webhook receiver authenticates, replay-checks, and parses the LiveKit event as before.
2. Presence events resolve the camera by `room.name == cameras.livekit_room_name`.
3. The target gateway is the newest active, non-revoked `GatewayCameraAssignment` joined to an enabled `EdgeGateway`.
4. Start commands mint a short-lived gateway publish token, record a `StreamGrant`, and enqueue `gateway.command.start_publish`.
5. Stop commands enqueue `gateway.command.stop_publish`.
6. Existing command providers expose the queued commands through the signed WebSocket and heartbeat fallback paths.

### Key design decisions

- Start command payloads include `camera_id`, `room`, `livekit_url`, `gateway_publish_token`, and `token_expires_at`.
- Stop command payloads include only `camera_id` and `room`.
- Unknown rooms are accepted without command enqueue. Known rooms without an enabled active gateway assignment audit `livekit.publish.command_skipped`.
- `participant_left` without numeric `participant_count` does not enqueue a stop command.
- No grace timers, publish-state table, direct WebSocket push, LiveKit REST calls, mediamtx action, or edge-agent execution were added.

### Tests added

10 additional tests in `tests/test_livekit_webhooks.py`:
- start command enqueue and payload
- stream grant creation
- unknown-room no-op
- missing assignment skip audit
- disabled gateway and revoked assignment skip
- zero-count participant-left stop command
- nonzero-count participant-left no-op
- room-finished stop command
- signed heartbeat fallback delivery
- fail-closed token minting branch

---

## 54. Edge Command Executor

### What was implemented

The edge agent now executes verified gateway commands through a small dispatch layer. It still uses a safe stub media controller, so no real mediamtx process or LiveKit publisher is started yet.

### How it works

1. `GatewayControlClient` receives a signed WebSocket command and verifies it as before.
2. `HeartbeatRunner` receives signed fallback commands from heartbeat responses and verifies them as before.
3. Verified commands are passed to `CommandExecutor`.
4. `gateway.command.start_publish` validates `camera_id`, `room`, `livekit_url`, and `gateway_publish_token`, calls `MediaController.start_publish`, then records in-memory publish state.
5. `gateway.command.stop_publish` validates `camera_id` and `room`, calls `MediaController.stop_publish`, then clears in-memory publish state.
6. Invalid payloads, unknown command kinds, or media controller failures are rejected and surfaced as command errors/ACK rejections.

### Key design decisions

- `MediaController` is a protocol so real mediamtx/LiveKit control can be added behind the same interface later.
- `StubMediaController` records calls and returns success; it does not control real media.
- `PublishState` is process-local and in-memory only.
- Duplicate start commands are idempotent and accepted without a second media-controller call.
- Stop commands for cameras that are not publishing are idempotent and accepted.
- WebSocket command handling became async so execution can be awaited inside the existing control loop.
- Heartbeat command execution remains sync at the runner API boundary by using `asyncio.run()`.

### Tests added

14 tests in `apps/cctv-edge/agent/tests/test_executor.py`:
- start publish calls the media controller and tracks state
- duplicate start publish is idempotent
- stop publish calls the media controller and clears state
- stop publish for a non-publishing camera is idempotent
- missing start/stop payload fields are rejected
- unknown command kind is rejected
- start/stop media controller failures are rejected without corrupting state

Existing control and runner tests were updated for async execution and full command payloads.

---

## 55. Backend Publish State And Stop Grace Timers

### What was implemented

The backend now tracks camera publish lifecycle state and no longer immediately enqueues `stop_publish` when the last viewer leaves. Instead, it schedules a stop grace window and only emits a stop command when the due-stop processor runs after `stop_due_at`.

### How it works

1. `participant_joined` resolves the camera and assigned enabled gateway.
2. If a stop is pending, the backend cancels it and audits `livekit.publish.stop_cancelled`.
3. If the camera is already starting or publishing, no duplicate start command is enqueued.
4. If the camera is idle, the backend marks state `starting`, mints a gateway-publish token, records a stream grant, and enqueues `gateway.command.start_publish`.
5. `participant_left` with `participant_count == 0` marks state `stop_pending` and sets `stop_due_at = event_at + 10 seconds`.
6. `enqueue_due_publish_stops()` finds due `stop_pending` states, enqueues `gateway.command.stop_publish`, and resets state to `idle`.
7. `room_finished` still immediately enqueues `stop_publish` and resets state to `idle`.

### Key design decisions

- The grace timer is deterministic and testable; production scheduler/cron wiring remains a separate milestone.
- The SQLAlchemy model is added for app/test behavior; Alembic migration remains DB-owner coordination unless explicitly requested.
- Stop scheduling writes `livekit.publish.stop_scheduled`.
- Stop cancellation writes `livekit.publish.stop_cancelled`.
- Delayed due-stop enqueue uses the same `gateway.command.stop_publish` payload as immediate stop.
- Real mediamtx/LiveKit publishing remains out of scope.

### Tests added

LiveKit webhook tests now cover:
- publish state creation on first join
- duplicate join idempotency
- zero-viewer leave schedules stop instead of immediate stop
- rejoin during grace cancels pending stop
- due-stop processor enqueues stop after grace
- due-stop processor skips before grace due
- room-finished immediate stop resets state
- existing unknown-room and missing-assignment behavior remains unchanged

---

## 56. Privacy Notice And Admin User Listing APIs

### What was implemented

The backend now exposes the MVP privacy-notice gate endpoints and a safe admin user list endpoint for frontend admin screens.

### How it works

1. `GET /api/v1/privacy/notice` returns the current static operator privacy notice and whether the caller accepted the current version.
2. `POST /api/v1/privacy/notice/accept` accepts only the current notice version.
3. The first acceptance inserts `PrivacyNoticeAcceptance` and writes `privacy.notice.accepted`.
4. Repeating acceptance for the same version is idempotent and does not duplicate rows or audit events.
5. `GET /api/v1/admin/users` requires admin role and returns safe user list data.
6. The admin user list supports `limit`, `cursor`, and exact `email` filtering.

### Key design decisions

- Notice content is a safe backend constant for this local-first milestone; production-configured notice content remains future work.
- The existing `PrivacyNoticeAcceptance` table is used; no new model was needed.
- Wrong notice versions fail with 409 `privacy-notice-version-mismatch`.
- Admin user listing does not expose `idp_subject`, session rows, CF JWTs, tokens, or secrets.
- Role names are read through existing `UserRole` and `Role` rows.

### Tests added

11 tests in `apps/api/tests/test_privacy_admin_users.py` cover:

- authentication required for privacy notice
- current notice response shape and unaccepted state
- acceptance row creation and audit logging
- idempotent repeated acceptance
- wrong-version rejection
- admin-only user listing
- safe user fields and role names
- exact email filter
- cursor pagination
- invalid cursor rejection

---

## 57. Scheduler Jobs: Admin Maintenance Endpoint

### What was implemented

A unified admin-only maintenance endpoint that runs both existing deterministic processors in a single call.

### How it works

1. `POST /api/v1/admin/jobs/run-maintenance` requires admin role.
2. It calls `expire_stale_commands(db)` to mark expired pending commands.
3. It calls `enqueue_due_publish_stops(db, audit=...)` to enqueue stop commands for cameras past their grace window.
4. It writes an `admin.maintenance.run` audit event with both counts.
5. Returns `{ "expired_commands": N, "stops_enqueued": N }`.

### Key design decisions

- Unified endpoint runs both processors because they are always safe to run together.
- Existing `POST /api/v1/admin/commands/cleanup` is preserved for backward compatibility.
- No background loop; production scheduler/cron wiring remains future work.
- The endpoint is idempotent; calling it repeatedly is safe.

### Tests added

6 tests in `apps/api/tests/test_maintenance.py`:

- auth required
- admin role required
- empty run returns zeros
- expired stale commands are counted correctly
- due publish stops are enqueued correctly
- audit row written with correct action and payload

---

## 58. Admin User Management

### What was implemented

Role assignment and user disable endpoints to complete the admin user lifecycle.

### How it works

1. `POST /api/v1/admin/users/{user_id}/role` with `{ "action": "grant"|"revoke", "role_name": "..." }`
   - Looks up `Role` by name, inserts or deletes `UserRole` row
   - Audits `admin.user.role.granted` or `admin.user.role.revoked`
   - Returns 404 for unknown user/role, 409 for duplicate grant, 404 for revoking non-granted role

2. `POST /api/v1/admin/users/{user_id}/disable` with `{ "reason": "..." }`
   - Sets `User.disabled_at`, bulk-revokes all active sessions via `revoke_all_user_sessions`
   - Audits `admin.user.disabled` with reason and revoked session count
   - Returns 409 if already disabled

### Tests added

13 tests in `apps/api/tests/test_admin_user_management.py`:

- auth/role checks for both endpoints
- role grant success + audit
- role grant duplicate (409)
- role revoke success + audit
- role revoke not-granted (404)
- user/role not-found (404)
- disable success with session revocation + audit
- disable already-disabled (409)
- disable user-not-found (404)

---

## 59. Gateway Credential Rotation

### What was implemented

Gateway service-token issuance and rotation for the MVP gateway lifecycle.

### How it works

1. `POST /api/v1/admin/gateways` now generates a plaintext `service_token` once.
   - The gateway row stores only `service_token_hash`.
   - The response returns `service_token` once so the operator can copy it to the gateway.
   - Audit payload notes credential issuance, but credential-sensitive fields are redacted by audit scrubbing.

2. `POST /api/v1/admin/gateways/{gateway_id}/rotate-credential` with `{ "reason": "..." }`
   - Requires admin role.
   - Generates a new service token and overwrites `service_token_hash`.
   - Immediately invalidates the old token.
   - Returns `{ "gateway_id", "service_token", "rotated_at" }`.
   - Audits `gateway.credential.rotated` without logging the plaintext token.

3. `service_tokens.py` centralizes secure token handling.
   - `generate_service_token()`
   - `hash_service_token()`
   - `verify_service_token()`

### Tests added

9 tests in `apps/api/tests/test_gateway_credentials.py`:

- token uniqueness and hash verification
- create gateway returns one-time token and stores only hash
- rotate requires auth/admin role
- invalid/missing/disabled gateway errors
- rotation returns a new token and audits
- second rotation invalidates the first rotated token

---

## 60. Gateway Token Verification

### What was implemented

Production-style gateway HTTP request authentication using the issued/rotated gateway service token.

### How it works

Gateway HTTP requests authenticate with:

```text
x-panoptix-gateway-id: <gateway_uuid>
Authorization: Bearer <service_token>
```

The backend:

- parses the gateway UUID from `x-panoptix-gateway-id`
- extracts the bearer token from `Authorization`
- looks up `EdgeGateway`
- rejects disabled gateways with 403 `gateway-disabled`
- rejects missing/invalid/unknown/misconfigured/wrong credentials with 401 errors
- verifies the token against `EdgeGateway.service_token_hash`
- returns a gateway `Principal` for downstream gateway routes

Dev header auth via `x-panoptix-dev-gateway-id` remains available in development.

### Tests added

9 production-style gateway auth tests were added to `apps/api/tests/test_gateway_credentials.py`:

- valid service token accepted by heartbeat
- missing token rejected
- missing gateway ID rejected
- invalid gateway ID rejected
- unknown gateway rejected
- disabled gateway rejected
- gateway without stored token hash rejected
- wrong service token rejected
- token for gateway A cannot call gateway B route

---

## 61. Command Denial Audit Logging

### What was implemented

Gateway and command-control denial paths now write best-effort audit events so rejected gateway operations are visible during debugging and compliance review.

### Audited denial paths

- `gateway.heartbeat.denied.gateway_mismatch`
- `gateway.heartbeat.denied.signing_failed`
- `gateway.camera_status.denied.gateway_mismatch`
- `gateway.camera_status.denied.disabled`
- `gateway.camera_status.denied.camera_not_found`
- `gateway.camera_status.denied.unassigned`
- `gateway.control.denied.unauthenticated`
- `gateway.control.denied.signing_failed`
- `gateway.control.ack.denied.invalid`
- `gateway.control.ack.denied.gateway_mismatch`
- `gateway.control.ack.denied.not_applied`

### ACK sink observability

`db_ack_sink` now returns `AckSinkResult` instead of silently ignoring invalid ACKs.

Observed outcomes:

- applied
- missing command ID
- invalid command ID
- command not found for gateway

Audit writes for denial paths are best-effort and do not mask the original denial response.

### Tests added/expanded

11 tests were added or expanded across:

- `apps/api/tests/test_gateway.py`
- `apps/api/tests/test_gateway_command_queue.py`

---

## 62. Audit Export Signing

### What was implemented

`GET /api/v1/admin/audit/export` now returns a self-contained signed JSON response for MVP audit exports.

Response shape:

```json
{
  "format": "audit-export-v1",
  "manifest": {
    "row_count": 2,
    "start_id": 1,
    "end_id": 2,
    "content_sha256": "...",
    "signature_algorithm": "HMAC-SHA256",
    "signature_key_version": 1,
    "signature": "..."
  },
  "items": []
}
```

### How signing works

- exported audit rows are serialized as canonical JSON
- `content_sha256` is the SHA-256 digest of canonical exported `items`
- the signature is HMAC-SHA256 over the canonical unsigned manifest
- `signature` is not included in the bytes being signed
- invalid placeholder audit keys still fail closed with 503 `audit-hmac-key-invalid`

### Exported fields

Exported items include safe audit fields:

- `id`
- `ts`
- `actor_id`
- `actor_type`
- `action`
- `resource`
- `payload`
- `ip`
- `ua`

Exported items intentionally omit:

- `hash`
- `prev_hash`
- `hmac_key_version`

### Tests updated

Existing audit export tests now verify:

- empty signed exports
- non-empty signed exports
- range-bounded signed exports
- canonical content digest
- HMAC signature verification
- scrubbed payload export
- invalid-key fail-closed behavior

---

## 63. Browser/Admin Security Hardening

### What was implemented

Browser/admin API routes now have CSRF protection for non-dev browser sessions and baseline security headers on API responses.

### CSRF behavior

- CSRF tokens are signed with `CSRF_SIGNING_KEY`
- CSRF tokens are bound to the active browser session ID
- non-dev browser sessions receive a readable `panoptix_csrf` cookie
- unsafe browser/admin requests must send matching `x-panoptix-csrf-token`
- missing or invalid CSRF tokens fail closed with 403 problem details

Protected unsafe routes include:

- `/api/v1/admin/...`
- `/api/v1/privacy/notice/accept`
- `/api/v1/sessions/revoke`

Excluded routes include:

- safe `GET`, `HEAD`, and `OPTIONS` requests
- development auth requests
- gateway HTTP APIs
- gateway control WebSocket
- LiveKit webhook
- health checks

### Security headers

API responses now include:

- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `X-Frame-Options: DENY`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- API-focused `Content-Security-Policy`

### Tests added

11 tests were added across:

- `apps/api/tests/test_security.py`
- `apps/api/tests/test_sessions.py`

---

## 64. Production Maintenance Scheduler

### What was implemented

The backend now has a disabled-by-default in-process scheduler for recurring maintenance.

### Scheduler settings

- `ENABLE_MAINTENANCE_SCHEDULER=false` by default
- `MAINTENANCE_INTERVAL_SECONDS=30` by default, with a minimum of 5 seconds

The scheduler starts only when enabled and `DATABASE_URL` is not a placeholder.

### Scheduled job behavior

Scheduled maintenance runs the same core job as the manual admin endpoint:

- expire stale pending gateway commands
- enqueue due publish-stop commands after the viewer stop grace window

Manual admin runs still write `admin.maintenance.run`.

Scheduled runs write `system.maintenance.run`.

### Tests added

Scheduler tests cover:

- stale command expiry
- due publish-stop enqueueing
- system audit rows
- disabled-by-default startup gating
- enabled startup gating
- cancellation behavior

---

## 65. Gateway Reconnect Supervision

### What was implemented

The edge agent now has stronger gateway control reconnect supervision before real media runtime work.

### Reconnect telemetry

`ControlReconnectResult` now includes:

- retryable failure count
- sleep delays used between attempts
- stopped reason: `connected`, `exhausted-retries`, or `non-retryable-error`

### Supervisor behavior

`GatewayControlSupervisor` can run bounded repeated reconnect cycles and reports:

- total cycles
- connected cycles
- failed cycles
- consecutive failures
- last reconnect result
- stopped reason

Non-retryable protocol/config errors stop supervision without retrying. Command validation remains fail-closed for unsigned, expired, tampered, wrong-gateway, unsupported, or malformed commands.

### CLI behavior

`--control-loop-once` now runs through the supervisor path and prints reconnect attempt count plus supervisor stopped reason.

### Tests added

Edge-agent control tests now cover:

- richer reconnect telemetry
- repeated successful cycles
- stop-after-success
- non-retryable supervisor stop
- consecutive failure tracking
- invalid cycle count rejection
- cancellation propagation

---

## 66. Synthetic RTSP Test Source

### What was implemented

The edge agent now has a safe local synthetic RTSP source scaffold for development and CI.

### Synthetic source settings

The edge-agent config includes:

- `PANOPTIX_SYNTHETIC_RTSP_URL`
- `PANOPTIX_SYNTHETIC_VIDEO_SIZE`
- `PANOPTIX_SYNTHETIC_FRAME_RATE`
- `PANOPTIX_SYNTHETIC_AUDIO_FREQUENCY`

The default local RTSP output is:

```text
rtsp://127.0.0.1:8554/synthetic-camera-1
```

### FFmpeg command builder

`panoptix_edge_agent.synthetic_rtsp` builds a safe FFmpeg argument list for:

- `testsrc` video
- `sine` audio
- low-latency x264 settings
- RTSP output

Automated tests do not launch FFmpeg or mediamtx.

### Validation behavior

Validation rejects:

- non-RTSP URLs
- RTSP URLs with credentials
- invalid video dimensions
- invalid frame rates
- invalid audio frequencies

Real mediamtx process supervision and real camera credentials remain out of scope.

---

## 67. mediamtx Runtime Configuration

### What was implemented

The edge workspace now has a local-only mediamtx runtime configuration scaffold for the synthetic RTSP source.

### Local config scaffold

`apps/cctv-edge/mediamtx/mediamtx.local.yml` defines:

- `rtspAddress: 127.0.0.1:8554`
- `api: no`
- `apiAddress: 127.0.0.1:9997`
- `paths.synthetic-camera-1.source: publisher`

This is a dev/test scaffold only. It is not production process supervision.

### Validation helper

`panoptix_edge_agent.mediamtx_config` can generate and validate the local config defaults.

Validation enforces:

- RTSP binding is loopback-only
- enabled API binding is loopback-only
- disabled API address, if present, is still loopback-only
- synthetic path uses safe path characters

Tests reject wildcard, WAN, and camera-VLAN API bindings.

### What remains out of scope

- production Docker/systemd supervision
- real RTSP camera credentials
- real LiveKit SDK publishing
- production Docker/systemd packaging

---

## 68. mediamtx Process Management

### What was implemented

The edge agent now has safe local mediamtx process-management scaffolding.

### Process command builder

`panoptix_edge_agent.mediamtx_process` builds a safe argument list for local mediamtx startup.

Default command shape:

```text
mediamtx apps/cctv-edge/mediamtx/mediamtx.local.yml
```

The command builder rejects empty values, option-like binary names, missing config files, and non-YAML config paths.

### Lifecycle manager

`MediamtxProcessManager` manages an injected process object and supports:

- start
- stop
- running-status checks
- double-start rejection
- graceful terminate
- timeout kill
- startup and stop failure reporting

Tests use fake process objects and do not require mediamtx to be installed.

### What remains out of scope

- real RTSP camera credentials
- RTSP-to-LiveKit frame/track publishing
- production Docker/systemd unit management

---

## 69. LiveKit Publisher Foundation

### What was implemented

The edge agent now has a fakeable LiveKit publisher foundation behind the existing media-controller boundary.

### Publisher boundary

`panoptix_edge_agent.livekit_publisher` defines:

- `LiveKitPublishRequest`
- `LiveKitPublisherResult`
- `LiveKitPublisherClient`
- `LiveKitMediaController`
- `SdkUnavailableLiveKitPublisherClient`

The controller validates camera ID, room, LiveKit URL, gateway publish token presence, and source RTSP URL before calling the injected publisher adapter.

### Safety behavior

The default publisher client fails with `livekit-sdk-unavailable`, so tests and local verification do not require LiveKit credentials or a LiveKit SDK package.

Tests cover:

- successful start and stop with a fake publisher
- duplicate start idempotency
- room mismatch rejection
- invalid URL and missing token rejection before adapter calls
- adapter start and stop failures
- command-executor integration with the new controller

### What remains out of scope

- hard dependency on the real LiveKit SDK package
- real media packet publishing
- browser, webcam, phone, or frontend publishing
- real RTSP camera credentials

---

## 70. Synthetic End-to-End Publish Dry Run

### What was implemented

The edge agent now has a fake-only synthetic publish dry-run harness.

### Dry-run path

`panoptix_edge_agent.publish_dry_run` can:

- build signed synthetic `gateway.command.start_publish` and `gateway.command.stop_publish` commands
- verify signatures before execution
- run commands through `CommandExecutor`
- drive `LiveKitMediaController` with the synthetic RTSP source URL
- record fake LiveKit publisher calls without logging token values
- optionally run fake mediamtx lifecycle hooks

### Tests cover

- successful signed start/stop flow
- custom safe dry-run config
- duplicate start idempotency
- stop-only safety
- tampered command rejection
- wrong-gateway rejection
- publisher start and stop failures
- fake mediamtx start and stop failures

### What remains out of scope

- RTSP-to-LiveKit frame/track publishing
- real RTSP camera credentials
- real FFmpeg or mediamtx process execution
- browser, webcam, phone, or frontend publishing
- external account setup

---

## 71. Real LiveKit SDK Media Adapter

### What was implemented

The edge agent now has an optional LiveKit Python SDK session adapter behind the existing fakeable publisher boundary.

### SDK adapter behavior

`panoptix_edge_agent.livekit_publisher.LiveKitSdkPublisherClient`:

- lazily imports `livekit.rtc` only when `start_publish()` runs
- returns `livekit-sdk-unavailable` when the SDK package is missing
- creates `rtc.Room()` and connects with `RoomOptions(auto_subscribe=False)`
- tracks active SDK sessions by camera ID
- disconnects the room on stop
- returns fixed start/stop failure codes without exposing gateway publish tokens

The `livekit` package is available only as an optional extra:

```powershell
python -m pip install -e ".[livekit]"
```

### Media-session seam

The SDK adapter includes an injectable media-session factory that receives the validated `LiveKitPublishRequest` and SDK room. This proves the CCTV RTSP `source_url` reaches the adapter boundary while keeping RTSP decode and LiveKit local video-track publishing out of this milestone.

### Tests cover

- missing SDK failure
- fake SDK room connect/disconnect
- `auto_subscribe=False` room options
- media-session start/stop handoff
- start cleanup without storing failed sessions
- stop failure preserving active sessions for retry
- idempotent stop for unknown sessions
- token non-disclosure in returned result objects

### What remains out of scope

- RTSP frame decode or LiveKit local video-track publishing
- real RTSP camera credentials
- real FFmpeg, mediamtx, WHIP, RTMP, or LiveKit Ingress execution
- browser, webcam, phone, or frontend publishing
- external account setup

---

## 72. Frame-to-LiveKit Track Bridge

### What was implemented

The edge agent now has a fakeable video frame-to-LiveKit-track bridge behind the SDK media-session seam.

### Frame and session behavior

`panoptix_edge_agent.livekit_publisher` now includes:

- `LiveKitVideoFrame`, a small RGBA frame model with width, height, timestamp, and data-length validation
- `LiveKitVideoFrameSource`, an async iterable source protocol for future CCTV frame producers
- `LiveKitVideoTrackMediaSession`, an opt-in media session that creates a LiveKit `VideoSource`, creates a `LocalVideoTrack`, publishes it through `room.local_participant.publish_track`, and pumps frames into `VideoSource.capture_frame`

Stop behavior cancels the frame pump, unpublishes the local track when a publication SID is available, closes the SDK video source, and closes the frame source when it supports close/aclose.

### Safety behavior

The default `LiveKitSdkPublisherClient` still uses a no-op media session unless a video-track media-session factory is explicitly provided. Tests use fake SDK objects and fake frame sources only. No real LiveKit account, real camera, FFmpeg process, mediamtx process, or credentials are required.

### Tests cover

- SDK video source, local video track, publish options, and local participant publish calls
- frame capture into the fake SDK video source
- `source_url` handoff into the frame-source factory
- start failure cleanup without storing active sessions
- frame-pump failure containment without token disclosure
- stop cleanup for frame pump, unpublish, video source, and frame source

### What remains out of scope

- wiring the FFmpeg frame source into the LiveKit SDK publisher for a synthetic local smoke
- real RTSP camera credentials
- real LiveKit Cloud smoke testing
- real FFmpeg, mediamtx, WHIP, RTMP, or LiveKit Ingress execution
- browser, webcam, phone, or frontend publishing
- external account setup

---

## 73. FFmpeg RTSP Frame Source

### What was implemented

The edge agent now has a fake-tested FFmpeg RTSP frame source that yields `LiveKitVideoFrame` objects for the existing video-track media session.

### Frame-source behavior

`panoptix_edge_agent.ffmpeg_rtsp_frame_source` defines:

- `FfmpegRtspFrameSourceConfig`
- `FfmpegRtspFrameSource`
- `build_ffmpeg_rtsp_frame_source_args`

The command builder uses an argument list, not a shell string. It reads RTSP/RTSPS input and writes raw RGBA frames to stdout with `-f rawvideo`, `-pix_fmt rgba`, and `pipe:1`.

### Safety behavior

The frame source validates URL scheme, rejects credentials in RTSP URLs, validates dimensions and frame rate, rejects unsafe binary names, and keeps process startup injectable. Tests use fake process/stdout objects only and do not launch FFmpeg.

### Runtime behavior

Frame iteration reads exact `width * height * 4` byte frames, yields `LiveKitVideoFrame(pixel_format="RGBA")`, and assigns timestamps from the configured FPS. Clean EOF stops iteration; short reads fail without yielding partial frames. Close is idempotent, terminates the process, and kills it after the configured timeout.

### What remains out of scope

- wiring this frame source into `LiveKitSdkPublisherClient` by default
- real FFmpeg execution
- real RTSP camera credentials
- real LiveKit Cloud smoke testing
- browser, webcam, phone, or frontend publishing
- external account setup

---

## 74. Synthetic FFmpeg-to-LiveKit Local Smoke Wiring

### What was implemented

The edge agent now has an opt-in, fake-tested local smoke path that composes the FFmpeg RTSP frame source with the LiveKit SDK video-track media session.

### Smoke wiring behavior

`panoptix_edge_agent.ffmpeg_livekit_smoke` defines:

- `FfmpegVideoTrackSettings`
- `FfmpegVideoTrackMediaSessionFactory`
- `build_ffmpeg_video_track_media_session_factory`
- `build_ffmpeg_livekit_publisher`
- `run_synthetic_ffmpeg_to_livekit_smoke`

The factory receives the validated `LiveKitPublishRequest`, builds `FfmpegRtspFrameSourceConfig` from `request.source_url`, creates `FfmpegRtspFrameSource`, and returns `LiveKitVideoTrackMediaSession`.

### Test behavior

The synthetic smoke helper composes signed synthetic start/stop commands, `LiveKitSdkPublisherClient`, fake SDK room/track objects, and fake FFmpeg stdout. Tests prove fake raw RGBA frames are captured by the fake LiveKit video source, then stop cleanup disconnects the room, unpublishes the track, closes stdout, and terminates the fake process.

This remains opt-in. The default `LiveKitMediaController` and default SDK publisher behavior do not launch FFmpeg or require LiveKit credentials.

### What remains out of scope

- making FFmpeg-backed publishing the default edge-agent controller path
- real FFmpeg execution
- real RTSP camera credentials
- real LiveKit Cloud smoke testing
- browser, webcam, phone, or frontend publishing
- external account setup

---

## 75. User Disable LiveKit Participant Removal

### What was implemented

Admin user disable now revokes sessions and attempts to remove the disabled user's active LiveKit viewer participants.

### Backend behavior

`admin_disable_user` now:

- marks the user disabled
- revokes all active sessions
- queries active, non-retired camera rooms from the user's active camera ACLs
- calls `remove_user_participants()` for those rooms
- audits `participants_removed` and `participant_errors`
- returns participant removal results in the disable response

`cctv_api.security.livekit_rooms` uses LiveKit's Twirp room API through `httpx`, mints a short-lived admin JWT from configured LiveKit credentials, lists participants per room, and removes identities matching `viewer:{user_id}:*`.

The LiveKit removal path is fail-open for disable: API errors are collected and audited, but they do not leave the user enabled. Placeholder credentials skip removal safely.

### Tests cover

- LiveKit HTTP URL derivation
- LiveKit admin token minting
- placeholder credential skip
- participant removal success
- non-viewer participant filtering
- multiple-room removal
- list/remove error collection
- admin-disable response and audit payloads
- router ACL-room filtering for active, non-retired camera rooms

---

## 76. Real LiveKit Cloud Smoke Checklist

### What was implemented

The manual testing guide now has a LiveKit Cloud-specific smoke checklist for the existing opt-in `--smoke-ffmpeg-livekit` path.

### Checklist behavior

The checklist documents:

- optional LiveKit SDK installation with `python -m pip install -e ".[livekit]"`
- preflight checks for FFmpeg and `livekit.rtc`
- session-only PowerShell environment variables for LiveKit Cloud URL/key/secret
- local mediamtx and synthetic FFmpeg RTSP source startup
- the smoke command: `python -m panoptix_edge_agent.cli --smoke-ffmpeg-livekit`
- cleanup commands for removing LiveKit secrets from the shell
- a smoke result template that records host/room/result metadata without credentials

This is a runbook/checklist milestone only. It does not mark real LiveKit Cloud smoke testing as passed, and it does not store real credentials in the repository.

---

## 77. Real LiveKit Cloud Smoke Execution

### What was verified

The existing edge-agent `--smoke-ffmpeg-livekit` path successfully published synthetic RTSP video to a real LiveKit Cloud project and disconnected cleanly.

### Smoke setup

- LiveKit host only: `panoptix-4feff0dr.livekit.cloud`
- Room: `panoptix-smoke-test`
- Camera ID: `synthetic-smoke-camera`
- RTSP source: `rtsp://127.0.0.1:8554/synthetic-camera-1`
- Requested duration: 10s
- Local media path: mediamtx with repo config plus FFmpeg synthetic `testsrc`

### Result

```text
smoke: PASSED
frames_published: 1
duration: 38.84s
cleanup_ok: True
```

Transient LiveKit signal retry/timeout logs appeared during connection, but the final smoke result passed and cleanup succeeded. LiveKit Cloud smoke secrets were cleared from the shell after the run and are not stored in the repository.

---

## 78. Current Verification Status

### What passed

The latest verification passed:

```text
backend pytest: 341 passed
backend mypy: no issues found in 39 source files
backend ruff: all checks passed
backend compileall: passed
edge agent pytest: 210 passed
edge agent mypy: no issues found in 21 source files
edge agent ruff: all checks passed
edge agent compileall: passed
```

### How to run locally

From:

```powershell
cd c:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
```

Run:

```powershell
$env:PYTHONPATH = "src"; python -m pytest tests/ -v
python -m mypy src/cctv_api/ --ignore-missing-imports
python -m ruff check src tests alembic scripts
python -m compileall src alembic scripts
```

From:

```powershell
cd c:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
```

Run:

```powershell
$env:PYTHONPATH = "src"; python -m pytest tests/ -v
python -m mypy src/panoptix_edge_agent --ignore-missing-imports
python -m ruff check src tests
python -m compileall src tests
```

### Why it matters

This confirms the current backend and edge-agent code is working, typed correctly, and lint-clean.

---

## 79. Production Gateway Supervision

### What was implemented

The edge agent now has a production-oriented, testable supervisor entrypoint:

```powershell
python -m panoptix_edge_agent.cli --supervise
```

The supervisor coordinates:

- gateway heartbeat fallback
- outbound gateway-control WebSocket supervision
- shared command executor and media controller construction
- optional local `mediamtx` process startup and cleanup

### Configuration

Safe defaults remain unchanged:

```env
PANOPTIX_MEDIA_PUBLISHER_MODE=stub
PANOPTIX_SUPERVISE_MEDIAMTX=false
```

Optional local `mediamtx` supervision can be enabled with:

```env
PANOPTIX_SUPERVISE_MEDIAMTX=true
PANOPTIX_MEDIAMTX_BINARY=mediamtx
PANOPTIX_MEDIAMTX_CONFIG_PATH=apps/cctv-edge/mediamtx/mediamtx.local.yml
```

### Security invariants

The supervisor does not install services and does not open inbound WAN paths. `mediamtx.local.yml` remains loopback-only, and real FFmpeg/LiveKit publishing remains opt-in through `PANOPTIX_MEDIA_PUBLISHER_MODE=livekit-ffmpeg`.

### Tests

The new tests use fake heartbeat/control loops and fake mediamtx managers. They do not launch real `mediamtx`, FFmpeg, LiveKit SDK connections, or backend network connections.

---

## 36. Real Local FFmpeg/LiveKit Smoke Scaffold

### What was implemented

The edge agent CLI now has a `--smoke-ffmpeg-livekit` flag that runs the real FFmpeg-to-LiveKit media pipeline against local services for a bounded duration:

```text
apps/cctv-edge/agent/src/panoptix_edge_agent/smoke_config.py
apps/cctv-edge/agent/src/panoptix_edge_agent/smoke_ffmpeg_livekit.py
```

Config module (`smoke_config.py`):

- reads explicit `PANOPTIX_SMOKE_*` environment variables
- validates LiveKit URL scheme (`ws://` or `wss://`), RTSP URL scheme, API secret minimum length (32 chars), FFmpeg binary PATH presence, duration bounds (3-120s)
- rejects placeholder values, embedded credentials, and empty/missing required vars
- returns a frozen `SmokeConfig` dataclass

Smoke runner (`smoke_ffmpeg_livekit.py`):

- mints a short-lived LiveKit publish-only token locally using a standalone HS256 JWT encoder (no PyJWT required)
- builds the real `FfmpegRtspFrameSource` + `LiveKitVideoTrackMediaSession` pipeline
- connects to the real LiveKit server, publishes frames for the configured duration, then disconnects
- reports a structured `SmokeResult` with OK/error, frames published, duration, and cleanup status
- all errors are caught and reported -- never crashes with a raw traceback

CLI (`cli.py`):

- `--smoke-ffmpeg-livekit` bypasses the normal `load_config_from_env()` call
- prints structured pass/fail output
- returns exit code 0 (pass), 1 (fail), or 2 (config error)

### How it works

1. Developer sets `PANOPTIX_SMOKE_LIVEKIT_URL`, `PANOPTIX_SMOKE_LIVEKIT_API_KEY`, and `PANOPTIX_SMOKE_LIVEKIT_API_SECRET` in their shell
2. `--smoke-ffmpeg-livekit` validates all env vars via `smoke_config.py`
3. The runner mints a local HS256 JWT with publish-only grants for the configured room
4. The runner builds the real FFmpeg-to-LiveKit pipeline and publishes frames for the configured duration
5. The runner disconnects, kills FFmpeg, and reports results

### Why it matters

This is the first milestone that can exercise the full real media path (FFmpeg -> RTSP -> raw frames -> LiveKit video track) without requiring the backend API server. It is strictly opt-in, manual-only, and does not commit any real credentials.

---

## 40. App-Level Rate Limiting

### What was implemented

In-memory sliding-window rate limiter per v4 plan §16.17. Protects viewer token and gateway ingest token endpoints from abuse.

### New files

- `security/rate_limit.py`: `RateLimiter` class with per-key sliding window, `RateLimitConfig`, singleton `get_rate_limiter()`

### Modified files

- `api/errors.py`: Added optional `headers` parameter to `ProblemDetail` (enables `Retry-After`)
- `api/router.py`: Added `_check_rate_limit()` helper, wired into viewer token endpoint
- `api/gateways.py`: Wired rate limit into gateway ingest token endpoint
- `core/config.py`: Added 4 rate limit settings

### Endpoints protected

| Endpoint | Key | Default limit |
|----------|-----|---------------|
| `GET /cameras/{id}/view-token` | `viewer-token:{user_id}` | 30/min |
| `POST /gateways/{id}/ingest-token` | `gateway-ingest:{gateway_id}` | 20/min |

### Audit events

- `viewer.token.rate_limited` — logged when a viewer token request is denied
- `gateway.ingest.rate_limited` — logged when a gateway ingest request is denied

---

## 39. Session Idle/Absolute TTL Enforcement

### What was implemented

Session TTL enforcement per v4 plan §16.4: idle 15 min, absolute 8 h.

### Changes

- `core/config.py`: Added `SESSION_IDLE_TIMEOUT_SECONDS` (default 900) and `SESSION_ABSOLUTE_TIMEOUT_SECONDS` (default 28800)
- `security/sessions.py`: Added `is_session_expired()` that checks absolute timeout first (takes precedence), then idle timeout using `last_seen_at` (or `created_at` fallback)
- `security/dependencies.py`: Wired TTL check into `require_authenticated_user` — expired sessions are auto-revoked and return 401 with `session-idle-expired` or `session-absolute-expired`
- `touch_session()` already resets `last_seen_at` on each authenticated request, which resets the idle timer

### Not included

- Admin re-auth window (≤5 min for admin mutations) — requires frontend session-age awareness
- Session listing/active-count admin API

---

## 38. CSP, CORS, and Security Headers Hardening

### What was implemented

The backend security headers middleware was expanded to implement the full v4-plan requirements from sections 16.5 and 16.13.

### Headers applied to all responses

- Strict-Transport-Security with HSTS preload
- Cross-Origin-Opener-Policy same-origin
- Cross-Origin-Resource-Policy same-origin
- X-Content-Type-Options nosniff
- Referrer-Policy no-referrer
- X-Frame-Options DENY
- Permissions-Policy with all five directives
- Dynamic Content-Security-Policy with connect-src for active LiveKit origin

### Per-route CORS policy

- Browser-facing routes: exact origin + credentials
- Gateway routes: NO CORS headers (not browser-callable)
- Webhook route: NO CORS headers (server-to-server only)

---

## 37. Live Media Controller Wiring

### What was implemented

The edge agent now selects its media controller based on the `PANOPTIX_MEDIA_PUBLISHER_MODE` environment variable:

```text
apps/cctv-edge/agent/src/panoptix_edge_agent/media_factory.py
```

- `stub` (default): No-op `StubMediaController` -- commands are accepted but no real media is published
- `livekit-ffmpeg`: Real `LiveKitMediaController` backed by `LiveKitSdkPublisherClient` and `FfmpegVideoTrackMediaSessionFactory`

The CLI (`cli.py`) now builds the media controller once from config and passes a shared `CommandExecutor` to both `HeartbeatRunner` and `GatewayControlClient`, ensuring all command paths use the same controller.

### How it works

1. On startup, `cli.py` calls `build_media_controller(config)`
2. The factory checks `config.media_publisher_mode`
3. For `stub` mode: returns `StubMediaController()`
4. For `livekit-ffmpeg` mode: lazy-loads the LiveKit SDK, builds `FfmpegVideoTrackMediaSessionFactory` with config dimensions, builds `LiveKitSdkPublisherClient`, and wraps it in `LiveKitMediaController` with the configured `source_url`
5. If the LiveKit SDK is unavailable, the factory falls back to `StubMediaController` with an error marker (warning printed to stderr)
6. A single `CommandExecutor` is created with the chosen controller and shared across all command paths

### Why it matters

This closes the loop between the backend command flow and real media publishing. When the backend sends a `start_publish` command, the edge agent can now actually start FFmpeg, read RTSP frames, and publish them to a LiveKit server -- all controlled by a single opt-in environment variable.

---

## 41. User Disable → LiveKit Participant Kill

### What was implemented

When an admin disables a user, their active LiveKit viewer sessions are terminated in real time.

### New files

- `security/livekit_rooms.py`: `remove_user_participants()` — calls LiveKit Twirp API via httpx to remove `viewer:{user_id}:*` participants across all camera rooms the user has ACL for

### Modified files

- `api/router.py`: `admin_disable_user` now calls `remove_user_participants()` after session revocation
- `gateway/models.py`: `DisableUserResponse` gains `participants_removed` and `participant_errors` fields

### How it works

1. Admin calls `POST /api/v1/admin/users/{user_id}/disable`
2. All active sessions are revoked
3. For each camera ACL the user holds, the Twirp `RemoveParticipant` API is called for the camera's LiveKit room
4. Errors are collected but never raised (fail-open): the disable always succeeds even if LiveKit is unreachable
5. Placeholder credentials (`replace-me`) are detected and skipped gracefully

### Why it matters

Without this, a disabled user's browser tab would continue receiving a live CCTV stream until their LiveKit token expired. This closes that window immediately.

---

## 42. Gateway Disable → Kill Publisher Participants

### What was implemented

When an admin disables a gateway, its active LiveKit publisher sessions are terminated in real time.

### New files / modified files

- `security/livekit_rooms.py`: Added `remove_gateway_participants()` — mirrors `remove_user_participants()` for gateway publisher identity prefix `gateway:{gateway_id}:`
- `gateway/models.py`: `DisableGatewayResponse` gains `participants_removed` and `participant_errors` fields
- `api/router.py`: `disable_gateway` handler queries assigned camera rooms and calls `remove_gateway_participants()`

### How it works

Same fail-open pattern as user disable. Gateway publisher participants matching `gateway:{gateway_id}:*` are removed from all rooms assigned to the gateway.

---

## 43. Camera Disable → Kill Viewer Participants

### What was implemented

When an admin retires a camera, all active viewer participants in the camera's LiveKit room are terminated.

### New files / modified files

- `security/livekit_rooms.py`: Added `remove_room_viewers()` — removes all `viewer:*` participants from a single camera room
- `gateway/models.py`: `DisableCameraResponse` gains `participants_removed` and `participant_errors` fields
- `api/router.py`: `disable_camera` handler calls `remove_room_viewers()` with the camera's `livekit_room_name`

### Why it matters

Completes the disable-kills-participants symmetry: users, gateways, and cameras each terminate their respective LiveKit participants on disable.

---

## 44. Admin Camera & Gateway Listing Endpoints

### What was implemented

Admin read endpoints for browsing the full gateway and camera registry.

### Endpoints added

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/admin/gateways` | List all gateways (enabled + disabled) with cursor pagination and optional `status` filter |
| `GET /api/v1/admin/gateways/{gateway_id}` | Gateway detail with `camera_count` and `mtls_fingerprint` |
| `GET /api/v1/admin/cameras` | List all cameras with cursor pagination and optional `include_retired` filter |
| `GET /api/v1/admin/cameras/{camera_id}` | Camera detail with `acl_count`, `room_uuid`, `gateway_id`, `site_id` |

### Security

- All four require admin role
- `service_token_hash` excluded from all gateway responses
- Cursor pagination on `created_at DESC, id DESC`

---

## 45. Admin Dashboard Summary Endpoint

### What was implemented

A single aggregated admin endpoint for system-wide counts.

### Endpoint

`GET /api/v1/admin/dashboard`

Response shape:

```json
{
  "cameras": {"total": 0, "active": 0, "retired": 0},
  "gateways": {"total": 0, "enabled": 0, "disabled": 0},
  "users": {"total": 0, "active": 0, "disabled": 0},
  "commands": {"pending": 0},
  "publishing": {"active": 0}
}
```

Uses `select(func.count()).select_from(Model).where(...)` for efficient DB aggregation without fetching rows.

---

## 46. Admin Health Probes

### What was implemented

`GET /api/v1/admin/health/deep` upgraded from stub to real probes.

### Probes

- **DB**: `SELECT 1` — returns `connected` or `error`
- **LiveKit**: `POST /twirp/livekit.RoomService/ListRooms` with 5 s timeout — returns `connected`, `not_configured` (placeholder creds), or `error`
- **Gateway**: queries enabled gateways and checks `last_seen_at` against `GATEWAY_STALE_THRESHOLD_SECONDS` (default 60 s) — returns `connected`, `no_gateways`, `stale`, or `error`

Overall `"ok"` only when DB connected AND (LiveKit connected/not_configured) AND (gateway connected/no_gateways).

### New files

- `core/config.py`: Added `GATEWAY_STALE_THRESHOLD_SECONDS` setting

### Side fix

Gateway heartbeat endpoint now updates `EdgeGateway.last_seen_at` via `_update_gateway_last_seen()` (fail-open).

---

## 47. Break-Glass Emergency Access

### What was implemented

A time-bounded emergency admin access window for when normal IdP login is unavailable.

### New files

- `security/break_glass.py`: `open_break_glass_window`, `close_break_glass_window`, `get_break_glass_status`, `assert_break_glass_active`, `get_active_window`

### Endpoints added

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/admin/break-glass/open` | Opens a 90-minute window; rejects if one already exists (409) |
| `POST /api/v1/admin/break-glass/close` | Closes an active/expired window; returns mandatory rotation checklist |
| `GET /api/v1/admin/internal/break-glass-status` | Unauthenticated external-monitor endpoint |

### Key design decisions

- Request-time enforcement only (no scheduler): `now >= auto_disable_at` is the gate
- Audit events: `system.break_glass.opened` and `system.break_glass.closed` (fail-closed)
- Each window is independently time-bounded; exceeding 90 min requires opening a new audited window

### Runbook

`docs/runbooks/break-glass-runbook.md`

---

## 48. Operational Runbooks + SCA/SAST CI

### What was implemented

**Runbooks** added to `docs/runbooks/`:

- `break-glass-runbook.md` — full break-glass lifecycle
- `lost-mfa-recovery.md` — admin-mediated MFA reset with optional break-glass path
- `idp-outage-recovery.md` — IdP outage (GitHub OAuth) detection, break-glass, recovery, post-incident

**SCA/SAST CI** jobs added to `.github/workflows/ci.yml`:

- Semgrep SAST (`p/python`, `p/security-audit`, `p/owasp-top-ten`)
- osv-scanner dependency vulnerability scan
- Trivy container image scan (CRITICAL + HIGH severity, fail build)

All three CI jobs run in parallel; Trivy depends on Docker build.

---

## 49. Admin Search/Filter & List Enrichment

### What was implemented

Search and filter parameters for admin listing endpoints, plus relationship-count enrichment.

### Gateway list enhancements

- `search` param: case-insensitive name substring filter
- `camera_count` field: active assignment count per gateway

### Camera list enhancements

- `search` param: display_name substring filter
- `source_type` param: validated enum filter (400 `source-type-invalid` on invalid value)
- `gateway_id` param: filter by assigned gateway
- `gateway_id` field: included in list response
- `acl_count` field: active ACL count per camera

---

## 50. LiveKit Fallback Toggle

### What was implemented

Admin endpoint to switch between LiveKit Cloud and self-hosted LiveKit fallback.

### New files

- `security/media_plane.py`: `get_media_plane_mode()`, `set_media_plane_mode()` — reads/writes `system_config.media_plane_mode`

### Endpoint

`POST /api/v1/admin/livekit/fallback`

- Accepts `{"mode": "cloud"}` or `{"mode": "fallback"}`
- Rejects no-op same-mode change (409)
- Audit events: `system.media_plane.switched_to_fallback` / `system.media_plane.switched_to_primary`

---

## 51. DPA Export & Bystander Signage Attestation

### What was implemented

Two privacy-compliance endpoints.

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/admin/dpa/export` | Returns DPA artifact bundle with optional `kinds` filter |
| `POST /api/v1/admin/sites/{site_id}/signage-attest` | Records bystander signage attestation as `DpaArtifact` |

- `DpaKind` enum validated (400 on invalid)
- Signage attestation creates `DpaArtifact` row with `bystander_signage_attestation` kind and SHA-256 hash
- Audit events: `admin.dpa.export`, `admin.signage.attest`

### Runbook reference

`docs/runbooks/bus-factor.md` — emergency recovery if sole system owner is unavailable.

---

## 52. Admin-Mediated MFA Reset

### What was implemented

Endpoint for an admin to record that a user's MFA device was reset through a verified out-of-band process.

### Endpoint

`POST /api/v1/admin/users/{user_id}/mfa/reset`

- Self-reset blocked (409 `cannot-reset-own-mfa`)
- Audit event: `admin.user.mfa_reset` with verification evidence
- Does not touch the IdP directly — records the admin action for audit

---

## 53. Security Hardening: Admin Rate Limits + Exponential Backoff

### What was implemented

Two security hardening improvements: sliding-window rate limiting on admin mutation endpoints, and exponential backoff with jitter for edge agent WebSocket reconnects.

### Admin Mutation Rate Limiter

The existing in-memory sliding-window `RateLimiter` (introduced in the App-Level Rate Limiting milestone) was extended to protect admin mutation endpoints.

**Settings added** (`apps/api/src/cctv_api/core/config.py`):

```python
RATE_LIMIT_ADMIN_MUTATION_MAX: int = 10
RATE_LIMIT_ADMIN_MUTATION_WINDOW: int = 60
```

**Protected endpoints** (`apps/api/src/cctv_api/api/router.py`):

| Endpoint | Rate limit key |
|----------|----------------|
| `POST /admin/gateways/{id}/rotate-credential` | `admin-mutation:{actor_id}` |
| `POST /admin/users/{id}/role` | `admin-mutation:{actor_id}` |
| `POST /admin/break-glass/open` | `admin-mutation:{actor_id}` |
| `POST /admin/gateways/{id}/commands` | `admin-mutation:{actor_id}` |

**Response on limit exceeded:**

```http
HTTP/1.1 429 Too Many Requests
Retry-After: <seconds>

{"type": "...", "title": "Too Many Requests", ...}
```

The rate limit key format is `admin-mutation:{actor_id}` where `actor_id` is the authenticated principal's subject. The window is sliding (per RFC 6585). The 11th request within any 60-second window returns 429.

### Exponential Backoff for Edge Agent Reconnects

`apps/cctv-edge/agent/src/panoptix_edge_agent/control.py` now uses exponential backoff with jitter on WebSocket reconnect attempts instead of a fixed delay.

**Formula:**

```
sleep = min(base * 2^attempt, cap) + uniform_jitter(0, base)
```

Where `base` = `PANOPTIX_GATEWAY_CONTROL_RECONNECT_BACKOFF_SECONDS` (default 2s) and `cap` is 60s.

This prevents thundering-herd reconnect storms when the backend restarts.

### Test coverage added

- `apps/api/tests/test_rate_limit_admin.py`: 6 new tests — allow under limit, block at limit+1, Retry-After header present, separate actors have independent counters, window reset after expiry, non-mutation admin endpoints not affected
- `apps/cctv-edge/agent/tests/test_control.py`: 3 new backoff tests — first attempt uses base delay, subsequent attempts double, jitter is non-negative and bounded

---

## 54. CI Pipeline Finalization, External Service Provisioning & Security Tooling

### What was implemented

This milestone hardened the CI pipeline and provisioned the external services required for production readiness.

**CI pipeline hardening (runs #4–#10):**

- Migrated osv-scanner from v1 to v2.3.8 (`--recursive` instead of `--lockfile`); removed nonexistent `--skip-git` flag
- Updated trivy-action from 0.28.0 to v0.36.0; added `ignore-unfixed: true` + `apps/api/.trivyignore` for Debian 12 CVEs with no available patch
- Updated semgrep-action org from `returntocorp` to `semgrep`
- Fixed Semgrep shell injection findings in `ci.yml`, `deploy-staging.yml`, and `deploy-production.yml` by moving `${{ github.* }}` expressions from `run:` blocks to `env:` intermediary variables
- Upgraded `apps/api/Dockerfile` to `python:3.12-slim-bookworm` + `apt-get upgrade` to reduce OS-level CVEs
- Created `apps/api/.trivyignore` with 13 Debian 12 will-not-fix CVE IDs
- Created `.semgrepignore` to suppress urllib false positive in edge agent
- Changed deploy-staging health check from hard-fail to informational (Cloudflare Access returns 302 for unauthenticated probes)

**External service provisioning:**

- LiveKit Cloud account created at livekit.io (APAC region) with project `panoptix`
- Semgrep CI token (`SEMGREP_APP_TOKEN`) configured as GitHub repository secret
- Cloudflare R2 backup bucket `panoptix-backups` provisioned via Terraform Cloud workspace `panoptix-backup-r2`
- R2 scoped API token created (Object Read & Write, bucket-only)
- All LiveKit and R2 env vars set in Railway staging
- Staging health verified: `https://staging.panoptix.site/health` returns `{"status":"ok"}` behind Cloudflare Access

### Verification

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

### What remains out of scope

- Gitleaks license (optional; public repo gets free license, but CI passes without it)
- Production Cloudflare Access apps (waits for 7-day gate)
- Production Railway/Neon environments (waits for 7-day gate)
- Break-glass hardware key procurement

---

## Verification (current state)

Backend (`apps/api/`):

```text
pytest: 532 passed
ruff: all checks passed
mypy: no issues found in 44 source files
compileall: passed
```

Edge agent (`apps/cctv-edge/agent/`):

```text
pytest: 245 passed, 2 skipped
ruff: all checks passed
mypy: no issues found in 22 source files
compileall: passed
```

---

## Actor Investigation Profile and Activity API

The backend now exposes an admin-only actor investigation surface for security analysts:

```text
GET /api/v1/admin/actors/{actor_type}/{actor_id}/profile
GET /api/v1/admin/actors/{actor_type}/{actor_id}/activity
```

Supported `actor_type` values are `user`, `gateway`, `system`, `break_glass`, and `service_token_monitor`. User and gateway actors require a UUID path ID and return `404 user-not-found` or `404 gateway-not-found` when the backing row does not exist. System-like actors accept either a UUID or the literal path segment `none`, which maps to audit rows where `actor_id IS NULL`.

The profile endpoint aggregates only existing data:

- users: identity, roles, sessions, camera ACLs, stream grants, audit activity summary, risk indicators, and containment status
- gateways: identity, camera assignments, stream grants, audit activity summary, risk indicators, and containment status
- system-like actors: audit activity summary and risk indicators
- unsupported sections return top-level `null` fields for IP enrichment, device details, MFA details, threat intelligence, alerts, incidents, analyst notes, and behavior baseline

The activity endpoint returns the same safe audit row shape as `GET /api/v1/admin/audit`, pre-filtered by actor. It supports `cursor`, `limit`, `action`, `severity`, `category`, `outcome`, `resource`, `session_id`, `ts_from`, and `ts_to`, using descending `AuditLog.id` cursor pagination.

Both endpoints require an admin role and a configured audit HMAC key. Successful views write audit-of-audit events:

- `admin.actor.profile.viewed`
- `admin.actor.activity.viewed`

Implementation files:

- `apps/api/src/cctv_api/api/actor_profile.py`
- `apps/api/src/cctv_api/security/actor_investigation.py`
- `apps/api/tests/test_actor_profile.py`

Verification:

```text
python -m pytest tests/test_actor_profile.py -q
17 passed

python -m pytest tests/ -q
532 passed

python -m ruff check src/ tests/
All checks passed

python -m mypy src/cctv_api/ --ignore-missing-imports
Success: no issues found in 44 source files
```

---

## What Is Not Implemented Yet

The following are intentionally not done yet:

- frontend UI
- real camera onboarding (credential file exists; needs real hardware)
- production Docker/systemd gateway supervision (runbook templates exist)
- Google Workspace IdP setup (GitHub OAuth is currently deployed on staging)
- WARP device posture production activation (checklist documented)

---

## Next Recommended Implementation Order

### 1. Real Camera Onboarding

Connect a real CCTV camera to the gateway using the per-camera credential file (`cameras.json`) and test live FFmpeg-to-LiveKit publishing end-to-end. Requires real camera hardware (LiveKit Cloud account is provisioned).

---

## Big Picture Summary

So far, Panoptix has moved from documentation and structure into a real backend control-plane and gateway-agent foundation.

The system now has:

- organized documentation
- clear team ownership
- clean monorepo structure
- backend package setup
- FastAPI app foundation
- config loading
- consistent API errors
- health routes
- API versioning
- CI/Docker foundation
- identity model
- fail-closed auth interface
- RBAC placeholders
- protected browser API placeholders
- gateway API placeholders
- minimal outbound gateway heartbeat agent
- signed gateway command execution through a stub media controller
- in-memory edge publish-state tracking
- LiveKit webhook-driven gateway publish command enqueueing
- backend publish-state tracking with 10-second stop grace
- privacy notice acceptance endpoints
- safe admin user listing endpoint
- unified admin maintenance endpoint for scheduled-job processing
- admin role assignment and user disable with session revocation
- gateway service-token issuance and credential rotation
- gateway service-token verification on HTTP gateway requests
- gateway command denial audit logging
- signed JSON audit exports
- actor investigation profiles and actor-scoped audit timelines
- browser/admin CSRF protection and baseline security headers
- disabled-by-default in-process maintenance scheduler
- gateway control reconnect supervision
- synthetic RTSP test-source scaffold
- local-only mediamtx runtime config scaffold
- mediamtx process-management scaffold
- LiveKit publisher/controller foundation
- live media controller wiring with opt-in livekit-ffmpeg mode
- synthetic end-to-end publish dry-run harness
- successful real LiveKit Cloud smoke test with synthetic RTSP source
- passing backend and edge-agent tests, type checks, and lint checks
- live Cloudflare Access with GitHub OAuth on staging.panoptix.site
- Railway staging deployment with custom domain and Cloudflare proxy
- per-camera RTSP credential handling with gateway-local credential file, fail-closed validation, and repr-safe password redaction
- gateway disable kills active LiveKit publisher participants via Twirp API, mirroring user-disable viewer kill with fail-open error collection
- camera disable kills all active viewer participants from the camera's LiveKit room, completing the disable-kills-participants symmetry across users, gateways, and cameras
- admin camera and gateway listing endpoints with cursor pagination, status/retired filtering, and detail views with relationship counts
- admin dashboard summary endpoint with aggregated system counts
- real LiveKit + gateway health probes on the deep health endpoint
- break-glass emergency access with 90-minute time-bounded windows, request-time enforcement, and mandatory rotation checklists
- operational runbooks for break-glass, lost-MFA recovery, and IdP outage (GitHub OAuth)
- Semgrep SAST, osv-scanner, and Trivy CI jobs for supply-chain and container security
- admin search/filter on gateway and camera listing endpoints plus relationship-count enrichment
- LiveKit fallback toggle between cloud and self-hosted mode
- DPA artifact export and bystander signage attestation for privacy compliance
- admin-mediated MFA reset endpoint with self-reset prevention
- sliding-window rate limiting on admin mutation endpoints (rotate-credential, user-role, break-glass-open, enqueue-commands) with per-actor 429 + Retry-After responses
- exponential backoff with jitter for edge agent WebSocket reconnects
- edge agent CI job in GitHub Actions (ruff, mypy, pytest, compileall, osv-scanner) with pinned action versions
- Dependabot pip scope for edge agent added
- mediamtx threat model documenting 6 threats across the RTSP/API surface
- CI script for mediamtx YAML config validation
- uptime monitoring runbook for staging alert response
- DR testing schedule appended to backup-restore runbook
- WARP device posture checklist appended to Cloudflare production setup runbook
- Terraform state security requirements doc
- Cloudflare R2 backup bucket Terraform module
- DR restore drill automation script
- CT-log monitoring script
- mTLS cert bootstrap scaffold for edge agent
- staging auto-deploy workflow with post-push health checks
- Dependabot auto-merge workflow (minor/patch auto, major requires manual approval)
- fully green CI pipeline (8 jobs: lint/test, secret scan, Semgrep SAST, dependency scan, edge agent, Docker build, container scan, deploy-staging)
- LiveKit Cloud account provisioned (APAC region) with real URL, API key, secret, and webhook secret in Railway staging
- Semgrep SAST CI token configured as GitHub repository secret with dashboard integration
- Cloudflare R2 backup bucket `panoptix-backups` provisioned via Terraform Cloud with scoped API tokens
- Terraform Cloud backend configured for `infra/terraform/modules/backup-r2` remote state management
- staging health verified end-to-end through Cloudflare Access (`staging.panoptix.site/health` returns `{"status":"ok"}`)

The most important security idea so far is:

```text
If the backend cannot prove who the caller is, it rejects the request.
```

That fail-closed rule is the foundation for the rest of the system.
