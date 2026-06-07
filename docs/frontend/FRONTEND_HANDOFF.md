# Frontend Coworker Handoff

Last updated: 2026-06-06 (PR #27 cleanup merged; API failure and camera playback reliability hardening added)

This is the first document to read before changing the React app. The canonical checkout is `C:\Users\Ivan\Downloads\panoptix-main\panoptix-visitor-access`; branch `codex/visitor-access-requests` is synchronized with `origin/main` at `713098a`.

## Read Order

1. `docs/frontend/FRONTEND_HANDOFF.md`
2. `docs/frontend/BACKEND_STATUS.md`
3. `docs/frontend/FRONTEND_PRODUCTION_TODO.md`
4. `docs/frontend/PANOPTIX_DESIGN_SYSTEM.md`
5. `docs/implementation/api-reference.md`
6. `MANUAL_TESTING.md`

## Current State

- Branch: `codex/visitor-access-requests`, based on current `origin/main`
- PR #27 is merged. Gateway, camera, access-request, alert, visitor, and audit UI cleanup is on `main`.
- A June 6 production compression incident caused valid `200` API responses to fail in browsers with `ERR_CONTENT_DECODING_FAILED`. Cloudflare temporarily disables compression for `/api/v1/*`. This compression rule is not an Access bypass and is separate from the public access-request WAF rule.
- List hooks expose request errors. A failed gateway, camera, user, audit, DSR, or session request must render a retryable failure state, not a genuine-empty message.
- Camera playback labels are based on LiveKit connection and video-track subscription: requesting token, connecting, waiting for publisher, playing, offline/timeout, or connection error. Token issuance alone is not an active tunnel.
- Local backend uses ignored `apps/api/.env`; do not commit or copy real values.
- Local dev databases should run `alembic upgrade head`. Production is migrated through `0013_visitor_access_requests`.
- Local full-stack smoke through Vite and FastAPI has passed for the main same-origin admin surfaces already tested: dashboard/bootstrap, live-camera camera list, users, camera management, gateways, audit logs/verify, DSR list, break-glass status, backup status, deep health, sessions, and health.
- GitHub organization invites are live on staging (`panoptix-site` org). Inviting users through the Users & Access page creates local user records and sends GitHub org invitations.
- Alert records and backend SMTP email notifications are implemented. Production sends high/critical alert emails through Resend to active admin users with `ALERT_EMAIL_RECIPIENT_MODE=admins`, including `/entry` Continue events and selected intrusion/abuse audit events. The Alerts page is now wired to real backend alert APIs with status filtering, acknowledge, and resolve actions.
- Staging deployed browser smoke passed 2026-05-21: all 10 sidebar pages loaded through Cloudflare Access at `staging.panoptix.site` with no 500/502 errors.
- Full production sidebar smoke passed 2026-06-01: Dashboard, Live Cameras, Camera Management, Gateways, Users & Access, Audit Logs, Alerts, System Health, Break Glass, and Settings loaded through `panoptix.site` with no unexpected `404`/`500`/`502`. Transient recovered `401` bootstrap calls were observed; console output was browser-extension/content-script noise only; `localStorage`/`sessionStorage` contained no sensitive token material, and session storage was empty.
- **Production is now live at `panoptix.site` (2026-05-22)** behind Cloudflare Access with GitHub OAuth. Railway production backend + frontend deployed with new cryptographic keys.
- `SUSPICIOUS_LOGIN_DETECTION_ENABLED=true` in production (login baselines track normal device/IP patterns).
- The same-domain public visitor entry flow is operational at `https://panoptix.site/entry`. First-time root visits redirect to `/entry` only when `panoptix_visitor` is absent; visitors can manually return to `https://panoptix.site/entry?mode=request-access` after trying secure sign-in. Only `/entry`, `/assets/*`, `/logo.png`, `/api/v1/visitor/notice`, `/api/v1/visitor/collect`, and the narrow public `POST /api/v1/visitor/access-requests` exception bypass Cloudflare Access. Production admin API smoke confirms visitor detail responses expose `ip_details`, `browser_context`, `network_context`, `webrtc_details`, `timing`, `server_context`, and `risk_context`.
- Visitor access request workflow is implemented and deployed: `/entry` includes a secondary request-access form, `/entry?mode=request-access#request-access` returns visitors directly to it, and Users & Access includes an Access Requests review panel. Public requests are always ordinary user/viewer requests and create pending rows only; they do not create accounts, roles, sessions, camera ACLs, GitHub invites, Cloudflare authorization, or admin requests. Production smoke confirmed a manual public `requested_role: "admin"` payload is stored as `viewer`, admin approval sends/records a GitHub org invite as viewer, and smoke pending requests were cleaned up.
- Frontend access-request QA now covers `/entry` validation/success/duplicate/rate-limit states, Users & Access approve/reject dialogs, disabled-user messaging, and critical axe checks for the review dialog through Playwright desktop/mobile tests. A static guardrail scan also blocks browser media capture/publishing APIs, token storage, frontend gateway-only calls, Gateway Discovery UI calls, and obvious secret strings.
- Disabled local users are blocked by the backend with `403 user-disabled`, and invites/access-request approvals for existing disabled users return `409 user-disabled`. Production smoke confirmed disabled-user access-request approval does not re-enable the user and does not write invite metadata on the denied request. A GitHub or Cloudflare Access session does not re-enable a disabled Panoptix account.
- Production backup status is now `ok`: encrypted R2 backup evidence exists, isolated restore-drill evidence was recorded against a temporary Neon branch, that temporary branch was deleted, and the production GitHub Actions backup/retention workflow has succeeded. Backup automation and retention are system-owner work, not frontend work.
- Gateway Discovery V2 backend and edge-agent APIs are implemented and active on `main`, and production is migrated through `0013_visitor_access_requests`. Gateway Discovery UI is optional future frontend work only; do not start it unless Ivan explicitly reassigns it.
- Production gateway host traffic uses gateway auth plus Cloudflare Access service-token headers. Raw gateway service tokens and Cloudflare Access client secrets belong only on the gateway host, never in frontend code.
- Real LiveKit browser subscriber playback is implemented using `@livekit/components-react` and `livekit-client`; production `Tailscale RTSP Camera` playback passed on 2026-06-02 through the DigitalOcean `dropletGateway`.
- The real-camera pilot kept RTSP on Tailscale/private networking; the browser subscribed to LiveKit only, with no camera/mic prompt, no browser publishing, and no RTSP URL, gateway token, Cloudflare token, or LiveKit secret exposed in browser storage/logs/docs.
- The admin operations assistant is disabled by default in code and currently enabled in production after provider privacy approval. It is rendered only for admins after the backend status check, requires an AI/data disclosure, keeps conversation state in memory only, and calls only Panoptix `/api/v1/admin/assistant/*` endpoints.

## What To Do Next

1. ~~Wire the existing Alerts page to the real backend alert APIs~~ — ✅ Done. AlertsPanel wired to list/detail/acknowledge/resolve APIs.
2. ~~Build the admin visitor investigation UI~~ — ✅ Done. VisitorInvestigationPage shows all 8 documented sections.
3. ~~Build the actor investigation UI~~ — ✅ Done. ActorInvestigationPage shows profile + activity timeline.
4. ~~Finish real LiveKit subscriber playback~~ — ✅ Done. CameraDetailModal uses `@livekit/components-react` subscriber-only viewer.
5. ~~Add full audit filter controls~~ — ✅ Done. AuditLogTable has all 10 backend-supported filter parameters.
6. Deploy and smoke the frontend reliability changes:
   - API failures show error panels with retry controls
   - successful empty responses keep their genuine empty states
   - camera token failure, connection failure, no-publisher timeout, successful track arrival, and retry are distinct
7. Full production sidebar smoke is complete; rerun only after deploys or targeted fixes:
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
8. ~~Validate production LiveKit camera playback with a real camera pilot~~ - Done for the Tailscale RTSP Camera. Rerun targeted smoke only after new camera/gateway deployments.
9. Verify disabled-account UX returns clear messaging on login, invite attempts, and access-request approval attempts.
10. Remove any remaining phantom API calls (requests to endpoints that do not exist or are not yet implemented).
11. Frontend cleanup is reassigned for this milestone. Keep changes operational and page-focused; do not add roadmap-only pages.
12. Do not implement Gateway Discovery UI unless Ivan explicitly reassigns it. The backend/edge discovery path exists, but production-standard on-site camera LAN/VLAN hardening remains system-owner work for future sites. Do not start V380/V380ProQ16S camera integration from the frontend side.

## Hard Guardrails

- Do not request browser camera or microphone permission.
- Do not call `navigator.mediaDevices.getUserMedia`, `MediaRecorder`, or LiveKit publishing APIs from browser code.
- Do not store auth tokens in `localStorage`, `sessionStorage`, or IndexedDB.
- Do not add model-provider API keys, direct Groq/OpenAI-compatible browser calls, raw HTML rendering, or persisted assistant conversations.
- Do not expose RTSP URLs, LiveKit API secrets, LiveKit ingest tokens, gateway service tokens, Cloudflare Access service-token secrets, R2 keys, database URLs, backend-only credentials, or `.env` values in frontend code, logs, screenshots, storage, or UI.
- Do not call gateway-only endpoints from browser code.
- Never make broad `/api/v1/*` public or browser-call protected API groups from public entry code; only the documented visitor entry endpoints are public. The only access-request public exception is `POST /api/v1/visitor/access-requests`.
- Do not treat email alerts as frontend-delivered. Email delivery is backend SMTP only; browsers should display alert records and statuses, never send alert email.
- Do not redesign the coworker UI/UX unless the assigned task is explicitly design-system migration.

## Local Run Flow

Terminal 1:

```powershell
cd C:\Users\Ivan\Downloads\panoptix-main\panoptix-visitor-access\apps\api
$env:PYTHONPATH = "src"
python -m alembic upgrade head
python -m uvicorn cctv_api.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd C:\Users\Ivan\Downloads\panoptix-main\panoptix-visitor-access\apps\web
npm run dev
```

Open:

```text
http://localhost:3000
```

Expected local-only behavior:

- GitHub invites are live on staging. Inviting a user should succeed and create the local profile. If testing locally without GitHub env vars, `github-invites-not-configured` is still acceptable.
- Gateway health can be stale if no edge agent is heartbeating. Production edge heartbeat uses gateway auth plus Cloudflare Access service-token headers and the edge agent's stable `Panoptix-Edge-Agent/<version>` user agent.
- LiveKit playback is implemented; local playback may remain unavailable unless local LiveKit/gateway config is present.
- Current implemented pages should not show broad Internal Server Error failures.

## Verification Before Handoff Back

Run:

```powershell
cd C:\Users\Ivan\Downloads\panoptix-main\panoptix-visitor-access\apps\web
npm run lint
npm run build
npm run qa:guardrails
npm run test:e2e

cd ..\api
python -m ruff check src/ tests/
python -m mypy src/cctv_api/ --ignore-missing-imports
```

Security scan:

```powershell
cd C:\Users\Ivan\Downloads\panoptix-main\panoptix-visitor-access
rg -n "getUserMedia|MediaRecorder|publishTrack|localStorage|sessionStorage|rtsp://|LIVEKIT_API_SECRET|service_token" apps/web/src apps/web
```

Prefer `npm run qa:guardrails` over ad hoc search for final frontend handoff checks; it encodes the current approved allowlist for theme `localStorage` and one-time admin gateway token display.
