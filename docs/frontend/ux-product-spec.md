# UX and Product Specification

<!-- PE-FIX: Added frontend-ready UX specification required by council audit -->

This document gives the frontend owner implementation guidance without making the frontend a security authority.

## UX principles

- Security state must be visible, not hidden.
- Empty, loading, offline, denied, and degraded states must be explicit.
- The app must never ask for browser camera or microphone permission.
- Every data-bearing screen is populated from `cctv-api` only.
- Admin screens must show confirmation and audit implications for risky actions.

## Primary personas

| Persona | Goal | Risks/frustrations |
|---|---|---|
| Viewer | Watch assigned live cameras quickly. | Confusing offline states, slow start, accidental access denial. |
| Admin | Manage users, cameras, gateways, and compliance records. | Misconfiguring ACLs or gateway assignment. |
| Auditor | Review audit and compliance evidence without changing anything. | Lack of filters/evidence export clarity. |
| SuperAdmin | Perform high-risk recovery and key operations. | Accidentally triggering irreversible or rotation-heavy actions. |

## Core screens

### Dashboard

Required elements:

- Privacy notice gate before first use or updated notice.
- Camera grid: 1x1, 2x1, 2x2.
- Camera tile states: loading, online, offline, reconnecting, unavailable, gateway unavailable, permission denied.
- Viewer identity watermark area for pilot.
- Fullscreen button per tile.
- Clear “no assigned cameras” empty state.

### Admin users

Required elements:

- User list with role and disabled status.
- Role/permission editing with confirmation.
- MFA reset flow with out-of-band verification note.
- Disable user action with warning that sessions and LiveKit participants terminate.

### Admin cameras and gateways

Required elements:

- Camera registration form: name, site, source type, gateway assignment.
- Gateway health status: online, degraded, offline, cert expiring, disabled.
- Gateway control-channel state: WebSocket connected, heartbeat fallback, offline.
- Credential rotation flow with one-time display warning.

### Audit and compliance

Required elements:

- Audit filters: actor, action, resource, time range.
- Audit verifier status.
- Signed JSONL export action.
- DPA/signage export action.
- DSR request ledger view.

## Accessibility requirements

- Target WCAG 2.1 AA for app UI.
- Full keyboard navigation for dashboard and admin forms.
- Visible focus states.
- Color contrast at least 4.5:1 for text.
- Do not rely only on color for camera status.
- Live status changes use polite ARIA announcements where useful.
- Forms show field-level validation messages.
- Video tiles include accessible labels with camera display name and status.

## Responsive behavior

| Viewport | Layout |
|---|---|
| Mobile | Single-column camera list, one video primary at a time. |
| Tablet | 1x1 or 2x1 grid depending on orientation. |
| Desktop | 1x1, 2x1, 2x2 grid. |

## Error copy requirements

| Case | Message intent |
|---|---|
| Permission denied | User lacks access; contact admin. Do not reveal whether hidden cameras exist. |
| Gateway unavailable | Site gateway is offline or degraded; no action required by viewer. |
| Camera offline | Camera feed is not available. |
| Session expired | Ask user to refresh/re-authenticate through Cloudflare Access. |
| Break-glass expired | Emergency window is closed; open a new audited window if needed. |

## Frontend security boundaries

The frontend must not:

- Store auth tokens in `localStorage` or `sessionStorage`.
- Mint LiveKit tokens.
- Receive gateway-publish tokens.
- Receive RTSP credentials.
- Call browser camera APIs.
- Implement authorization decisions outside display hints.
