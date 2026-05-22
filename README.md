# Panoptix - Secure CCTV Web Monitoring System

Panoptix is a live-view CCTV monitoring system that connects IP cameras to authenticated browser viewers through a security-first, three-plane architecture.

> **Status:** Production live at `panoptix.site` (2026-05-22). Backend control plane, edge-agent, CI/security scans, LiveKit Cloud, and R2 backup provisioning complete. Frontend integrated (staging smoke passed); real CCTV hardware onboarding still pending.

## Architecture

| Plane | Purpose | Current implementation |
|-------|---------|------------------------|
| **Control plane** | Login, API, permissions, audit, actor investigation, gateway coordination | FastAPI backend in `apps/api/`, deployed to Railway staging behind Cloudflare Access |
| **Media plane** | Live video delivery via WebRTC SFU | LiveKit Cloud primary; fallback toggle exists, self-hosted fallback remains future operational work |
| **Camera plane** | Physical cameras, local gateway, isolated camera network | Edge agent in `apps/cctv-edge/agent/`; real camera onboarding waits for hardware |

Browsers are **viewers only**. Browser, phone, and laptop camera publishing are not supported.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, PyJWT, Pydantic Settings
- **Gateway agent:** Python 3.12, outbound HTTP/WebSocket control, FFmpeg/LiveKit scaffolds, local mediamtx process scaffolds
- **Frontend:** React 19, Vite, Tailwind CSS 4, TypeScript in `apps/web/`; LiveKit viewer UI owned by the frontend coworker
- **Database:** Neon Postgres staging, SQLAlchemy models and Alembic migrations
- **Identity:** Cloudflare Access with GitHub OAuth on staging; Google Workspace planned for production
- **Media:** LiveKit Cloud APAC primary
- **Infrastructure:** Railway, Cloudflare, Neon, Terraform Cloud/R2, GitHub Actions
- **Security:** RBAC, session cookies, CSRF, HMAC-chained audit, branch protection, SCA/SAST/container/secret scans

## Documentation

All project documentation is in [`docs/`](docs/). Start with [`docs/index.md`](docs/index.md).

| Document | Description |
|----------|-------------|
| [Progress](PROGRESS.md) | Current implementation status and next steps |
| [Implementation Guide](IMPLEMENTATION_GUIDE.md) | Chronological implementation history |
| [Manual Testing](MANUAL_TESTING.md) | Local and staging manual test procedures |
| [API Reference](docs/implementation/api-reference.md) | Current backend/gateway API contract |
| [Development Setup](docs/implementation/development-setup.md) | Local backend and edge-agent setup |
| [Frontend Integration Guide](docs/frontend/INTEGRATION_GUIDE.md) | Backend integration notes for the frontend owner |
| [Runbooks](docs/runbooks/) | Operations, deployment, rollback, backup, and gateway procedures |
| [ADRs](docs/adrs/) | Architecture decision records |

## Project Structure

```text
Panoptix/
  .github/
    CODEOWNERS
    workflows/
      ci.yml
      deploy-staging.yml
      deploy-production.yml
      staging-healthcheck.yml
  apps/
    api/
      Dockerfile
      pyproject.toml
      alembic/
      scripts/
      src/cctv_api/
      tests/
    cctv-edge/
      agent/
        pyproject.toml
        src/panoptix_edge_agent/
        tests/
      mediamtx/
    media-fallback/
    web/
  database/
  docs/
  infra/
    terraform/modules/backup-r2/
  scripts/
```

## Local Backend Checks

From `apps/api/`:

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/ -v
python -m ruff check src tests alembic scripts
python -m mypy src/cctv_api/ --ignore-missing-imports
python -m compileall src alembic scripts
```

From `apps/cctv-edge/agent/`:

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/ -v
python -m ruff check src tests
python -m mypy src/panoptix_edge_agent --ignore-missing-imports
python -m compileall src tests
```

## Current Next Steps

Non-frontend and non-hardware work is mostly operational:

- monitor the 7-day staging uptime gate
- prepare production Cloudflare/Railway/Neon environments after the gate clears
- configure Google Workspace IdP and WARP/device posture for production
- verify R2 backup/restore drills
- procure break-glass hardware keys

Real camera publishing requires physical camera/gateway hardware. Frontend implementation remains owned by the frontend coworker.

## Invariants

1. Browsers never publish media.
2. Gateway connections are outbound-only.
3. Camera RTSP credentials stay on the gateway.
4. Gateway publish tokens are never returned to browsers.
5. Auth and authorization fail closed.
6. Security-sensitive actions are audited.
7. Real secrets are never committed.

## License

Private / proprietary. Not open source.
