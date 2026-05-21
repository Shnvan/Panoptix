# Panoptix Web

React/Vite frontend integration branch for the Panoptix CCTV control plane.

## Current Status

This branch contains the coworker frontend work merged into `fullstack-integration` for combined backend/frontend testing. It should not be merged into `backend`; `backend` remains backend-only.

Implemented UI areas:

- Cloudflare Access gated login shell
- Viewer camera dashboard and camera detail modal
- Admin camera, gateway, user, audit, break-glass, and health screens
- Same-origin API client for `/api/v1/*`
- Dev-auth header support when `VITE_DEV_AUTH=true`
- DSR request list/create/detail/update API wiring

Known integration gaps:

- Browser LiveKit playback is not wired yet. The camera modal can request a short-lived viewer token only.
- Security check report endpoints are planned but not implemented in the backend.
- Site listing is planned but not implemented in the backend; signage attestation can only be used when a valid site ID is known.
- Full local/staging browser smoke and production polish are still pending.

## Local Development

```powershell
cd apps/web
npm ci
npm run dev
```

The Vite dev server runs on `http://localhost:3000` and proxies `/api/v1` plus `/health` to `http://127.0.0.1:8000`.

For local dev-auth testing, set:

```powershell
$env:VITE_DEV_AUTH="true"
$env:VITE_DEV_EMAIL="admin@example.test"
$env:VITE_DEV_ROLES="admin"
```

The backend must also allow dev auth.

## Checks

```powershell
npm run lint
npm run build
```

## Railway Deployment

Deploy the frontend as a separate Railway service from the same GitHub repository.

Railway service settings:

```text
Root directory: apps/web
Build command: npm ci && npm run build
Start command: npm start
```

Required frontend service environment variable:

```text
PANOPTIX_API_ORIGIN=https://staging.panoptix.site
```

Use the actual backend public origin if it differs. Do not include a trailing slash.

The production `npm start` command runs `server.mjs`, which serves the built React files from `dist/` and proxies same-origin browser requests for `/api/v1/*` and `/health` to `PANOPTIX_API_ORIGIN`. This preserves the frontend API client's same-origin contract and avoids putting backend secrets in the browser.

Do not set `VITE_DEV_AUTH=true` in a deployed frontend service. Dev-auth is local-only.

## Guardrails

- Do not request browser camera or microphone permissions.
- Do not store auth tokens in `localStorage`, `sessionStorage`, or IndexedDB.
- Do not call gateway-only endpoints from the browser.
- Do not expose RTSP URLs, camera passwords, service-token values beyond one-time gateway create/rotate display, or LiveKit admin credentials.
- Use same-origin API calls through `/api/v1/*`.
