# 08 - API And Integration Requirements

## API Overview

The backend is a FastAPI service. Most routes are mounted under `/api/v1`; `/health` is public/platform health. Errors use RFC 9457-style Problem Details. Unsafe browser mutations require CSRF protection.

## Browser And Session APIs

| Method | Endpoint | Auth | Request/query | Response | Related files | Status |
|---|---|---|---|---|---|---|
| GET | `/api/v1/me` | Authenticated user | None | Principal profile | `api/router.py` | Existing |
| GET | `/api/v1/cameras` | Authenticated user | `cursor`, `limit` | ACL-filtered camera list | `api/router.py`, `CameraAcl` | Existing |
| GET | `/api/v1/cameras/events` | Authenticated user | `since`, `limit` | SSE camera events | `api/router.py`, `CameraEvent` | Existing |
| GET | `/api/v1/cameras/{camera_id}/view-token` | Active camera ACL | Path UUID | Viewer LiveKit token | `security/livekit_tokens.py` | Existing |
| GET | `/api/v1/privacy/notice` | Authenticated user | None | Current notice and acceptance state | `api/router.py` | Existing |
| POST | `/api/v1/privacy/notice/accept` | Authenticated user + CSRF for browser | Notice version | Acceptance result | `PrivacyNoticeAcceptance` | Existing |
| GET | `/api/v1/sessions/active` | Authenticated user | None | Active sessions | `security/sessions.py` | Existing |
| POST | `/api/v1/sessions/revoke` | Owner/admin + CSRF for browser | Session ID | Revocation result | `security/sessions.py` | Existing |

## Admin APIs

| Method | Endpoint | Purpose | Status |
|---|---|---|---|
| GET | `/api/v1/admin/dashboard` | Aggregate cameras, gateways, users, commands, publishing counts | Existing |
| GET | `/api/v1/admin/users` | List users with roles and status | Existing |
| POST | `/api/v1/admin/users/{user_id}/role` | Grant/revoke role | Existing |
| POST | `/api/v1/admin/users/{user_id}/disable` | Disable user, revoke sessions, remove viewer participants | Existing |
| POST | `/api/v1/admin/users/{user_id}/mfa/reset` | Record MFA reset evidence | Existing |
| POST | `/api/v1/admin/users/invite` | GitHub organization invite and local role preparation | Existing |
| GET | `/api/v1/admin/gateways` | List gateways with filters/search | Existing |
| POST | `/api/v1/admin/gateways` | Register gateway and return one-time service token | Existing |
| GET | `/api/v1/admin/gateways/{gateway_id}` | Gateway detail | Existing |
| PATCH | `/api/v1/admin/gateways/{gateway_id}` | Update gateway metadata | Existing |
| POST | `/api/v1/admin/gateways/{gateway_id}/disable` | Disable gateway and remove publisher participants | Existing |
| POST | `/api/v1/admin/gateways/{gateway_id}/enable` | Re-enable disabled gateway | Existing |
| POST | `/api/v1/admin/gateways/{gateway_id}/rotate-credential` | Rotate one-time service token | Existing |
| POST | `/api/v1/admin/gateways/{gateway_id}/cameras` | Grant/revoke gateway-camera assignment | Existing |
| POST | `/api/v1/admin/gateways/{gateway_id}/commands` | Enqueue gateway command | Existing |
| GET | `/api/v1/admin/gateways/{gateway_id}/commands` | List commands | Existing |
| POST | `/api/v1/admin/gateways/{gateway_id}/commands/{command_id}/cancel` | Cancel pending command | Existing |
| POST | `/api/v1/admin/commands/cleanup` | Expire stale pending commands | Existing |
| POST | `/api/v1/admin/jobs/run-maintenance` | Run maintenance job | Existing |
| GET | `/api/v1/admin/cameras` | List cameras with filters/search | Existing |
| POST | `/api/v1/admin/cameras` | Create camera | Existing |
| GET | `/api/v1/admin/cameras/{camera_id}` | Camera detail | Existing |
| PATCH | `/api/v1/admin/cameras/{camera_id}` | Update camera display/source metadata | Existing |
| POST | `/api/v1/admin/cameras/{camera_id}/acl` | Grant/revoke camera ACL | Existing |
| POST | `/api/v1/admin/cameras/{camera_id}/disable` | Retire camera and remove viewer participants | Existing |
| POST | `/api/v1/admin/cameras/{camera_id}/enable` | Re-enable retired camera | Existing |
| GET | `/api/v1/admin/audit` | List scrubbed audit rows | Existing |
| GET | `/api/v1/admin/audit/verify` | Verify audit chain | Existing |
| GET | `/api/v1/admin/audit/export` | Export signed scrubbed audit records | Existing |
| POST | `/api/v1/admin/livekit/fallback` | Switch media plane mode | Existing |
| POST | `/api/v1/admin/dpa/export` | Export DPA artifacts | Existing |
| POST | `/api/v1/admin/sites/{site_id}/signage-attest` | Record signage attestation | Existing |
| POST | `/api/v1/admin/break-glass/open` | Open emergency access window | Existing |
| POST | `/api/v1/admin/break-glass/close` | Close emergency access window | Existing |
| GET | `/api/v1/admin/internal/break-glass-status` | Monitor break-glass state | Existing; unauthenticated monitor route |
| GET | `/api/v1/admin/backups/status` | Backup status | Existing; reports `backup_runs` readiness |
| GET/POST/PATCH | `/api/v1/admin/dsr-requests*` | DSR request workflow tracking | Existing |

## Gateway APIs

| Method | Endpoint | Auth | Purpose | Status |
|---|---|---|---|---|
| POST | `/api/v1/gateways/{gateway_id}/heartbeat` | Gateway identity | Liveness and command fallback | Existing |
| POST | `/api/v1/gateways/{gateway_id}/ingest-token` | Gateway identity | Mint gateway publish token for assigned camera | Existing |
| POST | `/api/v1/gateways/{gateway_id}/cameras/{camera_id}/status` | Gateway identity | Persist gateway-reported camera status | Existing |
| WEBSOCKET | `/api/v1/gateway-control/ws` | Gateway identity | Outbound command channel | Existing |

## External Integrations

| Integration | Purpose | Current status |
|---|---|---|
| Cloudflare Access | Browser/admin identity provider and access layer | Existing for staging; production planned |
| GitHub OAuth through Cloudflare | Final browser/admin IdP | Existing |
| GitHub organization invitations | Admin user onboarding source of truth | Existing |
| Google Workspace | Superseded identity option in older docs | Not current target |
| LiveKit Cloud | WebRTC media SFU and webhook sender | Existing integration; real streams blocked by hardware |
| Neon Postgres | Staging database | Existing |
| Railway | Backend deployment | Existing |
| Cloudflare R2 | Backup storage | Partially Existing |
| Terraform Cloud/R2 module | Provisioning backup bucket | Existing |
| mediamtx | Local RTSP bridge/scaffold | Partially Existing |
| FFmpeg | Synthetic and real publish pipeline support | Partially Existing |

## Missing Or Unclear API Behavior

- The merged frontend uses a hand-written API client; generated OpenAPI/TypeScript client is still not implemented.
- `GET /api/v1/admin/sites` and security report endpoints are still planned/nonexistent and must not appear as required production UI calls.
- Real LiveKit browser subscriber playback is still pending even though viewer token and synthetic publish paths exist.

