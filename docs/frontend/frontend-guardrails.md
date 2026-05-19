# Frontend Guardrails

<!-- PE-FIX: Added frontend coworker guardrails to prevent cross-workstream breakage -->

This document tells the frontend owner what **not** to do so `cctv-web` does not break backend security, database assumptions, gateway/media flow, or future operations.

## Ownership boundary

Frontend owns:

- Next.js routes and layouts.
- React components.
- Tailwind styling.
- Camera grid and tile states.
- Admin/privacy UI screens.
- Viewer-only LiveKit subscription components.

Frontend does **not** own security decisions, database writes, token minting, gateway control, audit integrity, or camera credentials.

## Do not bypass `cctv-api`

Do not:

- Call database providers directly from frontend code.
- Call LiveKit admin APIs from the browser.
- Call gateway endpoints directly from browser code.
- Implement Next.js API routes for protected backend actions.
- Store authorization rules only in React state.
- Decide camera access in the UI without backend confirmation.

All data-bearing actions must go through same-origin `/api/v1/*` routes owned by `cctv-api`.

## Do not create browser publishing paths

Do not add or import:

- `getUserMedia`
- `MediaRecorder`
- `navigator.mediaDevices`
- webcam demo pages
- phone camera pages
- browser publisher pages
- upload/record/snapshot features
- LiveKit publisher SDK code in browser bundles

The browser is viewer-only.

## Do not handle protected secrets or credentials

Do not expose, log, mock with real values, or place in frontend env vars:

- RTSP URLs with credentials.
- Camera usernames/passwords.
- Gateway service tokens.
- Gateway-publish tokens.
- LiveKit API secret.
- Cloudflare service tokens.
- Postgres URLs.
- Audit HMAC keys.

Frontend may receive only short-lived viewer-subscribe tokens from `/api/v1/cameras/:id/view-token`.

## Do not store auth tokens in browser storage

Do not store auth/session/token material in:

- `localStorage`
- `sessionStorage`
- IndexedDB
- non-HttpOnly cookies
- URL query strings
- React global state longer than the current page lifecycle

Use backend/session-cookie behavior only.

## Do not change API contracts alone

Do not rename, remove, or reinterpret fields from `../api-reference.md` without backend/database coordination.

Breaking examples:

- Changing `camera_id` to `id` in one screen only.
- Assuming `status` has values not in the API contract.
- Treating `permission-denied` as the same as `offline`.
- Expecting RTSP fields in `/api/v1/cameras`.
- Building against undocumented admin payloads.

If the frontend needs a different shape, request an API contract update first.

## Do not leak sensitive data through UI behavior

Do not:

- Show hidden camera names to unauthorized users.
- Use different error messages that reveal whether a camera exists.
- Render user/camera bootstrap data in static HTML on direct Railway origin.
- Put IDs, tokens, or internal route details in visible error copy unless needed.
- Capture real camera screenshots in docs/issues.

Use generic denied/unavailable states from `ux-product-spec.md`.

## Do not weaken security headers/CSP

Do not add dependencies or frontend patterns that require:

- `unsafe-inline` for scripts.
- `unsafe-eval`.
- wildcard `connect-src`.
- wildcard `media-src`.
- camera or microphone permissions.

If a UI library requires unsafe CSP, reject it or get system-owner approval before use.

## Do not break same-domain routing

Do not hardcode:

- Railway service URLs.
- API subdomains not selected by the architecture.
- localhost-only paths in production code.
- direct LiveKit fallback URLs outside the backend-provided config.

Browser API calls should be same-origin `/api/v1/*`.

## Do not hide operational states

Do not collapse these states into one generic error:

- loading
- online
- offline
- reconnecting
- unavailable
- gateway unavailable
- permission denied
- session expired

These states affect troubleshooting and user trust.

## Do not introduce compliance scope accidentally

Do not add:

- recording
- playback
- snapshots
- face recognition
- motion analytics
- export footage
- upload media
- public sharing links

Those features change the privacy/security scope and require future approval.

## Do not depend on publish-state internals

The backend tracks camera publish state and stop grace timers internally. Frontend must not:

- Query or display `camera_publish_states` rows directly.
- Assume stop commands happen immediately when a viewer leaves — there is a 10-second grace window.
- Build admin UI for managing publish state transitions — they are automated by LiveKit webhooks.
- Poll gateway command queue to determine whether a camera is "live" — use camera events SSE instead.

Camera online/offline status for the dashboard should come from `/api/v1/cameras/events` SSE, not from publish-state or command-queue internals.

## Required coordination before merging frontend changes

Coordinate with the system owner before changes that affect:

- API request/response shapes.
- LiveKit client behavior.
- auth/session handling.
- admin workflows.
- camera states.
- privacy notice flow.
- CSP/security headers.
- environment variables.

Coordinate with the database coworker if UI changes require new fields, filters, reports, or admin list queries.
