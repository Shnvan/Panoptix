# Backend Status For Frontend

This document lists every implemented backend API endpoint, what the frontend can build against today, what is not ready yet, and local dev setup instructions.

Last updated: 2026-05-10

---

## Local Dev Auth Setup

The backend supports a dev-auth mode so the frontend can run locally without Cloudflare Access.

Set these environment variables when running the backend:

```env
APP_ENV=development
ALLOW_DEV_AUTH=true
```

Then pass identity via request headers:

```
x-panoptix-dev-auth: 1
x-panoptix-dev-email: admin@example.test
x-panoptix-dev-subject: admin@example.test
x-panoptix-dev-roles: admin
```

The backend will treat these headers as a verified identity with admin role. Dev auth is rejected unless `ALLOW_DEV_AUTH=true` and `APP_ENV=development`.

The frontend API client should send these headers on every request during local development.

---

## Implemented Browser/Session Endpoints

These are the endpoints the frontend consumes directly.

### `GET /api/v1/me`

- **Auth:** any authenticated user
- **Response:** user profile with `email`, `subject`, `roles`, `permissions`
- **Use:** bootstrap the app — determine role, populate nav, gate admin screens

### `GET /api/v1/cameras`

- **Auth:** any authenticated user (filtered by camera ACL)
- **Query params:** `cursor` (uuid, optional), `limit` (1–200, default 50)
- **Response:**
  ```json
  {
    "items": [
      {
        "camera_id": "uuid",
        "display_name": "Front Gate",
        "source_type": "rtsp",
        "livekit_room_name": "camera_front_gate",
        "created_at": "2026-05-07T12:00:00"
      }
    ],
    "next_cursor": "uuid or null"
  }
  ```
- **Use:** camera grid, camera list, dashboard tiles

### `GET /api/v1/cameras/events`

- **Auth:** any authenticated user (filtered by camera ACL)
- **Query params:** `since` (ISO datetime, optional), `limit` (1–500, default 100)
- **Response:** `text/event-stream` SSE
  ```
  event: camera_event
  data: {"event_id":"uuid","camera_id":"uuid","gateway_id":"uuid","kind":"room_started","source":"livekit_webhook","at":"2026-05-07T12:00:00"}
  ```
- **Use:** live status updates on camera tiles, online/offline indicators

### `GET /api/v1/cameras/{camera_id}/view-token`

- **Auth:** viewer with active camera ACL
- **Response:**
  ```json
  {
    "camera_id": "uuid",
    "room": "camera_front_gate",
    "livekit_url": "wss://region.livekit.cloud",
    "token": "short-lived-viewer-subscribe-jwt",
    "expires_at": "2026-05-07T12:01:00"
  }
  ```
- **Use:** connect LiveKit JS SDK to watch a camera stream
- **Note:** token is subscriber-only, TTL ≤60s. Frontend must never publish.

### `GET /api/v1/sessions/active`

- **Auth:** any authenticated user (own sessions only)
- **Response:**
  ```json
  {
    "items": [
      {
        "id": "uuid",
        "created_at": "2026-05-07T12:00:00",
        "last_seen_at": "2026-05-07T12:05:00",
        "ua_fp": "browser fingerprint"
      }
    ]
  }
  ```
- **Use:** "active sessions" settings page

### `POST /api/v1/sessions/revoke`

- **Auth:** self (own sessions) or admin (any session)
- **Request:** `{ "session_id": "uuid" }`
- **Response:** `{ "revoked": true, "session_id": "uuid" }`
- **Use:** sign out other sessions

### `GET /api/v1/privacy/notice`

- **Auth:** any authenticated user
- **Response:**
  ```json
  {
    "notice_version": "2026-05-10",
    "title": "Panoptix CCTV Operator Privacy Notice",
    "body": "notice text",
    "accepted": false,
    "accepted_at": null
  }
  ```
- **Use:** first-login privacy notice gate

### `POST /api/v1/privacy/notice/accept`

- **Auth:** any authenticated user
- **Request:** `{ "notice_version": "2026-05-10" }`
- **Response:** `{ "notice_version": "2026-05-10", "accepted_at": "...", "status": "accepted" }`
- **Use:** record current privacy notice acceptance
- **Note:** repeated acceptance for the same current version is idempotent

---

## Implemented Admin Endpoints

All admin endpoints require the `admin` role.

### User Management

| Method | Path | Request | Response |
|---|---|---|---|
| `GET` | `/api/v1/admin/users` | query: `cursor`, `limit`, `email` | paginated safe user list |
| `POST` | `/api/v1/admin/users/{user_id}/role` | `{ "action": "grant"/"revoke", "role_name" }` | role action result |
| `POST` | `/api/v1/admin/users/{user_id}/disable` | `{ "reason" }` | `{ "user_id", "disabled_at", "sessions_revoked" }` |

- Returned user list fields: `user_id`, `email`, `roles`, `role_default`, `disabled_at`, `created_at`
- Role assignment: `action` must be `grant` or `revoke`; `role_name` must match a known role
- Disable: sets `disabled_at` and bulk-revokes all active sessions immediately

### Camera Management

| Method | Path | Request | Response |
|---|---|---|---|
| `POST` | `/api/v1/admin/cameras` | `{ "display_name", "source_type", "livekit_room_name" }` | camera summary |
| `POST` | `/api/v1/admin/cameras/{camera_id}/acl` | `{ "action": "grant"/"revoke", "user_email" }` | ACL result |
| `POST` | `/api/v1/admin/cameras/{camera_id}/disable` | `{ "reason" }` | retired camera |

- **`source_type`** must be one of: `rtsp`, `onvif`, `usb`, `file`, `test`
- **`livekit_room_name`** must be unique across all cameras

### Gateway Management

| Method | Path | Request | Response |
|---|---|---|---|
| `POST` | `/api/v1/admin/gateways` | `{ "name", "mtls_fingerprint"?, "cert_expires_at"? }` | gateway summary + one-time `service_token` |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/disable` | `{ "reason" }` | disabled gateway |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/rotate-credential` | `{ "reason" }` | `{ "gateway_id", "service_token", "rotated_at" }` |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/cameras` | `{ "action": "grant"/"revoke", "camera_id" }` | assignment result |

- Gateway `service_token` is returned only on create/rotate; frontend must display it once and never persist it.

### Command Queue

| Method | Path | Request | Response |
|---|---|---|---|
| `POST` | `/api/v1/admin/gateways/{gateway_id}/commands` | `{ "kind", "payload"?, "expires_in_seconds"? }` | enqueued command |
| `GET` | `/api/v1/admin/gateways/{gateway_id}/commands` | query: `cursor`, `limit`, `status` | paginated command list |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/commands/{command_id}/cancel` | none | cancelled command |
| `POST` | `/api/v1/admin/commands/cleanup` | none | `{ "expired_count" }` |

- **`status`** filter accepts: `pending`, `accepted`, `rejected`, `expired`, `cancelled`

### Maintenance

| Method | Path | Request | Response |
|---|---|---|---|
| `POST` | `/api/v1/admin/jobs/run-maintenance` | none | `{ "expired_commands", "stops_enqueued" }` |

Runs expired-command cleanup and due publish-stop processing in a single admin call. Idempotent and safe to call repeatedly.

### Audit

| Method | Path | Request | Response |
|---|---|---|---|
| `GET` | `/api/v1/admin/audit` | query: `cursor`, `limit`, `action` | paginated audit rows |
| `GET` | `/api/v1/admin/audit/verify` | query: `start_id`, `end_id` | `{ "valid", "checked", "error" }` |
| `GET` | `/api/v1/admin/audit/export` | query: `start_id`, `end_id` | JSONL file download |

---

## Implemented Health Endpoints

| Method | Path | Auth | Response |
|---|---|---|---|
| `GET` | `/health` | none | `{ "status": "ok" }` |
| `GET` | `/api/v1/admin/health/deep` | admin | `{ "status", "db", "checks" }` |

---

## Gateway-Only Endpoints (Not For Frontend)

These endpoints are called by the edge gateway agent, not the browser. **Do not call these from frontend code.**

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/gateways/{id}/heartbeat` | gateway heartbeat |
| `POST` | `/api/v1/gateways/{id}/ingest-token` | gateway publish token |
| `POST` | `/api/v1/gateways/{id}/cameras/{cameraId}/status` | camera status push |
| `GET` | `/api/v1/gateway-control/ws` | WebSocket command channel |
| `POST` | `/api/v1/webhooks/livekit` | LiveKit webhook receiver |

---

## Error Format

All errors use RFC 9457 Problem Details:

```json
{
  "type": "https://panoptix.local/problems/forbidden",
  "title": "Forbidden",
  "status": 403,
  "detail": "camera-access-denied",
  "instance": "/api/v1/cameras/123/view-token"
}
```

Common `detail` values the frontend should handle:

| Detail | Status | Meaning |
|---|---|---|
| `camera-not-found` | 404 | camera does not exist or is retired |
| `camera-access-denied` | 403 | user has no ACL for this camera |
| `user-disabled` | 403 | user account is disabled |
| `gateway-not-found` | 404 | gateway does not exist |
| `acl-already-active` | 409 | duplicate ACL grant |
| `acl-not-found` | 404 | no active ACL to revoke |
| `command-not-pending` | 409 | command already processed |
| `source-type-invalid` | 400 | invalid camera source type |
| `room-name-taken` | 409 | LiveKit room name already used |
| `audit-hmac-key-invalid` | 503 | audit system misconfigured |
| `session-not-owned` | 403 | non-admin trying to revoke another user's session |
| `privacy-notice-version-mismatch` | 409 | frontend submitted a stale privacy notice version |
| `cursor-invalid` | 400 | cursor is not a valid UUID for UUID-cursor endpoints |

---

## Pagination Convention

List endpoints use cursor-based pagination:

- Send `cursor` (from previous `next_cursor`) and `limit`
- Response includes `items` array and `next_cursor` (null when no more pages)
- Audit list uses integer cursor (`id`); camera list uses UUID cursor
- Admin users list uses UUID cursor and supports exact `email` filtering

---

## What Frontend Can Build Now

### Viewer Dashboard

- [x] Login-protected layout using `/api/v1/me`
- [x] Camera grid from `/api/v1/cameras`
- [x] Camera status badges from `/api/v1/cameras/events` SSE
- [x] "View camera" button → fetch `/api/v1/cameras/{id}/view-token`
- [x] Placeholder video tile (real LiveKit playback can be wired later)
- [x] Empty state: "no assigned cameras"
- [x] Loading / error / offline / reconnecting states
- [x] First-login privacy notice gate with acceptance persistence

### Admin Screens

- [x] Basic user list
- [x] Create camera form
- [x] Disable/retire camera
- [x] Grant/revoke camera ACL by user email
- [x] Create gateway
- [x] Disable gateway
- [x] Assign/revoke camera to gateway
- [x] List queued gateway commands with status filter
- [x] Cancel pending commands
- [x] Run expired-command cleanup
- [x] Audit log viewer with action filter and pagination
- [x] Audit chain verification display
- [x] Audit JSONL export download

### Session Management

- [x] Active sessions list
- [x] Revoke session

### Health/Operations

- [x] Basic health indicator
- [x] Deep health display (admin only)

---

## What Is NOT Ready Yet

Do not build against or depend on these:

| Feature | Status |
|---|---|
| Real LiveKit Cloud video playback | LiveKit tokens are mintable but no gateway is publishing real streams yet |
| Real camera streams | Edge agent has stub media controller only |
| Full admin user management | role update, disable, MFA reset, and IdP invite flow are not implemented |
| Gateway credential rotation | `POST /api/v1/admin/gateways/{id}/rotate-credential` is not implemented |
| DPA/signage export | `POST /api/v1/admin/dpa/export` and signage attestation are not implemented |
| LiveKit fallback mode | `POST /api/v1/admin/livekit/fallback` is not implemented |
| Production Cloudflare Access | Use dev-auth locally; real CF Access is not configured yet |
| Production scheduler | Due publish stop processing requires scheduler wiring |

Frontend can use placeholder/mock UI for these features and wire them when the backend adds them.

---

## Important Conventions

- **All browser API calls are same-origin** `/api/v1/*`
- **Auth is session-cookie based** — do not store tokens in localStorage
- **Camera IDs and gateway IDs are UUIDs**
- **Timestamps are ISO 8601** with timezone
- **SSE events use `event: camera_event`** with JSON `data` field
- **Admin role is required** for all `/admin/*` endpoints
- **Every state-changing action is audited** — admin UI should reflect this to users
