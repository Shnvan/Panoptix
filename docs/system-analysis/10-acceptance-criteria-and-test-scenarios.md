# 10 - Acceptance Criteria And Test Scenarios

## Existing Test Coverage Summary

The repository contains extensive backend and edge-agent tests:

| Area | Evidence | Coverage status |
|---|---|---|
| Backend API/security | `apps/api/tests/` | Existing |
| Edge agent | `apps/cctv-edge/agent/tests/` | Existing |
| Manual testing | `MANUAL_TESTING.md` | Existing |
| QA strategy | `docs/implementation/test-plan.md` | Existing |
| Browser E2E | No Playwright app tests found | Missing |
| Load/security artifacts | k6/ZAP/SBOM noted as future gates | Missing |

## Acceptance Criteria

| ID | Criteria | Status |
|---|---|---|
| AC-001 | Unauthenticated browser requests to protected routes are rejected. | Existing |
| AC-002 | Authenticated users can retrieve their principal profile. | Existing |
| AC-003 | Viewers see only active cameras with active ACLs. | Existing |
| AC-004 | Viewer tokens are denied for missing ACLs, retired cameras, disabled users, or invalid camera IDs. | Existing |
| AC-005 | Gateway routes reject unauthenticated, disabled, mismatched, or unassigned gateway requests. | Existing |
| AC-006 | Admin-only endpoints reject non-admin users. | Existing |
| AC-007 | Admin camera/gateway/user changes write audit rows where required. | Existing |
| AC-008 | Audit verification detects tampering or invalid key conditions. | Existing |
| AC-009 | Gateway command queue supports enqueue, list, cancel, expire, deliver, and ACK. | Existing |
| AC-010 | Edge agent rejects tampered, expired, or wrong-gateway commands. | Existing |
| AC-010a | Admin user invite creates local role state, sends a GitHub organization invitation, and writes sanitized audit metadata. | Existing |
| AC-011 | Frontend displays viewer/admin workflows using backend APIs. | Missing |
| AC-012 | Real camera publishes through edge agent to LiveKit with production-like settings. | Partially Existing |
| AC-013 | Backup status is visible to admins. | Missing |
| AC-014 | DSR workflow is usable end to end. | Missing |

## Test Scenarios

| Test ID | Scenario | Given | When | Then | Existing evidence |
|---|---|---|---|---|---|
| TS-001 | Protected route rejects anonymous user | No valid identity | Request `/api/v1/me` | Response is unauthorized | `test_security.py` |
| TS-002 | Viewer gets assigned cameras | User has active ACL | Request `/api/v1/cameras` | Only assigned active cameras return | `test_cameras.py` |
| TS-003 | Viewer token denied without ACL | User lacks camera ACL | Request view token | Response is forbidden | `test_livekit_tokens.py`, `test_cameras.py` |
| TS-004 | Admin creates camera | Admin is authenticated | Submit valid camera body | Camera row and audit event exist | `test_cameras.py` |
| TS-005 | Invalid source type rejected | Admin submits invalid `source_type` | Create camera | `source-type-invalid` error | `test_cameras.py` |
| TS-006 | Gateway cannot publish unassigned camera | Gateway authenticated but assignment missing | Request ingest token | Forbidden response and audit where applicable | `test_gateway.py` |
| TS-007 | Gateway command signing rejects tampering | Command payload/signature altered | Edge verifies command | Verification error | `test_commands.py` |
| TS-008 | LiveKit webhook replay rejected | Duplicate signature/body received | Webhook called twice | Second request rejected | `test_livekit_webhooks.py` |
| TS-009 | Break-glass lifecycle works | Admin opens window | Open then close | Window and audit records exist | `test_break_glass.py` |
| TS-010 | Audit chain tampering detected | Audit row is modified | Verify chain | Invalid result returned | `test_audit.py` |
| TS-011 | Disable user removes access | Admin disables user | User requests token/session | Access denied and sessions revoked | `test_admin_user_management.py`, `test_audit.py` |
| TS-011a | Invite user through GitHub | Admin submits email and role names | Backend calls GitHub invite client | Local user/roles and sanitized audit row exist | `test_stub_endpoints.py` |
| TS-012 | Disable camera stops viewers | Camera has active room viewers | Admin disables camera | Camera retired and viewer participants removed/skipped safely | `test_cameras.py`, `test_livekit_rooms.py` |
| TS-013 | Disable gateway stops publishers | Gateway has assigned rooms | Admin disables gateway | Gateway disabled and publisher participants removed/skipped safely | `test_admin_gateways.py`, `test_livekit_rooms.py` |
| TS-014 | Privacy notice acceptance idempotent | User accepts current version | Repeat acceptance | Accepted status remains valid | `test_privacy_admin_users.py` |
| TS-015 | Frontend viewer dashboard | Frontend app exists | User logs in and opens dashboard | Grid, empty/error states, and LiveKit player render correctly | Missing |
| TS-016 | Real camera publish | Real camera and gateway configured | Viewer joins room | Gateway publishes camera stream to LiveKit | Partially Existing smoke scaffolds |
| TS-017 | Backup status | Backup run exists | Admin opens backup status | Latest status and restore checks display | `test_backup_status.py` |
| TS-018 | DSR workflow | DSR request received | Admin records lifecycle | Request status/outcome and artifact link persist | Missing |

## QA Recommendations

- Add Playwright coverage when `apps/web/` is implemented.
- Add hardware-backed smoke tests for real RTSP camera to LiveKit publishing.
- Keep restore drill evidence as a manual operations artifact until backup automation records real rows.
- Add DSR API tests if the team approves DSR workflow scope.
- Keep manual evidence for staging health, restore drills, and production readiness gates.

