# API Reference

This is the current backend and gateway API contract for the implemented FastAPI service. API routes are mounted under `/api/v1` except `/health`.

FastAPI remains the security authority. Browser responses must not expose RTSP URLs, camera credentials, gateway publish tokens, raw Cloudflare JWTs, database URLs, or long-lived auth tokens.

## Shared Rules

- Browser routes require Cloudflare Access/app-session auth, or dev auth only in local development.
- Admin routes require the `admin` role unless explicitly marked as monitor/internal.
- Gateway HTTP and WebSocket routes require gateway identity.
- Unsafe browser mutations require CSRF protection.
- Errors use RFC 9457-style Problem Details.
- Lists use cursor pagination where implemented.
- Viewer and gateway LiveKit tokens are short-lived and kind-distinct.

## Health and Webhooks

| Method | Path | Auth | Status |
|---|---|---|---|
| `GET` | `/health` | public/platform health | implemented |
| `GET` | `/api/v1/admin/health/deep` | admin | implemented; probes DB, LiveKit, and gateway freshness |
| `POST` | `/api/v1/webhooks/livekit` | LiveKit webhook JWT/body hash | implemented |

## Browser and Session Routes

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/me` | authenticated user | current principal profile |
| `GET` | `/api/v1/cameras` | authenticated user | ACL-filtered camera list |
| `GET` | `/api/v1/cameras/events` | authenticated user | SSE stream of accessible camera events |
| `GET` | `/api/v1/cameras/{camera_id}/view-token` | active camera ACL | LiveKit viewer subscribe token |
| `GET` | `/api/v1/privacy/notice` | authenticated user | current privacy notice and acceptance state |
| `POST` | `/api/v1/privacy/notice/accept` | authenticated user | records current notice acceptance |
| `GET` | `/api/v1/sessions/active` | authenticated user | active app sessions |
| `POST` | `/api/v1/sessions/revoke` | authenticated user | revokes one owned session |

## Admin Routes

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/admin/dashboard` | aggregate system counts |
| `GET` | `/api/v1/admin/users` | list users |
| `POST` | `/api/v1/admin/users/{user_id}/role` | grant/revoke role |
| `POST` | `/api/v1/admin/users/{user_id}/disable` | disable user, revoke sessions, remove LiveKit viewer participants |
| `POST` | `/api/v1/admin/users/{user_id}/mfa/reset` | audit admin-mediated MFA reset |
| `POST` | `/api/v1/admin/users/invite` | stub; returns `501 idp-invite-not-implemented` |
| `GET` | `/api/v1/admin/gateways` | list gateways with filters/search |
| `POST` | `/api/v1/admin/gateways` | register gateway and return one-time service token |
| `GET` | `/api/v1/admin/gateways/{gateway_id}` | gateway detail |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/disable` | disable gateway and remove LiveKit publisher participants |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/rotate-credential` | rotate one-time gateway service token |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/cameras` | grant/revoke gateway-camera assignment |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/commands` | enqueue gateway command |
| `GET` | `/api/v1/admin/gateways/{gateway_id}/commands` | list gateway commands |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/commands/{command_id}/cancel` | cancel pending command |
| `POST` | `/api/v1/admin/commands/cleanup` | expire stale pending commands |
| `POST` | `/api/v1/admin/jobs/run-maintenance` | run maintenance job once |
| `GET` | `/api/v1/admin/cameras` | list cameras with filters/search |
| `POST` | `/api/v1/admin/cameras` | create camera |
| `GET` | `/api/v1/admin/cameras/{camera_id}` | camera detail |
| `POST` | `/api/v1/admin/cameras/{camera_id}/acl` | grant/revoke user camera ACL |
| `POST` | `/api/v1/admin/cameras/{camera_id}/disable` | retire camera and remove LiveKit viewer participants |
| `GET` | `/api/v1/admin/audit` | list scrubbed audit rows |
| `GET` | `/api/v1/admin/audit/verify` | verify audit HMAC chain |
| `GET` | `/api/v1/admin/audit/export` | export scrubbed audit JSONL |
| `POST` | `/api/v1/admin/livekit/fallback` | switch `media_plane_mode` between `cloud` and `fallback` |
| `POST` | `/api/v1/admin/dpa/export` | export DPA artifacts |
| `POST` | `/api/v1/admin/sites/{site_id}/signage-attest` | record bystander signage attestation |
| `POST` | `/api/v1/admin/break-glass/open` | open emergency access window |
| `POST` | `/api/v1/admin/break-glass/close` | close emergency access window and return rotation checklist |
| `GET` | `/api/v1/admin/internal/break-glass-status` | unauthenticated monitor endpoint |
| `GET` | `/api/v1/admin/backups/status` | stub; returns `501 backup-status-not-implemented` |

## Gateway Routes

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/gateways/{gateway_id}/heartbeat` | heartbeat plus pending command fallback |
| `POST` | `/api/v1/gateways/{gateway_id}/cameras/{camera_id}/status` | persist gateway-reported camera status |
| `POST` | `/api/v1/gateways/{gateway_id}/ingest-token` | LiveKit gateway publish token |
| `WEBSOCKET` | `/api/v1/gateway-control/ws` | outbound gateway control channel |

## Important Response Shapes

Viewer token:

```json
{
  "camera_id": "uuid",
  "room": "camera_front_gate",
  "livekit_url": "wss://region.livekit.cloud",
  "token": "short-lived-viewer-subscribe-jwt",
  "expires_at": "2026-05-13T12:01:00Z"
}
```

Admin dashboard:

```json
{
  "cameras": { "total": 0, "active": 0, "retired": 0 },
  "gateways": { "total": 0, "enabled": 0, "disabled": 0 },
  "users": { "total": 0, "active": 0, "disabled": 0 },
  "commands": { "pending": 0 },
  "publishing": { "active": 0 }
}
```

Gateway command envelope:

```json
{
  "command_id": "uuid",
  "kind": "gateway.command.start_publish",
  "gateway_id": "uuid",
  "issued_at": "2026-05-13T12:00:00Z",
  "expires_at": "2026-05-13T12:05:00Z",
  "payload": {},
  "signature": "base64url-signature"
}
```

Gateway ACK:

```json
{
  "type": "command_ack",
  "command_id": "uuid",
  "gateway_id": "uuid",
  "status": "accepted",
  "error": null
}
```

## Deferred or Not Implemented

- Frontend-generated OpenAPI/TypeScript client.
- Dynamic CSP middleware driven by `media_plane_mode`.
- R2-backed backup status implementation.
- IdP invite automation.
- Browser bundle scan and frontend API type generation.
