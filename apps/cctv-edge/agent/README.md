# Gateway Agent

Minimal outbound gateway agent for Panoptix edge deployments.

The agent currently reports heartbeat and camera status to `cctv-api`. It does not open inbound listeners and preserves the zero-inbound-WAN-port invariant.

## Configuration

Set these environment variables before running:

| Variable | Required | Default | Purpose |
|---|---:|---|---|
| `PANOPTIX_API_BASE_URL` | yes | none | Base URL for `cctv-api`, for example `http://localhost:8000` |
| `PANOPTIX_GATEWAY_ID` | yes | none | Gateway ID to report as |
| `PANOPTIX_HEARTBEAT_INTERVAL_SECONDS` | no | `10` | Heartbeat loop interval, minimum `5` |
| `PANOPTIX_REQUEST_TIMEOUT_SECONDS` | no | `5.0` | HTTP request timeout |
| `PANOPTIX_AGENT_VERSION` | no | package version | Version string reported to the backend |
| `PANOPTIX_CAMERA_IDS` | no | empty | Comma-separated camera IDs reported as online in heartbeat payloads |
| `PANOPTIX_DEV_GATEWAY_IDENTITY` | no | `false` | Sends the backend dev gateway identity header for local development |

## Run once

```powershell
$env:PYTHONPATH = "src"
$env:PANOPTIX_API_BASE_URL = "http://localhost:8000"
$env:PANOPTIX_GATEWAY_ID = "gateway-1"
$env:PANOPTIX_DEV_GATEWAY_IDENTITY = "true"
python -m panoptix_edge_agent.cli --once
```

## Run continuously

```powershell
$env:PYTHONPATH = "src"
python -m panoptix_edge_agent.cli
```

## Test

```powershell
$env:PYTHONPATH = "src"; python -m pytest tests/ -v
python -m ruff check src tests
python -m mypy src/panoptix_edge_agent --ignore-missing-imports
python -m compileall src tests
```

## Not included yet

- gateway control WebSocket
- signed command validation
- mediamtx process management
- LiveKit publishing orchestration
