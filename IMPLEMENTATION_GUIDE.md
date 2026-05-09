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

The backend now has a minimal audit writer:

```text
apps/api/src/cctv_api/security/audit.py
```

It writes real rows to the existing append-only `audit_log` table and ensures a placeholder audit key exists in `audit_hmac_keys`.

### How it works

The audit writer records:

- actor type and actor ID
- action name
- resource name
- request IP and user agent when available
- scrubbed JSON payload
- placeholder `prev_hash`, `hash`, and `hmac_key_version`

Sensitive payload fields such as tokens, JWTs, secrets, cookies, credentials, passwords, and API keys are redacted before insertion.

The current integrations audit:

- viewer token issued and denied paths
- gateway ingest-token issued and denied paths
- session revoke success, not-found, and not-owned denial paths

### Important limitation

The current audit hash is a deterministic placeholder, not a real HMAC chain. Real HMAC-SHA-256 chaining, previous-hash continuity, key rotation, verifier jobs, admin audit endpoints, and export signing remain future work.

### Why it matters

The backend now records security-critical actions without storing raw media tokens or credentials, while preserving the long-term append-only audit architecture.

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

## 32. Current Verification Status

### What passed

The latest verification passed:

```text
edge agent pytest: 37 passed
edge agent mypy: no issues found
edge agent ruff: all checks passed
edge agent compileall: passed
pytest: 63 passed
mypy: no issues found
ruff: all checks passed
compileall: passed
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

## What Is Not Implemented Yet

The following are intentionally not done yet:

- frontend UI
- persistent backend command queue
- edge gateway control reconnect/backoff loop
- mediamtx runtime configuration
- audit HMAC chain implementation
- admin audit list/export/verify endpoints
- gateway command queue/dispatch/ACK
- LiveKit publishing orchestration

---

## Next Recommended Implementation Order

### 1. Edge Gateway Control Reconnect/Backoff Skeleton

Add bounded reconnect/backoff behavior for the outbound gateway control WebSocket before any persistent DB command queue, mediamtx control, or LiveKit publishing orchestration.

### 2. Audit HMAC Chain Foundation

Replace placeholder audit hashes with real HMAC-SHA-256 chaining, previous-hash continuity, key lifecycle handling, and verification helpers.

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
- passing backend and edge-agent tests, type checks, and lint checks

The most important security idea so far is:

```text
If the backend cannot prove who the caller is, it rejects the request.
```

That fail-closed rule is the foundation for the rest of the system.
