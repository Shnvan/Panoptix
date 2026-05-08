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

## 23. Current Verification Status

### What passed

The latest verification passed:

```text
pytest: 26 passed
mypy: no issues found
ruff: all checks passed
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
python -m ruff check src/ tests/
```

### Why it matters

This confirms the current backend code is working, typed correctly, and lint-clean.

---

## What Is Not Implemented Yet

The following are intentionally not done yet:

- real Cloudflare Access JWT verification
- real session store
- real database integration
- database schema/migrations
- frontend UI
- real LiveKit viewer token minting
- real gateway publish token minting
- real WebSocket command stream
- real gateway agent
- mediamtx runtime configuration
- audit HMAC chain implementation

---

## Next Recommended Implementation Order

### 1. Real Cloudflare Access JWT Verification

Add production JWT verification using Cloudflare Access JWKS, issuer, audience, and clock-skew validation.

### 2. Backend Session Foundation

Add session interfaces after coordinating database table contracts with the database coworker.

### 3. LiveKit Token Minting Foundation

Add viewer-subscribe token generation and gateway-publish token generation, with strict token kind separation.

### 4. Audit Foundation

Add backend audit event interfaces while coordinating append-only storage with the database coworker.

### 5. Gateway Agent Foundation

Begin the actual gateway agent under `apps/cctv-edge/agent` after backend routes and contracts are stable.

---

## Big Picture Summary

So far, Panoptix has moved from documentation and structure into a real backend control-plane foundation.

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
- passing backend tests, type checks, and lint checks

The most important security idea so far is:

```text
If the backend cannot prove who the caller is, it rejects the request.
```

That fail-closed rule is the foundation for the rest of the system.
