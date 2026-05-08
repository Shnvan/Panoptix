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
- [x] `.gitignore` added (ignores `.env`, `__pycache__`, `node_modules`, `CLAUDE.md`, `execute.md`)
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

---

## Next Steps (In Order)

### 1. Security Foundation
Add Cloudflare Access JWT verification interfaces, RBAC module placeholders, and security error handling.

### 2. Gateway Foundation
Add backend-to-gateway command channel interfaces, heartbeat structure, and WebSocket entry point.

---

## Key References

| What | Where |
|------|-------|
| Full system plan | `docs/planning/secure-cctv-monitoring-system-v4.md` |
| API contract | `docs/implementation/api-reference.md` |
| Team ownership | `docs/implementation/team-raci-checklist.md` |
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
