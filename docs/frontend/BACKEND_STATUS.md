# Backend Status For Frontend

This document lists every implemented backend API endpoint, what the frontend can build against today, what is not ready yet, and local dev setup instructions.

Last updated: 2026-05-13 (post LiveKit Cloud provisioning, R2 bucket provisioning, CI finalization)

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

Production/non-dev browser sessions use signed cookies and CSRF protection:

- safe authenticated `GET` requests can establish/refresh `panoptix_session` and `panoptix_csrf`
- unsafe browser/admin requests must send `x-panoptix-csrf-token` matching the `panoptix_csrf` cookie
- CSRF enforcement applies to admin mutations, privacy notice acceptance, and session revoke
- gateway APIs and LiveKit webhooks do not use browser CSRF

All API responses include baseline security headers such as `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy`, and an API-focused `Content-Security-Policy`.

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
| `PATCH` | `/api/v1/admin/cameras/{camera_id}` | `{ "display_name"?, "source_type"?, "livekit_room_name"? }` | camera summary |
| `POST` | `/api/v1/admin/cameras/{camera_id}/acl` | `{ "action": "grant"/"revoke", "user_email" }` | ACL result |
| `POST` | `/api/v1/admin/cameras/{camera_id}/disable` | `{ "reason" }` | retired camera |
| `POST` | `/api/v1/admin/cameras/{camera_id}/enable` | none | camera summary |

- **`source_type`** must be one of: `rtsp`, `nvr_rtsp`, `onvif_profile_s`, `onvif_profile_t`, `synthetic_rtsp_test_source`
- **`livekit_room_name`** must be unique across all cameras

### Gateway Management

| Method | Path | Request | Response |
|---|---|---|---|
| `POST` | `/api/v1/admin/gateways` | `{ "name", "mtls_fingerprint"?, "cert_expires_at"? }` | gateway summary + one-time `service_token` |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/disable` | `{ "reason" }` | disabled gateway |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/rotate-credential` | `{ "reason" }` | `{ "gateway_id", "service_token", "rotated_at" }` |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/cameras` | `{ "action": "grant"/"revoke", "camera_id" }` | assignment result |

- Gateway `service_token` is returned only on create/rotate; frontend must display it once and never persist it.
- Gateway HTTP APIs authenticate with `x-panoptix-gateway-id` plus `Authorization: Bearer <service_token>`; browser/frontend code must never call gateway APIs with these credentials.
- Gateway and control denial paths write backend audit events; frontend can surface related audit rows from the admin audit API.

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

The backend also has a disabled-by-default in-process maintenance scheduler controlled by `ENABLE_MAINTENANCE_SCHEDULER` and `MAINTENANCE_INTERVAL_SECONDS`; the admin endpoint remains available for manual runs.

### Audit

| Method | Path | Request | Response |
|---|---|---|---|
| `GET` | `/api/v1/admin/audit` | query: `cursor`, `limit`, `action`, `actor_type`, `actor_id`, `severity`, `category`, `outcome`, `resource`, `session_id`, `ts_from`, `ts_to` | paginated audit rows |
| `GET` | `/api/v1/admin/audit/verify` | query: `start_id`, `end_id` | `{ "valid", "checked", "error" }` |
| `GET` | `/api/v1/admin/audit/export` | query: `start_id`, `end_id` | signed JSON export: `{ "format", "manifest", "items" }` |

- Audit export manifest includes row count, first/last row IDs, canonical content SHA-256, signature algorithm, signature key version, and HMAC-SHA256 signature.

### Actor Investigation

| Method | Path | Request | Response |
|---|---|---|---|
| `GET` | `/api/v1/admin/actors/{actor_type}/{actor_id}/profile` | path actor type/id | composite actor profile |
| `GET` | `/api/v1/admin/actors/{actor_type}/{actor_id}/activity` | query: `cursor`, `limit`, `action`, `severity`, `category`, `outcome`, `resource`, `session_id`, `ts_from`, `ts_to` | actor-scoped audit rows |

- Supported `actor_type` values: `user`, `gateway`, `system`, `break_glass`, `service_token_monitor`.
- `user` and `gateway` require UUID actor IDs and return `404 user-not-found` or `404 gateway-not-found` when missing.
- System-like actors can use `none` as the path ID to request rows with null `actor_id`, for example `/api/v1/admin/actors/system/none/profile`.
- Profile fields include `identity`, `roles`, `sessions`, `camera_access`, `stream_grants`, `activity_summary`, `risk_indicators`, and `containment_status`.
- Unsupported enrichment sections are present as top-level `null` fields: `ip_details`, `device_details`, `mfa_details`, `threat_intelligence`, `alerts`, `incidents`, `analyst_notes`, and `behavior_baseline`.
- These are admin-only read endpoints. They are not covered by the admin mutation rate limiter.
- Successful views create audit events `admin.actor.profile.viewed` and `admin.actor.activity.viewed`.

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
| Real LiveKit Cloud video playback | LiveKit Cloud account provisioned (APAC); direct synthetic FFmpeg-to-LiveKit and backend-controlled synthetic gateway publish smoke passed. Frontend still needs subscriber playback UI. |
| Real camera streams | Edge agent supports opt-in `livekit-ffmpeg` publishing and synthetic RTSP smoke has passed. Real CCTV hardware validation is still pending. |
| Full admin user management | role update, disable, MFA reset, and GitHub-backed invite flow implemented. |
| Gateway credential rotation | `POST /api/v1/admin/gateways/{id}/rotate-credential` is **implemented** (generates new service token, revokes old hash, audit-logged) |
| DPA/signage export | `POST /api/v1/admin/dpa/export` and `POST /api/v1/admin/sites/:id/signage-attest` are **implemented** (JSONL bundle with kind filter, audit-logged) |
| LiveKit fallback mode | `POST /api/v1/admin/livekit/fallback` is **implemented** (DB flag flip between `cloud`/`fallback`, audit-logged) |
| Production Cloudflare Access | Staging is live (`staging.panoptix.site`) with GitHub OAuth via Cloudflare Access. Production waits for 7-day gate (clears 2026-05-20) |
| Production scheduler | Maintenance scheduler is implemented (`ENABLE_MAINTENANCE_SCHEDULER`) but disabled by default. Manual admin endpoint `POST /api/v1/admin/jobs/run-maintenance` is available |

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
