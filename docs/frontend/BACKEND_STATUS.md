# Backend Status For Frontend

This document lists every implemented backend API endpoint, what the frontend can build against today, what is not ready yet, and local dev setup instructions.

Last updated: 2026-05-22 (production live at panoptix.site, visitor visits migration 0010 deployed)

Read first: [Frontend Coworker Handoff](FRONTEND_HANDOFF.md).

## Current Backend State For Frontend

- Local full-stack smoke is working through Vite and FastAPI when `apps/api/.env` is configured locally. That file is ignored and must never be committed.
- The active local database has reached Alembic head `0008_alerts_email`.
- Admin users, cameras, gateways, DSR requests, backup status, break-glass, health, and alert APIs are backend-available.
- `POST /api/v1/admin/users/invite` is implemented, but `github-invites-not-configured` is expected unless GitHub invite settings are intentionally enabled.
- Alert records and backend SMTP email notification support are implemented. Email is backend-only and disabled by default until SMTP settings are configured.
- Real LiveKit browser playback is still not production-complete. The backend mints subscriber-only viewer tokens; the frontend still needs the subscriber player.
- Real CCTV hardware validation is still pending. Staging browser smoke passed 2026-05-21. Production deployed at `panoptix.site` 2026-05-22.
- The public visitor collector pilot has backend APIs plus a first public `entry.panoptix.site` entry view on the existing web service; the future admin visitor dashboard remains frontend handoff work.

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

### Public visitor entry

The Cloudflare Access-protected app host cannot run pre-auth frontend JavaScript. The first frontend entry view runs on the intentionally public `entry.panoptix.site` host, shows the backend notice before its explicit Continue action, and redirects to `panoptix.site` after the collection attempt.

| Method | Path | Auth | Use |
|---|---|---|---|
| `GET` | `/api/v1/visitor/notice` | public when collector enabled | render the current visitor security notice |
| `POST` | `/api/v1/visitor/collect` | public when collector enabled | record approved entry-page signals after the visitor continues |

The collect request carries `notice_version`, `notice_acknowledged`, `page_path`, screen width/height, timezone, and language. The backend adds request IP, user-agent, Ipregistry subset when configured, and an HttpOnly visitor cookie for later login correlation. Do not add WebRTC collection or raw Ipregistry payload rendering for this pilot.

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
| `PATCH` | `/api/v1/admin/gateways/{gateway_id}` | `{ "name"?, "mtls_fingerprint"?, "cert_expires_at"? }` | gateway summary |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/disable` | `{ "reason" }` | disabled gateway |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/enable` | none | gateway summary |
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
| `POST` | `/api/v1/admin/jobs/run-maintenance` | none | `{ "expired_commands", "stops_enqueued", "purged_visitor_visits" }` |

Runs expired-command cleanup, due publish-stop processing, and anonymous visitor retention cleanup in a single admin call. Idempotent and safe to call repeatedly.

The backend also has a disabled-by-default in-process maintenance scheduler controlled by `ENABLE_MAINTENANCE_SCHEDULER` and `MAINTENANCE_INTERVAL_SECONDS`; the admin endpoint remains available for manual runs.

### Alerts

| Method | Path | Request | Response |
|---|---|---|---|
| `GET` | `/api/v1/admin/alerts` | query: `cursor`, `limit`, `status`, `severity`, `category` | `{ "items": [...], "next_cursor": null }` |
| `GET` | `/api/v1/admin/alerts/{alert_id}` | none | alert detail |
| `POST` | `/api/v1/admin/alerts/{alert_id}/acknowledge` | none | acknowledged alert |
| `POST` | `/api/v1/admin/alerts/{alert_id}/resolve` | none | resolved alert |

- Alert fields include `alert_id`, `severity`, `category`, `title`, `message`, `status`, `source`, linked resource fields, actor fields, timestamps, and sanitized metadata.
- Backend creates alerts for break-glass open, invalid audit verification, admin role grants, gateway disable, rejected gateway commands, and degraded/missing backup status checks.
- SMTP email notification is backend-only. The frontend should show alert records and statuses, not send email directly.

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
- Profile fields include `identity`, `roles`, `sessions`, `camera_access`, `stream_grants`, `activity_summary`, `risk_indicators`, `containment_status`, and direct actor-linked `alerts` summaries with up to 10 recent alert rows.
- User profiles expose a safe `behavior_baseline` summary from stored login baseline counts and last-login context; non-user actor profiles keep `behavior_baseline: null`.
- User profiles expose bounded `ip_details` and `device_details` over the latest 10 stored sessions. IP enrichment uses configured Ipregistry actor-profile lookups and may report `not_configured` or `unavailable`; device detail is parsed from stored session user agents.
- Non-user profiles keep `ip_details: null` and `device_details: null`. Unsupported enrichment sections remain top-level `null` fields for `mfa_details`, `threat_intelligence`, `incidents`, and `analyst_notes`.
- These are admin-only read endpoints. They are not covered by the admin mutation rate limiter.
- Successful views create audit events `admin.actor.profile.viewed` and `admin.actor.activity.viewed`.

### Visitor Entry Investigation

| Method | Path | Request | Response |
|---|---|---|---|
| `GET` | `/api/v1/admin/visitor-visits` | query: `cursor`, `limit` | paginated collected entry visits |
| `GET` | `/api/v1/admin/visitor-visits/{visit_id}` | path visit ID | approved entry visit detail and login correlation |

- Admin detail reads write `admin.visitor.visit.viewed`.
- Returned records include page/time, request IP and stored normalized Ipregistry subset, parsed browser/OS/device summary, screen/timezone/language, and linked user/session fields when the visitor later logs in.
- The first pilot covers users who enter through the public entry host. Collector failure on that entry page must not block the redirect into secure sign-in. Direct Cloudflare Access challenge visits to `panoptix.site` do not run browser-side collector code.

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
- [x] GitHub organization invite form can call the backend route; local disabled-config error is expected unless invite env is enabled
- [x] MFA reset action
- [x] Create camera form
- [x] Update camera supported fields
- [x] Disable/retire camera
- [x] Re-enable camera
- [x] Grant/revoke camera ACL by user email
- [x] Create gateway
- [x] Update gateway supported fields
- [x] Disable gateway
- [x] Re-enable gateway
- [x] Rotate gateway credential with one-time token display
- [x] Assign/revoke camera to gateway
- [x] List queued gateway commands with status filter
- [x] Cancel pending commands
- [x] Run expired-command cleanup
- [x] Audit log viewer with action filter and pagination
- [x] Audit chain verification display
- [x] Audit JSONL export download
- [x] DSR request list/create/detail/update APIs are backend-ready
- [x] Backup status is implemented from database-known backup readiness
- [ ] Alerts page should use the real alert list/detail/acknowledge/resolve APIs

### Session Management

- [x] Active sessions list
- [x] Revoke session

### Health/Operations

- [x] Basic health indicator
- [x] Deep health display (admin only)

---

## What Still Needs Caution

These features are either incomplete in the frontend, need staged/production smoke, or require external configuration before full use:

| Feature | Status |
|---|---|
| Real LiveKit Cloud video playback | LiveKit Cloud account provisioned; direct synthetic FFmpeg-to-LiveKit and backend-controlled synthetic gateway publish smoke passed. Frontend still needs subscriber playback UI. |
| Real camera streams | Edge agent supports opt-in `livekit-ffmpeg` publishing and synthetic RTSP smoke has passed. Real CCTV hardware validation is still pending. |
| Full admin user management | Role update, disable, MFA reset, and GitHub-backed invite flow are implemented. GitHub invite requires configured invite env before real emails are sent. |
| Gateway credential rotation | `POST /api/v1/admin/gateways/{id}/rotate-credential` is **implemented** (generates new service token, revokes old hash, audit-logged) |
| DPA/signage export | `POST /api/v1/admin/dpa/export` and `POST /api/v1/admin/sites/:id/signage-attest` are **implemented** (JSONL bundle with kind filter, audit-logged) |
| LiveKit fallback mode | `POST /api/v1/admin/livekit/fallback` is **implemented** (DB flag flip between `cloud`/`fallback`, audit-logged) |
| Production Cloudflare Access | Production live at `panoptix.site` (2026-05-22). Staging smoke passed 2026-05-21. Production browser smoke needed. |
| Production scheduler | Maintenance scheduler is implemented (`ENABLE_MAINTENANCE_SCHEDULER`) but disabled by default. Manual admin endpoint `POST /api/v1/admin/jobs/run-maintenance` is available |

Frontend should use real backend APIs for implemented features and show planned/disabled states only for routes that are not implemented.

---

## Important Conventions

- **All browser API calls are same-origin** `/api/v1/*`
- **Auth is session-cookie based** — do not store tokens in localStorage
- **Camera IDs and gateway IDs are UUIDs**
- **Timestamps are ISO 8601** with timezone
- **SSE events use `event: camera_event`** with JSON `data` field
- **Admin role is required** for all `/admin/*` endpoints
- **Every state-changing action is audited** — admin UI should reflect this to users
