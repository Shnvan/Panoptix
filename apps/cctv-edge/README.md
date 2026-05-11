# Panoptix CCTV Edge

Gateway and edge-service workspace owned by the system owner.

## Scope

This area is for the on-site gateway implementation, including:

- outbound command/control client
- gateway identity handling
- camera-plane coordination
- mediamtx integration
- LiveKit publishing integration

The gateway must preserve the documented zero-inbound-WAN-port invariant.

## Runtime supervisor

The edge agent exposes a long-running supervisor mode:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\Panoptix\apps\cctv-edge\agent
$env:PYTHONPATH = "src"
python -m panoptix_edge_agent.cli --supervise
```

Supervisor mode coordinates the normal gateway heartbeat and outbound control loops. It can optionally start and stop local `mediamtx` when `PANOPTIX_SUPERVISE_MEDIAMTX=true`.

Safe defaults:

- `PANOPTIX_MEDIA_PUBLISHER_MODE=stub` keeps real media publishing disabled unless explicitly enabled.
- `PANOPTIX_SUPERVISE_MEDIAMTX=false` avoids launching local media infrastructure by default.
- `PANOPTIX_MEDIAMTX_CONFIG_PATH=apps/cctv-edge/mediamtx/mediamtx.local.yml` points at the loopback-only local scaffold.
- The gateway remains outbound-only; do not expose RTSP, HLS, WebRTC, RTMP, or mediamtx API listeners to WAN.
