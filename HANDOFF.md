# Panoptix Project Handoff

This handoff gives a new IDE/LLM enough project context, development rules, and navigation instructions to continue Panoptix without starting from scratch.

## First Instructions For The New IDE/LLM

Before making any changes, read this file completely, then read these files in order:

1. `PROGRESS.md`
2. `IMPLEMENTATION_GUIDE.md`
3. `MANUAL_TESTING.md`
4. `README.md`
5. `CLAUDE.md`
6. `docs/index.md`
7. `docs/implementation/api-reference.md`
8. `docs/implementation/development-setup.md`
9. `docs/implementation/test-plan.md`
10. `docs/runbooks/gateway-control-channel.md`

After that, inspect the source files related to the active task. Do not assume the whole repository has been loaded into context. Search and read files on demand.

## Repository

- Path: `C:\Users\Ivan\Downloads\panoptix-main\Panoptix`
- Current branch: `backend`
- Remote: `https://github.com/Shnvan/Panoptix`
- Current development mode: local-first backend and edge-agent foundation

## Current Objective

Build the local-only secure CCTV control-plane and edge-agent foundation before moving to cloud accounts, real media publishing, mediamtx orchestration, or frontend UI.

The system is Panoptix, a secure live-view CCTV web monitoring system with three planes:

- Control plane: FastAPI backend and future Next.js frontend
- Media plane: LiveKit Cloud primary, self-hosted LiveKit fallback later
- Camera plane: on-site edge gateway/NUC, mediamtx, isolated camera network

Permanent product constraint: browsers are viewers only. No browser, phone, or laptop camera publishing.

## High-Level Architecture

### Control Plane

Location: `apps/api/`

FastAPI backend currently implements:

- app factory
- configuration loading
- health endpoints
- RFC 9457-style problem details
- local development auth
- Cloudflare Access JWT verification scaffolding
- session cookie helpers
- RBAC/policy placeholders
- gateway heartbeat endpoint
- gateway camera status endpoint
- LiveKit viewer token endpoint
- LiveKit gateway ingest token endpoint
- gateway control WebSocket skeleton
- gateway command signing helpers
- in-memory/test-scaffolded WebSocket command dispatch + ACK handling
- in-memory/test-scaffolded heartbeat command fallback
- HMAC-SHA-256 audit hash chain writer and verifier helpers
- read-only admin audit verification endpoint with optional ID ranges and key-version handling
- admin audit export endpoint returning scrubbed JSONL rows

### Edge / Camera Plane

Location: `apps/cctv-edge/`

Current implemented code is in `apps/cctv-edge/agent/`:

- environment-driven agent config
- HTTP client for backend heartbeat/status calls
- one-shot and continuous heartbeat runner
- command envelope verifier
- gateway control WebSocket client skeleton
- heartbeat pending-command verifier
- `--once` CLI for heartbeat
- `--control-once` CLI for one-shot WebSocket control check
- `--control-loop-once` CLI for bounded reconnect/backoff control check

Placeholders:

- `apps/cctv-edge/mediamtx/` is documentation-only for now
- no real camera process management yet
- no mediamtx runtime config generation yet

### Media Plane

Location: `apps/media-fallback/` and docs

Current state:

- LiveKit token minting exists in backend tests/source
- actual LiveKit Cloud account setup is not required yet
- fallback LiveKit app remains placeholder

### Frontend

Location: `apps/web/`

Current state:

- placeholder only
- frontend coworker ownership zone
- do not add backend/security logic here

### Database

Location: `database/`, `apps/api/alembic/`, `apps/api/src/cctv_api/models/`

Current state:

- Alembic migrations exist
- SQLAlchemy models exist
- command queue persistence has not been implemented yet
- DB coworker ownership is documented, but backend tests use database helpers where needed

## Recently Completed Milestones

### Audit Export Skeleton

Completed in this milestone.

Implemented:

- `GET /api/v1/admin/audit/export` admin-only endpoint
- scrubbed audit rows returned as newline-delimited JSON (JSONL)
- optional inclusive `start_id` and `end_id` range filtering
- `application/x-ndjson` content type with `Content-Disposition: attachment` header
- internal chain fields excluded from export
- fail-closed 503 when HMAC key is placeholder or empty

Not included:

- export signing
- audit row listing with cursor pagination
- key rotation UI/workflow
- broad browsing filters
- database migrations
- self-auditing the export call

### Audit Verification Range/Key-Version Support

Completed in this milestone.

Implemented:

- optional inclusive `start_id` and `end_id` query params on `GET /api/v1/admin/audit/verify`
- full-chain verification remains the default
- open-ended ranges when only one bound is provided
- continuity checks against the latest row before `start_id`
- per-row key lookup using `audit_log.hmac_key_version` and local `audit_hmac_keys.key_enc`
- structured failures for missing or invalid stored key versions

Not included:

- audit row listing
- audit export signing
- key rotation UI/workflow
- database migrations
- self-auditing the verification call

### Admin Audit Verification Endpoint Skeleton

Completed and pushed in commit:

```text
5003679 Add admin audit verification endpoint
```

Implemented:

- `GET /api/v1/admin/audit/verify`
- admin-role enforcement through existing browser/user auth and policy helpers
- full audit-chain verification in `audit_log.id` order
- structured `valid`, `checked`, and `error` response
- `503 audit-hmac-key-invalid` when the configured audit HMAC key is blank or `replace-me`

Not included:

- audit row listing
- audit export signing
- key rotation UI/workflow
- database migrations
- self-auditing the verification call

### Audit HMAC Chain Foundation

Completed in this milestone.

Implemented:

- `AUDIT_HMAC_KEY_VERSION`
- `AUDIT_HMAC_KEY`
- fail-closed audit writes when the HMAC key is blank or left as `replace-me`
- HMAC-SHA-256 audit hashes over canonical scrubbed audit material
- `prev_hash` continuity for newly written audit rows
- active audit HMAC key row handling using `audit_hmac_keys.key_enc` as local placeholder storage
- single-row and sequence verifier helpers for future admin verification surfaces

Not included:

- admin audit list/export/verify endpoints
- export signing
- KMS/envelope encryption
- key rotation UI/workflow
- database migrations

### Edge Gateway Control Reconnect/Backoff Skeleton

Completed and pushed in commit:

```text
b4a4262 Add gateway control reconnect backoff
```

Implemented:

- `PANOPTIX_GATEWAY_CONTROL_RECONNECT_ATTEMPTS`
- `PANOPTIX_GATEWAY_CONTROL_RECONNECT_BACKOFF_SECONDS`
- bounded `GatewayControlClient.run_with_reconnect()`
- `--control-loop-once` local CLI check
- retry for temporary connection/run failures
- no retry for malformed fail-closed control messages
- no inbound gateway listener, command execution, mediamtx control, or LiveKit publishing

Verification:

```text
edge agent pytest: 43 passed
edge agent mypy: no issues found
edge agent ruff: all checks passed
edge agent compileall: passed
```

### Gateway WebSocket Command Dispatch + ACK Skeleton

Completed and pushed in commit:

```text
97f00e7 Add gateway command dispatch ACK skeleton
```

Implemented:

- backend sends signed in-memory/test-scaffolded command envelopes over the existing gateway WebSocket
- edge agent receives and verifies command envelopes
- edge agent sends `command_ack` for valid commands
- edge agent sends rejected ACKs for invalid/tampered/wrong-gateway commands
- backend receives ACK/reject messages through an app-state test hook
- no DB command queue, mediamtx action, LiveKit publishing, or real camera action

### Gateway Heartbeat Command Fallback Skeleton

Completed and pushed in commit:

```text
8c96180 Add gateway heartbeat command fallback
```

Implemented:

- backend heartbeat response can return signed in-memory/test-scaffolded `pending_commands`
- backend fails closed instead of returning unsigned heartbeat commands when signing is misconfigured
- edge heartbeat runner verifies pending commands
- edge heartbeat runner records accepted/rejected command counts and local verifier errors
- no DB command queue, heartbeat ACK persistence, mediamtx action, LiveKit publishing, or real camera action

### Gateway Command Signing + Agent Verifier

Completed and pushed.

Backend:

- `apps/api/src/cctv_api/gateway/command_signing.py`
- `apps/api/src/cctv_api/gateway/models.py`
- `apps/api/tests/test_gateway_command_signing.py`

Edge agent:

- `apps/cctv-edge/agent/src/panoptix_edge_agent/commands.py`
- `apps/cctv-edge/agent/tests/test_commands.py`

Implemented:

- canonical JSON signing payload
- HMAC-SHA-256 signatures
- base64url signatures
- command expiry validation
- gateway target validation
- constant-time signature compare
- fail-closed verifier behavior

### Edge Gateway Control WebSocket Client

Completed and pushed in commit:

```text
2a641d6 Add edge gateway control websocket client
```

Implemented:

- `apps/cctv-edge/agent/src/panoptix_edge_agent/control.py`
- `apps/cctv-edge/agent/tests/test_control.py`
- `--control-once` in `apps/cctv-edge/agent/src/panoptix_edge_agent/cli.py`
- `PANOPTIX_GATEWAY_CONTROL_WS_PATH` config
- `websockets>=15.0` dependency
- docs/manual testing updates

Behavior:

- agent builds `ws://` or `wss://` URL from `PANOPTIX_API_BASE_URL`
- agent connects outbound to `/api/v1/gateway-control/ws`
- agent sends dev gateway identity header when enabled
- agent receives backend connected hello
- agent validates hello gateway ID
- agent can parse future command envelopes
- agent verifies command signatures
- invalid JSON raises client error
- unsigned/tampered/wrong-gateway commands are rejected
- no command execution yet

## Latest Known Verification Status

Backend from `apps/api/`:

```powershell
$env:PYTHONPATH = "src"; python -m pytest tests/ -v
$env:PYTHONPATH = "src"; python -m ruff check src tests alembic scripts
$env:PYTHONPATH = "src"; python -m mypy src/cctv_api/ --ignore-missing-imports
$env:PYTHONPATH = "src"; python -m compileall src alembic scripts
```

Latest result:

```text
pytest: 93 passed
ruff: all checks passed
mypy: no issues found in 28 source files
compileall: passed
```

Edge agent from `apps/cctv-edge/agent/`:

```powershell
$env:PYTHONPATH = "src"; python -m pytest tests/ -v
$env:PYTHONPATH = "src"; python -m ruff check src tests
$env:PYTHONPATH = "src"; python -m mypy src/panoptix_edge_agent --ignore-missing-imports
$env:PYTHONPATH = "src"; python -m compileall src tests
```

Latest result:

```text
pytest: 43 passed
ruff: all checks passed
mypy: no issues found in 7 source files
compileall: passed
```

## Next Recommended Milestone

Recommended next task:

```text
Audit Row Listing Endpoint
```

Recommended scope:

- add a narrow admin audit row listing scaffold with cursor pagination
- return scrubbed audit rows similar to the export endpoint but as paginated JSON
- keep broad browsing filters, export signing, key rotation UI/workflows, and migrations deferred

Why this is the best next step:

- admin export now returns scrubbed JSONL for offline review
- operators also need an in-browser audit browsing surface for quick inspection
- it stays backend-local and small before command persistence or real camera actions

## Not Implemented Yet

- admin audit row listing endpoint
- audit export signing
- backend command queue table
- persistent dispatch/retry model
- production gateway control reconnect policy/supervision
- command ACK persistence
- mediamtx runtime configuration
- real camera start/stop
- LiveKit publishing orchestration
- frontend UI
- real Cloudflare Access setup
- Google Workspace setup
- Railway deployment
- Neon production database setup
- admin audit row listing endpoint
- audit export signing

## External Accounts Status

Do not require these yet for current local work:

- LiveKit Cloud
- Google Workspace
- Cloudflare Access
- Railway
- Neon
- R2
- Sentry/Better Stack/UptimeRobot

Use local/dev placeholders and fail-closed behavior. Do not ask the user to set up external accounts until local protocol foundations are ready.

## Development Rules

### Mandatory Rules

- Always update `MANUAL_TESTING.md` when behavior or local manual testing steps change.
- Always update `PROGRESS.md` when a milestone is completed or next step changes.
- Update `IMPLEMENTATION_GUIDE.md` for meaningful implementation milestones.
- Add or update tests for every backend or edge behavior change.
- Run backend and edge verification before declaring completion.
- Keep gateway control fail-closed.
- Reject invalid, unsigned, expired, tampered, or wrong-gateway commands.
- Edge gateway must connect outbound to cloud/backend; do not add inbound WAN listeners.
- Do not execute real camera/media actions until protocol skeletons are proven.
- Do not add database persistence for commands until dispatch + ACK protocol behavior is proven.
- Do not hardcode real secrets, API keys, database passwords, school/user data, or production credentials.
- Use dev auth only for local development.
- Preserve the CCTV-only invariant: browser viewers never publish media.
- Keep gateway publish tokens away from browser responses.
- Prefer small, testable milestones over large invasive changes.
- Preserve existing code style and avoid unrelated edits.

### Command Safety Rules

- On Windows PowerShell, use the command working directory instead of putting `cd` inside commands.
- Safe read-only commands can run directly.
- Be careful with destructive commands, dependency installs, migrations, process kills, and network calls.
- If starting a dev server, check for existing servers/processes first.

### Git / Handoff Rules

- Work on branch `backend` unless user explicitly says otherwise.
- After completing a milestone, show `git status --short --branch` and `git diff --stat`.
- Commit message style used recently:
  - `Add gateway command signing and agent verifier`
  - `Add edge gateway control websocket client`

## Important Files And What They Do

### Root Docs

- `README.md`: high-level architecture, invariants, project structure
- `PROGRESS.md`: current completion status and next steps
- `IMPLEMENTATION_GUIDE.md`: implementation history and verification status
- `MANUAL_TESTING.md`: local manual test guide; must be updated with behavior changes
- `CLAUDE.md`: AI coding/development guidance and security invariants
- `.env.example`: environment variable schema; contains placeholders only
- `.gitignore`: ignores local envs, caches, build outputs, and local-only AI/process instructions

### Backend Source

- `apps/api/src/cctv_api/main.py`: FastAPI app factory
- `apps/api/src/cctv_api/core/config.py`: backend settings/env parsing
- `apps/api/src/cctv_api/api/router.py`: versioned API router
- `apps/api/src/cctv_api/api/errors.py`: problem detail errors
- `apps/api/src/cctv_api/api/health.py`: health endpoints
- `apps/api/src/cctv_api/api/gateways.py`: gateway heartbeat, camera status, LiveKit token endpoints, gateway control WebSocket
- `apps/api/src/cctv_api/db.py`: database/session setup
- `apps/api/src/cctv_api/gateway/models.py`: gateway API and command envelope Pydantic models
- `apps/api/src/cctv_api/gateway/command_signing.py`: backend command signing/verifying
- `apps/api/src/cctv_api/models/tables.py`: SQLAlchemy table models
- `apps/api/src/cctv_api/models/enums.py`: DB/domain enums
- `apps/api/src/cctv_api/security/cloudflare_access.py`: CF Access JWT handling
- `apps/api/src/cctv_api/security/dependencies.py`: auth dependencies
- `apps/api/src/cctv_api/security/identity.py`: principal identity model
- `apps/api/src/cctv_api/security/livekit_tokens.py`: LiveKit token helpers
- `apps/api/src/cctv_api/security/policy.py`: RBAC policy helpers
- `apps/api/src/cctv_api/security/session_cookie.py`: signed session cookie helpers
- `apps/api/src/cctv_api/security/sessions.py`: session management
- `apps/api/src/cctv_api/security/stream_access.py`: stream access checks
- `apps/api/src/cctv_api/security/audit.py`: audit writer, scrubbing, HMAC chain, and verifier helpers

### Backend Tests

- `apps/api/tests/conftest.py`: backend pytest setup
- `apps/api/tests/test_gateway.py`: heartbeat, camera status, gateway control WebSocket tests
- `apps/api/tests/test_gateway_command_signing.py`: command signing tests
- `apps/api/tests/test_livekit_tokens.py`: viewer/gateway LiveKit token tests
- `apps/api/tests/test_security.py`: auth/dev-auth tests
- `apps/api/tests/test_sessions.py`: session tests
- `apps/api/tests/test_audit.py`: audit tests
- `apps/api/tests/test_policy.py`: RBAC tests
- `apps/api/tests/test_config.py`: config tests
- `apps/api/tests/test_health.py`: health tests

### Edge Agent Source

- `apps/cctv-edge/agent/src/panoptix_edge_agent/config.py`: agent env config
- `apps/cctv-edge/agent/src/panoptix_edge_agent/client.py`: HTTP JSON client to backend
- `apps/cctv-edge/agent/src/panoptix_edge_agent/runner.py`: heartbeat runner
- `apps/cctv-edge/agent/src/panoptix_edge_agent/commands.py`: command envelope parser/verifier
- `apps/cctv-edge/agent/src/panoptix_edge_agent/control.py`: gateway control WebSocket client
- `apps/cctv-edge/agent/src/panoptix_edge_agent/cli.py`: CLI entrypoint for heartbeat/control checks

### Edge Agent Tests

- `apps/cctv-edge/agent/tests/test_config.py`: agent config tests
- `apps/cctv-edge/agent/tests/test_client.py`: HTTP client tests
- `apps/cctv-edge/agent/tests/test_runner.py`: heartbeat runner tests
- `apps/cctv-edge/agent/tests/test_commands.py`: command verifier tests
- `apps/cctv-edge/agent/tests/test_control.py`: WebSocket control client tests

### Migrations / Database

- `apps/api/alembic/versions/0001_initial_schema.py`: initial schema
- `apps/api/alembic/versions/0002_camera_display_name.py`: camera display name
- `apps/api/alembic/versions/0003_roles_and_grants.py`: roles and grants
- `apps/api/alembic/versions/0004_constraints_and_indexes.py`: constraints/indexes
- `apps/api/alembic/versions/0005_seed_roles.py`: seed roles

### Planning / Architecture Docs

- `docs/index.md`: documentation map
- `docs/planning/secure-cctv-monitoring-system-v4.md`: full system plan
- `docs/planning/cctv-core-functionality-features.md`: core feature list
- `docs/planning/cctv-future-functionality-features.md`: future features
- `docs/planning/tech-stack-simple.md`: simple tech stack explanation
- `docs/implementation/api-reference.md`: API contract
- `docs/implementation/development-setup.md`: local setup
- `docs/implementation/deployment-guide.md`: deployment model
- `docs/implementation/test-plan.md`: QA/test plan
- `docs/implementation/team-raci-checklist.md`: ownership boundaries
- `docs/runbooks/gateway-control-channel.md`: gateway control operations guidance
- `docs/security/threat-model-stride.md`: STRIDE threat model
- `docs/frontend/ux-product-spec.md`: frontend UX/product spec
- `docs/database/database-guardrails.md`: database guardrails

## Project Tree Summary

```text
Panoptix/
  .env.example
  .gitignore
  CLAUDE.md
  CONTRIBUTING.md
  IMPLEMENTATION_GUIDE.md
  MANUAL_TESTING.md
  PROGRESS.md
  README.md
  SECURITY.md
  apps/
    api/
      Dockerfile
      README.md
      pyproject.toml
      alembic/
        versions/
          0001_initial_schema.py
          0002_camera_display_name.py
          0003_roles_and_grants.py
          0004_constraints_and_indexes.py
          0005_seed_roles.py
      scripts/
        db_validate.py
      src/cctv_api/
        main.py
        db.py
        api/
          errors.py
          gateways.py
          health.py
          router.py
        core/
          config.py
        gateway/
          command_signing.py
          models.py
        models/
          base.py
          enums.py
          tables.py
        security/
          audit.py
          cloudflare_access.py
          dependencies.py
          identity.py
          livekit_tokens.py
          policy.py
          session_cookie.py
          sessions.py
          stream_access.py
          users.py
      tests/
        conftest.py
        test_audit.py
        test_cloudflare_access.py
        test_config.py
        test_gateway.py
        test_gateway_command_signing.py
        test_health.py
        test_livekit_tokens.py
        test_policy.py
        test_security.py
        test_sessions.py
    cctv-edge/
      README.md
      agent/
        README.md
        pyproject.toml
        src/panoptix_edge_agent/
          cli.py
          client.py
          commands.py
          config.py
          control.py
          runner.py
        tests/
          test_client.py
          test_commands.py
          test_config.py
          test_control.py
          test_runner.py
      mediamtx/
        README.md
    media-fallback/
      README.md
    web/
      README.md
  database/
    README.md
  docs/
    index.md
    adrs/
      0001-plane-separation.md
      0002-idp-selection.md
      0003-postgres-tier.md
      0004-livekit-fallback.md
      0005-break-glass.md
      0006-reserved.md
      0007-version-pinning.md
      0008-gateway-identity.md
      0009-cctv-only-ingest.md
      0010-origin-binding.md
      0011-bystander-signage-policy.md
      0012-camera-network-design.md
      0013-gateway-hardware-standard.md
      0014-railway-python-control-plane.md
    architecture/
      data-flow.mmd
      erd.mmd
      network-security.mmd
      request-flow.mmd
      sequence-admin-actions.mmd
      sequence-camera-stream.mmd
      sequence-viewer-login.mmd
      system-overview.mmd
    database/
      database-guardrails.md
      README.md
    frontend/
      frontend-guardrails.md
      README.md
      ux-product-spec.md
    implementation/
      api-reference.md
      deployment-guide.md
      development-setup.md
      team-raci-checklist.md
      test-plan.md
    planning/
      cctv-core-functionality-features.md
      cctv-future-functionality-features.md
      secure-cctv-monitoring-system-v4.md
      tech-stack.md
      tech-stack-simple.md
    privacy/
      bystander-signage-template.md
      compliance-readiness-checklist.md
      pia-template.md
      vendor-dpa-template.md
    procurement/
      camera-spec.md
      procurement-guide.md
    reference/
      glossary.md
    review/
      document-review-report-current.md
    runbooks/
      backup-restore.md
      cf-access-rollback.md
      deploy-rollback.md
      gateway-control-channel.md
    security/
      threat-model-stride.md
  infra/
    README.md
    terraform/
      README.md
  scripts/
    README.md
```

## Manual Local Testing Pointers

Use `MANUAL_TESTING.md` as the authoritative local testing guide.

Important local checks currently include:

- backend health
- dev auth behavior
- gateway heartbeat
- gateway camera status
- LiveKit token local/fail-closed checks
- gateway command signing local check
- admin audit export
- backend gateway control WebSocket hello check
- backend gateway control WebSocket dispatch/ACK test
- gateway heartbeat command fallback test
- edge-agent heartbeat `--once`
- edge-agent gateway control `--control-once`
- edge-agent gateway control `--control-loop-once`

## Suggested Prompt For The New IDE/LLM

```text
Read HANDOFF.md and follow its instructions. Then read PROGRESS.md, IMPLEMENTATION_GUIDE.md, MANUAL_TESTING.md, README.md, CLAUDE.md, and the source files related to the next milestone. Confirm the current state and development rules before making changes. The next recommended milestone is Audit Row Listing Endpoint.
```

## Final Notes

The new IDE/LLM will not automatically know every file's full contents. This handoff gives it the map, rules, current state, and read-first order. It should still search and read files on demand before editing.
