# Development Setup Guide

<!-- PE-FIX: Added standalone setup guide required by the council audit -->

This guide defines the expected local development shape before application code is written.

## Repository services

| Service | Owner | Purpose |
|---|---|---|
| `cctv-web` | Frontend | Next.js/React/Tailwind UI and LiveKit viewer components. |
| `cctv-api` | Backend/Security | FastAPI API, CF JWT verification, RBAC, sessions, token minting, audit, gateway control, DB writes. |
| `cctv-gateway` | Backend/Ops | Gateway agent plus `mediamtx` for synthetic RTSP and production gateway behavior. |
| `postgres` | Database | Local Postgres matching Neon behavior closely enough for migrations/tests. |
| `synthetic-rtsp` | QA/Gateway | FFmpeg `testsrc` RTSP stream only; never real camera footage. |

## Local prerequisites

- Windows with WSL2 or a Linux-compatible shell for Docker workflows.
- Git.
- Node.js exact patch version from ADR 0007.
- Python exact patch version from ADR 0007.
- Docker Desktop.
- Postgres client tools: `psql`, `pg_dump`, `pg_restore`.
- FFmpeg for synthetic RTSP testing.

## Local auth model

Real Cloudflare Access is not used locally. Local dev uses a fake-CF-Access middleware only when all of these are true:

```text
APP_ENV=development
ALLOW_DEV_AUTH=1
DEV_CF_JWT_SIGNING_KEY is set
```

The fake middleware must issue a dev-signed JWT and exercise the same verifier path as production. Raw `Cf-Access-*` headers are never trusted directly.

## Environment files

Use `.env.example` as the source of required variables. Local secrets go into ignored `.env.local` files per service.

Required local groups:

- Cloudflare Access verifier settings.
- App session/cookie keys.
- Postgres URL and migration URL.
- LiveKit Cloud/fallback test settings.
- Gateway service token/mTLS placeholders.
- R2 backup test settings.
- Observability disabled-by-default settings.

## Startup sequence

1. Start local Postgres.
2. Apply database migrations once they exist.
3. Start `synthetic-rtsp` with FFmpeg test pattern.
4. Start `cctv-api` with dev auth enabled.
5. Start `cctv-web` against same-origin API proxy settings.
6. Start `cctv-gateway` with outbound control WebSocket to local `cctv-api`.
7. Open the dashboard through the local frontend URL.

## Synthetic RTSP source

Synthetic source requirements:

- Uses FFmpeg `testsrc` plus optional `sine` audio.
- Contains no real people or real site data.
- Source type is `synthetic_rtsp_test_source` only.
- Forbidden browser-publisher paths remain forbidden even in local dev.

## Local testing gates

Before opening a PR, run the local equivalents of:

- Backend unit tests.
- Frontend typecheck and lint.
- Playwright smoke tests.
- Browser bundle forbidden-term scan.
- Secret scan.
- API contract smoke tests.
- Gateway command-channel test with WebSocket and heartbeat fallback.

## Development invariants

- No real RTSP credentials in local env files.
- No browser camera/microphone permissions.
- No gateway-publish token returned to browser.
- No direct camera credentials in API responses.
- No long-lived browser auth tokens.
- No bypass of FastAPI as security authority.
