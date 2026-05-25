# 01 - System Analysis

## Project Overview

Panoptix is a secure live-view CCTV monitoring system. It connects fixed IP cameras to authenticated browser viewers through a three-plane architecture:

| Plane | Current evidence | Status |
|---|---|---|
| Control plane | FastAPI backend in `apps/api/src/cctv_api`, SQLAlchemy models, Alembic migrations, tests, Railway staging docs | Existing |
| Media plane | LiveKit Cloud token minting, webhook receiver, room-presence command enqueue, fallback mode flag | Partially Existing |
| Camera plane | Edge agent, outbound heartbeat/control, FFmpeg/LiveKit scaffolds, mediamtx local config | Partially Existing |
| Frontend | React/Vite app in `apps/web`, merged coworker frontend branch, frontend docs | V1 integrated / production incomplete |

The system is designed for browser viewing only. Browser, phone, and laptop camera publishing are explicitly out of scope.

## System Purpose

Panoptix enables authorized users to view assigned CCTV cameras while keeping camera credentials and camera network access outside the browser and outside the public internet. The backend enforces identity, roles, camera ACLs, session controls, audit logging, gateway coordination, and compliance-related records.

## Objectives

- Provide authenticated browser access to assigned live CCTV cameras.
- Enforce admin-only management of users, cameras, gateways, audit, break-glass, compliance artifacts, and maintenance operations.
- Keep RTSP camera credentials on the local gateway only.
- Deliver viewer and gateway LiveKit tokens with distinct, short-lived grants.
- Maintain tamper-evident audit records for security-sensitive actions.
- Support developer, frontend, database, QA, and operations handoff with clear documented contracts.

## Scope

| Area | Scope statement | Status |
|---|---|---|
| Viewer camera list and token access | Backend returns only active cameras with active ACLs and mints subscriber tokens | Existing |
| Admin camera, gateway, and user onboarding | Backend supports camera/gateway lifecycle control and GitHub-backed user invites | Existing |
| Gateway command/control | Persistent command queue plus WebSocket and heartbeat fallback | Existing |
| Edge publishing | Agent verifies commands and has LiveKit/FFmpeg scaffolds; real hardware validation pending | Partially Existing |
| Frontend | React/Vite frontend V1 exists for viewer/admin workflows; production smoke and LiveKit playback remain pending | Partially Existing |
| Recording/playback/snapshots | Excluded from MVP | Out of scope |
| Backup operations | R2 provisioning docs, scripts, and database-known backup status API exist; restore drill evidence pending | Partially Existing |

## Limitations

- The merged React/Vite frontend is integrated but still needs browser smoke evidence, Playwright coverage, and real LiveKit subscriber playback.
- Real camera onboarding and production camera-to-LiveKit publishing require physical hardware.
- Backend DSR workflow APIs exist and frontend DSR API wiring is present; production browser smoke is still pending.
- Self-hosted LiveKit fallback is represented by docs/configuration and a mode switch, not full operations.

## Users And Roles

| Actor | Description | Evidence | Status |
|---|---|---|---|
| Viewer | Authenticated user who can view assigned cameras only | `GET /api/v1/cameras`, camera ACL checks, `viewer` role seed | Existing |
| Admin | Manages users, cameras, gateways, audit, break-glass, compliance, and maintenance | Admin routes require `admin` role | Existing |
| Gateway | Machine identity for on-site edge agent | Gateway auth dependencies, service token hash, gateway routes | Existing |
| Auditor | Persona in UX docs for audit/compliance review | Frontend UX docs; no separate code role found | Needs Team Confirmation |
| SuperAdmin | Persona for high-risk recovery | UX docs; no distinct database/code role found | Needs Team Confirmation |

## Existing Modules

- Authentication and identity: Cloudflare Access verification, local dev auth, signed sessions.
- Authorization: role checks plus camera ACLs and gateway-camera assignments.
- Camera management: create, list, detail, disable/retire, user ACL grant/revoke.
- Gateway management: create, list, detail, update, disable, enable, rotate credentials, assign cameras.
- User onboarding: GitHub organization invite plus local Panoptix role preparation.
- Gateway command queue: enqueue, list, cancel, expire, ACK processing, signed envelopes.
- LiveKit integration: viewer tokens, gateway tokens, webhooks, room-presence-driven start/stop.
- Audit: HMAC-chained audit rows, verification, listing, export.
- Privacy and compliance: privacy notice acceptance, DPA export, DSR workflow tracking, signage attestation.
- Operations: health checks, maintenance job, runbooks, CI/security scans, backup scripts.
- Edge agent: heartbeat, command verification, command execution, supervisor, media scaffolds.

## Proposed Or Missing Modules

| Module | Rationale | Status |
|---|---|---|
| Frontend web application | Required for viewer dashboard and admin workflows | V1 Integrated / Production Incomplete |
| Real hardware onboarding workflow | Required to validate real camera publishing | Partially Existing |
| DSR workflow UI | Backend DSR API exists and frontend DSR API wiring exists; production browser smoke is still pending | Partially Existing |
| Backup worker and restore drill evidence | Status endpoint reads `backup_runs`, but production backup artifacts and restore evidence are pending | Partially Existing |
| Production self-hosted LiveKit fallback runbook/execution | Fallback mode exists but full operations remain future work | Partially Existing |

## Main Workflows

```mermaid
flowchart LR
  Viewer["Viewer"] -->|"Cloudflare Access / session"| API["FastAPI control plane"]
  API -->|"ACL-filtered cameras"| Viewer
  Viewer -->|"View token request"| API
  API -->|"Subscriber token"| LiveKit["LiveKit Cloud"]
  LiveKit -->|"participant webhook"| API
  API -->|"start/stop command"| Gateway["Edge gateway agent"]
  Gateway -->|"RTSP pull"| Camera["IP camera"]
  Gateway -->|"publish stream"| LiveKit
```

## Assumptions

- The current branch represents the intended current project state.
- Existing dirty files outside `docs/system-analysis/` are unrelated and should not be reverted.
- Frontend and database ownership boundaries in existing docs remain authoritative unless the team changes them.

## Risks

| Risk | Impact | Recommendation |
|---|---|---|
| Frontend production readiness incomplete | Users can test the merged UI, but production acceptance still needs LiveKit playback, browser smoke, and E2E coverage | Finish frontend production hardening against the documented API contract |
| Hardware not onboarded | Real live camera behavior remains unproven | Procure and validate with supported RTSP cameras |
| Documentation/code drift | Frontend or QA may build against wrong fields | Treat code and API tests as authoritative and update docs |
| DSR workflow needs browser evidence | Compliance case tracking should not be treated as production-ready until the merged UI flow is smoke-tested | Smoke-test DSR case management against the implemented backend routes |

## Constraints

- Browser must never publish media.
- Gateway connections must remain outbound-only.
- RTSP credentials must stay on the gateway.
- Gateway publish tokens must not be returned to browsers.
- Security-sensitive actions must be audited.
- Real secrets must not be committed.

## Recommendations

- Use `docs/system-analysis/` as a handoff index for analysts, QA, frontend, and backend developers.
- Fix the documented camera source type mismatch in `docs/frontend/BACKEND_STATUS.md`.
- Complete frontend LiveKit playback, browser smoke, and E2E tests before MVP acceptance.
- Treat real hardware onboarding as a release gate for camera streaming.
- Keep Cloudflare Access policies aligned with the configured GitHub organization/team used for invites.

## Project Inventory Summary

| Inventory item | Found evidence |
|---|---|
| Important folders | `apps/api`, `apps/cctv-edge`, `apps/web`, `database`, `docs`, `infra`, `scripts`, `.github` |
| Important source files | `apps/api/src/cctv_api/api/router.py`, `apps/api/src/cctv_api/api/gateways.py`, `apps/api/src/cctv_api/models/tables.py`, `apps/cctv-edge/agent/src/panoptix_edge_agent/cli.py` |
| Existing documentation | `docs/index.md`, planning docs, API reference, test plan, frontend docs, runbooks, security docs, ADRs |
| Database files | `apps/api/alembic/versions/*.py`, `apps/api/src/cctv_api/models/*.py`, `docs/architecture/erd.mmd` |
| UI files | React/Vite app under `apps/web/`; frontend specs in `docs/frontend/` |
| API files | FastAPI routers under `apps/api/src/cctv_api/api/` |
| Reports/export logic | Audit export, DPA export, health dashboard data, backup scripts/status API |
| Features confirmed from code | Auth, sessions, CSRF, RBAC, camera ACL, gateway control, LiveKit tokens/webhooks, audit, break-glass, DPA/signage |
| Features documented but not found as complete code | Real LiveKit browser playback, real hardware publishing evidence, full self-hosted fallback |
| Features found in code but under-documented or inconsistent | No current camera source-type drift found; `docs/frontend/BACKEND_STATUS.md` now matches `CameraSourceType` |

