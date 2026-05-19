# Frontend Production TODO

This is the frontend source of truth for production-readiness work on the combined `fullstack-integration` branch. It tracks every implemented backend capability and makes each one either usable in the frontend, intentionally hidden, or explicitly marked backend/gateway-only.

Design direction: new frontend work should follow [Panoptix Design System](PANOPTIX_DESIGN_SYSTEM.md). The current cyan/slate/rounded UI can migrate gradually, but new production screens should move toward the BSIT 2-2-inspired dashboard/admin adaptation: dark-first, compact, sharp, orange-accented, and scan-focused.

## Backend-to-frontend Coverage Matrix

| Category | Backend capability | Frontend state | Required action |
|---|---|---|---|
| Implemented and usable | `/api/v1/me` | Wired through login/session bootstrap | Keep as the authenticated user source. |
| Implemented and usable | `/api/v1/cameras` | Viewer dashboard uses assigned camera list | Keep for viewer-facing camera grid only. |
| Implemented but incomplete | `/api/v1/cameras/{camera_id}/view-token` | Token request works, playback placeholder remains | Wire real subscriber-only LiveKit browser viewer. |
| Implemented but incomplete | `/api/v1/cameras/events` | Disabled in dev-auth mode because EventSource cannot send custom headers | Keep production SSE path; test with Cloudflare/session cookies in staging. |
| Implemented and usable | `/api/v1/privacy/notice`, `/api/v1/privacy/notice/accept` | Privacy notice gate exists | Verify notice mismatch and accepted states in browser. |
| Implemented and usable | `/api/v1/sessions/active`, `/api/v1/sessions/revoke` | Settings/session UI exists | Verify revoke UX and session refresh behavior. |
| Implemented but incomplete | `/api/v1/admin/users`, role update, disable | User admin UI exists | Add MFA reset and invite flows; fix stale copy that says MFA reset is not implemented. |
| Implemented but missing UI | `/api/v1/admin/users/{user_id}/mfa/reset` | Marked as not implemented in current UI/report | Add admin-mediated MFA reset action and result messaging. |
| Implemented but missing UI | `/api/v1/admin/users/invite` | No complete invite UI | Add invite flow or explicitly document no production UI yet. |
| Implemented but incomplete | `/api/v1/admin/audit`, verify, export | Audit table exists with limited filtering | Add full audit filters for actor, severity, category, outcome, resource, session, and date range. |
| Implemented but missing UI | `/api/v1/admin/actors/{actor_type}/{actor_id}/profile` | No actor investigation UI | Add actor profile page/drawer linked from users, gateways, audit rows, and break-glass/system actors. |
| Implemented but missing UI | `/api/v1/admin/actors/{actor_type}/{actor_id}/activity` | No actor activity timeline UI | Add activity timeline with cursor pagination and filters. |
| Implemented but incomplete | `/api/v1/admin/dashboard` | Dashboard currently uses local/frontend summaries | Wire dashboard metrics from backend. |
| Implemented but incomplete | `/api/v1/admin/cameras`, detail, create, ACL, disable | Camera management uses viewer camera list in places | Use admin camera list/detail for admin screens and viewer camera list only for viewer dashboard. |
| Implemented but incomplete | `/api/v1/admin/gateways`, detail, create, disable, rotate, assignment | Gateway screen has placeholder data comments | Replace placeholders with real list/detail data and production states. |
| Implemented but incomplete | Gateway commands create/list/cancel, command cleanup, maintenance job | Some actions are wired | Verify command history, command creation, cancel, cleanup, and maintenance UX against real backend data. |
| Implemented and usable | `/api/v1/admin/break-glass/open`, `/close` | Break-glass section exists | Add status read from internal break-glass status endpoint. |
| Implemented but missing UI | `/api/v1/admin/internal/break-glass-status` | No clear live status integration | Display current emergency window status and expiry when available. |
| Implemented and usable | `/api/v1/admin/livekit/fallback` | Toggle is wired after API contract fix | Verify mode, reason, previous mode, and switched-at messaging. |
| Implemented and usable | `/api/v1/admin/dpa/export` | DPA export is wired after API contract fix | Verify downloaded/exported artifact count and error handling. |
| Implemented but incomplete | `/api/v1/admin/sites/{site_id}/signage-attest` | Attestation call exists, but site listing source is missing | Disable or clearly mark until a real site list source exists, or add backend site listing later. |
| Implemented but missing UI | `/api/v1/admin/backups/status` | No production UI | Add backup status card or document why it stays admin/API-only. |
| Frontend calls nonexistent endpoint | `/api/v1/admin/sites` | API client has `listSites()` but backend route is not present | Remove, disable, or mark planned until backend route exists. |
| Frontend calls nonexistent endpoint | `/api/v1/admin/dsr-requests` | API client has `listDsrRequests()` but backend route is not present | Remove, disable, or mark planned until backend route exists. |
| Frontend calls nonexistent endpoint | `/api/v1/admin/exposure-check`, `/media-isolation-check`, `/origin-binding-check` | API client has security check calls but backend routes are not present | Remove, disable, or mark planned until backend routes exist. |
| Backend/gateway-only | Gateway heartbeat, ingest token, camera status, gateway WebSocket, LiveKit webhook | Must not be browser-callable | Keep out of frontend UI and browser API client. |
| Pilot/future only | Viewer watermark, alerts, incident workflow, analyst notes, behavior baseline | Not production-ready | Keep as pilot backlog until backend data sources and models exist. |

## P0 Production Blockers

These must be resolved before treating the frontend as production-ready.

| Task | Status | Notes |
|---|---|---|
| Real LiveKit browser viewer playback | Not done | Use backend viewer tokens to connect with the LiveKit client as a subscriber only. |
| Replace placeholder gateway UI | Required | Gateway list/detail, command history, assignment, disable, and rotate views must use real `/api/v1/admin/gateways` data. |
| Separate viewer camera data from admin camera data | Required | Viewer dashboard uses `/api/v1/cameras`; admin camera management uses `/api/v1/admin/cameras` and detail routes. |
| Remove or disable nonexistent endpoint calls | Required | Security reports, DSR listing, and site listing must not appear as broken production features. |
| Expose missing implemented admin actions | Required | Add or document UI for MFA reset, user invite, backup status, break-glass status, and actor profile/activity. |
| Full local smoke test | Required | Run the frontend against a local backend with dev auth and verify every sidebar page loads without React crashes or failed required calls. |
| Full staging smoke test | Required | Test with Cloudflare Access session cookies, CSRF, backend routes, SSE where applicable, and deployed frontend assets. |
| Browser publishing absence check | Required | Confirm the browser bundle does not request camera/microphone permission and does not publish media to LiveKit. |
| Sensitive-value exposure check | Required | Confirm no RTSP URLs, camera passwords, LiveKit admin secrets, Cloudflare service tokens, or long-lived auth tokens appear in frontend code, logs, storage, or UI. |

## P1 Admin Feature Completion

These are important for production operations, but can follow the P0 blockers.

| Task | Status | Notes |
|---|---|---|
| Full audit filtering UI | Partial | Expose actor type/id, severity, category, outcome, resource, session ID, and date range filters supported by the backend. |
| Actor investigation pages | Not done | Use `/api/v1/admin/actors/{actor_type}/{actor_id}/profile` and `/activity`; link from users, gateways, and audit rows. |
| admin dashboard integration | Not done | Use `/api/v1/admin/dashboard` for backend-provided operational metrics. |
| Gateway command workflow | Partial | Verify command creation, list, cancel, cleanup, and maintenance against real backend data and production copy. |
| Session management UI | Partial | Make active sessions and revoke behavior clear, including current-session consequences. |
| Health and admin action polish | Partial | Keep destructive or risky admin actions behind confirmation states and show audit implications where relevant. |
| Validation error rendering | Partial | API validation errors should always render as readable strings and never crash React. |
| Empty, denied, degraded, offline, and planned states | Partial | Each data-bearing screen should clearly distinguish no data, permission denied, backend unavailable, feature planned, and feature not implemented. |

## P2 Pilot And Future

These belong to pilot/future work unless the team explicitly pulls them forward.

| Task | Status | Notes |
|---|---|---|
| Viewer identity watermark | Pilot | Add visible viewer identity watermarking on video once live playback is wired. |
| Alerts UI | Pilot | Surface suspicious activity, camera tamper, gateway degradation, and actor-risk detections when backend detection models exist. |
| Incident workflow | Pilot | Add incident list/detail screens after backend incident models exist. |
| Analyst notes | Pilot | Add admin/security notes attached to actor profiles after backend note storage exists. |
| Behavior baseline and actor risk score UI | Pilot | Display normal-vs-unusual actor behavior only after backend baselines and risk scoring exist. |

## Do Not Integrate In Browser

These backend routes exist for gateways, webhooks, or internal control flow. They must not be called from browser/frontend code.

| Route/capability | Reason |
|---|---|
| `POST /api/v1/gateways/{gateway_id}/heartbeat` | Gateway-agent heartbeat only; requires gateway identity. |
| `POST /api/v1/gateways/{gateway_id}/ingest-token` | Gateway publish-token minting only; browser must never receive publisher capability. |
| `POST /api/v1/gateways/{gateway_id}/cameras/{camera_id}/status` | Gateway status report only. |
| `GET /api/v1/gateway-control/ws` | Gateway command WebSocket only. |
| `POST /api/v1/webhooks/livekit` | LiveKit server webhook receiver only. |
| Any route requiring gateway service credentials | Gateway service tokens must never be present in browser code, browser storage, or frontend env vars. |

## Frontend Security Guardrails

These rules are mandatory for production.

- Do not store auth/session/token material in `localStorage`, `sessionStorage`, or IndexedDB.
- Do not expose RTSP URLs or camera credentials in browser code, API responses, logs, or UI.
- Do not put LiveKit API keys, LiveKit API secrets, Cloudflare service tokens, or gateway service tokens in frontend environment variables.
- Gateway service tokens may only be displayed once after gateway create/rotate responses, and must not be persisted by the frontend.
- Do not request browser camera or microphone permission.
- Do not call `navigator.mediaDevices.getUserMedia`, `MediaRecorder`, or LiveKit publishing APIs from the browser.
- Do not call gateway-only endpoints from browser code.
- Keep all browser data-bearing calls on same-origin `/api/v1/*` routes owned by `cctv-api`.

## Verification Checklist

Run these checks before merging frontend integration work forward:

- Every frontend API client method maps to a real backend endpoint or is explicitly marked planned/disabled.
- Every implemented admin backend feature has a visible frontend path or a documented no-UI reason.
- `npm run lint`
- `npm run build`
- `python -m ruff check src/ tests/`
- `python -m mypy src/cctv_api/ --ignore-missing-imports`
- Browser smoke test for all viewer and admin pages.
- Security scan for forbidden browser APIs and sensitive strings:

```powershell
rg -n "getUserMedia|MediaRecorder|publishTrack|localStorage|sessionStorage|rtsp://|LIVEKIT_API_SECRET|CLOUDFLARE|service_token" apps/web/src apps/web
```

For the smoke test:

1. Start the backend with dev auth enabled.
2. Start the frontend with `VITE_DEV_AUTH=true`.
3. Log in as an admin test user.
4. Open every sidebar page.
5. Open a camera detail modal and request a stream token.
6. Run implemented admin health and maintenance actions.
7. Verify planned features are marked as planned or disabled.
8. Confirm there are no React page errors, token leaks, or unexpected 4xx/5xx responses for implemented features.

## Current Default Next Task

The next frontend implementation task should be real LiveKit browser viewer playback. The backend already mints short-lived subscriber tokens; the frontend still needs the subscriber-only player.
