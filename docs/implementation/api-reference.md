# API Reference

<!-- PE-FIX: Extracted implementation-ready API contract from the council audit findings and main plan §15 -->

This document is the working contract between the Next.js frontend, FastAPI backend, gateway agent, database owner, and QA. FastAPI remains the security authority for every data-bearing route.

## Contract rules

- API version prefix: `/api/v1`.
- Public UI routes are served by `cctv-web`; API, health, webhook, and gateway-control routes are served by `cctv-api`.
- Browser calls are same-origin through the Cloudflare-protected custom domain.
- Protected browser routes require a verified Cloudflare Access JWT and app session.
- Gateway routes require gateway identity: service token for MVP, mTLS for pilot+.
- Errors use RFC 9457 Problem Details.
- Cursor pagination is used for list endpoints.
- State-changing browser requests require CSRF protection.
- No response may include RTSP URLs, camera passwords, gateway-publish tokens to browsers, or long-lived auth tokens.

## Shared response shapes

### Problem Details

```json
{
  "type": "https://panoptix.local/problems/forbidden",
  "title": "Forbidden",
  "status": 403,
  "detail": "camera-access-denied",
  "instance": "/api/v1/cameras/123/view-token",
  "trace_id": "cf-ray-or-request-id"
}
```

### Camera summary

```json
{
  "id": "uuid",
  "display_name": "Front Gate",
  "status": "online",
  "last_seen_at": "2026-05-07T12:00:00Z",
  "viewer_layout_allowed": true
}
```

### Viewer token response

```json
{
  "camera_id": "uuid",
  "room": "camera_ab12cd34",
  "livekit_url": "wss://region.livekit.cloud",
  "token": "short-lived-viewer-subscribe-jwt",
  "expires_at": "2026-05-07T12:01:00Z"
}
```

## Browser/session endpoints

| Method | Path | AuthZ | Request | Response | Notes |
|---|---|---|---|---|---|
| `GET` | `/api/v1/me` | any authenticated user | none | user profile, roles, permissions, camera ACL summary | Frontend bootstrap endpoint. |
| `GET` | `/api/v1/cameras` | viewer/admin filtered by ACL | cursor params | list of camera summaries | Must not expose RTSP fields. |
| `GET` | `/api/v1/cameras/:id/view-token` | viewer with active camera ACL | none | viewer token response | Subscriber-only token, TTL ≤60s. |
| `GET` | `/api/v1/cameras/events` | viewer/admin filtered by ACL | optional cursor/last event | SSE event stream | Polling fallback at 30s. |
| `GET` | `/api/v1/sessions/active` | self | none | active sessions | No raw CF JWTs. |
| `POST` | `/api/v1/sessions/revoke` | self/admin | `{ "session_id": "uuid" }` | revocation result | Triggers LiveKit participant removal where applicable. |
| `GET` | `/api/v1/privacy/notice` | any authenticated user | none | current notice content/version | User must accept current version before dashboard. |
| `POST` | `/api/v1/privacy/notice/accept` | any authenticated user | `{ "notice_version": "string" }` | acceptance record | Writes audit event. |

## Admin endpoints

| Method | Path | AuthZ | Request | Response | Notes |
|---|---|---|---|---|---|
| `GET` | `/api/v1/admin/users` | admin | filters/cursor | user list | |
| `POST` | `/api/v1/admin/users/:id/role` | admin | role update | updated user | All changes audited. |
| `POST` | `/api/v1/admin/users/:id/disable` | admin | reason | disabled user | Revokes sessions and removes LiveKit participants ≤10s. |
| `POST` | `/api/v1/admin/users/:id/mfa/reset` | admin | verification evidence | recovery window | Admin-mediated only. |
| `POST` | `/api/v1/admin/cameras` | admin | name, source type, gateway, site | camera summary | Source type must be CCTV-only enum. |
| `POST` | `/api/v1/admin/cameras/:id/acl` | admin | grant/revoke user camera ACL | ACL result | Enforces one active grant per user/camera. |
| `POST` | `/api/v1/admin/cameras/:id/disable` | admin | reason | disabled/retired camera | Terminates active viewer sessions ≤10s. |
| `POST` | `/api/v1/admin/gateways` | admin | gateway metadata | one-time service token or cert bundle | Raw credential shown once. |
| `POST` | `/api/v1/admin/gateways/:id/disable` | admin | reason | disabled gateway | Publish stopped ≤10s if channel available. |
| `POST` | `/api/v1/admin/gateways/:id/rotate-credential` | admin | rotation reason | one-time credential | Old credential revoked after confirmed switchover. |
| `POST` | `/api/v1/admin/gateways/:id/cameras` | admin | add/remove camera assignment | assignment state | Enforces one active assignment per gateway/camera. |
| `GET` | `/api/v1/admin/audit` | admin | filters/cursor | audit rows | Payloads scrubbed. |
| `GET` | `/api/v1/admin/audit/verify` | admin | range/version | verifier result | Verifies HMAC chain and key versions. |
| `GET` | `/api/v1/admin/audit/export` | admin | filters | signed JSONL bundle | Synchronous MVP export. |
| `POST` | `/api/v1/admin/dpa/export` | admin | artifact selection | signed DPA bundle | Includes signage attestations. |
| `POST` | `/api/v1/admin/sites/:id/signage-attest` | admin | attestation metadata | artifact record | Required before real-site pilot. |
| `POST` | `/api/v1/admin/livekit/fallback` | admin | mode and reason | active media mode | Changes dynamic CSP on next request. |

## Gateway endpoints

| Method | Path | AuthZ | Request | Response | Notes |
|---|---|---|---|---|---|
| `POST` | `/api/v1/gateways/:id/heartbeat` | gateway identity | gateway status, camera status, agent version | server time, pending fallback commands | Browser sessions rejected. |
| `POST` | `/api/v1/gateways/:id/ingest-token` | gateway identity + assignment | camera ID | gateway-publish token | Publisher-only, TTL ≤60s. |
| `POST` | `/api/v1/gateways/:id/cameras/:cameraId/status` | gateway identity + assignment | status event | accepted event | Pushes dashboard event. |
| `GET` | `/api/v1/gateway-control/ws` | gateway identity | WebSocket upgrade | signed command stream | Gateway-initiated outbound channel only. |

## Gateway control command envelope

```json
{
  "command_id": "uuid",
  "kind": "gateway.command.start_publish",
  "gateway_id": "uuid",
  "issued_at": "2026-05-07T12:00:00Z",
  "expires_at": "2026-05-07T12:00:30Z",
  "payload": {
    "camera_id": "uuid",
    "room": "camera_ab12cd34",
    "gateway_publish_token": "short-lived-publisher-jwt"
  },
  "signature": "base64url-signature"
}
```

The signature covers the canonical JSON form of the envelope excluding `signature`: UTF-8 JSON, sorted keys, compact separators, and UTC datetimes normalized to `Z`. The current implementation uses HMAC-SHA-256 and base64url signatures. Gateway validates signature, target gateway, command expiry, active assignment, idempotency, and token scope before acting.

## Webhook and health endpoints

| Method | Path | AuthZ | Request | Response | Notes |
|---|---|---|---|---|---|
| `POST` | `/api/v1/webhooks/livekit` | LiveKit HMAC + 60s timestamp | LiveKit event | 2xx/4xx | No CORS; preflight rejected. |
| `GET` | `/health` | CF Access monitor service token or non-sensitive platform health | none | `{ "status": "ok" }` | No version/framework/DB info. |
| `GET` | `/api/v1/admin/health/deep` | admin | none | deep health | DB, LiveKit, R2, gateway channel state. |

## Frontend implementation notes

- Generate frontend types from FastAPI OpenAPI once code exists.
- Until generated types exist, this document is the manual contract.
- React components must never import gateway-publish types into browser-published bundles.
- `cctv-web` treats all authorization state as display data from `cctv-api`; it does not decide permission.
