# Frontend Coworker Handoff

Last updated: 2026-05-23 (production `/entry` visitor flow verified)

This is the first document the frontend coworker should read before changing the React app on `fullstack-integration`. It summarizes what the system owner has verified, what backend APIs are ready, and what frontend work should happen next.

## Read Order

1. `docs/frontend/FRONTEND_HANDOFF.md`
2. `docs/frontend/BACKEND_STATUS.md`
3. `docs/frontend/FRONTEND_PRODUCTION_TODO.md`
4. `docs/frontend/PANOPTIX_DESIGN_SYSTEM.md`
5. `docs/implementation/api-reference.md`
6. `MANUAL_TESTING.md`

## Current State

- Branch: `fullstack-integration`
- Local backend uses ignored `apps/api/.env`; do not commit or copy real values.
- Local database migration head has reached `0009_login_baselines`.
- Local full-stack smoke through Vite and FastAPI has passed for the main same-origin admin surfaces already tested: dashboard/bootstrap, live-camera camera list, users, camera management, gateways, audit logs/verify, DSR list, break-glass status, backup status, deep health, sessions, and health.
- GitHub organization invites are live on staging (`panoptix-site` org). Inviting users through the Users & Access page creates local user records and sends GitHub org invitations.
- Alert records and backend SMTP email-notification foundation are implemented. SMTP email is backend-only and disabled by default until configured. The Alerts page currently shows a frontend placeholder and needs wiring to the real backend alert APIs.
- Staging deployed browser smoke passed 2026-05-21: all 10 sidebar pages loaded through Cloudflare Access at `staging.panoptix.site` with no 500/502 errors.
- **Production is now live at `panoptix.site` (2026-05-22)** behind Cloudflare Access with GitHub OAuth. Railway production backend + frontend deployed with new cryptographic keys.
- `SUSPICIOUS_LOGIN_DETECTION_ENABLED=true` in production (login baselines track normal device/IP patterns).
- The same-domain public visitor entry flow is operational at `https://panoptix.site/entry`. First-time root visits redirect to `/entry` only when `panoptix_visitor` is absent. Only `/entry`, `/assets/*`, `/logo.png`, `/api/v1/visitor/notice`, and `/api/v1/visitor/collect` bypass Cloudflare Access.
- Real LiveKit browser subscriber playback is still not production-complete.
- Real CCTV hardware validation is still pending.

## What To Do Next

1. Wire the existing Alerts page to the real backend alert APIs:
   - `GET /api/v1/admin/alerts`
   - `GET /api/v1/admin/alerts/{alert_id}`
   - `POST /api/v1/admin/alerts/{alert_id}/acknowledge`
   - `POST /api/v1/admin/alerts/{alert_id}/resolve`
2. Finish real LiveKit subscriber playback using `GET /api/v1/cameras/{camera_id}/view-token`.
3. Build the backend-ready investigation UIs when assigned:
   - actor profile/activity drawer or page
   - admin visitor visit list/detail UI
   - full audit filter controls
4. Browser-smoke every current sidebar page against the local backend:
   - Dashboard
   - Live Cameras
   - Camera Management
   - Gateways
   - Users & Access
   - Audit Logs
   - Alerts
   - System Health
   - Break Glass
   - Settings
5. Fix only API contract and wiring issues found during smoke. Do not redesign UI/UX or add roadmap-only pages unless explicitly assigned.

## Hard Guardrails

- Do not request browser camera or microphone permission.
- Do not call `navigator.mediaDevices.getUserMedia`, `MediaRecorder`, or LiveKit publishing APIs from browser code.
- Do not store auth tokens in `localStorage`, `sessionStorage`, or IndexedDB.
- Do not expose RTSP URLs, LiveKit API secrets, gateway service tokens, R2 keys, database URLs, or `.env` values in frontend code, logs, screenshots, storage, or UI.
- Do not call gateway-only endpoints from browser code.
- Never make broad `/api/v1/*` public or browser-call protected API groups from public entry code; only the documented visitor entry endpoints are public.
- Do not treat email alerts as frontend-delivered. Email delivery is backend SMTP only.
- Do not redesign the coworker UI/UX unless the assigned task is explicitly design-system migration.

## Local Run Flow

Terminal 1:

```powershell
cd C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m alembic upgrade head
python -m uvicorn cctv_api.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\web
npm run dev
```

Open:

```text
http://localhost:3000
```

Expected local-only behavior:

- GitHub invites are live on staging. Inviting a user should succeed and create the local profile. If testing locally without GitHub env vars, `github-invites-not-configured` is still acceptable.
- Gateway health can be stale if no edge agent is heartbeating.
- LiveKit playback can remain placeholder/pending until subscriber playback is implemented.
- Current implemented pages should not show broad Internal Server Error failures.

## Verification Before Handoff Back

Run:

```powershell
cd C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\web
npm run lint
npm run build

cd ..\api
python -m ruff check src/ tests/
python -m mypy src/cctv_api/ --ignore-missing-imports
```

Security scan:

```powershell
cd C:\Users\Ivan\Downloads\panoptix-main\Panoptix
rg -n "getUserMedia|MediaRecorder|publishTrack|localStorage|sessionStorage|rtsp://|LIVEKIT_API_SECRET|service_token" apps/web/src apps/web
```
