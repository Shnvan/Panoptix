# Runbook: Edge Gateway Service

## Purpose

Operate the Panoptix edge gateway supervisor as a managed host service while preserving the zero-inbound-WAN-port invariant.

This runbook is documentation-only. It does not install services, create production Docker images, create real `.env` files, or provision external accounts.

## Runtime entrypoint

The edge runtime supervisor entrypoint is:

```powershell
python -m panoptix_edge_agent.cli --supervise
```

The supervisor coordinates:

1. gateway heartbeat fallback
2. outbound gateway-control WebSocket supervision
3. shared command executor and media controller construction
4. optional local `mediamtx` process startup and cleanup

## Required operator decisions

Before installing any real service, decide and record:

| Decision | Required value |
|---|---|
| Host OS | Ubuntu server, Docker host, or Windows host |
| Gateway identity | Gateway ID issued by backend/admin process |
| Credential source | Service token or future mTLS material |
| Media mode | `stub` or explicitly approved `livekit-ffmpeg` |
| mediamtx ownership | externally managed or `PANOPTIX_SUPERVISE_MEDIAMTX=true` |
| Log destination | journald, Docker logs, Windows Event Log wrapper, or file collector |
| Network placement | WAN-side interface plus optional camera-VLAN interface |

## Environment file checklist

Start from `.env.example` and create a local untracked service environment file on the target host.

Minimum edge settings:

```env
PANOPTIX_API_BASE_URL=https://<backend-host>
PANOPTIX_GATEWAY_ID=<gateway-id>
PANOPTIX_GATEWAY_COMMAND_SIGNING_KEY=<gateway-command-signing-key>
PANOPTIX_GATEWAY_CONTROL_WS_PATH=/api/v1/gateway-control/ws
PANOPTIX_GATEWAY_CONTROL_RECONNECT_ATTEMPTS=3
PANOPTIX_GATEWAY_CONTROL_RECONNECT_BACKOFF_SECONDS=1.0
PANOPTIX_MEDIA_PUBLISHER_MODE=stub
PANOPTIX_SUPERVISE_MEDIAMTX=false
PANOPTIX_MEDIAMTX_BINARY=mediamtx
PANOPTIX_MEDIAMTX_CONFIG_PATH=/etc/cctv-gateway/mediamtx.yml
```

Only enable real media publishing after a separate production media review:

```env
PANOPTIX_MEDIA_PUBLISHER_MODE=livekit-ffmpeg
PANOPTIX_MEDIA_SOURCE_URL=rtsp://<camera-or-local-mediamtx-source>
PANOPTIX_MEDIA_WIDTH=640
PANOPTIX_MEDIA_HEIGHT=480
PANOPTIX_MEDIA_FRAME_RATE=15
PANOPTIX_MEDIA_FFMPEG_BINARY=ffmpeg
```

Secret handling rules:

- Store service environment files outside the repository.
- Use mode `0600` where supported.
- Do not paste API keys, LiveKit secrets, RTSP passwords, generated JWTs, or raw gateway credentials into docs, chats, screenshots, or tickets.
- Do not commit `.env`.
- Rotate the gateway credential if it is exposed.

## Network security gates

Before service enablement, verify:

- WAN router has no port forwards to the gateway.
- Host firewall has no inbound WAN allow rules for the edge agent.
- Gateway can reach backend/API over outbound TLS.
- Gateway can reach LiveKit Cloud over outbound TLS only when real publishing is intentionally enabled.
- `mediamtx` API is disabled or bound to `127.0.0.1` only.
- RTSP, HLS, WebRTC, RTMP, and mediamtx API listeners are not reachable from WAN.
- Camera VLAN, if present, allows only the approved camera-plane flows.
- Browser viewers never receive gateway publish tokens or camera credentials.

## Linux systemd runbook

Preferred production gateway hosts are Linux mini-PCs or NUC-style hosts.

Recommended layout:

```text
/etc/cctv-gateway/gateway.env
/etc/cctv-gateway/mediamtx.yml
/opt/panoptix/edge-agent/
/var/lib/cctv-gateway/
```

Recommended service identity:

```text
user: cctv-gateway
group: cctv-gateway
shell: nologin
sudo: no
```

Operator install outline:

1. Create service user and directories.
2. Install Python runtime, FFmpeg, and pinned `mediamtx` using the approved release process.
3. Deploy edge-agent source or package to `/opt/panoptix/edge-agent/`.
4. Write `/etc/cctv-gateway/gateway.env` with mode `0600`.
5. Write `/etc/cctv-gateway/mediamtx.yml` with mode `0600` if supervising or running `mediamtx` locally.
6. Create a systemd unit that runs `python -m panoptix_edge_agent.cli --supervise` from the agent directory.
7. Use hardening such as `NoNewPrivileges=yes`, restricted write paths, and a dedicated user.
8. Start service only after the network security gates pass.

Recommended systemd behavior:

```text
Restart=always
RestartSec=5
EnvironmentFile=/etc/cctv-gateway/gateway.env
WorkingDirectory=/opt/panoptix/edge-agent
ExecStart=python -m panoptix_edge_agent.cli --supervise
```

Do not install this from the development machine without a separate reviewed deployment milestone.

Reviewed templates are available in [`docs/runbooks/templates/`](templates/):

- [`cctv-gateway.service.example`](templates/cctv-gateway.service.example) — systemd unit file with hardening settings
- [`gateway.env.example`](templates/gateway.env.example) — environment file with placeholder-only values

Copy and adapt these templates to the target host. Do not use them without completing the network security gates.

Health checks:

```bash
systemctl status cctv-gateway
journalctl -u cctv-gateway -n 100 --no-pager
```

Expected healthy behavior:

- service remains running
- heartbeat succeeds
- gateway-control channel reconnects after transient failures
- backend marks gateway online
- no inbound WAN listener appears in firewall or router checks

## Docker runbook

Docker is acceptable when the gateway host operational model includes container image pinning and controlled updates.

Container expectations:

- Pin image tags; do not use `latest`.
- Provide environment via an external env file, not committed Compose secrets.
- Use read-only filesystem where feasible.
- Bind only required local files, such as mediamtx config and writable runtime state.
- Do not publish WAN-facing ports.
- Do not expose mediamtx ports to WAN.

Operator outline:

1. Build or pull the approved edge-agent image by immutable tag.
2. Place the service env file outside the repository.
3. Mount mediamtx config read-only if local mediamtx supervision is enabled.
4. Run the supervisor command as the container entrypoint.
5. Verify no container `ports:` mapping exposes RTSP, HLS, WebRTC, RTMP, or APIs to WAN.

Allowed pattern:

```text
command: python -m panoptix_edge_agent.cli --supervise
env_file: /etc/cctv-gateway/gateway.env
read_only: true
restart: unless-stopped
```

Banned pattern:

```text
ports:
  - "8554:8554"
  - "8888:8888"
  - "9997:9997"
```

Reviewed templates are available in [`docs/runbooks/templates/`](templates/):

- [`Dockerfile.edge-agent.example`](templates/Dockerfile.edge-agent.example) — Docker image template with non-root user and no EXPOSE
- [`docker-compose.edge-agent.example.yml`](templates/docker-compose.edge-agent.example.yml) — Compose template with no ports, external env, read-only FS

Copy and adapt these templates to the target host. Do not use them without completing the network security gates.

Docker health checks:

```bash
docker ps
docker logs --tail 100 <gateway-container>
docker inspect <gateway-container>
```

## Windows/NSSM runbook

Windows service operation is useful for local operators or Windows-based pilot hosts, but it is not the assumed production default.

Recommended layout:

```text
C:\Panoptix\edge-agent\
C:\Panoptix\config\gateway.env
C:\Panoptix\config\mediamtx.yml
C:\Panoptix\logs\
```

Operator outline:

1. Install Python, FFmpeg, pinned `mediamtx`, and the edge-agent package using approved installers.
2. Store `gateway.env` outside the repository.
3. Configure NSSM or the chosen Windows service wrapper to run `python -m panoptix_edge_agent.cli --supervise`.
4. Set the startup directory to the edge-agent directory.
5. Configure stdout/stderr log files under `C:\Panoptix\logs\`.
6. Run as a dedicated local service account where feasible.
7. Verify Windows Firewall does not allow inbound WAN media/API ports.

NSSM-style service shape:

```text
Application: python
Arguments: -m panoptix_edge_agent.cli --supervise
Startup directory: C:\Panoptix\edge-agent
Environment: loaded from C:\Panoptix\config\gateway.env by wrapper or service manager
```

Reviewed templates are available in [`docs/runbooks/templates/`](templates/):

- [`nssm-install.example.ps1`](templates/nssm-install.example.ps1) — NSSM service install script with placeholder values
- [`gateway.env.example`](templates/gateway.env.example) — environment file with placeholder-only values (shared with Linux)

Copy and adapt these templates to the target host. Do not use them without completing the network security gates.

Windows checks:

```powershell
Get-Service cctv-gateway
Get-NetFirewallRule | Where-Object DisplayName -like "*cctv*"
Get-NetTCPConnection -State Listen
```

## mediamtx supervision rules

Use `PANOPTIX_SUPERVISE_MEDIAMTX=true` only when the edge supervisor should own the local `mediamtx` process lifecycle.

Safe local rules:

- Keep `mediamtx.yml` outside the repository when it contains camera credentials.
- Use `api: no` unless the gateway agent explicitly needs the API.
- If the API is enabled, bind it to `127.0.0.1` only.
- Do not expose RTSP/HLS/WebRTC/RTMP to WAN.
- Do not put RTSP credentials in `PANOPTIX_MEDIA_SOURCE_URL` committed examples.

If another service owns `mediamtx`, keep:

```env
PANOPTIX_SUPERVISE_MEDIAMTX=false
```

## Startup procedure

1. Confirm `.env` is not committed and no real credentials are in the repo.
2. Confirm backend/API URL and gateway ID are correct.
3. Confirm gateway credential or signing key is present in the target host environment file.
4. Confirm `PANOPTIX_MEDIA_PUBLISHER_MODE=stub` unless real publishing is intentionally approved.
5. Confirm mediamtx binding and firewall checks pass.
6. Start the service.
7. Confirm gateway heartbeat appears in backend/admin view.
8. Confirm logs do not contain secrets.
9. Record operator, host, version, and gateway ID in the deployment log.

## Shutdown procedure

1. Stop the service through the service manager.
2. Confirm the supervisor exits cleanly.
3. If `PANOPTIX_SUPERVISE_MEDIAMTX=true`, confirm supervised `mediamtx` stops.
4. Confirm backend marks gateway offline or degraded after heartbeat timeout.
5. Record reason for shutdown.

## Rollback procedure

1. Stop the new gateway service.
2. Restore the previous known-good edge-agent package or image tag.
3. Restore the previous known-good service env file if it changed.
4. Restore the previous known-good mediamtx config if it changed.
5. Start the previous service.
6. Confirm heartbeat and control channel recover.
7. Rotate credentials if rollback was caused by suspected credential exposure.

## Incident checklist

Treat these as incidents:

- Any inbound WAN media/API port is reachable.
- mediamtx API binds to `0.0.0.0`, camera VLAN, or WAN interface.
- RTSP camera credentials appear in logs, commits, screenshots, or chat.
- Gateway receives commands for the wrong gateway ID.
- Command signatures fail repeatedly.
- Browser responses contain gateway publish tokens.

Immediate response:

1. Disable the gateway in backend/admin tooling if available.
2. Stop the local service.
3. Remove WAN exposure or unsafe binding.
4. Rotate affected gateway/camera/LiveKit credentials.
5. Preserve logs for audit without copying secrets into tickets.
6. Re-enable only after security gates pass.

## Verification summary

A service installation is ready for pilot only when:

- service starts after reboot
- heartbeat succeeds
- outbound gateway-control channel works or heartbeat fallback works
- service logs are available to operators
- mediamtx bindings are loopback/local-only as intended
- no inbound WAN ports are open
- no real secrets are committed
- rollback procedure has been tested
