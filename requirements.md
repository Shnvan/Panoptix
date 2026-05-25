# Panoptix Requirements and Dependencies

This file lists the tools and package managers currently used by the repository. It distinguishes implemented workspaces from planned/frontend-owned work.

## System Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Git | latest stable | Version control |
| Python | 3.12+ | Backend and edge-agent runtime |
| Docker | latest stable | Backend image build and future gateway containers |
| PostgreSQL client tools | 16+ | `psql`, `pg_dump`, `pg_restore` |
| FFmpeg | 6.1+ recommended | Synthetic RTSP and LiveKit smoke tests |
| mediamtx | pinned later | Local RTSP bridge for gateway testing |
| Terraform | latest stable | Cloudflare R2 module operations |
| AWS CLI or rclone | latest stable | R2 backup verification and restore drills |

Node.js is required for the frontend (`apps/web/`). Package manager: `npm` using `package.json`.

## Backend - `apps/api/`

Package manager: `pip` using `pyproject.toml`.

Production dependencies currently declared:

- `fastapi`
- `uvicorn[standard]`
- `pydantic`
- `pydantic-settings`
- `PyJWT[crypto]`
- `sqlalchemy`
- `psycopg[binary]`
- `alembic`
- `httpx`

Development dependencies currently declared:

- `pytest`
- `ruff`
- `mypy`

Install and verify:

```powershell
Set-Location apps\api
python -m pip install --upgrade pip
python -m pip install ".[dev]"
$env:PYTHONPATH = "src"
python -m pytest tests/ -v
python -m ruff check src tests alembic scripts
python -m mypy src/cctv_api/ --ignore-missing-imports
python -m compileall src alembic scripts
```

Run locally:

```powershell
Set-Location apps\api
$env:PYTHONPATH = "src"
python -m uvicorn cctv_api.main:app --reload --host 127.0.0.1 --port 8000
```

## Edge Agent - `apps/cctv-edge/agent/`

Package manager: `pip` using `pyproject.toml`.

Production dependencies currently declared:

- `websockets`
- `cryptography`

Optional LiveKit publishing dependency:

- `livekit` via `.[livekit]`

Development dependencies currently declared:

- `pytest`
- `ruff`
- `mypy`

Install and verify:

```powershell
Set-Location apps\cctv-edge\agent
python -m pip install --upgrade pip
python -m pip install ".[dev]"
$env:PYTHONPATH = "src"
python -m pytest tests/ -v
python -m ruff check src tests
python -m mypy src/panoptix_edge_agent --ignore-missing-imports
python -m compileall src tests
```

Install optional LiveKit SDK support:

```powershell
Set-Location apps\cctv-edge\agent
python -m pip install -e ".[livekit]"
```

## Frontend - `apps/web/`

The frontend is owned by the frontend coworker. Current stack:

- React 19
- Vite 6
- TypeScript
- Tailwind CSS 4
- Lucide React (icons)
- Recharts (charts)
- Motion (animations)
- `livekit-client` for viewer-subscribe only (planned)

## Database

The backend contains SQLAlchemy models and Alembic migrations under `apps/api/`. Database design ownership remains documented in `docs/implementation/team-raci-checklist.md`.

Useful tools:

- PostgreSQL 16+ client tools
- Alembic from backend dependencies
- `apps/api/scripts/db_validate.py`

## CI/CD

GitHub Actions currently runs:

- backend lint, type check, tests
- Docker build check
- Gitleaks secret scan
- Semgrep SAST
- osv-scanner dependency scans for backend and edge agent
- Trivy container image scan
- edge-agent lint, type check, tests, compile check

Not currently implemented as CI gates:

- frontend bundle scan
- SBOM generation/signing
- Playwright
- ZAP baseline
- k6 load tests
- exact Python dependency lockfile install

Those remain future/frontend or pilot-readiness work unless implemented in a later milestone.

## External Services

| Service | Current status |
|---------|----------------|
| GitHub | Active repository, CI, Dependabot, branch rules |
| Railway | Staging backend active |
| Cloudflare | Domain, Access staging app, R2 bucket active |
| Neon | Staging database active |
| LiveKit Cloud | APAC project provisioned |
| Google Workspace | Planned for production IdP |
| Sentry / Better Stack / UptimeRobot | Planned, not required for current backend/edge work |

## References

| What | Where |
|------|-------|
| Environment variables | `.env.example` |
| Backend API contract | `docs/implementation/api-reference.md` |
| Local manual checks | `MANUAL_TESTING.md` |
| Team ownership | `docs/implementation/team-raci-checklist.md` |
| Current status | `PROGRESS.md` |
