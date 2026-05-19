# Production Readiness Runbook

This runbook is the top-level operator checklist for deciding whether Panoptix is ready to move from a verified full-stack foundation toward production deployment.

It does not deploy code, create infrastructure, run migrations, or store secrets. Use the linked runbooks for detailed procedures.

## Current Readiness Position

Production is not approved yet.

Verified:

- Backend API foundation is implemented and tested.
- Database migration `0007_gateway_command_tables` exists for `gateway_command_queue` and `camera_publish_states`.
- Direct synthetic RTSP to LiveKit Cloud smoke passed.
- Backend-controlled gateway command publish smoke passed with `gateway.command.start_publish`.
- Gateway publish tokens are backend-to-gateway only and must not be exposed to browsers.

Still blocking production:

- Frontend LiveKit subscriber playback is pending.
- Real CCTV hardware validation is pending.
- Production Railway, Neon, Cloudflare, R2, and monitoring readiness must be reviewed before cutover.

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
12. Run browser smoke tests once frontend subscriber playback exists.
13. Record approval, remaining risks, and rollback owner.

## Migration Check

From `apps/api`, with `MIGRATION_DATABASE_URL` set to the migration connection:

```powershell
python -m alembic current
```

Expected current revision:

```text
0007_gateway_command_tables
```

Confirm the command and publish-state tables exist:

```text
gateway_command_queue exists
camera_publish_states exists
```

If the database is behind this revision, do not run gateway command publish verification until migrations are applied.

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

Production remains blocked until every item below is true:

- [ ] `fullstack-integration` or later release candidate has passing backend and frontend checks.
- [ ] No tracked secrets, env files, Terraform state, local AI files, or private key/cert files.
- [ ] Gitleaks or equivalent secret scan passes.
- [ ] Cloudflare Access policies are reviewed and default-deny.
- [ ] Production environment variables are set in secret stores only.
- [ ] Database migration is at `0007_gateway_command_tables` or newer.
- [ ] `/health` and deep health checks pass.
- [ ] Gateway heartbeat and backend-controlled command publish smoke pass.
- [ ] Frontend LiveKit subscriber playback is implemented and browser-tested.
- [ ] Real CCTV hardware test passes.
- [ ] Backup and restore-drill plan is reviewed.
- [ ] Rollback owner and incident communication owner are named.
