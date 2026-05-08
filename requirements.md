# Panoptix — Full Requirements & Dependencies

Complete list of tools, runtimes, packages, and services needed across all workstreams.

---

## System Prerequisites (All Team Members)

Install these on your development machine before working on any part of the project.

| Tool | Version | Purpose | Install |
|------|---------|---------|---------|
| Git | latest stable | Version control | https://git-scm.com/downloads |
| Docker Desktop | latest stable | Container builds, local services | https://www.docker.com/products/docker-desktop |
| Python | 3.12.7+ | Backend runtime | https://www.python.org/downloads/ |
| Node.js | 22.x LTS | Frontend runtime/build | https://nodejs.org/ |
| FFmpeg | 6.1+ | Synthetic RTSP test source (dev/CI only) | https://ffmpeg.org/download.html |
| PostgreSQL client tools | 16+ | `psql`, `pg_dump`, `pg_restore` | https://www.postgresql.org/download/ |

---

## Backend — `apps/api/` (System Owner)

### Python packages (production)

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework for control-plane API |
| `uvicorn[standard]` | ASGI server |
| `pydantic` | Data validation |
| `pydantic-settings` | Environment/config loader |
| `PyJWT[crypto]` | Cloudflare Access JWT signature and claim verification |
| `sqlalchemy` | Database ORM and typed model definitions |
| `psycopg[binary]` | PostgreSQL driver |
| `alembic` | Database migration runner |

### Python packages (dev/test)

| Package | Purpose |
|---------|---------|
| `pytest` | Test framework |
| `httpx` | HTTP client for FastAPI TestClient |
| `ruff` | Linter and formatter |
| `mypy` | Static type checker |

### Future backend packages (not yet installed)

| Package | Purpose | When needed |
|---------|---------|-------------|
| `livekit-api` | LiveKit Server SDK | Viewer flow phase |
| `websockets` | Gateway WebSocket channel | Gateway foundation phase |
| `sentry-sdk[fastapi]` | Error monitoring | Pre-pilot |
| `age` | Backup encryption | Backup/restore runbook |

### Install commands

```powershell
cd apps\api
pip install .              # production deps
pip install ".[dev]"       # production + dev/test deps
```

### Run commands

```powershell
cd apps\api
$env:PYTHONPATH = "src"

# Run the API server locally
uvicorn cctv_api.main:app --reload

# Run tests
python -m pytest tests/ -v

# Lint
ruff check src/

# Type check
mypy src/cctv_api/ --ignore-missing-imports
```

---

## Frontend — `apps/web/` (Frontend Coworker)

### Node.js packages

| Package | Purpose |
|---------|---------|
| `next` | React framework with routing and SSR |
| `react` | UI component library |
| `react-dom` | React DOM renderer |
| `tailwindcss` | Utility-first CSS framework |
| `livekit-client` | LiveKit browser SDK (viewer-subscribe only) |
| `typescript` | Type safety |

### Dev packages

| Package | Purpose |
|---------|---------|
| `eslint` | Linter |
| `prettier` | Formatter |
| `playwright` | Browser/E2E tests |

### Install commands

```powershell
cd apps\web
npm install        # or pnpm install
```

### Important

- Frontend coworker owns this folder.
- Read `docs/frontend/frontend-guardrails.md` before starting.
- Browser must never publish camera/mic — viewer-subscribe only.
- All auth decisions come from `cctv-api`, not frontend code.

---

## Database — `database/` (Database Coworker)

### Tools

| Tool | Purpose |
|------|---------|
| PostgreSQL 16+ | Local database matching Neon behavior |
| `psql` | Database CLI |
| `pg_dump` / `pg_restore` | Backup/restore |
| SQLAlchemy 2.x | Python ORM (used by backend, schema owned by DB coworker) |
| Alembic | Migration management |

### Install commands

```powershell
# PostgreSQL — install from https://www.postgresql.org/download/
# Python packages (installed in backend venv)
pip install sqlalchemy alembic psycopg[binary]
```

### Important

- Database coworker owns this folder.
- Read `docs/database/database-guardrails.md` before starting.
- Schema must match `docs/architecture/erd.mmd`.
- Append-only audit triggers required.
- Runtime DB user must have least-privilege access.

---

## Gateway / Edge — `apps/cctv-edge/` (System Owner)

### Tools & binaries

| Tool | Version | Purpose |
|------|---------|---------|
| mediamtx | pinned release (TBD at procurement) | RTSP bridge on gateway |
| FFmpeg | 6.1+ | Synthetic RTSP test source |
| Docker | latest stable | Container runtime on gateway |
| Ubuntu Server | 22.04+ LTS | Gateway OS |

### Python packages (gateway agent)

| Package | Purpose |
|---------|---------|
| `websockets` | Outbound command channel to `cctv-api` |
| `httpx` | Heartbeat and token requests |
| `pydantic` | Command validation |

---

## Infrastructure — `infra/` (System Owner)

### Tools

| Tool | Purpose |
|------|---------|
| Terraform | Infrastructure as code for Cloudflare, Railway, Neon, R2 |
| Cloudflare CLI (optional) | DNS and Access policy management |

---

## CI/CD — `.github/` (System Owner)

### GitHub Actions used

| Action | Purpose |
|--------|---------|
| `actions/checkout` | Repo checkout |
| `actions/setup-python` | Python runtime in CI |
| `gitleaks/gitleaks-action` | Secret scanning |

### CI tools (installed in pipeline)

| Tool | Purpose |
|------|---------|
| ruff | Python linting |
| mypy | Python type checking |
| pytest | Python tests |
| Docker | Image build verification |

---

## External Services (Accounts Needed)

| Service | Purpose | Who sets up |
|---------|---------|-------------|
| GitHub | Code hosting, CI/CD | System owner |
| Railway | App hosting (frontend + backend) | System owner |
| Cloudflare | DNS, Access, WAF, R2 backups | System owner |
| Neon | Managed PostgreSQL | System owner |
| LiveKit Cloud | Media plane (video streaming) | System owner |
| Google Workspace | Identity provider (user login) | School admin |
| Sentry | Error monitoring | System owner |
| Better Stack | Log aggregation | System owner |
| UptimeRobot | External uptime checks | System owner |
| Telegram | Alert notifications | System owner |

---

## Quick Start for Each Role

### System owner (you)
```powershell
cd apps\api
pip install ".[dev]"
$env:PYTHONPATH = "src"; python -m pytest tests/ -v
```

### Frontend coworker
```powershell
cd apps\web
npm install
npm run dev
```

### Database coworker
```powershell
# Start local Postgres
# Then:
pip install sqlalchemy alembic psycopg[binary]
```

---

## References

| What | Where |
|------|-------|
| Tech stack explained | `docs/planning/tech-stack-simple.md` |
| Version pinning policy | `docs/adrs/0007-version-pinning.md` |
| Development setup | `docs/implementation/development-setup.md` |
| Environment variables | `.env.example` |
| API contract | `docs/implementation/api-reference.md` |
| Team ownership | `docs/implementation/team-raci-checklist.md` |
