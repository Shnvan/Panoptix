# 07 - Screen And Page Requirements

## UI Implementation Status

`apps/web/README.md` states that the frontend is a placeholder owned by the frontend coworker. No implemented Next.js/React UI files were found. The screen requirements below are based on existing backend APIs and frontend documentation, not implemented UI code.

## Required Screens

| Screen/page | Purpose | Role access | Fields/data | Buttons/actions | Existing file/component | Status |
|---|---|---|---|---|---|---|
| Login/access shell | Enter through Cloudflare Access and bootstrap app state | Viewer/Admin | Principal, roles, permissions | Re-auth/refresh | Placeholder only | Missing |
| Privacy notice gate | Display current notice and record acceptance | Viewer/Admin | Notice title, body, version, accepted state | Accept notice | Placeholder only | Missing |
| Viewer dashboard | Show assigned camera grid | Viewer/Admin with camera ACL | Camera name, status, room metadata | View, fullscreen, layout select | Placeholder only | Missing |
| Camera tile/player | Connect to LiveKit as subscriber only | Viewer/Admin with camera ACL | Camera ID/name, token state, live status | Start view, retry, fullscreen | Placeholder only | Missing |
| Active sessions | List and revoke sessions | Viewer/Admin | Session ID, created, last seen, UA fingerprint | Revoke session | Placeholder only | Missing |
| Admin dashboard | Show aggregate operational counts | Admin | Camera/gateway/user/command/publish counts | Refresh, navigate | Placeholder only | Missing |
| Admin users | Manage users and roles | Admin | Email, roles, disabled state, created date | Grant role, revoke role, disable, MFA reset | Placeholder only | Missing |
| Admin cameras | Register and manage cameras | Admin | Name, source type, room, gateway/site, ACL count | Create, disable, grant/revoke ACL | Placeholder only | Missing |
| Admin gateways | Register and manage gateways | Admin | Name, status, last seen, cert metadata, camera count | Create, disable, rotate credential, assign camera | Placeholder only | Missing |
| Gateway commands | Inspect and control command queue | Admin | Command kind, payload, status, expiry, ACK/error | Enqueue, cancel, cleanup | Placeholder only | Missing |
| Audit log | Review audit rows and verification status | Admin/Auditor | Actor, action, resource, timestamp, payload | Filter, verify, export | Placeholder only | Missing |
| Compliance | Export DPA artifacts and record signage | Admin/Auditor | Artifact kind, hash, effective dates, site | Export, signage attest | Placeholder only | Missing |
| Health/operations | Show backend, DB, LiveKit, and gateway freshness | Admin | Deep health check result | Refresh, run maintenance | Placeholder only | Missing |
| Backup status | Show backup health | Admin | Backup metadata | Refresh | Endpoint stub only | Missing |
| DSR ledger | Track data subject requests | Admin/Auditor | Requester, type, due date, status, outcome | Create/update/export | Data model only | Missing |

## Field And Validation Notes

| Screen | Required validation/error handling |
|---|---|
| Camera create | `display_name` 1-255 chars; `source_type` must match actual backend enum; `livekit_room_name` 1-64 chars and unique. |
| Camera ACL | Action must be `grant` or `revoke`; user email required; duplicate active grants show conflict. |
| Gateway create | Name required; one-time service token must be displayed once and never stored by frontend. |
| Gateway assignment | Action must be `grant` or `revoke`; camera ID must be valid and active. |
| User role | Action must be `grant` or `revoke`; role must exist. |
| Disable actions | Reason required; UI must warn that sessions/viewers/publishers may be terminated. |
| Break-glass | Reason required; UI must show emergency nature and rotation checklist after close. |
| Audit export | Export may fail closed if HMAC key configuration is invalid. |
| Session revoke | Non-admin users can revoke only owned sessions. |

## Recommended UI Behaviors

- Render explicit states for loading, empty, offline, degraded, unavailable, permission denied, and session expired.
- Do not request browser camera, microphone, or screen-capture permissions.
- Do not store auth or LiveKit tokens in `localStorage` or `sessionStorage`.
- Do not expose gateway credentials, RTSP URLs, or backend secrets.
- Use backend problem-detail `detail` values for user-safe error mapping.

