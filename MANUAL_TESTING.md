# Panoptix Manual Testing Guide

This guide helps you manually exercise the Panoptix backend API, the minimal gateway heartbeat agent, and the verification commands implemented so far.

## 1. Assumptions

- You are running commands on Windows PowerShell.
- Your repository root is:

```powershell
C:\Users\Ivan\Downloads\panoptix-main\Panoptix
```

- API examples assume the backend runs at:

```text
http://127.0.0.1:8000
```

- Development auth examples require:

```powershell
$env:APP_ENV = "development"
$env:ALLOW_DEV_AUTH = "true"
$env:AUDIT_HMAC_KEY_VERSION = "1"
$env:AUDIT_HMAC_KEY = "local-dev-audit-hmac-key-change-me"
```

- Token success paths need real or test database rows for users, cameras, ACLs, gateways, and assignments.
- LiveKit token success paths need non-placeholder LiveKit settings.
- Audit-producing success paths need a non-placeholder `AUDIT_HMAC_KEY`; audit writes fail closed when it is missing or left as `replace-me`.
- Non-dev browser unsafe requests require a CSRF header matching the `panoptix_csrf` cookie; local development auth remains exempt.

## 2. Start The API Locally

From the API app directory:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
$env:APP_ENV = "development"
$env:ALLOW_DEV_AUTH = "true"
$env:AUDIT_HMAC_KEY_VERSION = "1"
$env:AUDIT_HMAC_KEY = "local-dev-audit-hmac-key-change-me"
python -m uvicorn cctv_api.main:app --reload --host 127.0.0.1 --port 8000
```

Open docs in the browser:

```text
http://127.0.0.1:8000/docs
```

## 3. Common Test Variables

Open a second PowerShell terminal and set:

```powershell
$BaseUrl = "http://127.0.0.1:8000"
$GatewayId = "11111111-1111-1111-1111-111111111111"
$CameraId = "22222222-2222-2222-2222-222222222222"
$SessionId = "33333333-3333-3333-3333-333333333333"
```

Development browser/user auth headers:

```powershell
$UserHeaders = @{
  "x-panoptix-dev-auth" = "1"
  "x-panoptix-dev-subject" = "dev-user-1"
  "x-panoptix-dev-email" = "dev@example.test"
  "x-panoptix-dev-roles" = "viewer"
}
```

Development admin auth headers:

```powershell
$AdminHeaders = @{
  "x-panoptix-dev-auth" = "1"
  "x-panoptix-dev-subject" = "dev-admin-1"
  "x-panoptix-dev-email" = "admin@example.test"
  "x-panoptix-dev-roles" = "admin"
}
```

Security headers should be present on API success and problem-detail responses:

```powershell
Invoke-WebRequest -Uri "$BaseUrl/api/v1/me" -Headers $UserHeaders | Select-Object -ExpandProperty Headers
```

For non-dev browser session testing, first call a safe authenticated `GET` to receive `panoptix_session` and `panoptix_csrf`, then send the CSRF cookie value as `x-panoptix-csrf-token` on unsafe browser/admin requests.

Development gateway auth headers:

```powershell
$GatewayHeaders = @{
  "x-panoptix-dev-gateway-id" = $GatewayId
}
```

For `curl.exe`, use headers inline:

```powershell
-H "x-panoptix-dev-auth: 1"
-H "x-panoptix-dev-email: dev@example.test"
-H "x-panoptix-dev-gateway-id: $GatewayId"
```

## 4. Public Health Checks

### Basic health

```powershell
curl.exe -s "$BaseUrl/health"
```

Expected response:

```json
{"status":"ok"}
```

### Deep health placeholder

```powershell
curl.exe -s "$BaseUrl/api/v1/admin/health/deep"
```

Expected response for the current placeholder:

```json
{"status":"ok","db":"not_connected","livekit":"not_connected","gateway":"not_connected"}
```

## 5. Browser/User API Endpoints

These endpoints require browser/user identity. In development mode, use `x-panoptix-dev-auth: 1`.

### Current user

PowerShell:

```powershell
Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/v1/me" -Headers $UserHeaders
```

curl:

```powershell
curl.exe -s "$BaseUrl/api/v1/me" `
  -H "x-panoptix-dev-auth: 1" `
  -H "x-panoptix-dev-email: dev@example.test" `
  -H "x-panoptix-dev-roles: viewer"
```

Expected response shape:

```json
{
  "kind": "user",
  "subject": "dev-user-1",
  "email": "dev@example.test",
  "roles": ["viewer"],
  "permissions": [],
  "is_dev": true
}
```

### Cameras list placeholder

```powershell
Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/v1/cameras" -Headers $UserHeaders
```

Expected response:

```json
{"items":[],"next_cursor":null}
```

### Active sessions

```powershell
Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/v1/sessions/active" -Headers $UserHeaders
```

Notes:

- With dev auth, the endpoint creates or finds a dev user by email/subject.
- Response depends on the configured database.

Expected response shape:

```json
{
  "items": []
}
```

### Revoke session

```powershell
$Body = @{ session_id = "00000000-0000-0000-0000-000000000000" } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri "$BaseUrl/api/v1/sessions/revoke" -Headers $UserHeaders -ContentType "application/json" -Body $Body
```

Notes:

- A non-admin user can only revoke their own active sessions.
- If the session is not owned by the user, expect `403` with `session-not-owned`.
- Successful or not-found revoke paths write audit events.

Expected response shape for an allowed request:

```json
{
  "revoked": true,
  "session_id": "33333333-3333-3333-3333-333333333333"
}
```

### Privacy notice

Fetch the current operator privacy notice:

```powershell
Invoke-RestMethod -Method GET `
  -Uri "$BaseUrl/api/v1/privacy/notice" `
  -Headers $UserHeaders
```

Expected response includes:

```json
{
  "notice_version": "2026-05-10",
  "title": "Panoptix CCTV Operator Privacy Notice",
  "accepted": false,
  "accepted_at": null
}
```

Accept the current notice:

```powershell
$NoticeBody = @{ notice_version = "2026-05-10" } | ConvertTo-Json
Invoke-RestMethod -Method POST `
  -Uri "$BaseUrl/api/v1/privacy/notice/accept" `
  -Headers $UserHeaders `
  -ContentType "application/json" `
  -Body $NoticeBody
```

Expected behavior:

- Response has `status = accepted`.
- A `privacy_notice_acceptances` row exists for the user/version.
- Audit contains `privacy.notice.accepted`.
- Repeating the same accept call is idempotent and does not create duplicate rows.
- Wrong versions return `409 privacy-notice-version-mismatch`.

### Admin users

List users as admin:

```powershell
Invoke-RestMethod -Method GET `
  -Uri "$BaseUrl/api/v1/admin/users?limit=50" `
  -Headers $AdminHeaders
```

Expected response:

```json
{
  "items": [
    {
      "user_id": "uuid",
      "email": "admin@example.test",
      "roles": ["admin"],
      "role_default": "none",
      "disabled_at": null,
      "created_at": "..."
    }
  ],
  "next_cursor": null
}
```

Notes:

- Viewer/non-admin callers receive `403 role-required`.
- Exact email filtering is available with `?email=user@example.test`.
- The response intentionally excludes `idp_subject`, session rows, CF JWTs, tokens, and secrets.

Disable a user as admin:

```powershell
$UserId = "00000000-0000-0000-0000-000000000000"
$DisableBody = @{ reason = "manual disable test" } | ConvertTo-Json
Invoke-RestMethod -Method POST `
  -Uri "$BaseUrl/api/v1/admin/users/$UserId/disable" `
  -Headers $AdminHeaders `
  -ContentType "application/json" `
  -Body $DisableBody
```

Expected response shape:

```json
{
  "user_id": "uuid",
  "disabled_at": "...",
  "sessions_revoked": 0,
  "participants_removed": 0,
  "participant_errors": []
}
```

Notes:

- Admin disable revokes all active sessions for the target user.
- The backend attempts LiveKit viewer participant removal for active camera ACL rooms.
- Placeholder LiveKit credentials skip participant removal and return `livekit-credentials-placeholder`.
- LiveKit removal errors are returned and audited but do not block the disable.
- Raw LiveKit admin JWTs and API secrets must never appear in responses or audit payloads.

## 6. Viewer LiveKit Token Endpoint

Endpoint:

```text
GET /api/v1/cameras/{camera_id}/view-token
```

Manual command:

```powershell
Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/v1/cameras/$CameraId/view-token" -Headers $UserHeaders
```

Success requires:

- `ALLOW_DEV_AUTH=true`
- active user row matching the dev auth identity
- active camera row for `$CameraId`
- active `camera_acl` row for user + camera
- non-placeholder LiveKit settings

Without DB authorization rows, expect one of:

```text
camera-not-found
camera-access-denied
livekit-token-config-invalid
```

Expected success response shape:

```json
{
  "camera_id": "22222222-2222-2222-2222-222222222222",
  "room": "camera_test_room",
  "livekit_url": "wss://...",
  "token": "...jwt...",
  "expires_at": "..."
}
```

Audit notes:

- Success writes `viewer.token.issued`.
- Denial paths write `viewer.token.denied.*`.
- Raw tokens are not stored in audit payloads.

## 7. Gateway API Endpoints

These endpoints require gateway identity. In development mode, use `x-panoptix-dev-gateway-id`.

### Gateway heartbeat

PowerShell:

```powershell
$HeartbeatBody = @{
  status = "online"
  agent_version = "manual-test"
  cameras = @(
    @{
      camera_id = $CameraId
      status = "online"
      detail = "manual heartbeat test"
    }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method POST -Uri "$BaseUrl/api/v1/gateways/$GatewayId/heartbeat" -Headers $GatewayHeaders -ContentType "application/json" -Body $HeartbeatBody
```

curl:

```powershell
curl.exe -s -X POST "$BaseUrl/api/v1/gateways/$GatewayId/heartbeat" `
  -H "Content-Type: application/json" `
  -H "x-panoptix-dev-gateway-id: $GatewayId" `
  -d "{\"status\":\"online\",\"agent_version\":\"manual-test\",\"cameras\":[]}"
```

Expected response shape:

```json
{
  "server_time": "...",
  "pending_commands": []
}
```

Current fallback behavior:

- by default, `pending_commands` remains empty
- local test scaffolding can attach an in-memory command provider to return signed pending commands
- signing failures fail closed instead of returning unsigned commands
- no public enqueue API exists yet
- no pending command is executed by the edge agent yet

### Gateway ID mismatch test

```powershell
curl.exe -s -X POST "$BaseUrl/api/v1/gateways/99999999-9999-9999-9999-999999999999/heartbeat" `
  -H "Content-Type: application/json" `
  -H "x-panoptix-dev-gateway-id: $GatewayId" `
  -d "{\"status\":\"online\",\"agent_version\":\"manual-test\",\"cameras\":[]}"
```

Expected result:

```text
403 gateway-id-mismatch
```

### Gateway camera status

```powershell
$StatusBody = @{
  status = "online"
  detail = "manual status test"
} | ConvertTo-Json

Invoke-RestMethod -Method POST -Uri "$BaseUrl/api/v1/gateways/$GatewayId/cameras/$CameraId/status" -Headers $GatewayHeaders -ContentType "application/json" -Body $StatusBody
```

Expected response:

```json
{"accepted":true}
```

### Gateway ingest token

Endpoint:

```text
POST /api/v1/gateways/{gateway_id}/ingest-token
```

Manual command:

```powershell
$IngestBody = @{ camera_id = $CameraId } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri "$BaseUrl/api/v1/gateways/$GatewayId/ingest-token" -Headers $GatewayHeaders -ContentType "application/json" -Body $IngestBody
```

Success requires:

- `$GatewayId` is a UUID
- `$CameraId` is a UUID
- enabled `edge_gateways` row for `$GatewayId`
- active `cameras` row for `$CameraId`
- active `gateway_camera_assignments` row for gateway + camera
- non-placeholder LiveKit settings

Without those rows/settings, expect one of:

```text
gateway-disabled-or-not-found
camera-not-found
gateway-camera-assignment-denied
livekit-token-config-invalid
```

Expected success response shape:

```json
{
  "camera_id": "22222222-2222-2222-2222-222222222222",
  "room": "camera_test_room",
  "livekit_url": "wss://...",
  "token": "...jwt...",
  "expires_at": "..."
}
```

Audit notes:

- Success writes `gateway.ingest.token.issued`.
- Denial paths write `gateway.ingest.denied.*`.
- Raw tokens are not stored in audit payloads.

### Gateway control WebSocket

Current endpoint:

```text
GET /api/v1/gateway-control/ws
```

This is a real WebSocket endpoint. Valid gateway identities are accepted and receive a connected message. Missing gateway identity and browser/user dev auth are rejected with WebSocket close code `1008`.

Manual Python check from `apps/api`:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$WsCheck = @'
import asyncio
import json
import websockets

async def main():
    async with websockets.connect(
        "ws://127.0.0.1:8000/api/v1/gateway-control/ws",
        additional_headers={"x-panoptix-dev-gateway-id": "11111111-1111-1111-1111-111111111111"},
    ) as ws:
        print(json.dumps(json.loads(await ws.recv()), indent=2))

asyncio.run(main())
'@
python -c $WsCheck
```

Expected response:

```json
{
  "type": "connected",
  "gateway_id": "11111111-1111-1111-1111-111111111111"
}
```

This endpoint does not send real camera/media commands yet. Persistent command queues and full production reconnect behavior remain future work.
By default, a manually started backend still sends only this hello message unless local test code attaches an in-memory command provider hook.

Edge-agent one-shot gateway control check from `apps/cctv-edge/agent`:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
$env:PANOPTIX_API_BASE_URL = "http://127.0.0.1:8000"
$env:PANOPTIX_GATEWAY_ID = "11111111-1111-1111-1111-111111111111"
$env:PANOPTIX_DEV_GATEWAY_IDENTITY = "true"
$env:PANOPTIX_GATEWAY_COMMAND_SIGNING_KEY = "local-dev-command-signing-key-change-me"
python -m panoptix_edge_agent.cli --control-once
```

Expected output:

```text
gateway control accepted
```

Edge-agent bounded gateway control reconnect check from `apps/cctv-edge/agent`:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
$env:PANOPTIX_API_BASE_URL = "http://127.0.0.1:8000"
$env:PANOPTIX_GATEWAY_ID = "11111111-1111-1111-1111-111111111111"
$env:PANOPTIX_DEV_GATEWAY_IDENTITY = "true"
$env:PANOPTIX_GATEWAY_COMMAND_SIGNING_KEY = "local-dev-command-signing-key-change-me"
$env:PANOPTIX_GATEWAY_CONTROL_RECONNECT_ATTEMPTS = "3"
$env:PANOPTIX_GATEWAY_CONTROL_RECONNECT_BACKOFF_SECONDS = "1.0"
python -m panoptix_edge_agent.cli --control-loop-once
```

Expected output when the API is available:

```text
gateway control reconnect accepted after 1 attempt(s)
```

Expected failure when the API is unavailable after all attempts:

```text
gateway control reconnect failed: gateway control websocket failed: ...
```

Current behavior:

- the agent connects outbound to `/api/v1/gateway-control/ws`
- the backend sends the connected hello message
- the agent verifies that the hello message targets its configured gateway ID
- command envelope parsing and signature verification exist in the agent
- if the backend sends a test-scaffolded signed command, the agent sends a `command_ack` with `status: accepted`
- if the backend sends an invalid, unsigned, tampered, expired, or wrong-gateway command, the agent sends a `command_ack` with `status: rejected` and an error code
- `--control-loop-once` retries temporary connection/run failures using the configured bounded attempts and backoff
- malformed control messages still fail closed and are not retried
- no public command enqueue API exists yet
- no real commands are executed yet

The dispatch and ACK loop is intentionally in-memory/test-scaffolded. Use the automated tests to exercise it locally:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_gateway.py -v

Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/test_control.py -v
```

Expected ACK shape:

```json
{
  "type": "command_ack",
  "command_id": "11111111-1111-1111-1111-111111111111",
  "gateway_id": "11111111-1111-1111-1111-111111111111",
  "status": "accepted"
}
```

Rejected ACKs use:

```json
{
  "type": "command_ack",
  "command_id": "11111111-1111-1111-1111-111111111111",
  "gateway_id": "11111111-1111-1111-1111-111111111111",
  "status": "rejected",
  "error": "gateway-command-signature-invalid"
}
```

## 8. Minimal Edge Heartbeat Agent

From the edge agent directory:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
$env:PANOPTIX_API_BASE_URL = "http://127.0.0.1:8000"
$env:PANOPTIX_GATEWAY_ID = "11111111-1111-1111-1111-111111111111"
$env:PANOPTIX_DEV_GATEWAY_IDENTITY = "true"
$env:PANOPTIX_CAMERA_IDS = "22222222-2222-2222-2222-222222222222"
python -m panoptix_edge_agent.cli --once
```

Expected output:

```text
heartbeat accepted
```

Run continuously:

```powershell
python -m panoptix_edge_agent.cli
```

Stop with `Ctrl+C`.

Expected failure if API is not running:

```text
heartbeat failed: gateway request failed: ...
```

Expected failure if required config is missing:

```text
configuration error: PANOPTIX_API_BASE_URL is required
```

## 9. Optional Seed Data For Token Success Paths

Use this section only against a local development database.

Example UUIDs used by earlier commands:

```text
Gateway: 11111111-1111-1111-1111-111111111111
Camera:  22222222-2222-2222-2222-222222222222
User:    created by dev auth when `/api/v1/me` or session endpoints run
```

Token success paths require real rows. The exact insert commands depend on your current migration state and database credentials, but the needed tables are:

```text
users
edge_gateways
cameras
camera_acl
gateway_camera_assignments
```

Recommended safer flow:

1. Run `/api/v1/me` with dev auth to ensure the user exists.
2. Insert an enabled gateway row for `$GatewayId`.
3. Insert an active camera row for `$CameraId` with a unique `livekit_room_name`.
4. Insert active ACL and assignment rows.
5. Set non-placeholder LiveKit env vars before starting the API.

Required LiveKit env vars for cloud mode:

```powershell
$env:LIVEKIT_CLOUD_URL = "wss://your-livekit-host"
$env:LIVEKIT_CLOUD_API_KEY = "your-api-key"
$env:LIVEKIT_CLOUD_API_SECRET = "your-api-secret-with-enough-entropy"
```

Do not commit real LiveKit secrets.

## 24. LiveKit Webhook Receiver

The `POST /api/v1/webhooks/livekit` endpoint accepts signed LiveKit webhook events, stores a replay-cache entry, writes an audit row, and creates `camera_events` rows for status-relevant room events.

### Local signed webhook example

Set non-placeholder LiveKit and audit settings before starting the API:

```powershell
$env:LIVEKIT_CLOUD_URL = "wss://livekit.example.test"
$env:LIVEKIT_CLOUD_API_KEY = "local-livekit-key"
$env:LIVEKIT_CLOUD_API_SECRET = "local-livekit-secret-with-at-least-32-bytes"
$env:AUDIT_HMAC_KEY_VERSION = "1"
$env:AUDIT_HMAC_KEY = "local-dev-audit-hmac-key-change-me"
```

Generate a signed body and Authorization JWT from `apps/api`:

```powershell
$Webhook = @'
import base64
import hashlib
import json
import jwt
from datetime import datetime, timedelta, timezone

body = json.dumps({
    "id": "11111111-1111-1111-1111-111111111111",
    "event": "track_published",
    "createdAt": int(datetime.now(timezone.utc).timestamp()),
    "room": {"name": "room-front-gate"},
    "participant": {"identity": "gateway:local"},
    "track": {"sid": "TR_local"},
}, separators=(",", ":"), sort_keys=True)

now = datetime.now(timezone.utc)
token = jwt.encode({
    "iss": "local-livekit-key",
    "nbf": int(now.timestamp()) - 1,
    "iat": int(now.timestamp()),
    "exp": int((now + timedelta(minutes=5)).timestamp()),
    "sha256": base64.b64encode(hashlib.sha256(body.encode()).digest()).decode("ascii"),
}, "local-livekit-secret-with-at-least-32-bytes", algorithm="HS256")

print(token)
print(body)
'@
$Signed = python -c $Webhook
$LiveKitAuth = $Signed[0]
$LiveKitBody = $Signed[1]
curl.exe -s -X POST "$BaseUrl/api/v1/webhooks/livekit" `
  -H "Content-Type: application/webhook+json" `
  -H "Authorization: Bearer $LiveKitAuth" `
  -d $LiveKitBody
```

Expected response:

```json
{"accepted":true,"event_id":"11111111-1111-1111-1111-111111111111"}
```

### Notes

- LiveKit webhook auth uses the current LiveKit Authorization JWT format: HS256 JWT signed by the active LiveKit API secret, issuer equal to the active API key, and a `sha256` claim over the raw body.
- The webhook `createdAt` UNIX timestamp must be within 60 seconds of server time.
- Duplicate webhook JWT signatures are rejected via `webhook_replay_cache`.
- `track_published` creates an `online` event, `track_unpublished` and `room_finished` create `offline`, and `participant_connection_aborted` creates `degraded`.
- Room events are mapped by `room.name == cameras.livekit_room_name`; unknown rooms are accepted but do not create camera events.
- Created events use `source = livekit_webhook` and are visible through `GET /api/v1/cameras/events` for viewers with active camera ACLs.
- Browser preflight is not enabled; this endpoint is server-to-server only.

### Room-presence publish command checks

`participant_joined` for a known camera room with an enabled gateway assignment queues a `gateway.command.start_publish` command. The command payload includes `camera_id`, `room`, `livekit_url`, `gateway_publish_token`, and `token_expires_at`.

Use the same signing helper above, changing the body to:

```json
{
  "id": "11111111-1111-1111-1111-111111111111",
  "event": "participant_joined",
  "createdAt": 1760000000,
  "room": {"name": "room-front-gate"},
  "participant": {"identity": "viewer:test"}
}
```

After posting the webhook, confirm a pending start command exists:

```powershell
Invoke-RestMethod -Method GET `
  -Uri "$BaseUrl/api/v1/admin/gateways/$GatewayId/commands?status=pending" `
  -Headers $AdminHeaders
```

Expected command item:

```json
{
  "kind": "gateway.command.start_publish",
  "payload": {
    "camera_id": "22222222-2222-2222-2222-222222222222",
    "room": "room-front-gate",
    "livekit_url": "wss://livekit.example.test",
    "gateway_publish_token": "...",
    "token_expires_at": "..."
  }
}
```

`participant_left` with `participant_count: 0` schedules a stop after the 10-second grace window instead of immediately queueing `gateway.command.stop_publish`:

```json
{
  "event": "participant_left",
  "createdAt": 1760000000,
  "participant_count": 0,
  "room": {"name": "room-front-gate"}
}
```

Expected behavior:

- No new stop command appears immediately.
- A `camera_publish_states` row is set to `status = stop_pending`.
- `stop_due_at` is approximately 10 seconds after the webhook event time.
- Audit contains `livekit.publish.stop_scheduled`.

If another `participant_joined` arrives before `stop_due_at`, the pending stop is cancelled:

- No duplicate start command is enqueued.
- Publish state returns to `publishing`.
- Audit contains `livekit.publish.stop_cancelled`.

When a deterministic scheduler/cron calls `enqueue_due_publish_stops()` after `stop_due_at`, the backend enqueues `gateway.command.stop_publish` and resets the publish state to `idle`. Production scheduler wiring is still a separate milestone.

`room_finished` still queues `gateway.command.stop_publish` immediately and resets publish state to `idle`.

The gateway heartbeat fallback returns pending commands as signed envelopes:

```powershell
$HeartbeatBody = @{ status = "online"; agent_version = "manual-test"; cameras = @() } | ConvertTo-Json
Invoke-RestMethod -Method POST `
  -Uri "$BaseUrl/api/v1/gateways/$GatewayId/heartbeat" `
  -Headers $GatewayHeaders `
  -ContentType "application/json" `
  -Body $HeartbeatBody
```

Notes:

- `participant_left` with `participant_count > 0` does not schedule or enqueue a stop command.
- Missing/non-numeric `participant_count` on `participant_left` is treated as "do not stop".
- Unknown rooms are accepted/audited but do not enqueue commands.
- Known rooms without an enabled active gateway assignment are accepted and audit `livekit.publish.command_skipped`.
- Backend stop grace is deterministic and tested, but production scheduler/cron wiring remains deferred.
- Edge-agent mediamtx execution remains deferred.

### Run LiveKit webhook tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_livekit_webhooks.py -v
```

## 10. Audit Log Manual Checks

The first audit admin endpoint is implemented:

```text
GET /api/v1/admin/audit/verify
```

It verifies the full audit HMAC chain by default, or an inclusive audit ID range when `start_id` and/or `end_id` are provided. It does not list rows, export data, rotate keys, or write a new audit event.

Local audit HMAC settings:

```powershell
$env:AUDIT_HMAC_KEY_VERSION = "1"
$env:AUDIT_HMAC_KEY = "local-dev-audit-hmac-key-change-me"
```

Do not use the placeholder `replace-me` for local audit-producing success paths. The audit writer fails closed if the key is blank or left as the placeholder.

Manual verification call:

```powershell
Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/v1/admin/audit/verify" -Headers $AdminHeaders
```

Manual range verification call:

```powershell
Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/v1/admin/audit/verify?start_id=10&end_id=20" -Headers $AdminHeaders
```

Expected response shape:

```json
{
  "valid": true,
  "checked": 0,
  "error": null
}
```

Notes:

- `checked` is the number of audit rows verified in ID order.
- `start_id` and `end_id` are optional inclusive audit log IDs; omitted bounds are open-ended.
- When `start_id` is present, the verifier checks continuity against the latest row before `start_id`.
- Each row is verified with its stored `hmac_key_version` using local `audit_hmac_keys.key_enc`.
- Tampering returns `200` with `valid: false` and an error such as `audit-chain-hash-mismatch`.
- Missing stored key versions return `200` with `valid: false` and `audit-chain-key-missing`.
- Invalid stored keys return `200` with `valid: false` and `audit-chain-key-invalid`.
- Missing or placeholder `AUDIT_HMAC_KEY` returns `503 audit-hmac-key-invalid`.
- Non-admin users receive `403 role-required`.

Audit-producing paths implemented so far:

```text
viewer.token.issued
viewer.token.denied.user_disabled
viewer.token.denied.camera_not_found
viewer.token.denied.access
viewer.token.denied.livekit_config
gateway.ingest.token.issued
gateway.ingest.denied.gateway_mismatch
gateway.ingest.denied.disabled
gateway.ingest.denied.camera_not_found
gateway.ingest.denied.unassigned
gateway.ingest.denied.livekit_config
session.revoke.succeeded
session.revoke.not_found
session.revoke.denied.not_owned
command.enqueue
command.cancel
commands.cleanup
livekit.webhook.received
livekit.webhook.replay_rejected
livekit.publish.start_enqueued
livekit.publish.stop_enqueued
livekit.publish.command_skipped
```

Sensitive payload values such as tokens, JWTs, secrets, cookies, credentials, passwords, API keys, and encrypted keys should be redacted before insertion.

Current hash-chain behavior:

```text
New audit rows store prev_hash continuity and an HMAC-SHA-256 hash over canonical scrubbed audit material.
The configured key version is stored in audit_log.hmac_key_version and audit_hmac_keys.key_enc stores the local configured key bytes as a foundation placeholder.
```

Backend audit HMAC chain tests:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_audit.py -v
```

## 11. Admin Audit Listing

Endpoint:

```text
GET /api/v1/admin/audit
```

This endpoint returns scrubbed audit rows as paginated JSON (newest first).

Manual command:

```powershell
Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/v1/admin/audit" -Headers $AdminHeaders
```

curl:

```powershell
curl.exe -s "$BaseUrl/api/v1/admin/audit" `
  -H "x-panoptix-dev-auth: 1" `
  -H "x-panoptix-dev-subject: admin@example.test" `
  -H "x-panoptix-dev-email: admin@example.test" `
  -H "x-panoptix-dev-roles: admin"
```

With pagination and filter:

```powershell
curl.exe -s "$BaseUrl/api/v1/admin/audit?limit=10&action=viewer.token.issued" `
  -H "x-panoptix-dev-auth: 1" `
  -H "x-panoptix-dev-subject: admin@example.test" `
  -H "x-panoptix-dev-email: admin@example.test" `
  -H "x-panoptix-dev-roles: admin"
```

Next page using cursor:

```powershell
curl.exe -s "$BaseUrl/api/v1/admin/audit?limit=10&cursor=42" `
  -H "x-panoptix-dev-auth: 1" `
  -H "x-panoptix-dev-subject: admin@example.test" `
  -H "x-panoptix-dev-email: admin@example.test" `
  -H "x-panoptix-dev-roles: admin"
```

Expected response shape:

```json
{
  "items": [
    {
      "id": 42,
      "ts": "2026-05-09T10:30:00+00:00",
      "actor_id": "uuid-or-null",
      "actor_type": "user",
      "action": "viewer.token.issued",
      "resource": "camera:uuid",
      "payload": {"safe": "value", "token": "[REDACTED]"},
      "ip": "127.0.0.1",
      "ua": "Mozilla/5.0"
    }
  ],
  "next_cursor": "37"
}
```

Notes:

- Requires admin role; non-admin users receive `403 role-required`.
- Missing or placeholder `AUDIT_HMAC_KEY` returns `503 audit-hmac-key-invalid`.
- `cursor` is the ID of the last item seen; the next page returns items with lower IDs.
- `limit` defaults to 50, max 200.
- `action` is an optional exact-match filter on the audit action field.
- Results are sorted newest first (descending by ID).
- `next_cursor` is `null` when there are no more pages.
- Internal chain fields (`hash`, `prev_hash`, `hmac_key_version`) are excluded.
- Payload values are already scrubbed at write time.

Backend audit listing tests:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_audit.py -v -k "list"
```

## 12. Admin Audit Export

Endpoint:

```text
GET /api/v1/admin/audit/export
```

This endpoint returns scrubbed audit rows as newline-delimited JSON (JSONL).

Manual command:

```powershell
Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/v1/admin/audit/export" -Headers $AdminHeaders
```

curl:

```powershell
curl.exe -s "$BaseUrl/api/v1/admin/audit/export" `
  -H "x-panoptix-dev-auth: 1" `
  -H "x-panoptix-dev-subject: admin@example.test" `
  -H "x-panoptix-dev-email: admin@example.test" `
  -H "x-panoptix-dev-roles: admin"
```

With optional ID range:

```powershell
curl.exe -s "$BaseUrl/api/v1/admin/audit/export?start_id=10&end_id=20" `
  -H "x-panoptix-dev-auth: 1" `
  -H "x-panoptix-dev-subject: admin@example.test" `
  -H "x-panoptix-dev-email: admin@example.test" `
  -H "x-panoptix-dev-roles: admin"
```

Expected response:

- Content-Type: `application/x-ndjson`
- Content-Disposition: `attachment; filename="audit-export.jsonl"`
- Body: one JSON object per line, or empty if no audit rows exist

Example JSONL row:

```json
{"id":1,"ts":"2026-05-07T12:00:00","actor_id":"uuid","actor_type":"user","action":"viewer.token.issued","resource":"camera:uuid","payload":{"safe":"value","token":"[REDACTED]"},"ip":"127.0.0.1","ua":"Mozilla/5.0"}
```

Notes:

- Requires admin role; non-admin users receive `403 role-required`.
- Missing or placeholder `AUDIT_HMAC_KEY` returns `503 audit-hmac-key-invalid`.
- `start_id` and `end_id` are optional inclusive audit log IDs.
- Invalid bounds (`start_id > end_id`, zero values) return `422`.
- Exported rows do not include internal chain fields (`hash`, `prev_hash`, `hmac_key_version`).
- Payload values are already scrubbed at write time; raw tokens or credentials are never returned.
- Export signing is not implemented yet.

Backend audit export tests:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_audit.py -v -k "export"
```

## 13. Gateway Command Signing Local Check

This is local-only and does not require LiveKit, Cloudflare, Google Workspace, or PostgreSQL.

Backend signing helper tests:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_gateway_command_signing.py -v
```

Edge-agent verifier tests:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/test_commands.py -v
```

Agent command verifier config:

```powershell
$env:PANOPTIX_GATEWAY_COMMAND_SIGNING_KEY = "local-dev-command-signing-key-change-me"
```

Notes:

- The backend signs canonical JSON excluding the `signature` field.
- The edge agent verifies HMAC-SHA-256 signatures before future command execution.
- Tampered, expired, wrong-gateway, or unsigned commands fail closed.
- The WebSocket can send local test-scaffolded signed commands and receive ACK/reject responses.
- There is no persistent command queue and no real camera/media command execution yet.
- Do not use real production signing keys in local shell history.

## 14. Database Validation

If `DATABASE_URL` points to a real local PostgreSQL database:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python scripts/db_validate.py
```

Rollback-only write-path self-test:

```powershell
python scripts/db_validate.py --selftest
```

## 15. Verification Commands

### Maintenance scheduler

Manual maintenance remains available:

```powershell
Invoke-RestMethod -Method POST -Uri "$BaseUrl/api/v1/admin/jobs/run-maintenance" -Headers $AdminHeaders
```

Expected response:

```json
{"expired_commands":0,"stops_enqueued":0}
```

The automatic in-process scheduler is disabled by default. To enable it for local smoke testing, set:

```powershell
$env:ENABLE_MAINTENANCE_SCHEDULER = "true"
$env:MAINTENANCE_INTERVAL_SECONDS = "30"
```

The scheduler only starts when `DATABASE_URL` is not a placeholder. Scheduled runs write `system.maintenance.run` audit events.

### Backend

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/ -v
python -m mypy src/cctv_api/ --ignore-missing-imports
python -m ruff check src tests alembic scripts
python -m compileall src alembic scripts
```

### Edge agent

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/ -v
python -m mypy src/panoptix_edge_agent --ignore-missing-imports
python -m ruff check src tests
python -m compileall src tests
```

## 16. Quick Smoke Test Order

Use this order for a fast manual check after starting the API:

```powershell
curl.exe -s "$BaseUrl/health"
curl.exe -s "$BaseUrl/api/v1/me" -H "x-panoptix-dev-auth: 1"
curl.exe -s -X POST "$BaseUrl/api/v1/gateways/$GatewayId/heartbeat" -H "Content-Type: application/json" -H "x-panoptix-dev-gateway-id: $GatewayId" -d "{\"status\":\"online\",\"agent_version\":\"manual-test\",\"cameras\":[]}"
```

Then run the edge agent one-shot heartbeat:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
$env:PANOPTIX_API_BASE_URL = "http://127.0.0.1:8000"
$env:PANOPTIX_GATEWAY_ID = "11111111-1111-1111-1111-111111111111"
$env:PANOPTIX_DEV_GATEWAY_IDENTITY = "true"
python -m panoptix_edge_agent.cli --once
```

If those pass, the public health path, dev user auth path, gateway auth path, and edge heartbeat foundation are working.

## 17. Gateway Control Reconnect Supervision Check

The edge agent has a bounded gateway control reconnect supervisor for local smoke testing.

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
$env:PANOPTIX_API_BASE_URL = "http://127.0.0.1:8000"
$env:PANOPTIX_GATEWAY_ID = "11111111-1111-1111-1111-111111111111"
$env:PANOPTIX_DEV_GATEWAY_IDENTITY = "true"
$env:PANOPTIX_GATEWAY_COMMAND_SIGNING_KEY = "test-command-signing-key-with-enough-entropy"
$env:PANOPTIX_GATEWAY_CONTROL_RECONNECT_ATTEMPTS = "3"
$env:PANOPTIX_GATEWAY_CONTROL_RECONNECT_BACKOFF_SECONDS = "1"
python -m panoptix_edge_agent.cli --control-loop-once
```

Expected success output includes:

```text
gateway control reconnect accepted after 1 attempt(s); supervisor stopped: connected
```

Expected failure output includes the final reconnect error. The supervisor does not weaken command verification; invalid, unsigned, expired, tampered, or wrong-gateway commands are still rejected.

## 18. Synthetic RTSP Test Source Check

The synthetic RTSP source is a dev/test scaffold. Automated tests only validate FFmpeg argument construction; they do not launch FFmpeg or mediamtx.

Run the focused tests:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/test_synthetic_rtsp.py tests/test_config.py -v
```

Default synthetic output URL:

```text
rtsp://127.0.0.1:8554/synthetic-camera-1
```

Manual end-to-end testing requires starting `mediamtx` separately, then running the generated FFmpeg argument list against that local RTSP server. Keep `mediamtx` local-only and keep its HTTP API disabled or bound to loopback.

Security expectations:

- no browser, webcam, or phone publishing path is introduced
- no RTSP credentials are allowed in the synthetic URL
- real mediamtx supervision and real camera credentials remain future work

Local mediamtx config check:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/test_mediamtx_config.py -v
```

The checked-in local config is:

```text
apps/cctv-edge/mediamtx/mediamtx.local.yml
```

Expected behavior:

- `mediamtx.local.yml` matches the generated safe defaults
- RTSP is bound to `127.0.0.1:8554`
- the HTTP API is disabled by default
- wildcard, WAN, and camera-VLAN API bindings are rejected by tests

Local mediamtx process-management check:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/test_mediamtx_process.py -v
```

Expected behavior:

- process command construction returns an argument list, not a shell string
- default command references `apps/cctv-edge/mediamtx/mediamtx.local.yml`
- invalid binary/config values are rejected
- fake process lifecycle tests cover start, double-start rejection, graceful stop, timeout kill, and failure reporting
- tests do not require mediamtx to be installed

Local LiveKit publisher foundation check:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/test_livekit_publisher.py -v
```

Expected behavior:

- fake publisher clients receive validated start/stop publish requests
- invalid LiveKit URLs, RTSP source URLs, missing tokens, and room mismatches fail before unsafe adapter behavior
- the default SDK-unavailable client fails clearly without real LiveKit credentials or packages
- optional SDK adapter tests use fake SDK room/session objects, so no real LiveKit account or SDK package is required
- SDK adapter start connects a fake room with `auto_subscribe=False` and passes the CCTV source URL into the media-session seam
- SDK adapter stop disconnects the fake room, keeps sessions on stop failure for retry, and returns token-safe error codes
- video-track media-session tests publish fake CCTV frames into fake LiveKit video sources without real RTSP decoding
- frame-source cleanup, track unpublish, frame-pump failure containment, and token non-disclosure are covered by fake-only tests
- command-executor integration remains fail-closed and idempotent
- no browser, webcam, phone, or frontend publishing path is introduced

Local FFmpeg RTSP frame-source check:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/test_ffmpeg_rtsp_frame_source.py -v
```

Expected behavior:

- FFmpeg commands are safe argument lists that read RTSP/RTSPS input and write raw RGBA frames to stdout
- invalid source URLs, RTSP URLs with credentials, invalid dimensions/FPS, invalid binary names, and invalid stop timeouts are rejected
- fake stdout frames yield `LiveKitVideoFrame` objects with deterministic timestamps
- EOF, short reads, missing stdout, idempotent close, and timeout-kill cleanup are covered without launching FFmpeg
- this source remains opt-in; tests do not launch real FFmpeg or require camera credentials

Synthetic FFmpeg-to-LiveKit local smoke wiring check:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/test_ffmpeg_livekit_smoke.py -v
```

Expected behavior:

- the opt-in factory builds `FfmpegRtspFrameSourceConfig` from the signed synthetic publish request source URL
- fake FFmpeg stdout frames are published through fake LiveKit SDK video source/track objects
- stop cleanup disconnects the fake room, unpublishes the fake track, closes fake stdout, and terminates the fake process
- missing or invalid frame-source reads return token-safe SDK start errors
- no real LiveKit SDK, LiveKit Cloud account, FFmpeg process, camera, RTSP credentials, or browser publisher is required

Optional LiveKit SDK package install check:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
python -m pip install -e ".[livekit]"
```

This install is not required for automated tests. The current media bridge and synthetic FFmpeg-to-LiveKit smoke use fake SDK objects and fake FFmpeg processes; real LiveKit Cloud smoke testing, WHIP/RTMP, and LiveKit Ingress remain separate future work.

Synthetic end-to-end publish dry-run check:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/test_publish_dry_run.py -v
```

Expected behavior:

- signed synthetic `start_publish` and `stop_publish` commands verify before execution
- `CommandExecutor` drives `LiveKitMediaController` with the synthetic RTSP source URL
- fake LiveKit publisher calls record safe metadata without logging token values
- optional fake mediamtx lifecycle hooks run without launching mediamtx
- tampered and wrong-gateway commands fail closed
- no real LiveKit SDK, camera, FFmpeg, mediamtx process, browser publisher, or external account is required

## 19. Heartbeat Command Fallback Local Check

The heartbeat fallback path is local-only and test-scaffolded. It does not require LiveKit, Cloudflare, Google Workspace, PostgreSQL, mediamtx, or real cameras.

Backend heartbeat fallback tests:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_gateway.py -v
```

Edge-agent heartbeat pending-command verifier tests:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/test_runner.py -v
```

Expected behavior:

- valid signed pending commands are executed through the edge command executor and counted as accepted by the heartbeat runner
- tampered, expired, unsigned, or wrong-gateway pending commands are counted as rejected
- rejected commands include local error codes such as `gateway-command-signature-invalid`
- execution uses a stub media controller only; no real mediamtx or LiveKit process is started

---

## 20. Edge Command Executor Tests

The edge command executor dispatches verified `gateway.command.start_publish` and `gateway.command.stop_publish` commands to a safe stub media controller.

### Run executor tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/test_executor.py -v
```

Expected behavior:

- valid `start_publish` calls the media controller and records in-memory publish state
- duplicate `start_publish` for the same camera is accepted without a duplicate media-controller call
- valid `stop_publish` calls the media controller and clears publish state
- `stop_publish` for a camera that is not publishing is accepted
- incomplete payloads are rejected with `command-payload-incomplete`
- unsupported command kinds are rejected with `command-kind-unsupported`
- media controller failures reject the command without corrupting state
- the stub controller records calls only; it does not start real media processes

### Run updated control and runner tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/test_control.py tests/test_runner.py -v
```

Expected behavior:

- WebSocket commands are verified, executed, and ACKed as accepted or rejected
- heartbeat pending commands are verified, executed, and counted as accepted or rejected
- tampered, expired, unsigned, and wrong-gateway commands remain fail-closed

---

## 19. Gateway Command Queue Persistence Tests

The gateway command queue module adds persistent command storage with DB-backed provider and ACK sink implementations.

### Run command queue tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_gateway_command_queue.py -v
```

Expected behavior:

- `enqueue_command` creates a pending row with correct kind, payload, and gateway_id
- `db_command_provider` returns only pending, unexpired commands for the requested gateway in FIFO order
- `db_command_provider` excludes commands that are already accepted, rejected, or expired
- `db_ack_sink` marks a command as accepted and records `acked_at` timestamp
- `db_ack_sink` marks a command as rejected with an error message
- `db_ack_sink` silently ignores unknown command IDs and `None` command IDs (idempotent)
- `create_command_provider` opens its own session, queries commands, and closes the session
- `create_ack_sink` opens its own session, records the ACK, commits, and closes the session

### App factory wiring

When `DATABASE_URL` is configured (does not contain `replace-me`), the app factory automatically wires:

- `app.state.gateway_control_command_provider` → persistent command provider
- `app.state.gateway_control_ack_sink` → persistent ACK sink

Tests using the default placeholder URL do not activate the wiring. Tests that need specific command behavior override `app.state.*` directly after app creation.

---

## 20. Command Enqueue API Endpoint

Admin-only endpoint to enqueue commands for a specific gateway.

### Enqueue a command

```powershell
$headers = @{
    "x-panoptix-dev-auth" = "1"
    "x-panoptix-dev-email" = "admin@example.test"
    "x-panoptix-dev-subject" = "admin@example.test"
    "x-panoptix-dev-roles" = "admin"
}
$body = @{
    kind = "reload_config"
    payload = @{ key = "value" }
    expires_in_seconds = 300
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
    -Uri "http://127.0.0.1:8000/api/v1/admin/gateways/<GATEWAY_UUID>/commands" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body
```

Expected response (201 Created):

```json
{
    "command_id": "<uuid>",
    "gateway_id": "<gateway-uuid>",
    "kind": "reload_config",
    "status": "pending",
    "expires_at": "2026-05-09T12:05:00+00:00"
}
```

### Error cases

- No auth headers → 401
- Viewer role → 403 `role-required`
- Invalid gateway UUID → 400 `gateway-id-invalid`
- Valid UUID but no gateway row → 404 `gateway-not-found`

### Run endpoint tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_gateway_command_queue.py -k "endpoint" -v
```

---

## 21. Expired-Command Cleanup

The `expire_stale_commands(db)` function marks pending commands that have passed their `expires_at` as `expired`.

### Run cleanup tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_gateway_command_queue.py -k "expire_stale" -v
```

Expected behavior:

- pending commands past `expires_at` are marked `expired`
- unexpired pending commands remain `pending`
- already accepted/rejected commands are not touched
- returns the count of rows that were expired

---

## 22. Command Listing Admin Endpoint

Admin-only endpoint to list commands for a specific gateway with cursor pagination and optional status filter.

### List commands for a gateway

```powershell
$headers = @{
    "x-panoptix-dev-auth" = "1"
    "x-panoptix-dev-email" = "admin@example.test"
    "x-panoptix-dev-subject" = "admin@example.test"
    "x-panoptix-dev-roles" = "admin"
}

Invoke-RestMethod -Method GET `
    -Uri "http://127.0.0.1:8000/api/v1/admin/gateways/<GATEWAY_UUID>/commands" `
    -Headers $headers
```

curl:

```powershell
curl.exe -s "http://127.0.0.1:8000/api/v1/admin/gateways/<GATEWAY_UUID>/commands" `
  -H "x-panoptix-dev-auth: 1" `
  -H "x-panoptix-dev-subject: admin@example.test" `
  -H "x-panoptix-dev-email: admin@example.test" `
  -H "x-panoptix-dev-roles: admin"
```

With pagination and status filter:

```powershell
curl.exe -s "http://127.0.0.1:8000/api/v1/admin/gateways/<GATEWAY_UUID>/commands?limit=10&status=pending" `
  -H "x-panoptix-dev-auth: 1" `
  -H "x-panoptix-dev-subject: admin@example.test" `
  -H "x-panoptix-dev-email: admin@example.test" `
  -H "x-panoptix-dev-roles: admin"
```

Next page using cursor:

```powershell
curl.exe -s "http://127.0.0.1:8000/api/v1/admin/gateways/<GATEWAY_UUID>/commands?cursor=<LAST_COMMAND_UUID>" `
  -H "x-panoptix-dev-auth: 1" `
  -H "x-panoptix-dev-subject: admin@example.test" `
  -H "x-panoptix-dev-email: admin@example.test" `
  -H "x-panoptix-dev-roles: admin"
```

Expected response (200):

```json
{
    "items": [
        {
            "command_id": "<uuid>",
            "gateway_id": "<gateway-uuid>",
            "kind": "reload_config",
            "payload": {"key": "value"},
            "status": "pending",
            "issued_at": "2026-05-09T12:00:00+00:00",
            "expires_at": "2026-05-09T12:05:00+00:00",
            "acked_at": null,
            "error": null
        }
    ],
    "next_cursor": "<uuid>" | null
}
```

### Error cases

- No auth headers → 401
- Viewer role → 403 `role-required`
- Invalid gateway UUID → 400 `gateway-id-invalid`
- Valid UUID but no gateway row → 404 `gateway-not-found`
- Invalid status value → 400 `status-invalid`
- Invalid cursor UUID → 400 `cursor-invalid`

### Notes

- Requires admin role; non-admin users receive `403 role-required`.
- `cursor` is the command UUID of the last item seen; the next page returns items older than that cursor.
- `limit` defaults to 50, max 200.
- `status` is an optional filter: `pending`, `accepted`, `rejected`, or `expired`.
- Results are sorted newest first (descending by `issued_at`).
- `next_cursor` is `null` when there are no more pages.

### Run listing tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_gateway_command_queue.py -k "list_commands" -v
```

---

## 23. Command Cancellation Admin Endpoint

Admin-only endpoint to cancel a pending command for a specific gateway.

### Cancel a command

```powershell
$headers = @{
    "x-panoptix-dev-auth" = "1"
    "x-panoptix-dev-email" = "admin@example.test"
    "x-panoptix-dev-subject" = "admin@example.test"
    "x-panoptix-dev-roles" = "admin"
}

Invoke-RestMethod -Method POST `
    -Uri "http://127.0.0.1:8000/api/v1/admin/gateways/<GATEWAY_UUID>/commands/<COMMAND_UUID>/cancel" `
    -Headers $headers
```

curl:

```powershell
curl.exe -s -X POST "http://127.0.0.1:8000/api/v1/admin/gateways/<GATEWAY_UUID>/commands/<COMMAND_UUID>/cancel" `
  -H "x-panoptix-dev-auth: 1" `
  -H "x-panoptix-dev-subject: admin@example.test" `
  -H "x-panoptix-dev-email: admin@example.test" `
  -H "x-panoptix-dev-roles: admin"
```

Expected response (200):

```json
{
    "command_id": "<uuid>",
    "gateway_id": "<gateway-uuid>",
    "kind": "reload_config",
    "status": "cancelled",
    "cancelled_at": "2026-05-09T12:01:00+00:00"
}
```

### Error cases

- No auth headers → 401
- Viewer role → 403 `role-required`
- Invalid gateway UUID → 400 `gateway-id-invalid`
- Invalid command UUID → 400 `command-id-invalid`
- Valid gateway UUID but no gateway row → 404 `gateway-not-found`
- Valid UUIDs but no command row on that gateway → 404 `command-not-found`
- Command is not pending (already accepted/rejected/expired/cancelled) → 409 `command-not-pending`

### Notes

- Only `pending` commands can be cancelled.
- Cancelled commands are marked with status `cancelled` and `acked_at` set to the cancellation time.
- Cancelled commands will not be delivered to the gateway (provider only returns `pending` commands).
- Cancelled commands will not be expired by the cleanup utility (only touches `pending` rows).
- The `status` filter in the listing endpoint accepts `cancelled` as a valid value.

### Run cancellation tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_gateway_command_queue.py -k "cancel_command" -v
```

---

## 24. Expired-Command Cleanup Admin Endpoint

Admin-only endpoint to trigger cleanup of stale pending commands across all gateways.

### Trigger cleanup

```powershell
$headers = @{
    "x-panoptix-dev-auth" = "1"
    "x-panoptix-dev-email" = "admin@example.test"
    "x-panoptix-dev-subject" = "admin@example.test"
    "x-panoptix-dev-roles" = "admin"
}

Invoke-RestMethod -Method POST `
    -Uri "http://127.0.0.1:8000/api/v1/admin/commands/cleanup" `
    -Headers $headers
```

curl:

```powershell
curl.exe -s -X POST "http://127.0.0.1:8000/api/v1/admin/commands/cleanup" `
  -H "x-panoptix-dev-auth: 1" `
  -H "x-panoptix-dev-subject: admin@example.test" `
  -H "x-panoptix-dev-email: admin@example.test" `
  -H "x-panoptix-dev-roles: admin"
```

Expected response (200):

```json
{
    "expired_count": 3
}
```

### Error cases

- No auth headers → 401
- Viewer role → 403 `role-required`

### Notes

- Expires pending commands past their `expires_at` across ALL gateways in a single bulk update.
- Idempotent — calling it twice with no new expirations returns `expired_count: 0`.
- Does not touch accepted, rejected, or cancelled commands.
- No request body needed.

### Run cleanup endpoint tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_gateway_command_queue.py -k "expire_cleanup" -v
```

---

## 26. Admin Maintenance Endpoint

Unified admin-only endpoint that runs both `expire_stale_commands` and `enqueue_due_publish_stops` in a single call.

### Trigger maintenance

```powershell
Invoke-RestMethod -Method POST `
  -Uri "$BaseUrl/api/v1/admin/jobs/run-maintenance" `
  -Headers $AdminHeaders
```

Expected response:

```json
{
  "expired_commands": 0,
  "stops_enqueued": 0
}
```

Notes:

- Requires admin role; viewer callers receive `403 role-required`.
- Runs both `expire_stale_commands` and `enqueue_due_publish_stops` deterministically.
- Writes `admin.maintenance.run` audit event with both counts.
- Idempotent — calling it twice with no new work returns zeros.
- The existing `POST /api/v1/admin/commands/cleanup` is still available for backward compat.

### Run maintenance tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_maintenance.py -v
```

---

## 27. Admin User Role Assignment

Admin-only endpoint to grant or revoke a role for a user.

### Grant a role

```powershell
$userId = "<target-user-uuid>"
Invoke-RestMethod -Method POST `
  -Uri "$BaseUrl/api/v1/admin/users/$userId/role" `
  -Headers $AdminHeaders `
  -ContentType "application/json" `
  -Body '{"action":"grant","role_name":"viewer"}'
```

Expected: `{ "user_id": "...", "role_name": "viewer", "action": "grant", "status": "ok" }`

### Revoke a role

```powershell
Invoke-RestMethod -Method POST `
  -Uri "$BaseUrl/api/v1/admin/users/$userId/role" `
  -Headers $AdminHeaders `
  -ContentType "application/json" `
  -Body '{"action":"revoke","role_name":"viewer"}'
```

Notes:

- Unknown user → 404 `user-not-found`
- Unknown role → 404 `role-not-found`
- Duplicate grant → 409 `role-already-granted`
- Revoke without existing grant → 404 `role-not-granted`

---

## 28. Admin User Disable

Admin-only endpoint to disable a user and revoke all their active sessions.

### Disable a user

```powershell
$userId = "<target-user-uuid>"
Invoke-RestMethod -Method POST `
  -Uri "$BaseUrl/api/v1/admin/users/$userId/disable" `
  -Headers $AdminHeaders `
  -ContentType "application/json" `
  -Body '{"reason":"policy violation"}'
```

Expected: `{ "user_id": "...", "disabled_at": "...", "sessions_revoked": 2 }`

Notes:

- Already-disabled user → 409 `user-already-disabled`
- Unknown user → 404 `user-not-found`
- All active sessions are bulk-revoked immediately.

### Run admin user management tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_admin_user_management.py -v
```

---

## 29. Gateway Credential Rotation

Gateway creation now returns a one-time service token, and admins can rotate that token later.

### Create a gateway and capture the one-time token

```powershell
$gateway = Invoke-RestMethod -Method POST `
  -Uri "$BaseUrl/api/v1/admin/gateways" `
  -Headers $AdminHeaders `
  -ContentType "application/json" `
  -Body '{"name":"Local Gateway"}'

$gateway.gateway_id
$gateway.service_token
```

Expected:

- response includes `service_token`
- the token is shown once and should be copied to gateway config
- backend stores only a hash, not the plaintext token

### Rotate gateway credential

```powershell
$gatewayId = "<gateway-uuid>"
Invoke-RestMethod -Method POST `
  -Uri "$BaseUrl/api/v1/admin/gateways/$gatewayId/rotate-credential" `
  -Headers $AdminHeaders `
  -ContentType "application/json" `
  -Body '{"reason":"routine rotation"}'
```

Expected: `{ "gateway_id": "...", "service_token": "...", "rotated_at": "..." }`

Notes:

- The old token is invalidated immediately.
- Disabled gateway → 409 `gateway-disabled`.
- Missing gateway → 404 `gateway-not-found`.
- Audit event: `gateway.credential.rotated`.
- Audit payload never includes the plaintext token.

### Test gateway request authentication with the service token

```powershell
$gatewayHeaders = @{
    "x-panoptix-gateway-id" = $gateway.gateway_id
    "authorization" = "Bearer $($gateway.service_token)"
}

Invoke-RestMethod -Method POST `
  -Uri "$BaseUrl/api/v1/gateways/$($gateway.gateway_id)/heartbeat" `
  -Headers $gatewayHeaders `
  -ContentType "application/json" `
  -Body '{"status":"online","agent_version":"0.1.0","cameras":[]}'
```

Expected:

- valid service token → heartbeat succeeds
- missing token → 401 `gateway-identity-required`
- wrong token → 401 `gateway-credential-invalid`
- disabled gateway → 403 `gateway-disabled`
- token for another gateway route → 403 `gateway-id-mismatch`

### Run credential tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_gateway_credentials.py -v
```

---

## 25. Gateway Command Audit Logging

All gateway command mutation endpoints now write audit trail entries on success.

Gateway denial paths now also write best-effort audit trail entries when gateway command/control operations are rejected.

### Audited actions

| Endpoint | Audit Action |
|----------|-------------|
| `POST /admin/gateways/{id}/commands` | `command.enqueue` |
| `POST /admin/gateways/{id}/commands/{id}/cancel` | `command.cancel` |
| `POST /admin/commands/cleanup` | `commands.cleanup` |

### Audited denial actions

| Path | Audit Action |
|------|--------------|
| gateway heartbeat mismatch | `gateway.heartbeat.denied.gateway_mismatch` |
| gateway heartbeat signing failure | `gateway.heartbeat.denied.signing_failed` |
| camera status disabled gateway | `gateway.camera_status.denied.disabled` |
| camera status missing/retired camera | `gateway.camera_status.denied.camera_not_found` |
| camera status unassigned camera | `gateway.camera_status.denied.unassigned` |
| control WebSocket unauthenticated | `gateway.control.denied.unauthenticated` |
| control WebSocket signing failure | `gateway.control.denied.signing_failed` |
| control WebSocket invalid ACK | `gateway.control.ack.denied.invalid` |
| control WebSocket ACK gateway mismatch | `gateway.control.ack.denied.gateway_mismatch` |
| control WebSocket ACK not applied | `gateway.control.ack.denied.not_applied` |

### Notes

- Successful admin command mutation audit entries use the existing required user-audit pattern.
- Gateway denial audit entries are best-effort and do not mask the original denial reason.
- Actor is the authenticated admin user for admin mutations, or the gateway actor when gateway identity is known.
- Payload includes relevant identifiers such as `command_id`, `gateway_id`, `camera_id`, `kind`, `reason`, or `expired_count`.
- Requires a valid `AUDIT_HMAC_KEY` (not placeholder). In local dev, set:

```powershell
$env:AUDIT_HMAC_KEY_VERSION = "1"
$env:AUDIT_HMAC_KEY = "local-dev-audit-hmac-key-change-me"
```

### Run audit tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_gateway_command_queue.py -k "audit" -v
```

### Test signed audit export

```powershell
Invoke-RestMethod -Method GET `
  -Uri "$BaseUrl/api/v1/admin/audit/export" `
  -Headers $AdminHeaders
```

Expected:

- response is JSON, not JSONL
- `format` is `audit-export-v1`
- `manifest.row_count` matches the number of exported `items`
- `manifest.content_sha256` is the SHA-256 digest of canonical exported `items`
- `manifest.signature_algorithm` is `HMAC-SHA256`
- `manifest.signature_key_version` matches `AUDIT_HMAC_KEY_VERSION`
- `manifest.signature` verifies against the canonical unsigned manifest
- exported `items` do not include `hash`, `prev_hash`, or `hmac_key_version`

Run audit export tests:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_audit.py -k "audit_export" -v
```

---

## 18. Deep Health Check

The `/api/v1/admin/health/deep` endpoint performs a real database connectivity check using `SELECT 1`.

### Test deep health (DB connected)

When the backend can reach the database:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/admin/health/deep -Method GET
```

Expected response:

```json
{"status": "ok", "db": "connected", "livekit": "not_connected", "gateway": "not_connected"}
```

### Test deep health (DB unreachable)

If the backend cannot reach the database (e.g., wrong `DATABASE_URL`), the response will be:

```json
{"status": "degraded", "db": "error", "livekit": "not_connected", "gateway": "not_connected"}
```

### Run deep health tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_health.py -v
```

---

## 19. Camera List Endpoint

The `GET /api/v1/cameras` endpoint returns cameras the authenticated user has active ACL access to.

### List cameras (authenticated viewer)

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/cameras -Method GET -Headers @{
    "x-panoptix-dev-auth" = "1"
    "x-panoptix-dev-email" = "viewer@example.test"
    "x-panoptix-dev-subject" = "viewer@example.test"
    "x-panoptix-dev-roles" = "viewer"
}
```

Expected response (when user has ACL grants):

```json
{
  "items": [
    {
      "camera_id": "<uuid>",
      "display_name": "Front Door",
      "source_type": "rtsp",
      "livekit_room_name": "room-front-door",
      "created_at": "2026-05-09T12:00:00+00:00"
    }
  ],
  "next_cursor": null
}
```

### Notes

- Returns only cameras where the user has a non-revoked ACL entry
- Excludes retired cameras
- Supports cursor pagination via `?cursor=<uuid>&limit=<n>` (default limit 50, max 200)
- Requires authentication; returns 401 without auth headers
- Returns empty list when user has no camera ACL grants

### Run camera list tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_cameras.py -v
```

---

## 22. Gateway Camera Status Persistence

The `POST /api/v1/gateways/{gateway_id}/cameras/{camera_id}/status` endpoint records gateway-reported camera status into `camera_events`.

### Post camera status from a gateway

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/gateways/<gateway-uuid>/cameras/<camera-uuid>/status -Method POST -Headers @{
    "x-panoptix-dev-gateway-id" = "<gateway-uuid>"
    "Content-Type" = "application/json"
} -Body '{"status": "online", "detail": "synthetic camera healthy"}'
```

Expected response (200):

```json
{"accepted": true}
```

### Post status with gateway-observed time

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/gateways/<gateway-uuid>/cameras/<camera-uuid>/status -Method POST -Headers @{
    "x-panoptix-dev-gateway-id" = "<gateway-uuid>"
    "Content-Type" = "application/json"
} -Body '{"status": "offline", "observed_at": "2026-05-09T12:00:00+00:00"}'
```

### Notes

- Gateway identity must match the route `gateway_id`
- Gateway and camera IDs must be UUIDs
- Gateway must be enabled and assigned to the camera
- Camera must be active, not retired
- Accepted statuses: `online`, `offline`, `degraded`
- Successful status posts create `CameraEvent` rows with `source = heartbeat`
- The persisted events are visible through `GET /api/v1/cameras/events` for viewers with camera ACL

### Run gateway status tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_gateway.py -k "gateway_camera_status" -v
```

---

## 23. Admin Gateway Registry And Assignments

Admin-only endpoints register gateways, disable gateways, and grant/revoke gateway-camera assignments.

### Create a gateway

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/admin/gateways -Method POST -Headers @{
    "x-panoptix-dev-auth" = "1"
    "x-panoptix-dev-email" = "admin@example.test"
    "x-panoptix-dev-subject" = "admin@example.test"
    "x-panoptix-dev-roles" = "admin"
    "Content-Type" = "application/json"
} -Body '{"name": "East Wing Gateway", "mtls_fingerprint": "sha256:test"}'
```

Expected response (201):

```json
{"gateway_id": "<uuid>", "name": "East Wing Gateway", "status": "enabled", "created_at": "2026-05-09T12:00:00+00:00"}
```

### Grant a camera assignment

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/admin/gateways/<gateway-uuid>/cameras -Method POST -Headers @{
    "x-panoptix-dev-auth" = "1"
    "x-panoptix-dev-email" = "admin@example.test"
    "x-panoptix-dev-subject" = "admin@example.test"
    "x-panoptix-dev-roles" = "admin"
    "Content-Type" = "application/json"
} -Body '{"action": "grant", "camera_id": "<camera-uuid>"}'
```

Expected response (200):

```json
{"gateway_id": "<uuid>", "camera_id": "<uuid>", "action": "grant", "status": "applied"}
```

### Revoke a camera assignment

Use the same endpoint with `"action": "revoke"`.

### Disable a gateway

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/admin/gateways/<gateway-uuid>/disable -Method POST -Headers @{
    "x-panoptix-dev-auth" = "1"
    "x-panoptix-dev-email" = "admin@example.test"
    "x-panoptix-dev-subject" = "admin@example.test"
    "x-panoptix-dev-roles" = "admin"
    "Content-Type" = "application/json"
} -Body '{"reason": "Compromised gateway token"}'
```

Expected response (200):

```json
{"gateway_id": "<uuid>", "name": "East Wing Gateway", "status": "disabled", "disabled_at": "2026-05-09T12:00:00+00:00"}
```

### Notes

- All endpoints require admin role
- All successful mutations write audit entries
- Duplicate active assignments return 409 `gateway-camera-assignment-already-active`
- Revoking a missing active assignment returns 404 `gateway-camera-assignment-not-found`
- Gateway registration creates the registry row only; real credential bootstrap remains deferred

### Run admin gateway tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_admin_gateways.py -v
```

---

## 20. Admin Camera CRUD

Three admin-only endpoints for camera management: create, ACL grant/revoke, and disable/retire.

### Create a camera

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/admin/cameras -Method POST -Headers @{
    "x-panoptix-dev-auth" = "1"
    "x-panoptix-dev-email" = "admin@example.test"
    "x-panoptix-dev-subject" = "admin@example.test"
    "x-panoptix-dev-roles" = "admin"
    "Content-Type" = "application/json"
} -Body '{"display_name": "Front Gate", "source_type": "rtsp", "livekit_room_name": "room-front-gate"}'
```

Expected response (201):

```json
{"camera_id": "<uuid>", "display_name": "Front Gate", "source_type": "rtsp", "livekit_room_name": "room-front-gate"}
```

Valid source types: `rtsp`, `nvr_rtsp`, `onvif_profile_s`, `onvif_profile_t`, `synthetic_rtsp_test_source`

### Grant camera ACL to a user

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/admin/cameras/<camera-uuid>/acl -Method POST -Headers @{
    "x-panoptix-dev-auth" = "1"
    "x-panoptix-dev-email" = "admin@example.test"
    "x-panoptix-dev-subject" = "admin@example.test"
    "x-panoptix-dev-roles" = "admin"
    "Content-Type" = "application/json"
} -Body '{"action": "grant", "user_email": "viewer@example.test"}'
```

Expected response (200):

```json
{"camera_id": "<uuid>", "user_email": "viewer@example.test", "action": "grant", "status": "applied"}
```

### Revoke camera ACL from a user

Same endpoint with `"action": "revoke"`.

### Disable (retire) a camera

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/admin/cameras/<camera-uuid>/disable -Method POST -Headers @{
    "x-panoptix-dev-auth" = "1"
    "x-panoptix-dev-email" = "admin@example.test"
    "x-panoptix-dev-subject" = "admin@example.test"
    "x-panoptix-dev-roles" = "admin"
    "Content-Type" = "application/json"
} -Body '{"reason": "Decommissioned"}'
```

Expected response (200):

```json
{"camera_id": "<uuid>", "display_name": "Front Gate", "retired_at": "2026-05-09T12:00:00+00:00"}
```

### Notes

- All three endpoints require admin role (403 for non-admins)
- All three write audit trail entries via `_record_user_audit_required` (fail-closed)
- Duplicate room names return 409 `room-name-taken`
- Duplicate ACL grants return 409 `acl-already-active`
- Disabling an already-retired camera returns 409 `camera-already-retired`

### Run admin camera tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_cameras.py -v
```

---

## 21. Camera Events SSE Endpoint

The `GET /api/v1/cameras/events` endpoint returns a finite Server-Sent Events catch-up stream for persisted camera events the authenticated user can access.

### Stream camera events

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/cameras/events?limit=100" -Method GET -Headers @{
    "x-panoptix-dev-auth" = "1"
    "x-panoptix-dev-email" = "viewer@example.test"
    "x-panoptix-dev-subject" = "viewer@example.test"
    "x-panoptix-dev-roles" = "viewer"
}
```

Expected SSE frame shape when accessible events exist:

```text
event: camera_event
data: {"event_id":"<uuid>","camera_id":"<uuid>","gateway_id":null,"kind":"online","source":"heartbeat","at":"2026-05-09T12:00:00+00:00"}
```

### Catch up since a timestamp

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/cameras/events?since=2026-05-09T12%3A00%3A00%2B00%3A00&limit=50" -Method GET -Headers @{
    "x-panoptix-dev-auth" = "1"
    "x-panoptix-dev-email" = "viewer@example.test"
    "x-panoptix-dev-subject" = "viewer@example.test"
    "x-panoptix-dev-roles" = "viewer"
}
```

### Notes

- Returns only events for cameras where the user has a non-revoked ACL entry
- Excludes retired cameras and revoked ACL grants
- `since` is exclusive (`CameraEvent.at > since`)
- Invalid `since` returns 400 `since-invalid`
- This is a finite catch-up stream over persisted rows, not a long-running live event loop

### Run camera event tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_cameras.py -v
```

## 27. Real FFmpeg-to-LiveKit Smoke Test

The `--smoke-ffmpeg-livekit` CLI flag runs the real FFmpeg-to-LiveKit media pipeline for a bounded duration. This is a manual-only test path that requires real FFmpeg, a real RTSP source (e.g., mediamtx with synthetic testsrc), and a real LiveKit server.

### Prerequisites

- FFmpeg installed and on PATH
- mediamtx installed and running with synthetic RTSP source
- LiveKit server accessible (local dev `livekit-server --dev` or LiveKit Cloud)
- `livekit` Python package installed (`pip install livekit`)
- No backend API server required — this runs locally on the edge agent

### Required environment variables

Set these in the PowerShell session before running:

```powershell
$env:PANOPTIX_SMOKE_LIVEKIT_URL = "ws://127.0.0.1:7880"
$env:PANOPTIX_SMOKE_LIVEKIT_API_KEY = "devkey"
$env:PANOPTIX_SMOKE_LIVEKIT_API_SECRET = "secret-with-at-least-thirty-two-bytes"
```

Do not use real production secrets. These values are for local testing only.

### Optional environment variables

```powershell
$env:PANOPTIX_SMOKE_RTSP_URL = "rtsp://127.0.0.1:8554/synthetic-camera-1"
$env:PANOPTIX_SMOKE_ROOM = "smoke-test-room"
$env:PANOPTIX_SMOKE_CAMERA_ID = "smoke-test-camera"
$env:PANOPTIX_SMOKE_DURATION_SECONDS = "10"
$env:PANOPTIX_SMOKE_WIDTH = "640"
$env:PANOPTIX_SMOKE_HEIGHT = "480"
$env:PANOPTIX_SMOKE_FRAME_RATE = "15"
$env:PANOPTIX_SMOKE_FFMPEG_BINARY = "ffmpeg"
```

### Step-by-step

Terminal 1 — start mediamtx:

```powershell
mediamtx mediamtx.local.yml
```

Terminal 2 — start the synthetic RTSP source:

```powershell
ffmpeg -re -f lavfi -i "testsrc=size=640x480:rate=15" -c:v libx264 -pix_fmt yuv420p -preset veryfast -tune zerolatency -f rtsp rtsp://127.0.0.1:8554/synthetic-camera-1
```

Terminal 3 — run the smoke test:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
$env:PANOPTIX_SMOKE_LIVEKIT_URL = "ws://127.0.0.1:7880"
$env:PANOPTIX_SMOKE_LIVEKIT_API_KEY = "devkey"
$env:PANOPTIX_SMOKE_LIVEKIT_API_SECRET = "secret-with-at-least-thirty-two-bytes"
$env:PANOPTIX_SMOKE_DURATION_SECONDS = "10"
python -m panoptix_edge_agent.cli --smoke-ffmpeg-livekit
```

### Expected pass output

```text
smoke: starting FFmpeg-to-LiveKit smoke test
  livekit_url: ws://127.0.0.1:7880
  rtsp_url:    rtsp://127.0.0.1:8554/synthetic-camera-1
  room:        smoke-test-room
  camera_id:   smoke-test-camera
  duration:    10s
  resolution:  640x480@15fps
smoke: PASSED
  frames_published: 1
  duration:         10.01s
  cleanup_ok:       True
```

### Expected fail output

Missing LiveKit SDK:

```text
smoke: FAILED — livekit-sdk-unavailable
```

Missing environment variables:

```text
smoke config error: PANOPTIX_SMOKE_LIVEKIT_URL is required
```

FFmpeg not found:

```text
smoke config error: PANOPTIX_SMOKE_FFMPEG_BINARY 'ffmpeg' was not found on PATH
```

### Troubleshooting

- If the smoke test fails with `livekit-sdk-unavailable`, install the LiveKit SDK: `pip install livekit`
- If it fails with `smoke-start-failed`, check that mediamtx is running and the RTSP source is publishing
- If it fails with `smoke-token-mint-failed`, check that your API key/secret are valid
- The API secret must be at least 32 characters; short secrets are rejected
- The smoke test does not use the backend API server — it mints tokens locally

### LiveKit Cloud smoke checklist

Use this checklist when testing against a real LiveKit Cloud project. This is a manual-only validation path and must not introduce committed credentials.

Preflight:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pip install -e ".[livekit]"
ffmpeg -version
python -c "import livekit.rtc; print('livekit sdk available')"
```

Secret handling rules:

- Set LiveKit Cloud values only as session-scoped PowerShell environment variables.
- Do not write real values to `.env`, `.env.example`, Markdown files, screenshots, commits, tickets, or chat logs.
- Capture only the LiveKit host name in notes, not API keys, API secrets, or generated JWTs.
- Clear the PowerShell variables after the smoke run.

Set LiveKit Cloud variables in the same terminal that runs the smoke command:

```powershell
$env:PANOPTIX_SMOKE_LIVEKIT_URL = "wss://<your-livekit-cloud-host>"
$env:PANOPTIX_SMOKE_LIVEKIT_API_KEY = "<temporary-api-key>"
$env:PANOPTIX_SMOKE_LIVEKIT_API_SECRET = "<temporary-api-secret>"
$env:PANOPTIX_SMOKE_ROOM = "panoptix-smoke-test"
$env:PANOPTIX_SMOKE_CAMERA_ID = "synthetic-smoke-camera"
$env:PANOPTIX_SMOKE_DURATION_SECONDS = "10"
$env:PANOPTIX_SMOKE_RTSP_URL = "rtsp://127.0.0.1:8554/synthetic-camera-1"
```

Start local media prerequisites:

```powershell
mediamtx C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\mediamtx\mediamtx.local.yml
```

In another terminal:

```powershell
ffmpeg -re -f lavfi -i "testsrc=size=640x480:rate=15" -c:v libx264 -pix_fmt yuv420p -preset veryfast -tune zerolatency -f rtsp rtsp://127.0.0.1:8554/synthetic-camera-1
```

Run the LiveKit Cloud smoke:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m panoptix_edge_agent.cli --smoke-ffmpeg-livekit
```

After the run, clear secrets from the shell:

```powershell
Remove-Item Env:\PANOPTIX_SMOKE_LIVEKIT_URL -ErrorAction SilentlyContinue
Remove-Item Env:\PANOPTIX_SMOKE_LIVEKIT_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:\PANOPTIX_SMOKE_LIVEKIT_API_SECRET -ErrorAction SilentlyContinue
```

Smoke result template:

```text
Date/time:
LiveKit host only:
Room:
RTSP source:
Duration:
Result:
Cleanup OK:
Visible in LiveKit Cloud dashboard:
Notes:
Secrets removed from shell: yes/no
```

Expected interpretation:

- `smoke: PASSED` with `cleanup_ok: True` means the edge smoke path connected, published for the bounded duration, and disconnected cleanly.
- Transient LiveKit signal retry/timeout logs can appear during connection; judge the run by the final `smoke: PASSED` / `cleanup_ok` result.
- `livekit-sdk-unavailable` means the optional SDK package is missing from the active Python environment.
- `smoke-start-failed` usually means LiveKit connection, token, FFmpeg, mediamtx, or RTSP source setup failed.
- A successful checklist run is not complete until temporary secrets are cleared and no real secret values are captured in notes.

### Using livekit-ffmpeg mode for the edge agent

To make the edge agent use real FFmpeg/LiveKit publishing when receiving `start_publish` commands from the backend, set:

```powershell
$env:PANOPTIX_MEDIA_PUBLISHER_MODE = "livekit-ffmpeg"
$env:PANOPTIX_MEDIA_SOURCE_URL = "rtsp://127.0.0.1:8554/synthetic-camera-1"
$env:PANOPTIX_MEDIA_WIDTH = "640"
$env:PANOPTIX_MEDIA_HEIGHT = "480"
$env:PANOPTIX_MEDIA_FRAME_RATE = "15"
```

This is separate from the `--smoke-ffmpeg-livekit` manual smoke test. The media publisher mode controls the behavior of the normal heartbeat/control command paths.

Default mode is `stub` -- commands are accepted but no real media is published.

### Edge gateway supervisor mode

The edge agent can run the heartbeat and outbound gateway-control loops under a single supervisor entrypoint:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
$env:PANOPTIX_API_BASE_URL = "http://127.0.0.1:8000"
$env:PANOPTIX_GATEWAY_ID = "11111111-1111-1111-1111-111111111111"
python -m panoptix_edge_agent.cli --supervise
```

By default, supervisor mode does not start real media infrastructure and keeps media publishing in `stub` mode. To include local `mediamtx` process supervision for local-only testing:

```powershell
$env:PANOPTIX_SUPERVISE_MEDIAMTX = "true"
$env:PANOPTIX_MEDIAMTX_BINARY = "mediamtx"
$env:PANOPTIX_MEDIAMTX_CONFIG_PATH = "C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\mediamtx\mediamtx.local.yml"
```

Security expectations:

- Do not put LiveKit secrets, RTSP camera credentials, or generated JWTs in committed files.
- Keep `PANOPTIX_MEDIA_PUBLISHER_MODE=stub` unless intentionally testing real FFmpeg/LiveKit publishing.
- Keep `mediamtx.local.yml` loopback-only and do not expose RTSP, HLS, WebRTC, RTMP, or mediamtx API listeners to WAN.
- Stop the supervisor with `Ctrl+C`; it will attempt to stop supervised `mediamtx` before exit.

For host service operation guidance, see `docs/runbooks/edge-gateway-service.md`. That runbook covers Linux systemd, Docker, and Windows/NSSM service shapes without installing services or committing secrets.

### Review Cloudflare production setup prep

The docs-only Cloudflare production setup checklist is available at `docs/runbooks/cloudflare-production-setup.md`.

To review the Cloudflare prep locally:

```powershell
Get-Content C:\Users\Ivan\Downloads\panoptix-main\Panoptix\docs\runbooks\cloudflare-production-setup.md
Get-Content C:\Users\Ivan\Downloads\panoptix-main\Panoptix\docs\runbooks\cf-access-rollback.md
Get-Content C:\Users\Ivan\Downloads\panoptix-main\Panoptix\.env.example
```

Verification checks:

- The runbook contains only placeholder Cloudflare values, not real account IDs, audience IDs, JWTs, or secrets.
- Production environments must set `APP_ENV=production` and `ALLOW_DEV_AUTH=0`.
- `CF_ACCESS_ISSUER`, `CF_ACCESS_JWKS_URL`, `CF_ACCESS_AUD_DASHBOARD`, `CF_ACCESS_AUD_ADMIN`, and `CF_ACCESS_AUD_GATEWAY` must be provisioned from the deployment secret store.
- Browser/admin traffic uses `cf-access-jwt-assertion`; gateway HTTP traffic uses `x-panoptix-gateway-id` plus `Authorization: Bearer <gateway-service-token>`.
- Gateway routes must not accept browser JWTs as gateway credentials.
- Same-domain routing must send UI, API, health, gateway HTTP, and gateway WebSocket paths to the correct services.
- Rollback steps are documented in `docs/runbooks/cf-access-rollback.md`.

Optional backend test reference:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_config.py tests/test_cloudflare_access.py -v
```

Expected validation behavior:

- Development defaults remain allowed for local work.
- Staging/production startup fails with `unsafe-production-config` if guarded values still contain placeholders.
- `ALLOW_DEV_AUTH=true` is rejected before app startup outside development.

These steps do not modify Cloudflare, DNS, Railway, or Neon. They validate local backend guardrails only.

### Review Railway/Neon staging prep

The docs-only staging deployment prep is available at:

- `docs/runbooks/railway-neon-staging-prep.md` — main staging prep runbook
- `docs/runbooks/templates/railway-api.env.example` — Railway API env template
- `docs/runbooks/templates/neon-staging-checklist.md` — Neon database provisioning checklist

To review locally:

```powershell
Get-Content C:\Users\Ivan\Downloads\panoptix-main\Panoptix\docs\runbooks\railway-neon-staging-prep.md
Get-Content C:\Users\Ivan\Downloads\panoptix-main\Panoptix\docs\runbooks\templates\railway-api.env.example
Get-Content C:\Users\Ivan\Downloads\panoptix-main\Panoptix\docs\runbooks\templates\neon-staging-checklist.md
```

Verification checks:

- The runbook contains only placeholder values, not real Railway project IDs, Neon hosts, passwords, or API keys.
- Railway service plan matches the existing Dockerfile and start command in `apps/api/`.
- Neon roles separate runtime (`cctv_app_runtime`) from migration (`cctv_migrator`).
- Connection strings require `sslmode=require`.
- Migration safety section requires expand/contract pattern.
- Release gates reference existing deploy-rollback and Cloudflare setup runbooks.
- The Railway env template includes all guarded fields that the production auth guardrails check.

These steps do not create Railway services, Neon databases, or Cloudflare policies. They are preparation docs only.

### Review production service templates

Reviewed service templates are available in `docs/runbooks/templates/`:

- `cctv-gateway.service.example` — Linux systemd unit file with hardening settings
- `gateway.env.example` — environment file with placeholder-only values
- `Dockerfile.edge-agent.example` — Docker image template with non-root user and no EXPOSE
- `docker-compose.edge-agent.example.yml` — Docker Compose template with no ports, external env, read-only FS
- `nssm-install.example.ps1` — Windows/NSSM service install script with placeholder values

To review the templates locally:

```powershell
Get-Content C:\Users\Ivan\Downloads\panoptix-main\Panoptix\docs\runbooks\templates\cctv-gateway.service.example
Get-Content C:\Users\Ivan\Downloads\panoptix-main\Panoptix\docs\runbooks\templates\gateway.env.example
Get-Content C:\Users\Ivan\Downloads\panoptix-main\Panoptix\docs\runbooks\templates\Dockerfile.edge-agent.example
Get-Content C:\Users\Ivan\Downloads\panoptix-main\Panoptix\docs\runbooks\templates\docker-compose.edge-agent.example.yml
Get-Content C:\Users\Ivan\Downloads\panoptix-main\Panoptix\docs\runbooks\templates\nssm-install.example.ps1
```

Verification checks:

- Templates contain only placeholder values (no real secrets, API keys, or credentials).
- The systemd unit uses `NoNewPrivileges=yes`, `ProtectSystem=strict`, and a dedicated service user.
- The environment file defaults to `PANOPTIX_MEDIA_PUBLISHER_MODE=stub` and `PANOPTIX_SUPERVISE_MEDIAMTX=false`.
- Real media publishing lines are commented out.
- The Dockerfile has no `EXPOSE` directive and uses a non-root `cctv-gateway` user.
- The Compose file has no `ports:` section and uses `read_only: true`.
- The NSSM script contains only placeholder paths and warns about secrets and firewall.
- No WAN-facing port exposure is configured in any template.

These templates are not installed or enabled by any automated process. They are reference artifacts for future operator review.

### Run smoke config validation tests

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m pytest tests/test_smoke_config.py tests/test_smoke_ffmpeg_livekit.py -v
```
