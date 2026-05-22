# ADR 0014 — Railway + Python Control Plane

- **Status**: Accepted
- **Date**: 2026-05-07
- **Decision-makers**: System Owner, Software Architect
- **Decision**: Railway-hosted FastAPI backend with same-domain React + Vite frontend
- **Supersedes**: portions of ADR 0007 and plan §12 that assumed a single server-rendered FastAPI/Jinja2/HTMX UI or the older Next.js/Node/Fly control-plane default (frontend subsequently implemented with React + Vite, not Next.js)
- **Plan references**: §10.1–§10.4; §11; §12; §15; §16; §20; ADR 0002; ADR 0003; ADR 0008; ADR 0010

## Context

The previous v4.1 plan used a Next.js/Node.js control-plane application hosted on Fly.io. The project direction changed to **Railway** for hosting and **Python/FastAPI** for the backend. The team has now selected a dedicated frontend split: **React + Vite** for the UI and **FastAPI** for all backend/security-authoritative control-plane logic.

The non-negotiable security architecture remains unchanged:

- Google Workspace is the primary IdP.
- Cloudflare Access remains the identity-aware access gate.
- Cloudflare remains the public DNS/WAF/access boundary.
- Neon-first Postgres remains the database strategy.
- LiveKit Cloud remains the primary media plane.
- Production cameras still publish only through on-site gateways.
- Browsers remain viewers only; browser/phone/laptop publishing remains banned.

The key architectural question is how to use React + Vite for the frontend without weakening origin-binding, trusted-header validation, token minting, audit logging, gateway identity, or the CCTV-only invariant.

## Decision

**Use Railway to host the control plane as two services: a React + Vite frontend service and a Python/FastAPI backend service. Serve both through the same Cloudflare Access protected custom domain. The frontend owns the dashboard/admin/privacy UI; FastAPI remains the only authority for authentication verification, authorization, session validation, token minting, gateway identity, webhooks, audit, and database writes.**

The revised control-plane stack is:

| Layer | Decision |
|---|---|
| App hosting | Railway |
| Frontend framework | React + Vite |
| Frontend styling | Tailwind CSS |
| Backend framework | Python FastAPI |
| ASGI server | Uvicorn, with Gunicorn/Uvicorn workers if required by deployment mode |
| Public routing model | Same Cloudflare-protected custom domain for UI and API |
| Browser video client | LiveKit JavaScript client inside React viewer components only |
| Database ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Validation | Pydantic |
| Postgres driver | `psycopg` or `asyncpg`, selected at implementation |
| Token hashing | `argon2-cffi` |
| JWT/JWKS validation | Python JWT/JWKS library pinned in ADR 0007 addendum |
| LiveKit token minting | LiveKit Python Server SDK if suitable; otherwise direct JWT signing following LiveKit spec |

## What Railway hosts

Railway hosts the **control plane** only:

- React dashboard pages
- React admin pages
- React privacy notice pages
- React camera-grid and LiveKit viewer components
- FastAPI API endpoints
- Cloudflare Access JWT verification in FastAPI
- app session handling in FastAPI
- viewer-token minting in FastAPI
- gateway-token minting in FastAPI
- LiveKit webhook receiver in FastAPI
- audit logging in FastAPI/Postgres

The temporary Railway-generated URL recorded for submission/testing is:

```text
https://panoptix-control-production.up.railway.app
```

This URL is not the final user-facing entry point. The supported production user path remains the Cloudflare Access protected custom domain.

Railway does **not** host production camera ingest and does **not** replace the on-site gateway.

## What Railway should not host by default

Railway is not assumed to be suitable for the self-hosted LiveKit fallback because a LiveKit SFU normally needs UDP/media-port behaviour that may not match Railway's HTTP-first platform model.

Therefore:

- LiveKit Cloud remains primary.
- Self-hosted LiveKit fallback uses DigitalOcean Singapore as the first procurement candidate, or an equivalent UDP-capable APAC VPS/provider.
- The fallback provider must be verified to support WebRTC/SFU networking requirements.
- Railway is not selected as the fallback SFU host unless procurement verifies UDP/media-port compatibility.

## Access and origin model

The public user path remains:

```text
Browser
→ Cloudflare DNS/WAF
→ Cloudflare Access
→ Google Workspace login/MFA
→ Railway-hosted React + Vite frontend
→ same-origin `/api/v1/*` routes to Railway-hosted FastAPI backend
```

The application must still verify Cloudflare Access JWTs:

- Verify signature against Cloudflare JWKS.
- Pin `iss`.
- Pin `aud`.
- Validate `exp` and `nbf` with `CLOCK_SKEW_SECONDS = 30`.
- Fail closed if JWKS refresh exceeds the allowed staleness window.

Because Railway does not use the same Fly/cloudflared-socket model, ADR 0010 must be interpreted as a **Railway origin-binding policy**:

- The FastAPI backend must reject requests that do not contain a valid Cloudflare Access JWT on protected API routes.
- Trusted Cloudflare headers are never accepted as identity by themselves.
- FastAPI must strip or ignore caller-supplied `Cf-*`, `Cf-Access-*`, `X-Forwarded-*`, and similar headers unless the request passes the Cloudflare Access JWT verification path.
- Where Railway provides public origin URLs, those URLs must not become supported user entry points. The supported entry point is the Cloudflare-protected custom domain only.

If Railway supports private networking or ingress restrictions sufficient to accept only Cloudflare-origin traffic, those controls should be enabled. If not, application-level fail-closed CF JWT verification is mandatory on every protected route.

## UI approach

MVP uses React + Vite from day one because a dedicated frontend developer owns the UI implementation.

- React renders the dashboard, admin, emergency, and privacy pages.
- React components implement camera grids, live video tiles, status panels, forms, and admin workflows.
- Tailwind provides styling.
- The LiveKit JavaScript client is used only inside viewer components for browser-side WebRTC subscription.
- The browser remains a viewer only. No route or component may request camera/microphone permission, call `getUserMedia`, call `MediaRecorder`, or publish media.

The frontend is not a security authority. It displays state and calls same-origin API routes, but FastAPI decides every authorization, ACL, token-mint, gateway, audit, and compliance action.

### Same-domain routing

The preferred production shape is:

```text
https://<app-domain>/dashboard        → React + Vite frontend
https://<app-domain>/admin            → React + Vite frontend
https://<app-domain>/admin-emergency  → React + Vite frontend shell
https://<app-domain>/privacy          → React + Vite frontend
https://<app-domain>/api/v1/*         → FastAPI backend
https://<app-domain>/health           → FastAPI backend
```

This avoids cross-origin browser API calls by default. A separate API subdomain is not selected for MVP because it adds CORS, cookie, and CSRF complexity.

## Database impact

ADR 0003 remains valid. Neon-first Postgres still applies.

The backend ORM remains:

- SQLAlchemy 2.x for database access.
- Python type hints and Pydantic models for backend validation.
- Alembic for migrations.

The database security requirements remain unchanged:

- `sslmode=require`.
- least-privilege runtime role.
- runtime role cannot disable triggers/drop/truncate.
- audit log remains append-only and HMAC-chained.

## Gateway impact

ADR 0008 remains valid.

The gateway API endpoints are FastAPI endpoints, never frontend API routes. The same rules remain:

- browser sessions cannot call gateway token endpoints,
- gateway identity is required,
- gateway must be enabled,
- camera assignment must exist,
- camera must not be retired,
- gateway-publish token is ≤60 s and publisher-only.

The on-site gateway agent may also be written in Python for consistency, but this is not required by this ADR.

## Security impact

The security-critical implementation paths are all in Python/FastAPI:

- CF Access JWT verification
- app session creation and validation
- viewer-token minting
- gateway-token minting
- gateway credential hashing
- audit log writes
- LiveKit webhook verification
- break-glass enforcement
- admin authorization

These paths must avoid experimental framework features and must have direct unit/integration tests.

The frontend security rules are:

- no long-lived auth tokens in browser storage;
- no auth tokens in `localStorage` or `sessionStorage`;
- session cookies, where used, are `HttpOnly`, `Secure`, and `SameSite=Strict`;
- LiveKit viewer tokens are fetched on demand, short-lived, and memory-only;
- gateway-publish tokens are never returned to browser sessions;
- camera RTSP credentials are never returned to any browser response or included in any frontend bundle;
- strict CSP and `Permissions-Policy: camera=(), microphone=()` remain mandatory;
- same-origin API calls remain the default to avoid CORS complexity.

## Consequences

### Positive

- **Matches project constraint**: uses Railway and Python/FastAPI for the backend as requested.
- **Supports team ownership**: gives the dedicated frontend developer a React + Vite UI surface.
- **Simpler backend security model**: FastAPI is explicit and well suited for API-heavy control-plane logic.
- **Same-origin frontend/API model**: keeps browser API calls simple and reduces CORS risk compared with separate subdomains.
- **Keeps previous security decisions**: IdP, database, gateway identity, camera isolation, and LiveKit primary stay intact.
- **Railway-friendly deployment**: the control plane remains Railway-hosted, with separate frontend and backend services if needed.

### Migration notes

- **Existing FastAPI/Jinja2/HTMX content is amended**: version pinning, stack docs, CI, and deployment references now point to Railway + React + Vite frontend + FastAPI backend.
- **Browser-security details change**: CSP, bundle scanning, frontend dependency scanning, and same-origin API routing must be implemented for the React + Vite frontend.
- **Type sharing is possible through OpenAPI**: frontend types should be generated from FastAPI OpenAPI output when implementation begins.
- **Railway origin-binding differs from Fly**: Railway may expose a public origin URL, so app-level fail-closed CF JWT verification becomes even more important.
- **LiveKit fallback hosting is separate from Railway**: DigitalOcean Singapore is the first procurement candidate, but UDP/media-port and TCP/TLS:443 behaviour must still be verified before pilot.

### Risks accepted

- React + Vite adds a Node.js/frontend dependency surface. This is accepted because the team has a dedicated frontend owner, and ADR 0007 requires exact pins, lockfile-only installs, bundle scanning, and dependency review.
- A same-domain split adds service-routing complexity. This is accepted because it preserves a simpler browser security model than separate app/API subdomains.

## Alternatives considered

### A. Keep Next.js/Node/Fly as the full control plane

- **Rejected**: no longer matches the project direction. Railway and Python/FastAPI remain required for the backend and security-authoritative API.

### B. Railway + Django

- **Rejected for MVP**: Django is strong for admin-heavy CRUD apps, but FastAPI is more direct for API/token/webhook-heavy control-plane logic and async gateway/media integrations.

### C. Railway + Flask

- **Rejected for MVP**: Flask is simple, but FastAPI provides stronger request validation, OpenAPI output, dependency injection patterns, and type-hint-driven development.

### D. Railway + FastAPI backend + server-rendered Jinja2/HTMX frontend

- **Rejected after team decision**: still simpler, but the project now has a dedicated frontend developer and selects React + Vite for UI ownership and richer dashboard implementation.

### E. Railway + FastAPI backend + Next.js frontend

- **Rejected in favor of React + Vite**: Next.js gives routing conventions and SSR/static rendering options, but adds unnecessary complexity for a client-rendered SPA. React + Vite is simpler, faster to build, and sufficient for this dashboard.

### F. Railway for both control plane and LiveKit fallback

- **Rejected until verified**: LiveKit fallback requires media-plane networking behaviour that Railway may not support. Railway is selected for the control plane, not automatically for SFU/media hosting.

## Verification

- Protected route without Cloudflare Access JWT is rejected.
- Protected route with invalid `iss`, `aud`, `exp`, `nbf`, or signature is rejected.
- Valid Google Workspace/Cloudflare Access login reaches dashboard.
- React frontend calls FastAPI through same-origin `/api/v1/*` routes.
- Browser user can request viewer-subscribe token only for assigned cameras.
- Browser user cannot request gateway-publish token.
- Gateway can request gateway-publish token only with valid gateway identity and assignment.
- LiveKit webhook HMAC verification passes/fails correctly.
- Audit log write occurs for privileged actions.
- Railway public origin URL, if reachable, still fails closed without a valid CF Access JWT.
- Security headers are emitted consistently for frontend and backend responses.
- Frontend bundle scan confirms no `getUserMedia`, `MediaRecorder`, camera permission calls, gateway-publish token paths, or RTSP credential strings.

## Follow-up changes completed

- ADR 0007 pins Python/FastAPI dependencies and React + Vite frontend dependencies.
- ADR 0010 uses Railway-compatible origin-binding language.
- ADR 0004 decouples LiveKit fallback from Fly.io/Railway and records DigitalOcean Singapore or equivalent UDP-capable APAC host as the fallback candidate.
- Tech stack documentation now points to Railway + React + Vite frontend + FastAPI backend sources of truth.
- Main plan §10, §12, and §20 deployment references now reflect Railway-hosted frontend/backend control-plane services.
- Procurement guide includes Railway account setup and the temporary Railway URL.

## References

- ADR 0002 — Primary Identity Provider Selection
- ADR 0003 — Postgres Provider and Tier Strategy
- ADR 0008 — Gateway Identity and mTLS CA Design
- ADR 0010 — Origin-Binding and Trusted-Header Policy
- FastAPI documentation
- Vite documentation
- React documentation
- Railway documentation
- Cloudflare Access JWT validation documentation
- LiveKit server SDK / token documentation
