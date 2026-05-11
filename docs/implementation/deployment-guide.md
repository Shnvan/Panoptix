# Deployment Guide

<!-- PE-FIX: Added standalone deployment guide for Railway + Cloudflare same-domain architecture -->

This guide defines the intended deployment shape before implementation starts.

## Deployment topology

| Public route | Cloudflare Access | Railway service | Responsibility |
|---|---|---|---|
| `/`, `/dashboard`, `/admin`, `/admin-emergency`, `/privacy` | Required | `cctv-web` | Next.js UI shell and browser app. |
| `/_next/*` and frontend static assets | Required | `cctv-web` | Versioned frontend assets with strict headers. |
| `/api/v1/*` | Required unless gateway/webhook policy says otherwise | `cctv-api` | FastAPI protected API. |
| `/api/v1/gateway-control/ws` | Gateway policy | `cctv-api` | Gateway-initiated outbound WebSocket command channel. |
| `/api/v1/webhooks/livekit` | HMAC, server-to-server | `cctv-api` | LiveKit webhook receiver. |
| `/health` | Monitor service-token or non-sensitive platform health | `cctv-api` | Exact body `{ "status": "ok" }`. |

## Cloudflare routing

Cloudflare is the public entry point. Routing rules send frontend paths to `cctv-web` and API/gateway/webhook/health paths to `cctv-api`.

Required controls:

- Cloudflare Access protects the public custom domain.
- WAF and rate limits apply before Railway.
- DNS is orange-clouded for the application domain.
- CAA and CT-log monitoring are enabled before pilot.
- Separate Access policies exist for normal users, admins, break-glass, monitors, and gateways.

## Railway services

### `cctv-web`

- Next.js frontend service.
- No authorization authority.
- No long-lived browser tokens.
- Direct Railway URL must not expose user data; only harmless shell/redirect behavior is allowed.

### `cctv-api`

- FastAPI backend service.
- Verifies Cloudflare Access JWT fail-closed.
- Owns sessions, RBAC, camera ACLs, token minting, gateway identity, webhooks, audit, and DB writes.
- Direct Railway-origin protected routes fail closed without valid CF Access JWT or gateway identity.

## Environments

| Environment | Purpose | Data allowed |
|---|---|---|
| `dev` | Local development | Synthetic data only. |
| `staging` | Railway staging behind Cloudflare Access | Synthetic or scrubbed test data only. |
| `prod` | Railway production behind Cloudflare Access | Real data only after Phase 0 compliance/procurement gates. |

## Deployment gates

Promotion to staging requires:

- Lint/typecheck/unit tests pass.
- Backend integration tests pass.
- Browser bundle scan passes.
- Secret scan passes.
- Dependency/container scans have no critical/high findings.
- API contract smoke tests pass.
- Gateway WebSocket + heartbeat fallback tests pass.

Promotion to production requires:

- Staging smoke tests pass.
- T-30, T-45, T-56 pass.
- DPA/signage/compliance gate satisfied for real sites.
- Rollback plan reviewed.
- Manual approval from system owner.

## Rollback

Rollback order:

1. Stop promotion.
2. Revert Cloudflare routing change if routing caused the incident.
3. Roll back Railway service to previous known-good deployment.
4. If migration involved expand/contract schema, use the documented compatible rollback step only.
5. Run T-30 and API smoke tests.
6. Record incident and audit event.

## Staging Prep

Before first staging deploy, complete the [Railway/Neon Staging Prep](../runbooks/railway-neon-staging-prep.md) checklist and review the placeholder templates in `docs/runbooks/templates/`.

## Direct origin policy

Railway-generated service URLs are not supported user entry points. Protected API routes reject direct requests without valid CF Access JWT. Frontend direct-origin requests may render only a harmless shell/redirect and must not include data-bearing bootstrap content.
