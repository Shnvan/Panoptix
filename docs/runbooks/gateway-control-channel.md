# Runbook: Gateway Control Channel

<!-- PE-FIX: Added runbook for outbound gateway command channel resolving council critical finding -->

## Purpose

Operate and troubleshoot the gateway-initiated outbound control channel used for start/stop publish commands.

## Normal behavior

1. Gateway authenticates to `cctv-api` with service token or mTLS.
2. Gateway opens outbound TLS WebSocket to `/api/v1/gateway-control/ws`.
3. `cctv-api` sends signed command envelopes over the channel.
4. Gateway validates command signature, freshness, gateway ID, camera assignment, and idempotency.
5. Gateway ACKs success/failure.
6. `cctv-api` audits dispatch, ACK, retry, and rejection.

Current implementation note: the backend now supports persistent command queues, DB-backed ACK persistence, gateway control WebSocket dispatch, heartbeat fallback delivery, and bounded edge reconnect/backoff behavior. A backend-controlled synthetic RTSP publish smoke passed against LiveKit Cloud using `gateway.command.start_publish`. Real CCTV hardware validation and frontend subscriber playback remain separate production-readiness steps.

## Fallback behavior

If the WebSocket is unavailable:

1. Gateway continues outbound HTTPS heartbeat.
2. `cctv-api` queues pending start/stop commands.
3. Gateway picks up commands in heartbeat responses.
4. Gateway ACKs the command in the next heartbeat.

## Incident symptoms

| Symptom | Likely cause | Action |
|---|---|---|
| Gateway status degraded | WebSocket disconnected | Check heartbeat fallback and gateway logs. |
| Viewer sees gateway unavailable | Both WebSocket and heartbeat missing | Confirm site WAN, gateway power, and service status. |
| Start command rejected | Bad command signature, expired command, wrong assignment | Check audit event and assignment table. |
| Publish token rejected | Token expired or room mismatch | Re-mint token and verify camera room name. |

## Recovery steps

1. Check `edge_gateways.last_seen_at`.
2. Check recent audit events for `gateway.command.*`.
3. Confirm Cloudflare/Railway routing for `/api/v1/gateway-control/ws`.
4. Confirm gateway can reach `cctv-api` over outbound 443.
5. Restart gateway service if local process is unhealthy.
6. Rotate gateway credential if compromise is suspected.
7. Record incident report for repeated failures.

## Security rules

- Do not open inbound WAN ports.
- Do not add port forwards to the gateway.
- Do not expose `mediamtx` API outside loopback.
- Do not send RTSP credentials in commands.
- Do not return gateway-publish tokens to browsers.
