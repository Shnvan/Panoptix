# Runbook: Cloudflare Access Rollback

<!-- PE-FIX: Added standalone CF Access rollback runbook and clarified break-glass limits -->

## Purpose

Recover from Cloudflare Access, DNS, or policy misconfiguration that blocks legitimate access or opens an unintended path.

## Important scope note

Break-glass App C depends on Cloudflare Access. It is not assumed available during broad Cloudflare Access or DNS failure. Use provider-console recovery for this runbook.

## Triggers

- Legitimate users cannot reach dashboard/admin because of policy change.
- Direct path unexpectedly bypasses intended Access policy.
- Cloudflare routing sends API paths to wrong Railway service.
- Gateway policy blocks valid gateway heartbeats/control channel.

## Required access

- At least two named Cloudflare account members.
- Sealed-envelope recovery process for emergency account access.
- Last-known-good Terraform/config revision.
- Railway service status access.

## Steps

1. Freeze further deploy/config changes.
2. Access Cloudflare provider console using named admin or sealed-envelope procedure.
3. Identify recent Access/DNS/routing changes.
4. Compare current config with last-known-good revision.
5. Run dry-run/plan for rollback if using IaC.
6. Apply rollback.
7. Verify Apps A/B/C/D/E with known-good identities.
8. Verify same-domain routing:
   - UI routes to `cctv-web`.
   - `/api/v1/*`, `/health`, webhooks, and gateway WebSocket route to `cctv-api`.
9. Run T-30 and T-56.
10. Record audit/post-mortem.

## Communications

- Notify affected admins/operators.
- State whether camera viewing, admin actions, or gateway publish are affected.
- Provide recovery ETA and completion note.
