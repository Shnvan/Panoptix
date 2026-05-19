# Gateway Agent

Outbound edge gateway agent for Panoptix CCTV deployments.

The agent reports heartbeat and camera status to `cctv-api`, verifies signed gateway commands, dispatches `start_publish` / `stop_publish` commands, tracks publish state, supports a long-running supervisor, and includes fakeable FFmpeg/LiveKit/mediamtx boundaries for safe tests.

It does not open inbound WAN listeners. Camera RTSP credentials stay on the gateway.

## Configuration

| Variable | Required | Default | Purpose |
|---|---:|---|---|
| `PANOPTIX_API_BASE_URL` | yes | none | Base URL for `cctv-api`, for example `http://127.0.0.1:8000` |
| `PANOPTIX_GATEWAY_ID` | yes | none | Gateway ID to report as |
| `PANOPTIX_HEARTBEAT_INTERVAL_SECONDS` | no | `10` | Heartbeat loop interval, minimum `5` |
| `PANOPTIX_REQUEST_TIMEOUT_SECONDS` | no | `5.0` | HTTP request timeout |
| `PANOPTIX_AGENT_VERSION` | no | package version | Version string reported to the backend |
| `PANOPTIX_CAMERA_IDS` | no | empty | Comma-separated camera IDs reported in heartbeat payloads |
| `PANOPTIX_DEV_GATEWAY_IDENTITY` | no | `false` | Sends backend dev gateway identity header for local development |
| `PANOPTIX_GATEWAY_COMMAND_SIGNING_KEY` | no | empty | HMAC key used to verify gateway command envelopes |
| `PANOPTIX_GATEWAY_CONTROL_WS_PATH` | no | `/api/v1/gateway-control/ws` | Gateway control WebSocket path |
| `PANOPTIX_GATEWAY_CONTROL_RECONNECT_ATTEMPTS` | no | `3` | Bounded reconnect attempts for local checks |
| `PANOPTIX_GATEWAY_CONTROL_RECONNECT_BACKOFF_SECONDS` | no | `1.0` | Base reconnect backoff |
| `PANOPTIX_SYNTHETIC_RTSP_URL` | no | `rtsp://127.0.0.1:8554/synthetic-camera-1` | Synthetic RTSP output URL |
| `PANOPTIX_MEDIA_PUBLISHER_MODE` | no | `stub` | `stub` or `livekit-ffmpeg` |
| `PANOPTIX_MEDIA_SOURCE_URL` | no | synthetic RTSP URL | Global fallback media source URL; must not contain credentials |
| `PANOPTIX_MEDIA_WIDTH` | no | `640` | Published video width |
| `PANOPTIX_MEDIA_HEIGHT` | no | `480` | Published video height |
| `PANOPTIX_MEDIA_FRAME_RATE` | no | `15` | Published video frame rate |
| `PANOPTIX_MEDIA_FFMPEG_BINARY` | no | `ffmpeg` | FFmpeg binary name/path |
| `PANOPTIX_SUPERVISE_MEDIAMTX` | no | `false` | Whether supervisor starts local mediamtx |
| `PANOPTIX_MEDIAMTX_BINARY` | no | `mediamtx` | mediamtx binary name/path |
| `PANOPTIX_MEDIAMTX_CONFIG_PATH` | no | local scaffold path | mediamtx config path |
| `PANOPTIX_CAMERA_CREDENTIALS_PATH` | no | empty | JSON file with per-camera RTSP credentials |

Optional LiveKit smoke tests also use `PANOPTIX_SMOKE_*` variables documented in `.env.example`.

## CLI

Run one heartbeat:

```powershell
$env:PYTHONPATH = "src"
$env:PANOPTIX_API_BASE_URL = "http://127.0.0.1:8000"
$env:PANOPTIX_GATEWAY_ID = "11111111-1111-1111-1111-111111111111"
$env:PANOPTIX_DEV_GATEWAY_IDENTITY = "true"
python -m panoptix_edge_agent.cli --once
```

Run continuously:

```powershell
$env:PYTHONPATH = "src"
python -m panoptix_edge_agent.cli
```

Connect to gateway control once:

```powershell
$env:PYTHONPATH = "src"
$env:PANOPTIX_API_BASE_URL = "http://127.0.0.1:8000"
$env:PANOPTIX_GATEWAY_ID = "11111111-1111-1111-1111-111111111111"
$env:PANOPTIX_DEV_GATEWAY_IDENTITY = "true"
$env:PANOPTIX_GATEWAY_COMMAND_SIGNING_KEY = "local-dev-command-signing-key-change-me"
python -m panoptix_edge_agent.cli --control-once
```

Run one bounded reconnect/backoff control check:

```powershell
python -m panoptix_edge_agent.cli --control-loop-once
```

Run supervisor mode:

```powershell
python -m panoptix_edge_agent.cli --supervise
```

Run the optional FFmpeg-to-LiveKit smoke test:

```powershell
python -m pip install -e ".[livekit]"
python -m panoptix_edge_agent.cli --smoke-ffmpeg-livekit
```

## Per-Camera RTSP Credentials

When `PANOPTIX_CAMERA_CREDENTIALS_PATH` is set, the agent loads per-camera RTSP connection details from a local JSON file. See `docs/runbooks/templates/cameras.json.example`.

Rules:

- camera credentials live only on the gateway
- credentials are not sent to the backend, browser, or audit log
- Linux credential files must be mode `0600`
- missing camera credentials reject publish commands with `camera-credentials-not-found`
- without a credential file, the agent falls back to `PANOPTIX_MEDIA_SOURCE_URL`

## Tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/ -v
python -m ruff check src tests
python -m mypy src/panoptix_edge_agent --ignore-missing-imports
python -m compileall src tests
```

## Not Included Yet

- real production camera onboarding and validation
- production service installation on the physical gateway host
- self-hosted LiveKit fallback operations
- browser/frontend viewer UI
