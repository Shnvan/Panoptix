# API Reference

This is the current backend and gateway API contract for the implemented FastAPI service. API routes are mounted under `/api/v1` except `/health`.

FastAPI remains the security authority. Browser responses must not expose RTSP URLs, camera credentials, gateway publish tokens, raw Cloudflare JWTs, database URLs, or long-lived auth tokens.

## Shared Rules

- Browser routes require Cloudflare Access/app-session auth, or dev auth only in local development, except the explicit public visitor entry endpoints.
- Admin routes require the `admin` role unless explicitly marked as monitor/internal.
- Gateway HTTP and WebSocket routes require gateway identity.
- Unsafe authenticated browser mutations require CSRF protection.
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

## Public Visitor Entry Routes

The visitor collector pilot uses the narrowly public same-domain `https://panoptix.site/entry` frontend entry view. That page fetches the notice first and posts collection only after the visitor explicitly continues. Production Cloudflare redirects first-time `https://panoptix.site/` requests to `/entry` only when `panoptix_visitor` is absent; returning visitors with that signed cookie go directly to the protected Cloudflare Access flow. A successful Continue collection creates a high-severity backend alert/email to active admins with sanitized metadata only. The protected root itself does not collect visitor browser signals.

Public Access exceptions are limited to `/entry`, `/assets/*`, `/logo.png`, `/api/v1/visitor/notice`, `/api/v1/visitor/collect`, and `/api/v1/visitor/access-requests`. Keep `/`, `/api/v1/me`, `/api/v1/admin/*`, `/api/v1/cameras/*`, and `/api/v1/sessions/*` protected. Never make broad `/api/v1/*` public.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/visitor/notice` | public when collector enabled | current visitor security notice version/text |
| `POST` | `/api/v1/visitor/collect` | public when collector enabled | records approved entry signals after notice acknowledgement and sets signed visitor correlation cookie |
| `POST` | `/api/v1/visitor/access-requests` | public when collector enabled | receives an access request for admin review with a generic non-enumerating response; never creates an account or invite directly |

`POST /api/v1/visitor/collect` accepts the notice version, `notice_acknowledged = true`, entry `page_path`, screen width/height, browser timezone/language, referrer, viewport size, device pixel ratio, touch support, color scheme, cookie support, browser privacy flags, browser language list, network hints, entry timing, and a normalized WebRTC candidate summary. The backend records the trusted request IP, Cloudflare Ray/country headers when present, request user-agent, timestamp, and a stored normalized Ipregistry subset when available. Raw WebRTC SDP/candidate strings, raw Ipregistry payloads, canvas/audio/WebGL/font fingerprints, coordinates, and reverse-geocoded addresses are not stored.

Admin visitor list/detail responses expose the collected data as readable sections: `browser_context`, `network_context`, `webrtc_details`, `timing`, `server_context`, and `risk_context`. `risk_context` includes timezone/IP mismatch, language/country mismatch, WebRTC public-IP/request-IP mismatch, entry-IP/login-IP change, and repeat visitor count. The admin visitor investigation UI remains frontend handoff work.

Visitor access requests collect only minimal applicant identity: name, email, optional organization, reason, and requested role. The public create route returns the same generic `202 received` response for newly accepted and already-pending duplicate requests, and does not expose a request ID. Admin review routes live under `/api/v1/admin/access-requests`; approval uses the existing GitHub organization invite flow and still respects disabled-user denial. Public requests do not grant roles, camera ACLs, Cloudflare access, or application sessions.

## Admin Routes

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/admin/dashboard` | aggregate system counts |
| `GET` | `/api/v1/admin/users` | list users |
| `POST` | `/api/v1/admin/users/{user_id}/role` | grant/revoke role |
| `POST` | `/api/v1/admin/users/{user_id}/disable` | disable user, revoke sessions, remove LiveKit viewer participants |
| `POST` | `/api/v1/admin/users/{user_id}/mfa/reset` | audit admin-mediated MFA reset |
| `POST` | `/api/v1/admin/users/invite` | invite user through configured GitHub organization and assign local roles |
| `GET` | `/api/v1/admin/gateways` | list gateways with filters/search |
| `POST` | `/api/v1/admin/gateways` | register gateway and return one-time service token |
| `GET` | `/api/v1/admin/gateways/{gateway_id}` | gateway detail |
| `PATCH` | `/api/v1/admin/gateways/{gateway_id}` | update gateway display metadata; does not rotate credentials |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/disable` | disable gateway and remove LiveKit publisher participants |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/enable` | re-enable a disabled gateway without restoring revoked assignments |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/rotate-credential` | rotate one-time gateway service token |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/cameras` | grant/revoke gateway-camera assignment |
| `GET` | `/api/v1/admin/gateways/{gateway_id}/discovery-runs` | list sanitized gateway discovery run snapshots |
| `GET` | `/api/v1/admin/gateways/{gateway_id}/discovery-runs/latest` | latest sanitized discovery run snapshot |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/commands` | enqueue gateway command |
| `GET` | `/api/v1/admin/gateways/{gateway_id}/commands` | list gateway commands |
| `POST` | `/api/v1/admin/gateways/{gateway_id}/commands/{command_id}/cancel` | cancel pending command |
| `POST` | `/api/v1/admin/commands/cleanup` | expire stale pending commands |
| `POST` | `/api/v1/admin/jobs/run-maintenance` | run maintenance job once |
| `GET` | `/api/v1/admin/cameras` | list cameras with filters/search |
| `POST` | `/api/v1/admin/cameras` | create camera |
| `GET` | `/api/v1/admin/cameras/{camera_id}` | camera detail |
| `PATCH` | `/api/v1/admin/cameras/{camera_id}` | update camera display/source metadata; no RTSP credentials accepted |
| `POST` | `/api/v1/admin/cameras/{camera_id}/acl` | grant/revoke user camera ACL |
| `POST` | `/api/v1/admin/cameras/{camera_id}/disable` | retire camera and remove LiveKit viewer participants |
| `POST` | `/api/v1/admin/cameras/{camera_id}/enable` | re-enable a retired camera; viewer access still depends on camera ACLs |
| `GET` | `/api/v1/admin/actors/{actor_type}/{actor_id}/profile` | composite actor investigation profile |
| `GET` | `/api/v1/admin/actors/{actor_type}/{actor_id}/activity` | actor-scoped audit activity timeline |
| `GET` | `/api/v1/admin/visitor-visits` | list collected public entry visits |
| `GET` | `/api/v1/admin/visitor-visits/{visit_id}` | collected public entry visit detail; detail view is audited |
| `GET` | `/api/v1/admin/access-requests` | list pending or historical visitor access requests |
| `GET` | `/api/v1/admin/access-requests/{request_id}` | access request detail |
| `POST` | `/api/v1/admin/access-requests/{request_id}/approve` | approve a pending request and send the existing GitHub org invite |
| `POST` | `/api/v1/admin/access-requests/{request_id}/reject` | reject a pending request with an optional admin note |
| `GET` | `/api/v1/admin/audit` | list scrubbed audit rows |
| `GET` | `/api/v1/admin/audit/verify` | verify audit HMAC chain |
| `GET` | `/api/v1/admin/audit/export` | export scrubbed audit JSONL |
| `GET` | `/api/v1/admin/alerts` | list alert records with status/severity/category filters |
| `GET` | `/api/v1/admin/alerts/{alert_id}` | alert detail |
| `POST` | `/api/v1/admin/alerts/{alert_id}/acknowledge` | acknowledge an open alert |
| `POST` | `/api/v1/admin/alerts/{alert_id}/resolve` | resolve an alert |
| `POST` | `/api/v1/admin/livekit/fallback` | switch `media_plane_mode` between `cloud` and `fallback` |
| `POST` | `/api/v1/admin/dpa/export` | export DPA artifacts |
| `POST` | `/api/v1/admin/sites/{site_id}/signage-attest` | record bystander signage attestation |
| `POST` | `/api/v1/admin/break-glass/open` | open emergency access window |
| `POST` | `/api/v1/admin/break-glass/close` | close emergency access window and return rotation checklist |
| `GET` | `/api/v1/admin/internal/break-glass-status` | unauthenticated monitor endpoint |
| `GET` | `/api/v1/admin/backups/status` | database-known backup readiness from `backup_runs` |

Admin camera `source_type` values are exactly: `rtsp`, `nvr_rtsp`, `onvif_profile_s`, `onvif_profile_t`, and `synthetic_rtsp_test_source`.

Admin audit query filters:

- `/api/v1/admin/audit`: `cursor`, `limit`, `action`, `actor_type`, `actor_id`, `severity`, `category`, `outcome`, `resource`, `session_id`, `ts_from`, `ts_to`.
- `/api/v1/admin/actors/{actor_type}/{actor_id}/activity`: `cursor`, `limit`, `action`, `severity`, `category`, `outcome`, `resource`, `session_id`, `ts_from`, `ts_to`.
- Audit timeline cursors are integer audit row IDs; next pages fetch rows with `id < cursor`.

Backup status:

```json
{
  "status": "ok",
  "latest_backup": {
    "id": "uuid",
    "started_at": "2026-05-19T00:00:00+00:00",
    "finished_at": "2026-05-19T00:05:00+00:00",
    "size_bytes": 123456,
    "sha256": "hex-digest",
    "restore_format_ok": true,
    "restore_schema_ok": true,
    "row_count_estimate": 42,
    "upload_status": "uploaded",
    "notes": "operator note"
  },
  "latest_restore_drill": null,
  "checks": {
    "has_backup": true,
    "latest_upload_uploaded": true,
    "latest_backup_finished": true,
    "latest_restore_format_ok": true,
    "restore_drill_recorded": true,
    "latest_restore_schema_ok": true,
    "latest_backup_age_hours": 2.5
  }
}
```

`status` is `missing` when no backup rows exist, `ok` when the latest backup is uploaded/finished with restore-format success and a successful schema restore drill is recorded, and `degraded` otherwise. The endpoint does not call R2 or return object paths, credentials, database URLs, backup artifacts, or decryption material.

Production evidence note, 2026-05-25: production R2 credentials are present, bucket listing succeeds, and the bucket contains one encrypted `.dump.age` backup artifact. Object keys are intentionally withheld from docs and API output. Production `backup_runs` has two diagnostic failures, one successful uploaded/finished backup row `78901812-df12-4a32-b91f-9975772fdca2` with `restore_format_ok=true`, and one isolated restore-drill evidence row `564e2bfd-b449-4c9f-b46d-a0366856a7e0` with `restore_schema_ok=true`. Dry-run restore validation decrypted the artifact locally and `pg_restore --list` succeeded; the isolated restore drill used a temporary Neon branch, which was deleted after validation. Backup status returned `ok` after restore-drill evidence was recorded.

## Alert Routes

Admin-only alert records are available under:

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/admin/alerts` | list alerts; supports `status`, `severity`, `category`, `limit`, and `cursor` |
| `GET` | `/api/v1/admin/alerts/{alert_id}` | view one alert |
| `POST` | `/api/v1/admin/alerts/{alert_id}/acknowledge` | mark an open alert acknowledged and audit the action |
| `POST` | `/api/v1/admin/alerts/{alert_id}/resolve` | mark an alert resolved and audit the action |

Alert severities are `informational`, `low`, `medium`, `high`, and `critical`. Alert statuses are `open`, `acknowledged`, and `resolved`. Alert categories are `security`, `operations`, `compliance`, and `availability`.

The backend currently creates alert records for high-value security and operations events: break-glass opened, invalid/tampered audit verification, admin role grant, gateway disable, rejected gateway command, and backup status `missing`/`degraded`. Duplicate source events are treated idempotently where the source event has a stable ID.

Email notification is backend SMTP only. Production uses Resend with `ALERT_EMAIL_RECIPIENT_MODE=admins`, so alerts at or above `ALERT_EMAIL_MIN_SEVERITY` are sent to active admin users. High-value sources include break-glass, audit-chain failure, admin role grant, gateway disable, degraded backup status, `/entry` Continue collection, CSRF denial, disabled-user login attempts, invalid gateway credentials, gateway signing failures, unauthenticated gateway control attempts, LiveKit config fail-closed events, and alert email delivery failures. Non-production environments can use `static`, `admins`, or `both`; static recipients come from `ALERT_EMAIL_TO`. Alert API responses, notification records, audit payloads, and email bodies must not include SMTP passwords, gateway tokens, LiveKit secrets, raw provider responses, database URLs, cookies, headers, or RTSP credentials.

Alert response shape:

```json
{
  "alert_id": "uuid",
  "severity": "critical",
  "category": "security",
  "title": "Break-glass access opened",
  "message": "Emergency access was opened by an administrator.",
  "status": "open",
  "source": "system.break_glass.opened",
  "source_event_id": "audit-log-id",
  "resource": "break-glass",
  "actor_type": "user",
  "actor_id": "uuid",
  "metadata": {
    "reason": "sanitized reason"
  },
  "created_at": "2026-05-21T00:00:00+00:00",
  "acknowledged_at": null,
  "acknowledged_by": null,
  "resolved_at": null,
  "resolved_by": null
}
```

## DSR Workflow Routes

Admin-only Data Subject Request tracking is available under:

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/admin/dsr-requests` | list DSR cases; supports `status` and `limit` |
| `POST` | `/api/v1/admin/dsr-requests` | create a DSR case |
| `GET` | `/api/v1/admin/dsr-requests/{request_id}` | view one DSR case and audit the access |
| `PATCH` | `/api/v1/admin/dsr-requests/{request_id}` | update DSR lifecycle fields |

Supported `subject_type` values are `user`, `bystander`, and `site_contact`. Supported `request_type` values are `access`, `correction`, `deletion`, `objection`, `restriction`, and `other`. Supported `status` values are `open`, `verified`, `in_progress`, `completed`, `rejected`, and `cancelled`.

Create request:

```json
{
  "requester_contact": "person@example.com",
  "subject_type": "user",
  "request_type": "access",
  "site_id": "uuid-or-null",
  "camera_scope_note": "optional scope note",
  "due_at": "2026-06-19T00:00:00+00:00",
  "status": "open",
  "artifact_id": "uuid-or-null"
}
```

The API records `admin.dsr.created`, `admin.dsr.viewed`, and `admin.dsr.updated` audit events. It tracks the case lifecycle only; it does not automatically search, export, redact, or delete footage.

## Gateway Routes

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/gateways/{gateway_id}/heartbeat` | heartbeat plus pending command fallback |
| `POST` | `/api/v1/gateways/{gateway_id}/cameras/{camera_id}/status` | persist gateway-reported camera status |
| `POST` | `/api/v1/gateways/{gateway_id}/discovery-runs` | persist sanitized camera LAN/VLAN discovery report |
| `POST` | `/api/v1/gateways/{gateway_id}/ingest-token` | LiveKit gateway publish token |
| `WEBSOCKET` | `/api/v1/gateway-control/ws` | outbound gateway control channel |

Gateway discovery reports are gateway-authenticated and require the route gateway ID to match the authenticated gateway identity. The backend stores approved CIDRs, probed ports, run status, counts, timestamps, agent version, and sanitized findings only. Findings contain IP, optional hostname/hostnames, optional MAC address, optional MAC vendor/OUI label, open TCP ports, observed protocol labels, evidence labels, `possible_camera`/`possible_nvr`/`unknown_device`, device hint, and confidence. Current device hints are `ip_camera`, `nvr`, `router`, `switch_possible`, `printer`, `client_device_possible`, and `unknown_network_device`. Reports must not contain credentials, RTSP auth attempts, raw banners, full HTTP response bodies, packets, screenshots, public internet scan targets, or decrypted secrets.

Discovery enrichment is best-effort and gateway-local. ARP/MAC vendor lookup, mDNS/Bonjour, SSDP/UPnP, and safe HTTP/HTTPS title-category hints can improve the admin display, but they do not prove device identity. SNMP is not enabled by default and requires a separate customer-approved credentialed discovery milestone.

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

Actor investigation profile:

```json
{
  "actor_type": "user",
  "actor_id": "uuid",
  "identity": {},
  "roles": ["viewer"],
  "sessions": {},
  "camera_access": {},
  "stream_grants": {},
  "activity_summary": {},
  "risk_indicators": {},
  "containment_status": {},
  "ip_details": {
    "available": true,
    "status": "ok",
    "provider": "ipregistry",
    "distinct_ip_count": 1,
    "enriched_ip_count": 1,
    "recent_sessions": [
      {
        "session_id": "uuid",
        "created_at": "2026-05-22T03:30:00Z",
        "last_seen_at": "2026-05-22T03:35:00Z",
        "revoked_at": null,
        "ip": "203.0.113.10",
        "ip_type": "IPv4",
        "location": {
          "continent": "Asia",
          "country_code": "PH",
          "country": "Philippines",
          "region": "Calabarzon",
          "city": "Santa Rosa",
          "timezone": "Asia/Manila"
        },
        "network": {
          "asn": 64500,
          "organization": "Example Network",
          "domain": "network.example",
          "connection_type": "isp"
        },
        "company": {
          "name": "Example ISP",
          "domain": "network.example",
          "type": "isp"
        },
        "carrier": {
          "name": null
        },
        "security": {
          "is_anonymous": false,
          "is_vpn": false,
          "is_proxy": false,
          "is_tor": false,
          "is_tor_exit": false,
          "is_cloud_provider": false,
          "is_relay": false,
          "is_threat": false,
          "is_attacker": false,
          "is_abuser": false
        }
      }
    ]
  },
  "device_details": {
    "available": true,
    "distinct_user_agent_count": 1,
    "recent_sessions": [
      {
        "session_id": "uuid",
        "created_at": "2026-05-22T03:30:00Z",
        "last_seen_at": "2026-05-22T03:35:00Z",
        "revoked_at": null,
        "ua_fp": "browser",
        "browser": { "family": "Chrome", "version": "148.0.0.0" },
        "os": { "family": "Windows", "version": "10" },
        "device": {
          "family": null,
          "brand": null,
          "model": null,
          "device_class": "desktop"
        }
      }
    ]
  },
  "mfa_details": null,
  "threat_intelligence": null,
  "alerts": {
    "total_count": 2,
    "counts_by_status": {
      "open": 1,
      "acknowledged": 1,
      "resolved": 0
    },
    "counts_by_severity": {
      "informational": 0,
      "low": 0,
      "medium": 1,
      "high": 1,
      "critical": 0
    },
    "recent": []
  },
  "incidents": null,
  "analyst_notes": null,
  "behavior_baseline": {
    "available": true,
    "login_count": 12,
    "last_login_at": "2026-05-22T03:30:00Z",
    "last_login_country": "PH",
    "known_ip_count": 2,
    "known_country_count": 1,
    "known_user_agent_count": 2,
    "updated_at": "2026-05-22T03:30:00Z"
  }
}
```

Actor investigation activity:

```json
{
  "items": [
    {
      "id": 123,
      "ts": "2026-05-14T04:00:00Z",
      "actor_id": "uuid",
      "actor_type": "user",
      "action": "viewer.token.issued",
      "resource": "camera:uuid",
      "payload": {},
      "ip": "203.0.113.10",
      "ua": "browser",
      "event_severity": "low",
      "event_outcome": "success",
      "event_category": "authentication",
      "session_id": "uuid"
    }
  ],
  "next_cursor": null
}
```

Actor notes:

- `actor_type` supports `user`, `gateway`, `system`, `break_glass`, and `service_token_monitor`.
- `user` and `gateway` require UUID actor IDs and existing backing rows.
- System-like actors may use `none` as the path actor ID to inspect audit rows where `actor_id` is null.
- Profile `alerts` summarize only alerts directly linked by matching stored `actor_type` and `actor_id`; the recent list uses the alert response shape and is capped at 10 rows.
- User actor profiles summarize stored login-baseline counts in `behavior_baseline` without returning raw known IP, country, or user-agent lists. Profiles without a baseline return `available: false`. Non-user actor profiles keep `behavior_baseline: null`.
- User actor profiles expose bounded `ip_details` and `device_details` from the latest 10 stored sessions. `device_details` parses stored session user agents. `ip_details` uses optional Ipregistry backend lookups and returns `status` of `ok`, `not_configured`, or `unavailable` without failing the profile read.
- Gateway and system-like actor profiles keep `ip_details: null` and `device_details: null`.
- Profile and activity reads write `admin.actor.profile.viewed` and `admin.actor.activity.viewed` audit events.

Visitor visit admin responses expose collected time/page, the approved IP enrichment subset, parsed browser/OS/device summary, screen/timezone/language observations, and whether the signed entry visit later linked to an authenticated Panoptix user/session. Anonymous visitor rows are retained by maintenance for configured `VISITOR_RETENTION_DAYS`, default 30 days.

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

## Admin operations assistant

All assistant endpoints require an authenticated user with the `admin` role. The feature is disabled by default.

Production deep health also reports only the non-secret feature state as
`"assistant": "disabled"` or `"assistant": "enabled"`. Production monitoring
requires `disabled` until the provider privacy review is approved.

`GET /api/v1/admin/assistant/status`

```json
{
  "enabled": false,
  "provider": "openai-compatible",
  "model": "llama-3.3-70b-versatile",
  "max_history_messages": 20,
  "page_session_limit": 50
}
```

`POST /api/v1/admin/assistant/chat`

```json
{
  "messages": [
    {"role": "user", "content": "Summarize current system health."}
  ]
}
```

```json
{
  "message": "Current sanitized health summary...",
  "model": "llama-3.3-70b-versatile",
  "context_categories": ["health", "gateways", "cameras", "alerts", "backups"]
}
```

Messages must alternate starting with `user` and end with `user`. Limits are 20 messages, 2,000 characters per message, and 12,000 characters for the conversation. `429` responses include `Retry-After`. Provider failures use sanitized problem details such as `assistant-provider-timeout`, `assistant-provider-rate-limited`, or `assistant-provider-unavailable`.

## Deferred or Not Implemented

- Frontend-generated OpenAPI/TypeScript client.
- Dynamic CSP middleware driven by `media_plane_mode`.
- Browser bundle scan and frontend API type generation.
