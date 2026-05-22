# Frontend Integration Guide

<!-- PE-FIX: Created integration guide for frontend coworker covering auth, LiveKit, camera grid, and error handling -->

This guide explains how the React + Vite frontend (`cctv-web`) integrates with the FastAPI backend (`cctv-api`). It complements `BACKEND_STATUS.md` (endpoint reference) and `frontend-guardrails.md` (security rules).

---

## Table of Contents

1. [Authentication Flow](#authentication-flow)
2. [CSRF Protection](#csrf-protection)
3. [Camera Grid & Viewer](#camera-grid-viewer)
4. [LiveKit JS SDK Integration](#livekit-js-sdk-integration)
5. [Camera Status SSE](#camera-status-sse)
6. [Admin Screens](#admin-screens)
7. [Error Handling](#error-handling)
8. [Environment Variables](#environment-variables)

---

## Authentication Flow

### Production (Cloudflare Access)

```
Browser → Cloudflare Access (GitHub OAuth) → Railway (cctv-api)
```

1. User visits `https://staging.panoptix.site`
2. Cloudflare Access redirects to GitHub OAuth if not authenticated
3. After successful login, Cloudflare sets `CF_Authorization` cookie
4. Browser requests to `/api/v1/*` are same-origin and include the cookie
5. Backend verifies JWT via `cf-access-jwt-assertion` header (injected by Cloudflare)
6. Backend creates/updates app session and sets `panoptix_session` cookie
7. First `GET` request establishes `panoptix_csrf` cookie for mutation protection

### Local Development (Dev Auth)

Set backend env vars:

```env
APP_ENV=development
ALLOW_DEV_AUTH=true
```

Frontend API client sends these headers on **every** request:

```http
x-panoptix-dev-auth: 1
x-panoptix-dev-email: admin@example.test
x-panoptix-dev-subject: admin@example.test
x-panoptix-dev-roles: admin
```

**Never commit real email values.** Use test-only accounts in local dev.

### Bootstrap Pattern

```typescript
// On app load, call GET /api/v1/me
const me = await fetch("/api/v1/me").then(r => r.json());

// Response shape:
// {
//   "kind": "user",
//   "subject": "uuid",
//   "email": "user@example.com",
//   "roles": ["viewer"],
//   "permissions": [],
//   "gateway_id": null,
//   "is_dev": false
// }

// Use roles to gate admin routes
const isAdmin = me.roles.includes("admin");
```

### Privacy Notice Gate

Before showing the camera dashboard, check privacy notice acceptance:

```typescript
const notice = await fetch("/api/v1/privacy/notice").then(r => r.json());
if (!notice.accepted) {
  // Show privacy notice modal
  // User accepts → POST /api/v1/privacy/notice/accept
  // { "notice_version": notice.notice_version }
}
```

---

## CSRF Protection

### How it works

- Safe `GET` requests establish/refresh `panoptix_csrf` cookie (signed, session-bound)
- Unsafe requests (`POST`, `PUT`, `DELETE`, `PATCH`) must include `x-panoptix-csrf-token` header
- The header value must match the `panoptix_csrf` cookie for the active session
- Gateway APIs and LiveKit webhooks do NOT use browser CSRF (not browser-callable)

### Frontend implementation

```typescript
// Fetch wrapper that handles CSRF
async function apiFetch(path: string, options: RequestInit = {}) {
  const csrfToken = getCookie("panoptix_csrf"); // read from document.cookie

  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");

  if (options.method && options.method !== "GET") {
    if (!csrfToken) {
      // First, make a safe GET to establish the CSRF cookie
      await fetch("/api/v1/me", { credentials: "same-origin" });
      const freshToken = getCookie("panoptix_csrf");
      if (freshToken) headers.set("x-panoptix-csrf-token", freshToken);
    } else {
      headers.set("x-panoptix-csrf-token", csrfToken);
    }
  }

  // Dev auth headers (local only)
  if (process.env.NODE_ENV === "development") {
    headers.set("x-panoptix-dev-auth", "1");
    headers.set("x-panoptix-dev-email", "admin@example.test");
    headers.set("x-panoptix-dev-subject", "admin@example.test");
    headers.set("x-panoptix-dev-roles", "admin");
  }

  return fetch(path, {
    ...options,
    headers,
    credentials: "same-origin", // critical: sends cookies
  });
}
```

**Important:**
- `credentials: "same-origin"` is required on all fetch calls
- `localStorage` must NOT be used for auth/session material
- CSRF tokens expire with the session

---

## Camera Grid & Viewer

### Camera list

```typescript
const cameras = await apiFetch("/api/v1/cameras").then(r => r.json());
// { items: [{ camera_id, display_name, source_type, livekit_room_name, created_at }], next_cursor }
```

### Camera status (SSE)

```typescript
const eventSource = new EventSource("/api/v1/cameras/events?limit=100", {
  withCredentials: true, // sends session cookie
});

eventSource.addEventListener("camera_event", (e) => {
  const event = JSON.parse(e.data);
  // { event_id, camera_id, gateway_id, kind, source, at }
  // kind: "online", "offline", "degraded", "room_started", "room_finished", etc.
  updateCameraStatus(event.camera_id, event.kind);
});

// Cleanup on unmount
eventSource.close();
```

### Polling fallback

If SSE is unavailable (e.g., some corporate proxies block it), poll every 30s:

```typescript
// GET /api/v1/cameras/events?since=2026-05-13T10:00:00Z&limit=50
// Returns same SSE format but as a single HTTP response
```

### View token (LiveKit connection)

```typescript
// When user clicks "View Camera"
const tokenResponse = await apiFetch(`/api/v1/cameras/${cameraId}/view-token`)
  .then(r => r.json());

// {
//   camera_id: "uuid",
//   room: "camera_front_gate",
//   livekit_url: "wss://panoptix-xxx.livekit.cloud",
//   token: "jwt-token",
//   expires_at: "2026-05-13T12:01:00Z"
// }
```

Token TTL is ≤60 seconds. Frontend must use it immediately to connect to LiveKit.

---

## LiveKit JS SDK Integration

### Installation

```bash
npm install livekit-client
```

### Connect to a camera room

```typescript
import { Room, RoomEvent } from "livekit-client";

async function connectToCamera(viewTokenResponse: {
  room: string;
  livekit_url: string;
  token: string;
}) {
  const room = new Room({
    adaptiveStream: true,
    dynacast: true,
  });

  room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
    if (track.kind === "video") {
      const element = track.attach();
      document.getElementById("video-container")?.appendChild(element);
    }
  });

  room.on(RoomEvent.TrackUnsubscribed, (track) => {
    track.detach();
  });

  room.on(RoomEvent.Disconnected, () => {
    // Show reconnecting state or return to grid
  });

  await room.connect(viewTokenResponse.livekit_url, viewTokenResponse.token);

  return room;
}
```

### Token refresh pattern

The viewer token expires in ≤60s. When it expires, the room disconnects. To maintain a long viewing session:

```typescript
// Option 1: Re-fetch token before expiry and reconnect
// Option 2: On disconnect, prompt user to "Resume" (re-fetches fresh token)

// Do NOT cache tokens in localStorage
async function refreshAndReconnect(cameraId: string, room: Room) {
  const fresh = await apiFetch(`/api/v1/cameras/${cameraId}/view-token`)
    .then(r => r.json());
  await room.connect(fresh.livekit_url, fresh.token);
}
```

### Security rules

- Browser is **subscriber-only** — never call `localParticipant.publishTrack`
- Do NOT import LiveKit publisher SDK in browser bundles
- Do NOT call `getUserMedia`, `MediaRecorder`, or `navigator.mediaDevices`
- The backend CSP already blocks `camera`, `microphone`, and `geolocation` permissions

---

## Admin Screens

### Dashboard summary

```typescript
const dashboard = await apiFetch("/api/v1/admin/dashboard").then(r => r.json());
// {
//   cameras: { total, active, retired },
//   gateways: { total, enabled, disabled },
//   users: { total, active, disabled },
//   commands: { pending },
//   publishing: { active }
// }
```

### Admin camera list with filters

```typescript
const cameras = await apiFetch(
  "/api/v1/admin/cameras?search=front&source_type=rtsp&include_retired=false"
).then(r => r.json());
```

### Admin gateway list with search

```typescript
const gateways = await apiFetch(
  "/api/v1/admin/gateways?search=warehouse&status=enabled"
).then(r => r.json());
// Items include camera_count
```

### Create camera

```typescript
await apiFetch("/api/v1/admin/cameras", {
  method: "POST",
  body: JSON.stringify({
    display_name: "Front Gate",
    source_type: "rtsp",
    livekit_room_name: "room-front-gate",
  }),
});
```

### Grant camera ACL

```typescript
await apiFetch(`/api/v1/admin/cameras/${cameraId}/acl`, {
  method: "POST",
  body: JSON.stringify({
    action: "grant",
    user_email: "viewer@example.test",
  }),
});
```

### Rate limit awareness

Admin mutation endpoints are rate-limited (10 requests per 60 seconds per actor). If exceeded:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 45

{ "type": "...", "title": "Too Many Requests", "status": 429, "detail": "..." }
```

The `Retry-After` header indicates seconds until the window resets.

---

## Error Handling

### Problem Details format

All API errors return RFC 9457 Problem Details:

```json
{
  "type": "https://panoptix.local/problems/forbidden",
  "title": "Forbidden",
  "status": 403,
  "detail": "camera-access-denied",
  "instance": "/api/v1/cameras/123/view-token"
}
```

### Frontend error mapping

| `detail` | Status | User-facing message |
|----------|--------|---------------------|
| `camera-access-denied` | 403 | "You do not have access to this camera." |
| `camera-not-found` | 404 | "Camera not found or has been retired." |
| `user-disabled` | 403 | "Your account has been disabled. Contact an administrator." |
| `session-idle-expired` | 401 | "Your session has expired. Please log in again." |
| `session-absolute-expired` | 401 | "Your session has expired. Please log in again." |
| `privacy-notice-version-mismatch` | 409 | "The privacy notice has been updated. Please review and accept the latest version." |
| `role-required` | 403 | "You do not have permission to perform this action." |
| `gateway-not-found` | 404 | "Gateway not found." |
| `room-name-taken` | 409 | "This room name is already in use." |
| `rate-limit-exceeded` | 429 | "Too many requests. Please wait a moment." |
| `audit-hmac-key-invalid` | 503 | "Audit system is temporarily unavailable." |

### Generic fallback

For unknown `detail` values, display:
- Status 4xx → "Request failed. Please try again or contact support."
- Status 5xx → "Server error. Please try again later."

### Session expiry handling

If any request returns 401 with `session-idle-expired` or `session-absolute-expired`:
1. Clear any local UI state
2. Redirect to login (Cloudflare Access will handle re-auth)
3. Do NOT attempt to retry with cached credentials

---

## Environment Variables

The frontend Vite app needs these environment variables at build time:

```env
# Required
VITE_API_BASE_URL=/api/v1  # same-origin; no external domain needed

# Optional (development only)
VITE_DEV_AUTH_EMAIL=admin@example.test
```

**Do NOT put in frontend env:**
- LiveKit API secret
- Cloudflare service tokens
- Database URLs
- Gateway credentials
- Audit keys

The backend handles all LiveKit token minting. The frontend only receives short-lived viewer tokens via `/api/v1/cameras/{id}/view-token`.

---

## Quick Reference: Request Patterns

### Safe GET (no CSRF needed)

```typescript
apiFetch("/api/v1/me");
apiFetch("/api/v1/cameras");
apiFetch("/api/v1/cameras/events"); // SSE
```

### Unsafe POST (CSRF required)

```typescript
apiFetch("/api/v1/privacy/notice/accept", { method: "POST", body: "..." });
apiFetch("/api/v1/admin/cameras", { method: "POST", body: "..." });
apiFetch("/api/v1/admin/gateways", { method: "POST", body: "..." });
```

### With query params

```typescript
apiFetch(`/api/v1/admin/audit?cursor=${cursor}&limit=50&action=camera.create`);
```

### Pagination

```typescript
// First page
let response = await apiFetch("/api/v1/cameras?limit=50").then(r => r.json());

// Next page
if (response.next_cursor) {
  response = await apiFetch(`/api/v1/cameras?limit=50&cursor=${response.next_cursor}`)
    .then(r => r.json());
}
```

---

## Testing Checklist for Frontend Developer

Before handing off:

- [ ] Camera grid loads from `/api/v1/cameras`
- [ ] Camera status updates via SSE (`/api/v1/cameras/events`)
- [ ] Clicking camera fetches view token and connects LiveKit room
- [ ] Privacy notice gate blocks dashboard until accepted
- [ ] Admin dashboard shows summary counts
- [ ] Admin can create camera, grant ACL, assign to gateway
- [ ] CSRF token is present on all POST requests
- [ ] Session expiry redirects to login
- [ ] 403/404/409 errors show appropriate user messages
- [ ] No secrets in localStorage, sessionStorage, or URL params
- [ ] No `getUserMedia` or publisher SDK in browser bundle
