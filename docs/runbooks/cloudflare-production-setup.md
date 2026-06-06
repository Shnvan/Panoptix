# Cloudflare Production Setup Prep

Docs-only preparation checklist for configuring Cloudflare Access in front of the Panoptix production control plane.

## Purpose

Prepare the Cloudflare Access, DNS, routing, and backend environment decisions required before a production or staging deployment. This runbook does not create Cloudflare resources, change DNS, deploy Railway services, or store secrets.

## Scope

This runbook covers:

- Cloudflare Access application and policy shape
- Backend environment variables required for JWT verification
- Browser/admin and gateway identity boundaries
- Origin-binding and trusted-header expectations
- Same-domain routing expectations
- Manual validation and rollback checks

This runbook does not cover:

- Terraform or IaC implementation
- Real Cloudflare account IDs, zone IDs, policy IDs, or audience values
- Railway/Neon deployment steps
- Backend auth code changes
- Secrets provisioning

## Required Cloudflare Access Applications

Create separate Access applications or equivalent policy boundaries for these audiences:

| App | Purpose | Expected audience variable |
|-----|---------|----------------------------|
| Dashboard | Viewer/operator dashboard access | `CF_ACCESS_AUD_DASHBOARD` |
| Admin | Admin-only actions and management screens | `CF_ACCESS_AUD_ADMIN` |
| Gateway | Gateway-facing control-plane boundary | `CF_ACCESS_AUD_GATEWAY` |

Browser/user requests are verified against dashboard/admin audiences. Gateway HTTP ingest uses gateway identity headers plus service-token verification in the backend. The gateway WebSocket identity path must remain separate from browser JWT assumptions.

## Required Backend Environment

Production and staging backend environments must set:

```text
APP_ENV=production
ALLOW_DEV_AUTH=0
CF_ACCESS_ISSUER=https://<team-name>.cloudflareaccess.com
CF_ACCESS_AUD_DASHBOARD=<dashboard-access-audience>
CF_ACCESS_AUD_ADMIN=<admin-access-audience>
CF_ACCESS_AUD_GATEWAY=<gateway-access-audience>
CF_ACCESS_JWKS_URL=https://<team-name>.cloudflareaccess.com/cdn-cgi/access/certs
APP_PUBLIC_BASE_URL=https://<public-panoptix-host>
```

Rules:

- Do not use `replace-me` values in production.
- Do not commit real audience values or secrets to the repository.
- `ALLOW_DEV_AUTH` must be disabled outside local development.
- `APP_ENV` must not be `development` in production or staging.
- Cloudflare Access JWT verification depends on `CF_ACCESS_ISSUER`, `CF_ACCESS_JWKS_URL`, and the configured audience values matching Cloudflare.
- The backend fails fast during app startup for staging/production if guarded auth, Cloudflare, database, session, audit, or gateway values still contain placeholders.

## JWT Verification Expectations

The backend Cloudflare Access verifier expects:

- Header: `cf-access-jwt-assertion`
- Algorithm: `RS256`
- Issuer: `CF_ACCESS_ISSUER`
- Audience: one of `CF_ACCESS_AUD_DASHBOARD` or `CF_ACCESS_AUD_ADMIN` for browser/user requests
- JWKS source: `CF_ACCESS_JWKS_URL`
- Required claims: `exp`, `iat`, `nbf`, `iss`, `aud`, `sub`
- Clock skew bounded by `CLOCK_SKEW_SECONDS`

Expected fail-closed behavior:

- Unsafe staging/production configuration raises `unsafe-production-config` before the FastAPI app starts.
- Missing Cloudflare Access JWT returns `cf-access-token-required`.
- Invalid issuer, audience, signature, or expired token returns `cf-access-token-invalid`.
- Development auth headers are rejected when `APP_ENV` is not `development` or `ALLOW_DEV_AUTH` is false.
- Gateway HTTP routes do not accept browser JWTs as gateway credentials.

## Browser/Admin And Gateway Identity Split

Browser/admin traffic:

- Uses Cloudflare Access JWT assertion headers.
- Resolves user identity from Access claims.
- Uses backend session and CSRF behavior for unsafe browser requests.

Gateway HTTP traffic:

- Uses `x-panoptix-gateway-id` plus `Authorization: Bearer <gateway-service-token>`.
- Verifies the gateway exists, is enabled, and has a valid service-token hash.
- Does not rely on browser JWTs for gateway identity.

Gateway WebSocket traffic:

- Must remain an outbound edge-initiated control channel.
- Must not require inbound WAN exposure on the gateway host.
- Must not reuse dashboard/admin browser identity assumptions.

## Origin-Binding And Trusted Headers

Production routing must preserve these boundaries:

- Only Cloudflare should reach the public origin path intended for protected UI/API traffic.
- Do not trust client-supplied identity headers unless they are produced and protected by Cloudflare Access.
- Enable backend `TRUST_CF_CONNECTING_IP=true` only after that same origin-binding boundary is confirmed so browser session and audit IP capture may trust Cloudflare `CF-Connecting-IP`.
- Do not expose a direct public origin bypass that skips Cloudflare Access.
- Do not allow alternate hostnames to route to the same Railway service without the same Access policy.
- Keep any origin-bypass or provider-console access path documented, restricted, and audited.

Before production cutover, confirm the deployment follows ADR 0010 origin-binding and trusted-header policy.

## Same-Domain Routing Expectations

The public host should route by path while preserving the same external domain:

| Path | Target |
|------|--------|
| UI routes | frontend web service |
| `/api/v1/*` | backend API service |
| `/health` | backend API service |
| Gateway heartbeat/control HTTP paths | backend API service |
| Gateway control WebSocket path | backend API service with WebSocket support |

The gateway control WebSocket path is currently expected to align with:

```text
/api/v1/gateway-control/ws
```

## Public Access-Request WAF Rate Limit

Reserve the single Cloudflare Free-tier rate limiting rule for the public access-request submit endpoint. This edge rule is burst protection before Railway; the FastAPI access-request limiter remains the precise backend control.

Create one WAF rate limiting rule:

| Setting | Value |
|---------|-------|
| Rule name | `panoptix-public-access-request-submit` |
| Match expression | `http.request.uri.path eq "/api/v1/visitor/access-requests"` |
| Optional method condition | Add `http.request.method eq "POST"` only if the current Cloudflare plan/dashboard allows method matching |
| Counting characteristic | IP |
| Threshold | 3 requests per 10 seconds |
| Action | Block, or Managed Challenge if available and preferred |
| Mitigation timeout | 10 seconds |

Rules:

- Do not apply this rule to `/entry`, `/api/v1/visitor/notice`, or `/api/v1/visitor/collect`.
- Do not broaden it to `/api/v1/*`.
- Keep `/`, `/api/v1/me`, `/api/v1/admin/*`, `/api/v1/cameras/*`, and `/api/v1/sessions/*` Cloudflare Access-protected.
- Treat Free-tier limits as a constraint: one rate limiting rule, IP-based counting, 10-second counting period, and 10-second mitigation. If the zone is upgraded later, reassess rather than silently widening the rule.

## Temporary API Compression Mitigation

On 2026-06-06, Chrome reported `ERR_CONTENT_DECODING_FAILED 200 (OK)` for multiple JSON endpoints while direct PowerShell requests returned valid JSON. Keep this Cloudflare Compression Rule active until the malformed origin or edge compression source is identified:

```text
starts_with(http.request.uri.path, "/api/v1/")
```

Set the action to `Disable Compression`.

This broad path match is acceptable only because it controls response compression. It does not make `/api/v1/*` public, does not bypass Cloudflare Access, and is not a WAF rule. The separate `panoptix-public-access-request-submit` rate-limit rule must remain narrow.

Verify after changes:

```powershell
curl.exe -sS -D - https://panoptix.site/api/v1/visitor/notice
curl.exe --compressed -sS -D - https://panoptix.site/api/v1/visitor/notice
```

In a browser console, `fetch("/api/v1/visitor/notice").then(r => r.json()).then(console.log)` must resolve without `ERR_CONTENT_DECODING_FAILED`. Remove this mitigation only after the permanent compression fix passes browser and `curl.exe --compressed` checks across public and authenticated API responses.

## Production Safety Checklist

Before enabling production traffic:

- [ ] Cloudflare Access apps and policies are reviewed by two named operators.
- [ ] Audience values are copied from Cloudflare into the deployment secret store only.
- [ ] `APP_ENV=production` is set.
- [ ] `ALLOW_DEV_AUTH=0` is set.
- [ ] `CF_ACCESS_ISSUER` matches the Cloudflare team domain.
- [ ] `CF_ACCESS_JWKS_URL` points to the team certs endpoint.
- [ ] Dashboard/admin policies allow only approved users or groups.
- [ ] Gateway policy does not weaken gateway service-token verification.
- [ ] Direct origin bypass is blocked or restricted to documented break-glass operations.
- [ ] Same-domain routing sends UI, API, health, and WebSocket paths to the correct services.
- [ ] The Cloudflare Free-tier WAF rate limiting rule `panoptix-public-access-request-submit` is configured for only `POST /api/v1/visitor/access-requests`, or a tracked exception documents why it is not active.
- [ ] The temporary `/api/v1/*` compression-disable rule is tracked separately from Access and WAF policy, and browser compressed-response checks pass.
- [ ] Rollback procedure is reviewed before cutover.

## Manual Validation Steps

Docs-only local review:

```powershell
Get-Content C:\Users\Ivan\Downloads\panoptix-main\panoptix-visitor-access\docs\runbooks\cloudflare-production-setup.md
Get-Content C:\Users\Ivan\Downloads\panoptix-main\panoptix-visitor-access\docs\runbooks\cf-access-rollback.md
```

Backend test references:

```powershell
Set-Location C:\Users\Ivan\Downloads\panoptix-main\panoptix-visitor-access\apps\api
$env:PYTHONPATH = "src"
python -m pytest tests/test_config.py tests/test_cloudflare_access.py -v
```

Expected review results:

- Cloudflare runbook contains no real account IDs, audience IDs, JWTs, or secrets.
- Cloudflare Access tests cover valid browser JWTs and invalid issuer/audience/expired token cases.
- Gateway route tests confirm browser JWTs are not accepted as gateway credentials.
- Development auth remains limited to local development settings.
- The public access-request WAF rule is narrow, contains no secrets, and does not make broad `/api/v1/*` traffic public.

## Rollback

If Cloudflare Access, DNS, routing, or policy changes block legitimate access or open an unintended path, use:

- [`docs/runbooks/cf-access-rollback.md`](cf-access-rollback.md)

Rollback must verify:

- Dashboard and admin access for known-good identities
- Backend API routing
- Gateway heartbeat/control routing
- WebSocket routing
- No direct origin bypass around Access

## Approval Gate

Do not proceed from this preparation runbook to production changes until:

- The Cloudflare Access app/policy design is reviewed.
- The deployment environment values are provisioned in the secret store.
- Rollback access is verified.
- Manual validation steps are complete.
- A separate deployment milestone is approved.

## Device Posture (Cloudflare WARP)

Device posture enforcement ensures only managed devices with the Cloudflare WARP client
enrolled and active can reach Panoptix protected resources. Unmanaged or personal browsers
are blocked at the Access policy layer before any authentication prompt is shown.

This is a production hardening step. Staging uses GitHub OAuth only; WARP posture is layered
on top for production. The NUC gateway does NOT use WARP — it authenticates via mTLS gateway
service tokens and is exempt from device posture requirements.

### Checklist to enable WARP device posture

- [ ] **Step 1 — Enforce WARP enrollment.**
  In Zero Trust → Settings → WARP Client, enable "Require WARP" / mandatory enrollment for
  the Panoptix organization. Users must have WARP installed and connected before accessing.

- [ ] **Step 2 — Create a Device Posture rule.**
  Go to Zero Trust → Settings → Device Posture → Add rule. Select check type
  "WARP client active". Name it `panoptix-warp-active`. Save.

- [ ] **Step 3 — Add posture requirement to the Panoptix Access application.**
  Open the Dashboard (and Admin) Access application → Policies. Add a new require rule:
  `device_posture: warp` (select the `panoptix-warp-active` rule created above).
  Both the identity (IdP) and device posture conditions must pass for a session to be granted.

- [ ] **Step 4 — Test with a non-WARP browser.**
  From a browser without WARP enrolled, attempt to reach the Panoptix host.
  Expected result: Access blocks the request before the login screen appears.

- [ ] **Step 5 — Test with a WARP-enrolled browser.**
  From a device with WARP connected and enrolled, attempt to reach the Panoptix host.
  Expected result: passes device posture check, proceeds to Cloudflare Access login (Google
  Workspace IdP for production), and authenticates normally.
