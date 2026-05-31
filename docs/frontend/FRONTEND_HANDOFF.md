# Frontend Coworker Handoff

Last updated: 2026-05-30 (frontend UI gaps closed: alerts, actor investigation, visitor investigation, LiveKit playback, audit filters all implemented)

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
- Local and production databases should be at Alembic head `0012_gateway_discovery_runs`.
- Local full-stack smoke through Vite and FastAPI has passed for the main same-origin admin surfaces already tested: dashboard/bootstrap, live-camera camera list, users, camera management, gateways, audit logs/verify, DSR list, break-glass status, backup status, deep health, sessions, and health.
- GitHub organization invites are live on staging (`panoptix-site` org). Inviting users through the Users & Access page creates local user records and sends GitHub org invitations.
- Alert records and backend SMTP email notifications are implemented. Production sends high/critical alert emails through Resend to active admin users with `ALERT_EMAIL_RECIPIENT_MODE=admins`, including `/entry` Continue events and selected intrusion/abuse audit events. The Alerts page is now wired to real backend alert APIs with status filtering, acknowledge, and resolve actions.
- Staging deployed browser smoke passed 2026-05-21: all 10 sidebar pages loaded through Cloudflare Access at `staging.panoptix.site` with no 500/502 errors.
- **Production is now live at `panoptix.site` (2026-05-22)** behind Cloudflare Access with GitHub OAuth. Railway production backend + frontend deployed with new cryptographic keys.
- `SUSPICIOUS_LOGIN_DETECTION_ENABLED=true` in production (login baselines track normal device/IP patterns).
- The same-domain public visitor entry flow is operational at `https://panoptix.site/entry`. First-time root visits redirect to `/entry` only when `panoptix_visitor` is absent. Only `/entry`, `/assets/*`, `/logo.png`, `/api/v1/visitor/notice`, and `/api/v1/visitor/collect` bypass Cloudflare Access. Production admin API smoke confirms visitor detail responses expose `ip_details`, `browser_context`, `network_context`, `webrtc_details`, `timing`, `server_context`, and `risk_context`.
- Disabled local users are blocked by the backend with `403 user-disabled`, and invites for existing disabled users return `409 user-disabled`. A GitHub or Cloudflare Access session does not re-enable a disabled Panoptix account.
- Production backup status is now `ok`: encrypted R2 backup evidence exists, isolated restore-drill evidence was recorded against a temporary Neon branch, that temporary branch was deleted, and the production GitHub Actions backup/retention workflow has succeeded. Backup automation and retention are system-owner work, not frontend work.
- Gateway Discovery V2 backend and edge-agent APIs are implemented and active on `main`, and production is migrated through `0012_gateway_discovery_runs`. Gateway Discovery UI is optional future frontend work only; do not start it unless Ivan explicitly reassigns it.
- Production gateway host traffic uses gateway auth plus Cloudflare Access service-token headers. Raw gateway service tokens and Cloudflare Access client secrets belong only on the gateway host, never in frontend code.
- Real LiveKit browser subscriber playback is implemented using `@livekit/components-react` and `livekit-client`; production validation with real cameras is pending.
- Real CCTV hardware validation is still pending.

## What To Do Next

1. ~~Wire the existing Alerts page to the real backend alert APIs~~ — ✅ Done. AlertsPanel wired to list/detail/acknowledge/resolve APIs.
2. ~~Build the admin visitor investigation UI~~ — ✅ Done. VisitorInvestigationPage shows all 8 documented sections.
3. ~~Build the actor investigation UI~~ — ✅ Done. ActorInvestigationPage shows profile + activity timeline.
4. ~~Finish real LiveKit subscriber playback~~ — ✅ Done. CameraDetailModal uses `@livekit/components-react` subscriber-only viewer.
5. ~~Add full audit filter controls~~ — ✅ Done. AuditLogTable has all 10 backend-supported filter parameters.
6. Browser-smoke every current sidebar page and destructive/error states against production-like data:
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
7. Validate production LiveKit camera playback with real cameras once hardware is connected.
8. Verify disabled-account UX returns clear messaging on login and invite attempts.
9. Remove any remaining phantom API calls (requests to endpoints that do not exist or are not yet implemented).
10. Fix only API contract and wiring issues found during smoke. Do not redesign UI/UX or add roadmap-only pages unless explicitly assigned.
11. Do not implement Gateway Discovery UI unless Ivan explicitly reassigns it. The backend/edge discovery path exists, but real camera LAN/VLAN validation remains system-owner work.

## Hard Guardrails

- Do not request browser camera or microphone permission.
- Do not call `navigator.mediaDevices.getUserMedia`, `MediaRecorder`, or LiveKit publishing APIs from browser code.
- Do not store auth tokens in `localStorage`, `sessionStorage`, or IndexedDB.
- Do not expose RTSP URLs, LiveKit API secrets, LiveKit ingest tokens, gateway service tokens, Cloudflare Access service-token secrets, R2 keys, database URLs, backend-only credentials, or `.env` values in frontend code, logs, screenshots, storage, or UI.
- Do not call gateway-only endpoints from browser code.
- Never make broad `/api/v1/*` public or browser-call protected API groups from public entry code; only the documented visitor entry endpoints are public.
- Do not treat email alerts as frontend-delivered. Email delivery is backend SMTP only; browsers should display alert records and statuses, never send alert email.
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
- Gateway health can be stale if no edge agent is heartbeating. Production edge heartbeat uses gateway auth plus Cloudflare Access service-token headers and the edge agent's stable `Panoptix-Edge-Agent/<version>` user agent.
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
