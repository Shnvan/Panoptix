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
- [x] Placeholder audit hash/key fields added while real HMAC chaining remains deferred

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
- [x] Command queues, heartbeat fallback, persistence, and full reconnect loop remain deferred

---

## Next Steps (In Order)

### 1. Gateway Heartbeat Command Fallback Skeleton
Add in-memory/test-scaffolded heartbeat fallback delivery for pending commands before any persistent DB command queue, mediamtx control, or LiveKit publishing orchestration.

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
