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
```

- Token success paths need real or test database rows for users, cameras, ACLs, gateways, and assignments.
- LiveKit token success paths need non-placeholder LiveKit settings.

## 2. Start The API Locally

From the API app directory:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\api
$env:PYTHONPATH = "src"
$env:APP_ENV = "development"
$env:ALLOW_DEV_AUTH = "true"
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

This endpoint does not send real commands yet. Command queues, dispatch, ACKs, and full reconnect behavior remain future work.

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

Current behavior:

- the agent connects outbound to `/api/v1/gateway-control/ws`
- the backend sends the connected hello message
- the agent verifies that the hello message targets its configured gateway ID
- command envelope parsing and signature verification exist in the agent
- no real commands are sent or executed yet

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

Audit admin endpoints are not implemented yet. Until then, inspect audit rows through local DB tooling.

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

Current limitation:

```text
Audit hash fields are deterministic placeholders, not the final HMAC chain.
```

## 11. Gateway Command Signing Local Check

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
- The WebSocket does not send real commands yet.
- Do not use real production signing keys in local shell history.

## 12. Database Validation

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

## 13. Verification Commands

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

## 14. Quick Smoke Test Order

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
