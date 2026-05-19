# 12 - Requirements Traceability Matrix

## Functional Traceability

| Requirement | Business rules | Screens/pages | API endpoints | Database entities | Source files/classes | Test scenarios | Status |
|---|---|---|---|---|---|---|---|
| FR-001 Auth required | BR-001 | Login/access shell | `/api/v1/me`, protected routes | `users`, `sessions` | `security/dependencies.py` | TS-001 | Complete |
| FR-007 Viewer camera list | BR-003, BR-010 | Viewer dashboard | `GET /api/v1/cameras` | `cameras`, `camera_acl` | `api/router.py` | TS-002 | Complete |
| FR-008 Viewer token | BR-005 | Camera tile/player | `GET /api/v1/cameras/{id}/view-token` | `stream_grants`, `cameras`, `camera_acl` | `security/livekit_tokens.py` | TS-003 | Complete |
| FR-012 Admin user list | BR-002 | Admin users | `GET /api/v1/admin/users` | `users`, `user_roles`, `roles` | `api/router.py` | TS-011 | Complete |
| FR-013 Role grant/revoke | BR-002 | Admin users | `POST /api/v1/admin/users/{id}/role` | `user_roles`, `roles` | `api/router.py` | TS-011 | Complete |
| FR-014 Disable user | BR-002, BR-007 | Admin users | `POST /api/v1/admin/users/{id}/disable` | `users`, `sessions`, `audit_log` | `api/router.py`, `livekit_rooms.py` | TS-011 | Complete |
| FR-016 Invite user | BR-002 | Admin users | `POST /api/v1/admin/users/invite` | `users`, `user_roles`, `audit_log` | `api/router.py`, `github_invites.py` | TS-011a | Complete |
| FR-017 Create camera | BR-002 | Admin cameras | `POST /api/v1/admin/cameras` | `cameras` | `api/router.py` | TS-004, TS-005 | Complete |
| FR-019 Camera ACL | BR-003 | Admin cameras | `POST /api/v1/admin/cameras/{id}/acl` | `camera_acl`, `users` | `api/router.py` | TS-002, TS-003 | Complete |
| FR-020 Disable camera | BR-010 | Admin cameras | `POST /api/v1/admin/cameras/{id}/disable` | `cameras`, `audit_log` | `api/router.py`, `livekit_rooms.py` | TS-012 | Complete |
| FR-021 Camera lifecycle update | BR-002, BR-010 | Admin cameras | `PATCH /api/v1/admin/cameras/{id}`, `POST /api/v1/admin/cameras/{id}/enable` | `cameras`, `audit_log` | `api/router.py` | TS-004, TS-012 | Complete |
| FR-023 Create gateway | BR-004, BR-006 | Admin gateways | `POST /api/v1/admin/gateways` | `edge_gateways` | `api/router.py`, `service_tokens.py` | TS-006 | Complete |
| FR-025 Gateway lifecycle update | BR-004, BR-010 | Admin gateways | `PATCH /api/v1/admin/gateways/{id}`, `POST /api/v1/admin/gateways/{id}/disable`, `POST /api/v1/admin/gateways/{id}/enable` | `edge_gateways`, `audit_log` | `api/router.py`, `livekit_rooms.py` | TS-006, TS-012 | Complete |
| FR-027 Gateway assignment | BR-004 | Admin gateways | `POST /api/v1/admin/gateways/{id}/cameras` | `gateway_camera_assignments` | `api/router.py` | TS-006 | Complete |
| FR-031 Gateway commands | BR-004, BR-007 | Gateway commands | `/admin/gateways/{id}/commands*` | `gateway_command_queue` | `gateway/command_queue.py` | TS-007 | Complete |
| FR-036 Audit chain | BR-007, BR-008 | Audit log | `/admin/audit*` | `audit_log`, `audit_hmac_keys` | `security/audit.py` | TS-010 | Complete |
| FR-038 Break-glass | BR-009 | Admin recovery | `/admin/break-glass/*` | `break_glass_usage`, `audit_log` | `security/break_glass.py` | TS-009 | Complete |
| FR-041 DPA/signage | BR-013 | Compliance | `/admin/dpa/export`, `/admin/sites/{id}/signage-attest` | `dpa_artifacts`, `sites` | `api/router.py` | TS-014 | Partial |
| FR-042 DSR workflow | BR-015 | DSR ledger | `/api/v1/admin/dsr-requests*` | `dsr_requests`, `audit_log` | `api/router.py`, `models/tables.py` | TS-018 | Backend Complete |
| FR-043 Backup status | BR-014 | Backup status | `/admin/backups/status` | `backup_runs` | `api/router.py` | TS-017 | Complete |
| FR-011 Frontend dashboard | BR-003, BR-005 | Viewer dashboard | Uses browser APIs | N/A | `apps/web/README.md` only | TS-015 | Missing |
| FR-030 Real camera publish | BR-004, BR-006, BR-012 | Viewer dashboard | Gateway + LiveKit | `stream_grants`, `camera_publish_states` | edge media modules | TS-016 | Partial |

## Validation Traceability

| Validation rule | Requirement | Source evidence | Test scenario | Status |
|---|---|---|---|---|
| VR-001 UUID validation | FR-007, FR-008, FR-023, FR-031 | Router parse helpers | TS-003, TS-006 | Complete |
| VR-003 Role action values | FR-013 | `RoleActionRequest` | TS-011 | Complete |
| VR-005 Camera source enum | FR-017 | `CameraSourceType` | TS-005 | Complete |
| VR-006 Source type docs mismatch | FR-017 | `BACKEND_STATUS.md` vs enum | Recommended doc test | Partial |
| VR-010 Gateway route/principal match | FR-028 | `api/gateways.py` | TS-006 | Complete |
| VR-011 LiveKit webhook signature/replay | FR-035, FR-030 | `api/livekit_webhooks.py` | TS-008 | Complete |
| VR-013 Edge credential validation | FR-030 | `camera_credentials.py` | TS-016 | Partial |

## Non-Functional Traceability

| NFR | Related requirements | Evidence | Status |
|---|---|---|---|
| NFR-001 to NFR-007 Security | FR-001 to FR-006, FR-023 to FR-035 | Security modules, tests, `.env.example`, docs | Complete |
| NFR-010 Reliability | FR-031 to FR-035 | Command queue, WebSocket, heartbeat fallback tests | Complete |
| NFR-012 Hardware validation | FR-022, FR-030 | Edge smoke scaffolds, progress docs | Partial |
| NFR-015 Maintainability | All implemented modules | CI workflow, pyproject files, tests | Complete |
| NFR-023 Backup/recovery | FR-043 | Runbooks, scripts, R2 docs | Partial |
| NFR-025 UI usability | FR-011 | Frontend specs only | Missing |

