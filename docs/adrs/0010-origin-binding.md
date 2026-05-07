# ADR 0010 â€” Origin-Binding and Trusted-Header Policy

- **Status**: Accepted
- **Date**: 2026-05-07
- **Decision-makers**: Software Architect, System Owner
- **Supersedes**: None (fixes v3-review findings F-001 and F-002)
- **Amended by**: ADR 0014 â€” Railway + Python Control Plane
- **Plan references**: Invariant 14; Â§11.4; Â§11.6; Â§16.10; Â§18.2 T-56, T-64

## Context

After ADR 0014, the control plane (`cctv-api`) runs on Railway as a Python/FastAPI application. Cloudflare Access remains the supported public access path, federated to Google Workspace. Railway may provide a public origin URL for the service, so origin-binding can no longer depend solely on the earlier Fly/cloudflared Unix-socket model.

This architecture has two failure modes identified in the v3 review:

### F-001: Origin-exposure via direct connection

If an attacker discovers or guesses a Railway origin URL and the app accepts requests without a valid Cloudflare Access JWT, the attacker can bypass the intended Cloudflare Access entry point. The attacker would reach protected routes without MFA and without the intended WAF/rate-limit path.

### F-002: Trusted-header forgery

The app relies on headers like `Cf-Access-Jwt-Assertion` and `Cf-Connecting-IP` for authentication and IP attribution. If the app accepts these headers without verifying the Cloudflare Access JWT, an attacker connecting directly can inject forged headers to impersonate any user or spoof any IP.

Both failures are **control-plane compromise vectors**: they bypass the entire identity layer.

## Decision

**The supported public entry point is the Cloudflare-protected custom domain only. Every protected FastAPI route must fail closed unless it receives a valid Cloudflare Access JWT that passes signature, issuer, audience, expiry, and not-before checks. Headers `Cf-Access-Jwt-Assertion`, `Cf-Connecting-IP`, `Cf-Ray`, `X-Forwarded-For`, and `X-Real-IP` are never trusted by name alone; identity comes only from a verified Cloudflare Access JWT. Caller-supplied `Cf-*`, `Cf-Access-*`, and forwarding headers are stripped or ignored unless the JWT verification path succeeds.**

### Implementation: origin-binding (Inv 14)

1. **Railway custom-domain policy**: the supported user-facing domain is the Cloudflare-protected custom domain. Railway-generated service URLs are not documented or supported as user entry points.
2. **Fail-closed FastAPI middleware**: every protected route verifies the Cloudflare Access JWT before any route handler reads identity headers or session state.
3. **Header normalization**: FastAPI middleware strips or ignores caller-supplied `Cf-*`, `Cf-Access-*`, `X-Forwarded-*`, and `X-Real-IP` fields unless JWT verification succeeds.
4. **Railway ingress controls**: if Railway supports private networking, IP allow-lists, or equivalent origin restrictions compatible with Cloudflare, enable them. These controls are defense-in-depth, not the sole authorization boundary.

**Result**: the only supported path to protected `cctv-api` handlers is: public internet â†’ Cloudflare edge â†’ Cloudflare Access policy â†’ Railway FastAPI app with verified CF Access JWT. A direct Railway-origin request without a valid CF Access JWT fails closed.

### Implementation: trusted-header policy (F-002 fix)

**Layer 1 â€” App-side header stripping**:

The app middleware checks whether the request has a valid Cloudflare Access identity:

- If the Cloudflare Access JWT validates: identity context is built from verified JWT claims, and Cloudflare metadata may be used for attribution.
- If the Cloudflare Access JWT is missing or invalid: Cloudflare and forwarding headers are stripped/ignored, protected routes reject, and no identity context is created.

**Layer 2 â€” Cloudflare/Railway ingress hardening**:

Where platform support permits, ingress should restrict accepted sources or forwarded headers so the app receives only the minimal metadata it needs:

| Forwarded headers | Purpose |
|---|---|
| `cf-access-jwt-assertion` | Identity JWT from CF Access |
| `cf-ray` | CF request trace ID |
| `cf-connecting-ip` | Client IP as seen by CF edge |
| `host` | Standard HTTP |
| `user-agent` | Standard HTTP |
| `accept`, `accept-encoding`, `accept-language` | Standard HTTP |
| `content-type`, `content-length` | Standard HTTP |
| `cookie` | Session cookie |
| `authorization` | Gateway service-token (App E) |

**Any other `cf-*` or `cf-access-*` header is ignored by the FastAPI middleware unless explicitly allow-listed and tied to a verified JWT.** This prevents a request from smuggling a forged extension header like `cf-access-username-override` or `cf-access-group-membership`.

### Combined defense-in-depth

| Attack vector | Layer 1 (app) | Layer 2 (platform/Cloudflare) | Result |
|---|---|---|---|
| Direct Railway-origin request with forged `Cf-Access-Jwt-Assertion` | JWT signature/audience/issuer validation fails â†’ request rejected | Platform restrictions if available | **Blocked** |
| Request with smuggled `cf-access-username-override` | Header ignored; identity comes from verified JWT claims only | Header allow-listing if available | **Blocked** |
| Request through Cloudflare Access with valid `cf-access-jwt-assertion` | JWT validates â†’ identity context created | Forwarded by Cloudflare | **Allowed** (legitimate) |
| Health probe with service-token policy | Service-token policy/JWT validated for `/health` only | Cloudflare policy | **Allowed** (limited scope) |

## Consequences

### Positive

- **CF Access bypass blocked at app layer**: direct Railway-origin requests cannot access protected routes without a valid CF Access JWT.
- **Header forgery eliminated**: forged CF headers are ignored unless tied to a verified CF Access JWT.
- **WAF/rate-limit applied on supported entry point**: documented user traffic passes through CF edge, where WAF rules and rate limits are enforced.
- **Audit integrity**: every request that reaches a handler has a validated CF JWT; the `actor` field in audit logs is always derived from a trusted source.

### Negative

- **Local development requires a substitute**: developers cannot use real CF Access headers locally. The local-dev workflow uses a fake-CF-Access middleware that injects a dev-signed JWT, exercising the same verifier code path.
- **Railway public origin may remain reachable**: unlike the old Fly/cloudflared-socket model, the platform may expose a direct service URL. Mitigation is fail-closed JWT verification on every protected route plus platform ingress restrictions if available.
- **Health checks require care**: `/health` must be protected by a CF Access service-token policy or be strictly non-sensitive if exposed by platform health checks.

### Risks accepted

- If Railway does not support Cloudflare-only ingress restrictions, the direct Railway origin may remain internet-reachable. This is accepted only because protected routes fail closed without verified CF Access JWTs.
- Header allow-listing and normalization are application configuration artefacts. Misconfiguration is mitigated by T-64 integration tests and IaC/config review.

## Alternatives considered

### A. App validates CF JWT only on selected routes

- **Rejected**: any missed route becomes a bypass. Verification must be applied by default middleware with explicit public-route exceptions only.

### B. Rely only on Railway obscurity / unlisted service URL

- **Rejected**: unlisted URLs are not security boundaries. The app must assume the Railway origin URL can be discovered.

### C. IP allow-list only

- **Rejected as sole control**: Cloudflare egress/source behaviour and Railway ingress capabilities must be verified. IP allow-listing is useful defense-in-depth but cannot replace JWT verification.

### D. Custom app login without Cloudflare Access

- **Rejected**: would reintroduce app-managed password/session/MFA burden and leave more pre-auth surface on the Railway app.

## Verification

- **T-56 â€” Origin-binding test**:
  1. Direct request to Railway service URL without CF Access JWT â†’ rejected.
  2. Forged `Cf-Access-Jwt-Assertion` with invalid signature/audience/issuer â†’ rejected.
  3. `Cf-Connecting-IP` / `X-Forwarded-For` spoofed without valid JWT â†’ ignored.
  4. Request through Cloudflare Access with valid JWT â†’ accepted.

- **T-64 â€” trusted-header allow-list test**:
  1. Injection via direct Railway origin â†’ stripped/ignored + rejected.
  2. Injection of `cf-access-username-override` or similar extension header â†’ ignored before route handler identity construction.

- **T-30 â€” External-exposure checklist**:
  1. Railway-origin URL, if reachable, rejects protected routes without valid CF Access JWT.
  2. Public custom domain routes pass through Cloudflare Access.
  3. Shodan/Censys lookups show no unsupported origin endpoint as the documented user entry point.

- **IaC/config drift detector**: daily plan/config review detects if Railway/Cloudflare settings drift from the approved origin-binding posture.

## References

- v4 plan Invariant 14 (Â§ Non-Negotiable Invariants)
- v4 plan Â§11.4 (JWT validation â€” anti-forgery)
- v4 plan Â§11.6 (Trusted-header policy â€” F-002 fix; trusted-header allow-list â€” N-03)
- v4 plan Â§16.10 (Origin / control-plane exposure controls)
- v4 plan Â§18.2 T-30, T-56, T-64
- v3-review findings F-001 (Origin-binding) and F-002 (Trusted-header forgery)
- Cloudflare Access JWT validation documentation: https://developers.cloudflare.com/cloudflare-one/identity/authorization-cookie/validating-json/

