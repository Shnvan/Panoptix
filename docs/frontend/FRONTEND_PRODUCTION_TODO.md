# Frontend Production TODO

This is the frontend source of truth for production-readiness work on the combined `fullstack-integration` branch. It tracks every implemented backend capability and makes each one either usable in the frontend, intentionally hidden, or explicitly marked backend/gateway-only.

Design direction: new frontend work **must** follow [Panoptix Design System](PANOPTIX_DESIGN_SYSTEM.md). The current UI uses blue-tinted slate backgrounds (`#020617`, `#0f172a`), cyan accents (`#06b6d4`), and rounded corners — all of which must be replaced with pure dark backgrounds (`#0A0A0A`, `#111111`, `#1A1A1A`), warm orange accent (`#F07C1E`), and sharp edges (`border-radius: 0`). See the design system doc for the complete migration mapping.

## Backend-to-frontend Coverage Matrix

| Category | Backend capability | Frontend state | Required action |
|---|---|---|---|
| Implemented and usable | `/api/v1/me` | Wired through login/session bootstrap | Keep as the authenticated user source. |
| Implemented and usable | `/api/v1/cameras` | Viewer dashboard uses assigned camera list | Keep for viewer-facing camera grid only. |
| Implemented but incomplete | `/api/v1/cameras/{camera_id}/view-token` | Token request works, playback placeholder remains | Wire real subscriber-only LiveKit browser viewer. |
| Implemented but incomplete | `/api/v1/cameras/events` | Disabled in dev-auth mode because EventSource cannot send custom headers | Keep production SSE path; test with Cloudflare/session cookies in staging. |
| Implemented and usable | `/api/v1/privacy/notice`, `/api/v1/privacy/notice/accept` | Privacy notice gate exists | Verify notice mismatch and accepted states in browser. |
| Implemented and usable | `/api/v1/sessions/active`, `/api/v1/sessions/revoke` | Settings/session UI exists | Verify revoke UX and session refresh behavior. |
| Implemented and wired | `/api/v1/admin/users`, role update, disable | User admin UI exists and local smoke has loaded real users/roles | Continue browser smoke for destructive actions, disable behavior, and edge-case error states. |
| Implemented and wired | `/api/v1/admin/users/{user_id}/mfa/reset` | MFA reset modal calls the backend route | Browser smoke success/error states and audit copy. |
| Implemented and wired | `/api/v1/admin/users/invite` | GitHub invite form calls the backend route; `github-invites-not-configured` is expected when local GitHub invites are disabled | Browser smoke success and validation states only when real GitHub invite config is intentionally enabled. |
| Implemented but incomplete | `/api/v1/admin/audit`, verify, export | Audit table and verify endpoint pass local same-origin smoke; filtering UI remains limited | Add full audit filters for actor, severity, category, outcome, resource, session, and date range. |
| Implemented but missing UI | `/api/v1/admin/actors/{actor_type}/{actor_id}/profile` | No actor investigation UI | Add actor profile page/drawer linked from users, gateways, audit rows, and break-glass/system actors. |
| Implemented but missing UI | `/api/v1/admin/actors/{actor_type}/{actor_id}/activity` | No actor activity timeline UI | Add activity timeline with cursor pagination and filters. |
| Implemented and wired | `/api/v1/admin/dashboard` | Dashboard hook calls backend metrics | Browser smoke metrics and empty/degraded states. |
| Implemented and wired | `/api/v1/admin/cameras`, detail, create, update, ACL, disable, enable | Admin camera management uses backend admin routes and local smoke has loaded/created camera data | Continue browser smoke for update/disable/enable/ACL validation and edge states. |
| Implemented and wired | `/api/v1/admin/gateways`, detail, create, update, disable, enable, rotate, assignment | Gateway screen uses real gateway data and local smoke has created/listed gateway data | Continue browser smoke for update/disable/enable, assignment, rotation, command states, and one-time token handling. |
| Implemented but incomplete | Gateway commands create/list/cancel, command cleanup, maintenance job | Some actions are wired | Verify command history, command creation, cancel, cleanup, and maintenance UX against real backend data. |
| Implemented and wired | `/api/v1/admin/break-glass/open`, `/close` | Break-glass section exists | Browser smoke open/close confirmation, checklist, and error states. |
| Implemented and wired | `/api/v1/admin/internal/break-glass-status` | Break-glass status hook exists | Browser smoke current emergency window and expiry display. |
| Implemented and usable | `/api/v1/admin/livekit/fallback` | Toggle is wired after API contract fix | Verify mode, reason, previous mode, and switched-at messaging. |
| Implemented and usable | `/api/v1/admin/dpa/export` | DPA export is wired after API contract fix | Verify downloaded/exported artifact count and error handling. |
| Implemented but incomplete | `/api/v1/admin/sites/{site_id}/signage-attest` | Attestation call exists, but site listing source is missing | Disable or clearly mark until a real site list source exists, or add backend site listing later. |
| Implemented and wired | `/api/v1/admin/backups/status` | Health/admin UI can read backup status | Browser smoke missing, degraded, and ok states. |
| Frontend calls nonexistent endpoint | `/api/v1/admin/sites` | API client has `listSites()` but backend route is not present | Remove, disable, or mark planned until backend route exists. |
| Implemented and wired | `/api/v1/admin/dsr-requests` | DSR list/create/detail/update API client exists and compliance UI uses the list | Browser smoke DSR case creation/update flow and validation states. |
| Frontend calls nonexistent endpoint | `/api/v1/admin/exposure-check`, `/media-isolation-check`, `/origin-binding-check` | API client has security check calls but backend routes are not present | Remove, disable, or mark planned until backend routes exist. |
| Backend/gateway-only | Gateway heartbeat, ingest token, camera status, gateway WebSocket, LiveKit webhook | Must not be browser-callable | Keep out of frontend UI and browser API client. |
| Pilot/future only | Viewer watermark, alerts, incident workflow, analyst notes, behavior baseline | Not production-ready | Keep as pilot backlog until backend data sources and models exist. |

## P0 Production Blockers

These must be resolved before treating the frontend as production-ready.

| Task | Status | Notes |
|---|---|---|
| Real LiveKit browser viewer playback | Not done | Use backend viewer tokens to connect with the LiveKit client as a subscriber only. |
| Verify real gateway UI data | Required | Gateway list/detail, command history, assignment, update, disable, enable, and rotate views are wired; smoke them against local/staging backend data. |
| Verify viewer/admin camera split | Required | Viewer dashboard uses `/api/v1/cameras`; admin camera management uses `/api/v1/admin/cameras` and detail routes. |
| Remove or disable nonexistent endpoint calls | Required | Security reports and site listing must not appear as broken production features. |
| Expose or document remaining implemented admin actions | Required | Backup status has a UI path; actor profile/activity still needs a visible investigation path or documented no-UI decision. |
| Full local smoke test | Passed for current same-origin API surfaces | Dashboard/bootstrap, live-camera camera list, users, cameras, gateways, audit logs/verify, DSR list, break-glass status, backup status, deep health, sessions, and health pass through Vite against a local backend with dev auth. Continue manual page-specific destructive/action smoke where data allows. |
| Full staging smoke test | Required | Test with Cloudflare Access session cookies, CSRF, backend routes, SSE where applicable, and deployed frontend assets. |
| Browser publishing absence check | Required | Confirm the browser bundle does not request camera/microphone permission and does not publish media to LiveKit. |
| Sensitive-value exposure check | Required | Confirm no RTSP URLs, camera passwords, LiveKit admin secrets, Cloudflare service tokens, or long-lived auth tokens appear in frontend code, logs, storage, or UI. |

## P1 Admin Feature Completion

These are important for production operations, but can follow the P0 blockers.

| Task | Status | Notes |
|---|---|---|
| Full audit filtering UI | Partial | Expose actor type/id, severity, category, outcome, resource, session ID, and date range filters supported by the backend. |
| Actor investigation pages | Not done | Use `/api/v1/admin/actors/{actor_type}/{actor_id}/profile` and `/activity`; link from users, gateways, and audit rows. |
| Admin dashboard integration | Wired; needs smoke | Use `/api/v1/admin/dashboard` for backend-provided operational metrics and verify empty/degraded states. |
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

Current local evidence: Dashboard/bootstrap, live-camera camera list, Users & Access, Camera Management, Gateways, Audit Logs, audit verification, DSR list, break-glass status, backup status, deep health, sessions, and health have passed same-origin smoke against a local FastAPI backend using an ignored `apps/api/.env` and dev auth. Treat `github-invites-not-configured` as expected unless GitHub invite settings are intentionally enabled. Treat any one-time gateway service token shown in the UI as sensitive; do not screenshot it. The exposed local test gateway named `what` was disabled during smoke cleanup.

## Current Default Next Task

The next frontend implementation task should be real LiveKit browser viewer playback. The backend already mints short-lived subscriber tokens; the frontend still needs the subscriber-only player.
