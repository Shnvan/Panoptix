# Deployment Guide

<!-- PE-FIX: Added standalone deployment guide for Railway + Cloudflare same-domain architecture -->

This guide defines the intended deployment shape before implementation starts.

## Deployment topology

| Public route | Cloudflare Access | Railway service | Responsibility |
|---|---|---|---|
| `/entry`, `/assets/*`, `/logo.png` | Public visitor entry exception | `cctv-web` | Entry notice shell and static assets required before Cloudflare Access sign-in. |
| `/api/v1/visitor/notice`, `/api/v1/visitor/collect`, `/api/v1/visitor/access-requests` | Public collector policy/WAF | `cctv-web` proxy to `cctv-api` | Visitor notice, approved entry signal collection, and public access requests before protected app sign-in. |
| `/`, `/dashboard`, `/admin`, `/admin-emergency`, `/privacy` | Required | `cctv-web` | React/Vite UI shell and browser app. |
| `/api/v1/*` | Required unless gateway/webhook policy says otherwise | `cctv-web` proxy to `cctv-api` or direct `cctv-api` route | FastAPI protected API. |
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
- The public visitor collector exception must stay narrow: only `/entry`, `/assets/*`, `/logo.png`, `/api/v1/visitor/notice`, `/api/v1/visitor/collect`, and `/api/v1/visitor/access-requests` are public; the app root and all other API routes remain Access-protected. Never make broad `/api/v1/*` public. The entry view continues into secure sign-in after its collection attempt, including fail-soft collector errors.
- A Cloudflare Redirect Rule sends first-time root requests to `/entry` only when the signed visitor cookie is absent: `http.host eq "panoptix.site" and http.request.uri.path eq "/" and not http.cookie contains "panoptix_visitor="`. Use `302`, not `301`, because this decision depends on cookies.

## Railway services

### `cctv-web`

- React/Vite frontend service.
- No authorization authority.
- No long-lived browser tokens.
- Serves the built frontend from `apps/web/dist`.
- Proxies `/api/v1/*` and `/health` to `PANOPTIX_API_ORIGIN` so browser calls remain same-origin.
- Direct Railway URL must not expose user data; only harmless shell/redirect behavior is allowed.

Railway frontend service settings:

```text
Root directory: apps/web
Build command: npm ci && npm run build
Start command: npm start
Environment: PANOPTIX_API_ORIGIN=https://<backend-service-domain>
```

Do not set `VITE_DEV_AUTH=true` in deployed frontend environments. Do not add backend-only secrets such as database URLs, LiveKit API secrets, R2 keys, GitHub invite tokens, gateway service tokens, or audit keys to the frontend service.

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
2. Revert Cloudflare routing change if routing caused the incident. For visitor-entry incidents, disable/delete the first-visit Redirect Rule first; separately set `VISITOR_COLLECTOR_ENABLED=false` if the collector backend should stop recording entries.
3. Roll back Railway service to previous known-good deployment.
4. If migration involved expand/contract schema, use the documented compatible rollback step only.
5. Run T-30 and API smoke tests.
6. Record incident and audit event.

## Staging Prep

Before first staging deploy, complete the [Railway/Neon Staging Prep](../runbooks/railway-neon-staging-prep.md) checklist and review the placeholder templates in `docs/runbooks/templates/`.

## Direct origin policy

Railway-generated service URLs are not supported user entry points. Protected API routes reject direct requests without valid CF Access JWT. Frontend direct-origin requests may render only a harmless shell/redirect and must not include data-bearing bootstrap content.
