# Production Readiness Runbook

This runbook is the top-level operator checklist for ongoing production readiness checks and for moving from the one-month Tailscale/DigitalOcean pilot toward production-standard site rollout.

It does not deploy code, create infrastructure, run migrations, or store secrets. Use the linked runbooks for detailed procedures.

## Current Readiness Position

Production is live for the protected pilot path at `panoptix.site`. Use this runbook for ongoing checks and for future site hardening.

Verified:

- Backend API foundation is implemented and tested.
- Database migrations are applied through `0013_visitor_access_requests`; gateway command/publish-state and visitor access request tables are present.
- Direct synthetic RTSP to LiveKit Cloud smoke passed.
- Backend-controlled gateway command publish smoke passed with `gateway.command.start_publish`.
- Full authenticated production sidebar smoke passed.
- `Tailscale RTSP Camera` streamed through the DigitalOcean `dropletGateway`; frontend subscriber playback is implemented and browser-tested.
- Gateway publish tokens are backend-to-gateway only and must not be exposed to browsers.

Still required for broader production hardening:

- Production-standard on-site gateway/VLAN rollout for future camera sites.
- Break-glass hardware key procurement/test and monitoring posture.

Hardware-dependent on-site gateway/VLAN work is paused until a real site gateway, camera hardware, and approved camera network are available.

## DigitalOcean Gateway Soak Evidence

Latest evidence status: passed on 2026-06-02 after production redeploy to commit `cee14ad`. Accepted evidence showed `panoptix-edge-agent.service` active with `NRestarts=0`, supervisor PID `46735`, no idle `ffmpeg`, one expected playback `ffmpeg` child PID `50457` under supervisor `46735`, and `ffmpeg` exit after playback close. Browser smoke stayed subscriber-only with no camera/mic permission prompt; `localStorage` contained only `panoptix-theme=dark`, `sessionStorage` was empty, and no RTSP URL, gateway token, Cloudflare secret, LiveKit secret, or auth token was exposed in browser storage. Keep RTSP URLs redacted in any future written evidence.

Run this section from an authorized operator workstation. Do not paste `.env` files, full credential-bearing commands, RTSP URLs, gateway service tokens, Cloudflare Access service-token secrets, LiveKit tokens, or LiveKit API secrets into docs, screenshots, tickets, or chat.

Gateway baseline:

```bash
date -u
hostname
systemctl is-active panoptix-edge-agent.service
systemctl show panoptix-edge-agent.service \
  -p ActiveState \
  -p SubState \
  -p NRestarts \
  -p ExecMainPID \
  -p ExecMainStartTimestamp
pgrep -af "panoptix_edge_agent|panoptix-edge-agent|python.*--supervise"
pgrep -af ffmpeg || true
```

Failure scan:

```bash
journalctl -u panoptix-edge-agent.service --since "24 hours ago" --no-pager \
  | grep -Ei "error|failed|failure|exception|stale|restart|auth|401|403|websocket|livekit|ffmpeg|token" \
  | tail -n 200
journalctl -u panoptix-edge-agent.service -n 100 --no-pager
```

Production playback smoke:

1. Open `panoptix.site` and start the real `Tailscale RTSP Camera` stream.
2. Confirm playback starts through LiveKit with no browser camera/microphone permission prompt.
3. Confirm browser code remains subscriber-only and storage does not contain RTSP URLs, gateway tokens, Cloudflare service-token secrets, LiveKit secrets, or auth tokens.
4. While playback is active, run `pgrep -af ffmpeg || true`; `ffmpeg` should be present only for the active stream.
5. Close playback, wait 30-60 seconds, then run:

```bash
pgrep -af ffmpeg || true
journalctl -u panoptix-edge-agent.service --since "10 minutes ago" --no-pager \
  | grep -Ei "error|failed|failure|exception|stale|auth|401|403|livekit|ffmpeg|token" \
  | tail -n 100
```

Pass criteria: service active, exactly one supervisor process, no restart loop, no repeated stale-session/auth/LiveKit/WebSocket/publish failures, `ffmpeg` absent when idle and present only while streaming, and production playback works without browser publishing or secret exposure. If any criterion fails, record the failure as the next active task instead of marking the soak complete.

## Current Pilot Monitoring

The current no-hardware operating path is the DigitalOcean `dropletGateway` plus Tailscale RTSP pilot camera.

- Production app health remains covered by the existing production health workflow.
- Gateway control-plane health should be checked with admin deep health and recent gateway heartbeat status after deploys or incidents.
- DigitalOcean host health should show `panoptix-edge-agent.service` active, exactly one edge-agent supervisor process, and zero idle `ffmpeg`.
- Treat stale gateway heartbeat, repeated gateway WebSocket reconnect failures, repeated stale-session/auth/LiveKit/publish failures, or any idle `ffmpeg` process as actionable.
- Keep RTSP URLs, gateway tokens, Cloudflare service-token secrets, LiveKit secrets, and auth tokens out of docs, screenshots, logs pasted into chat, and browser storage.

Latest software operations evidence, 2026-06-02:

- API-visible scheduled `Production Health Check` run `26816176702` completed with `success` at `2026-06-02T11:16:44Z`; the workflow checks `/health` and `/api/v1/admin/health/deep`.
- Scheduled `Production Backup` run `26783867468` completed with `success` at `2026-06-01T21:45:05Z`; the workflow runs encrypted R2 backup and retention.
- No open GitHub failure issues named `Production health check failed` or `Production backup automation failed` were found.
- Read-only gateway host check at `2026-06-02T13:19:04Z` showed service active, `NRestarts=0`, one supervisor process, zero idle `ffmpeg`, and no matching failure log lines since service start.

## Required Services

Confirm these services exist and are owned by the team before production approval:

| Service | Purpose | Source of Truth |
|---|---|---|
| Cloudflare Access | Browser authentication, protected routing, device posture | [Cloudflare Production Setup](cloudflare-production-setup.md) |
| Railway API service | FastAPI control plane | [Railway/Neon Production Prep](railway-neon-production-prep.md) |
| Railway web service | Frontend application | [Deployment Guide](../implementation/deployment-guide.md) |
| Neon Postgres | Application database and audit log storage | [Railway/Neon Production Prep](railway-neon-production-prep.md) |
| LiveKit Cloud | WebRTC media plane | [Gateway Control Channel](gateway-control-channel.md) |
| Cloudflare R2 | Encrypted backup artifact storage | [Backup and Restore](backup-restore.md) |
| Edge gateway host | Local RTSP ingest and outbound command execution | [Edge Gateway Service](edge-gateway-service.md) |

## Environment Variable Groups

Use secret stores only. Do not commit real values to Git, Markdown, screenshots, tickets, or chat.

Required groups:

- Runtime mode and public URL: `APP_ENV`, `APP_PUBLIC_BASE_URL`, `PORT`.
- Database: `DATABASE_URL`, `MIGRATION_DATABASE_URL`.
- Sessions and CSRF: `SESSION_SIGNING_KEY`, `CSRF_SIGNING_KEY`.
- Audit integrity: `AUDIT_HMAC_KEY_VERSION`, `AUDIT_HMAC_KEY`.
- Gateway authentication and commands: `GATEWAY_SERVICE_TOKEN`, `GATEWAY_COMMAND_SIGNING_KEY`.
- Cloudflare Access: `CF_ACCESS_ISSUER`, `CF_ACCESS_JWKS_URL`, dashboard/admin/gateway audience values.
- GitHub invites: `GITHUB_INVITES_ENABLED`, `GITHUB_ORG`, `GITHUB_INVITE_TOKEN`, and optional `GITHUB_INVITE_TEAM_IDS`.
- LiveKit: `LIVEKIT_CLOUD_URL`, `LIVEKIT_CLOUD_API_KEY`, `LIVEKIT_CLOUD_API_SECRET`, `LIVEKIT_WEBHOOK_SECRET`.
- R2 backup storage: `R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`.

Production or staging must fail closed if guarded values are missing or placeholder values remain.

## Readiness Order

Follow this order before any production cutover:

1. Confirm branch and release candidate are approved.
2. Confirm Cloudflare Access app, policies, audiences, and routing; browser/admin policy must require the same GitHub organization/team configured for invites.
3. Confirm Neon database roles, SSL, migration connection, and runtime connection.
4. Confirm Railway API and web service environment variables.
5. Apply migrations with the migration database role.
6. Confirm backend shallow and deep health checks.
7. Confirm frontend loads only through the protected public hostname.
8. Confirm gateway service can authenticate and heartbeat.
9. Confirm LiveKit Cloud connectivity and webhook configuration.
10. Confirm R2 backup status and restore-drill plan.
11. Run synthetic media verification.
12. Run browser smoke tests after frontend/gateway deploys; real-camera Tailscale RTSP pilot evidence is passed for the current path.
13. Record approval, remaining risks, and rollback owner.

## Migration Check

From `apps/api`, with `MIGRATION_DATABASE_URL` set to the migration connection:

```powershell
python -m alembic current
```

Expected current revision:

```text
0013_visitor_access_requests
```

Confirm the command and publish-state tables exist:

```text
gateway_command_queue exists
camera_publish_states exists
visitor_access_requests exists
```

If the database is behind this revision, do not run visitor access request or gateway command verification until migrations are applied.

## Health Checks

Minimum checks before promotion:

| Check | Expected Result |
|---|---|
| `GET /health` | HTTP 200 with `{"status":"ok"}` |
| `GET /api/v1/admin/health/deep` | Authenticated admin response with database, LiveKit, and gateway status |
| Gateway heartbeat | Gateway `last_seen_at` is recent |
| LiveKit probe | Configured or connected, not invalid credentials |
| Frontend route | Loads through Cloudflare Access-protected hostname |
| Direct protected origin | Fails closed without valid auth |

Use [Uptime Monitoring](uptime-monitoring.md) and [Deploy and Rollback](deploy-rollback.md) for operational response.

## Synthetic Media Verification

Synthetic RTSP is the required pre-hardware media check.

Expected components:

- MediaMTX running locally for the synthetic RTSP endpoint.
- FFmpeg publishing a generated test pattern to MediaMTX.
- Backend API running with LiveKit Cloud settings.
- Edge agent configured with `PANOPTIX_MEDIA_PUBLISHER_MODE=livekit-ffmpeg`.
- Admin API creates or selects a gateway, camera, and gateway-camera assignment.
- Gateway ingest token is minted by the backend.
- Admin API enqueues `gateway.command.start_publish`.
- Edge agent receives, executes, and ACKs the command.

Pass conditions:

- Direct synthetic LiveKit smoke reports `smoke: PASSED`.
- Backend-controlled command status becomes `accepted`.
- Command has `acked_at`.
- No browser receives a gateway publish token.
- No LiveKit API key, API secret, generated JWT, or gateway publish token is written to files.

For command-channel behavior and recovery, use [Gateway Control Channel](gateway-control-channel.md).

## Audit Checks

Before production approval, verify audit behavior from an admin session:

- Audit chain verification succeeds.
- `audit.log.viewed` appears after audit browsing.
- Actor profile/activity views produce the expected success audit events.
- Gateway command enqueue, dispatch, ACK, and rejection events are present where applicable.
- No audit payload stores LiveKit secrets, gateway publish tokens, database URLs, or RTSP passwords.

If audit writes fail, do not proceed. Audit integrity is a production gate.

## Backup Checks

Before production approval:

- R2 bucket and scoped API token are configured in the secret store.
- Backup status endpoint or operational check reports healthy configuration.
- Restore drill procedure is known and assigned.
- Latest backup artifact can be located without exposing secrets.

Use [Backup and Restore](backup-restore.md) for the detailed procedure.

## Incident Shortcuts

Use these first-response paths:

| Incident | First Checks | Runbook |
|---|---|---|
| Legitimate users cannot log in | Cloudflare Access policy, IdP status, app audience, session errors | [IdP Outage Recovery](idp-outage-recovery.md) |
| Admin locked out | MFA status, break-glass scope, Cloudflare console access | [Lost-MFA Recovery](lost-mfa-recovery.md), [Break-Glass Runbook](break-glass-runbook.md) |
| Database unavailable | Neon status, connection limits, Railway logs, migration state | [Railway/Neon Production Prep](railway-neon-production-prep.md) |
| LiveKit publishing fails | LiveKit credentials, token expiry, room name, command payload, edge logs | [Gateway Control Channel](gateway-control-channel.md) |
| Gateway offline | Host power/network, outbound 443, heartbeat age, service supervisor | [Edge Gateway Service](edge-gateway-service.md) |
| Frontend outage | Railway web deployment, Cloudflare route, build artifact, protected origin behavior | [Deploy and Rollback](deploy-rollback.md) |
| Backup failure | R2 credentials, bucket permissions, object lock, latest artifact | [Backup and Restore](backup-restore.md) |

## Final Approval Checklist

Broader production hardening remains incomplete until every item below is true:

- [ ] `fullstack-integration` or later release candidate has passing backend and frontend checks.
- [ ] No tracked secrets, env files, Terraform state, local AI files, or private key/cert files.
- [ ] Gitleaks or equivalent secret scan passes.
- [ ] Cloudflare Access policies are reviewed and default-deny.
- [ ] Production environment variables are set in secret stores only.
- [ ] Database migration is at `0013_visitor_access_requests` or newer.
- [ ] `/health` and deep health checks pass.
- [x] Gateway heartbeat and backend-controlled command publish smoke pass.
- [x] Frontend LiveKit subscriber playback is implemented and browser-tested.
- [x] Real CCTV hardware test passes for the Tailscale RTSP pilot; production-standard on-site gateway/VLAN rollout is planned for future sites.
- [ ] Backup and restore-drill plan is reviewed.
- [ ] Rollback owner and incident communication owner are named.
