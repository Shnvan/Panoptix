# Development Setup Guide

This guide reflects the current backend and edge-agent repository state. The frontend remains a placeholder owned by the frontend coworker.

## Repository Services

| Service | Owner | Current state |
|---|---|---|
| `cctv-api` | System owner | FastAPI backend with auth, sessions, audit, admin, gateway, LiveKit, and health endpoints |
| `cctv-gateway` | System owner | Python edge agent with heartbeat, outbound control, supervisor, FFmpeg/LiveKit scaffolds, and camera credential loading |
| `mediamtx` | System owner | Local loopback-only config scaffold in `apps/cctv-edge/mediamtx/` |
| `cctv-web` | Frontend coworker | Placeholder only; no package metadata yet |
| `postgres` | Database/system owner coordination | Neon staging exists; local Postgres may be used for database-backed testing |

## Prerequisites

- Git
- Python 3.12+
- Docker Desktop for backend image checks
- PostgreSQL client tools if using local database or restore drills
- FFmpeg for synthetic RTSP and smoke tests
- mediamtx for local media-process manual tests

Node.js is only required when frontend work begins in `apps/web/`.

## Environment

Use `.env.example` as the schema for local values. Real secrets belong only in ignored `.env` files.

Important local groups:

- `APP_ENV`, `ALLOW_DEV_AUTH`, and Cloudflare Access placeholders
- session, CSRF, and audit signing keys
- database URLs
- LiveKit placeholders or staging-only credentials
- gateway service-token and command-signing values
- edge-agent `PANOPTIX_*` values
- optional `PANOPTIX_SMOKE_*` values for LiveKit smoke tests

## Backend Setup

```powershell
Set-Location apps\api
python -m pip install --upgrade pip
python -m pip install ".[dev]"
$env:PYTHONPATH = "src"
python -m uvicorn cctv_api.main:app --reload --host 127.0.0.1 --port 8000
```

Backend verification:

```powershell
Set-Location apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/ -v
python -m ruff check src tests alembic scripts
python -m mypy src/cctv_api/ --ignore-missing-imports
python -m compileall src alembic scripts
```

## Edge-Agent Setup

```powershell
Set-Location apps\cctv-edge\agent
python -m pip install --upgrade pip
python -m pip install ".[dev]"
$env:PYTHONPATH = "src"
$env:PANOPTIX_API_BASE_URL = "http://127.0.0.1:8000"
$env:PANOPTIX_GATEWAY_ID = "11111111-1111-1111-1111-111111111111"
$env:PANOPTIX_DEV_GATEWAY_IDENTITY = "true"
python -m panoptix_edge_agent.cli --once
```

Edge-agent verification:

```powershell
Set-Location apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/ -v
python -m ruff check src tests
python -m mypy src/panoptix_edge_agent --ignore-missing-imports
python -m compileall src tests
```

## Edge Supervisor

Supervisor mode coordinates heartbeat and outbound gateway control. It can optionally start local mediamtx.

```powershell
Set-Location apps\cctv-edge\agent
$env:PYTHONPATH = "src"
$env:PANOPTIX_API_BASE_URL = "http://127.0.0.1:8000"
$env:PANOPTIX_GATEWAY_ID = "11111111-1111-1111-1111-111111111111"
$env:PANOPTIX_DEV_GATEWAY_IDENTITY = "true"
$env:PANOPTIX_GATEWAY_COMMAND_SIGNING_KEY = "local-dev-command-signing-key-change-me"
$env:PANOPTIX_SUPERVISE_MEDIAMTX = "false"
python -m panoptix_edge_agent.cli --supervise
```

## Optional Smoke Tests

Synthetic FFmpeg-to-LiveKit smoke tests require:

- FFmpeg on `PATH`
- optional LiveKit SDK dependency: `python -m pip install -e ".[livekit]"`
- `PANOPTIX_SMOKE_*` variables set with real test-only LiveKit credentials

Do not commit LiveKit API keys, generated tokens, or RTSP camera credentials.

## Frontend State

`apps/web/` is currently a placeholder. The frontend owner should use:

- `docs/frontend/README.md`
- `docs/frontend/INTEGRATION_GUIDE.md`
- `docs/frontend/frontend-guardrails.md`
- `docs/frontend/ux-product-spec.md`

Do not document or require `npm install`, Playwright, or bundle-scan commands until `apps/web/package.json` exists.

## Development Invariants

- No browser camera, microphone, or publishing flow.
- No gateway publish token returned to browsers.
- No RTSP credentials in backend responses, frontend bundles, audit payloads, or committed files.
- Gateway and camera operations remain outbound-only from the gateway side.
- Production/staging config must not use placeholder secrets.
