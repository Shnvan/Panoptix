# Test Plan

<!-- PE-FIX: Extracted standalone QA plan from council audit findings and main plan §18 -->

This document organizes the main plan test IDs into an implementation-ready QA strategy.

## Test pyramid

| Layer | Target | Scope |
|---|---:|---|
| Unit | 55% | Auth verification, RBAC policy, token scoping, schema validation, command validation. |
| Integration | 30% | FastAPI + Postgres, LiveKit token/webhook flows, gateway identity, audit chain. |
| E2E/browser | 10% | Login shell, dashboard, admin flows, privacy notice, camera state UX. |
| Network/security drills | 5% | T-30, T-45, T-56, gateway no-inbound, fallback LiveKit. |

## Quality gates by phase

| Phase | Required tests |
|---|---|
| Phase 1 scaffold | Secret scan, dependency scan, lint/typecheck, `/health` smoke. |
| Phase 2 auth | T-1..T-4, T-25..T-28, T-47, T-48, T-51, T-56, T-64. |
| Phase 2.5 routing | Same-domain routing smoke, direct-origin denial, strict CSP spike. |
| Phase 3 viewer/audit | T-5, T-6, T-13, T-21, T-23, T-24, T-31, T-32, T-33, T-49, T-50. |
| Phase 4 gateway | T-14, T-35, T-43, T-44, T-55, T-60, T-61, T-62, gateway WebSocket + fallback command test. |
| Phase 5 admin/compliance | T-7..T-11, T-28, T-46, T-54. |
| Phase 6 hardening | T-10..T-12, T-15..T-19, T-29, T-53. |
| Phase 7 fallback | T-37, T-41, T-45. |
| Phase 8 exposure | T-30, T-56, pen-test checklist. |
| Phase 9 SRE | T-20, T-22, T-38, T-39, T-42, T-52. |

## New tests from council execution

| ID | Test | Layer | Acceptance |
|---|---|---|---|
| T-65 | Gateway opens outbound control WebSocket | Integration | Enabled gateway authenticates and receives ping/command stream without inbound port. |
| T-66 | Gateway command heartbeat fallback | Integration | When WebSocket is unavailable, pending start/stop command is delivered on heartbeat response. |
| T-67 | Direct `cctv-web` origin exposes no user data | E2E/security | Direct Railway frontend URL renders harmless shell/redirect and no camera/user/bootstrap JSON. |
| T-68 | Same-domain routing split | E2E | UI paths route to `cctv-web`; `/api/v1/*`, `/health`, webhooks, gateway WebSocket route to `cctv-api`. |
| T-69 | DSR request ledger | Integration | DSR request creates due date, verification status, outcome, and DPA artefact link. |

## Traceability matrix

| Requirement/story | Tests |
|---|---|
| Viewer sees only assigned cameras | T-5, T-13, T-60 |
| Copied stream URL expires | T-6, T-32, T-33 |
| No browser publishing | T-58, T-59, T-60, T-62 |
| Gateway publishes assigned cameras only | T-14, T-60, T-61, T-65, T-66 |
| Origin-binding | T-30, T-56, T-64, T-67, T-68 |
| Audit tamper evidence | T-21, T-23, T-24, T-31, T-49 |
| Backups and restore | T-22 |
| Compliance bundle | T-46, T-69 |
| Break-glass bounded access | T-52 |

## Evidence requirements

Every release candidate must keep:

- CI run URL.
- Test report artifact.
- ZAP report.
- SBOM artifact.
- Browser bundle scan artifact.
- T-30/T-45/T-56 evidence snapshots.
- Restore drill evidence for pilot.
- DPA/signage evidence for real-site deployment.
