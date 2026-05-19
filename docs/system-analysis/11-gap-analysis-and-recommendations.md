# 11 - Gap Analysis And Recommendations

| Gap ID | Description | Evidence or related file | Impact | Recommendation | Priority | Status |
|---|---|---|---|---|---|---|
| GAP-001 | Frontend application is not implemented. | `apps/web/README.md` | Users cannot operate the system through a browser UI. | Build viewer dashboard, admin screens, audit/compliance screens, and session UI. | Critical | Open |
| GAP-002 | Real camera onboarding and hardware validation are pending. | `PROGRESS.md`, edge-agent README | Live CCTV workflow is not fully proven end to end. | Procure supported cameras/gateway hardware and run real RTSP-to-LiveKit tests. | Critical | Open |
| GAP-003 | Edge agent has real publishing scaffolds, but production camera publishing remains partially validated. | `apps/cctv-edge/agent/src/`, tests | Stream reliability with real hardware remains unknown. | Add hardware smoke checklist and acceptance evidence. | High | Open |
| GAP-005 | Backup restore drill evidence is not recorded. | `GET /api/v1/admin/backups/status`, `backup_runs`, `docs/runbooks/backup-restore.md` | Admin can see database-known backup status, but production restore confidence still needs a real drill. | Run an isolated restore drill and record evidence without storing secrets or backup contents in Git. | High | Open |
| GAP-006 | DSR workflow tables exist but full API/UI workflow was not found. | `DsrRequest` model | Compliance workflow may be incomplete. | Define DSR scope and implement routes/UI if required. | Medium | Open |
| GAP-007 | Frontend backend-status doc lists wrong camera source types. | `docs/frontend/BACKEND_STATUS.md`, `CameraSourceType` enum | Frontend may submit invalid values or reject valid values. | Correct docs and generate frontend constants from backend contract. | High | Open |
| GAP-008 | Separate Auditor/SuperAdmin personas are documented but not implemented as roles. | `docs/frontend/ux-product-spec.md`, role seed migration | Role expectations may drift from actual authorization. | Confirm whether personas map to `admin` or require new roles. | Medium | Needs Team Confirmation |
| GAP-009 | Self-hosted LiveKit fallback is not fully operationalized. | ADRs/runbooks/config | Fallback readiness may be overestimated. | Mark fallback as operational future work until tested. | Medium | Open |
| GAP-010 | Browser E2E tests are missing. | No frontend app/tests found | UI regressions cannot be caught automatically. | Add Playwright tests with frontend implementation. | High | Open |
| GAP-011 | Load, ZAP, SBOM, and browser bundle scan artifacts are not implemented. | `requirements.md`, test plan | Pilot/production assurance may be incomplete. | Add gates when frontend and production release hardening begin. | Medium | Open |
| GAP-014 | Backup status API is database-only. | `BackupRun`, backup runbooks | Product status depends on backup job rows and does not directly verify R2 object availability. | Keep R2 verification in the backup job/runbook or add a dedicated worker-side verification path. | Medium | Open |
| GAP-015 | Site signage timestamp and DPA artifact both represent signage evidence. | `Site`, `DpaArtifact`, signage route | Source-of-truth ambiguity. | Decide whether route updates both records or artifact only. | Low | Needs Team Confirmation |

## Recently Closed Gaps

| Former Gap ID | Resolution |
|---|---|
| GAP-004 | GitHub-backed user invite is implemented through `POST /api/v1/admin/users/invite`; it invites by email to the configured GitHub organization/team, prepares local roles, and writes audit rows. |
| GAP-012 | Camera update/rename and re-enable routes are implemented as `PATCH /api/v1/admin/cameras/{camera_id}` and `POST /api/v1/admin/cameras/{camera_id}/enable`, with admin authorization and audit rows. |
| GAP-013 | Gateway update and re-enable routes are implemented as `PATCH /api/v1/admin/gateways/{gateway_id}` and `POST /api/v1/admin/gateways/{gateway_id}/enable`, with credential rotation kept separate from metadata updates. |

## Remaining Questions For The Team

- Should Auditor and SuperAdmin become explicit roles or remain personas under `admin`?
- What is the expected backup status response and operational source of truth?
- Should DSR handling be product-managed or handled manually with only database records?
- Which camera/NVR models will be accepted for the first hardware onboarding test?
- Should frontend validation constants be generated from OpenAPI to avoid source-type drift?

## Recommended Future Enhancements

- OpenAPI export and TypeScript client generation.
- Frontend Playwright test suite.
- Hardware-in-the-loop camera streaming smoke tests.
- Backup status dashboard and restore-drill evidence view.
- DSR case management UI and audit trail.
- Production observability dashboard and alerting integration.
- Explicit role model review before adding Auditor/SuperAdmin privileges.

## Needs Team Confirmation Items

- Auditor/SuperAdmin role mapping.
- DSR workflow ownership and scope.
- Backup status response shape.
- Signage attestation source of truth.

