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
$Body = @{ session_id = $SessionId } | ConvertTo-Json
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

## 17. Heartbeat Command Fallback Local Check

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

- valid signed pending commands are counted as accepted by the edge heartbeat runner
- tampered, expired, unsigned, or wrong-gateway pending commands are counted as rejected
- rejected commands include local error codes such as `gateway-command-signature-invalid`
- commands are verified only and are not executed
