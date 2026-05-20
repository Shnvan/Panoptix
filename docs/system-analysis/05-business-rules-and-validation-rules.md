# 05 - Business Rules And Validation Rules

## Business Rules

| Rule ID | Rule type | Rule description | Related module | Current status | Notes |
|---|---|---|---|---|---|
| BR-001 | Access control | New users start with no effective camera access until role and/or camera ACLs are granted. | Auth, Cameras | Confirmed in existing project | User creation happens through auth/user helpers; viewer camera access requires ACL. |
| BR-002 | Access control | Admin routes require the `admin` role. | Admin APIs | Confirmed in existing project | Implemented through `require_role(principal, "admin")`. |
| BR-003 | Access control | Viewer camera access is per user and per camera, not role-only. | Cameras | Confirmed in existing project | Implemented through `camera_acl`. |
| BR-004 | Gateway security | Gateways may publish only cameras with active gateway-camera assignments. | Gateway | Confirmed in existing project | Enforced on gateway ingest token and status routes. |
| BR-005 | Media security | Browsers are viewers only and must not receive gateway publish tokens. | Streaming | Confirmed in existing project | Separate `viewer_subscribe` and `gateway_publish` grants. |
| BR-006 | Credential handling | RTSP camera credentials must stay on the gateway and must not be sent to backend, browser, or audit logs. | Edge agent | Confirmed in existing project | Edge credential handling and docs support this. |
| BR-007 | Auditing | Security-sensitive actions must write audit events. | Audit | Confirmed in existing project | Existing tests cover many audit writes. |
| BR-008 | Audit integrity | Audit writes requiring HMAC keys fail closed when key configuration is placeholder/invalid. | Audit | Confirmed in existing project | Covered by audit tests. |
| BR-009 | Break-glass | Only one active break-glass window may exist; windows are time-bounded and require closure/rotation evidence. | Break-glass | Confirmed in existing project | `BREAK_GLASS_WINDOW_MINUTES` default is 90. |
| BR-010 | Camera lifecycle | Retired cameras must not appear in normal viewer camera lists or receive viewer tokens. | Cameras | Confirmed in existing project | Implemented via `retired_at`. |
| BR-011 | Gateway lifecycle | Disabled gateways must not mint publish tokens or publish assigned cameras. | Gateway | Confirmed in existing project | Implemented through gateway status checks. |
| BR-012 | LiveKit presence | Camera publishing should start on viewer presence and stop when no viewers remain after grace handling. | LiveKit webhooks | Confirmed in existing project | Room-presence command logic and tests exist. |
| BR-013 | Compliance | Privacy notice acceptance must be versioned and idempotent for the current version. | Privacy | Confirmed in existing project | `privacy_notice_acceptances` primary key includes user and version. |
| BR-014 | Backup visibility | Admins should see backup status in the product. | Operations | Confirmed in existing project | Endpoint reports database-known readiness from `backup_runs`; restore drill evidence remains operational. |
| BR-015 | DSR workflow | DSR requests should be tracked through receipt, verification, due date, outcome, and artifact link. | Compliance | Implemented backend API and frontend API wiring | Production browser smoke is pending. |

## Validation Rules

| Rule ID | Rule type | Rule description | Related module | Current status | Notes |
|---|---|---|---|---|---|
| VR-001 | Input validation | UUID path and cursor values must parse as UUIDs where required. | APIs | Confirmed in existing project | Invalid IDs return problem details. |
| VR-002 | Input validation | List endpoint limits are bounded, commonly `1..200` or `1..500`. | APIs | Confirmed in existing project | Pydantic/FastAPI query validation. |
| VR-003 | Input validation | Role actions must be `grant` or `revoke`. | Admin users | Confirmed in existing project | `RoleActionRequest` pattern. |
| VR-004 | Input validation | Disable, break-glass, fallback, signage, and MFA actions require reason/evidence text within bounded lengths. | Admin APIs | Confirmed in existing project | Pydantic `Field` constraints. |
| VR-005 | Input validation | Camera `source_type` must match actual enum values. | Cameras | Confirmed in existing project | Actual enum: `rtsp`, `nvr_rtsp`, `onvif_profile_s`, `onvif_profile_t`, `synthetic_rtsp_test_source`. |
| VR-006 | Documentation consistency | Frontend backend-status doc lists the same camera source types as the backend enum. | Documentation | Confirmed in current docs | Corrected to match code. |
| VR-007 | Input validation | LiveKit room names must be unique. | Cameras | Confirmed in existing project | Checked by API and DB unique constraint. |
| VR-008 | Input validation | Command expiry must be bounded. | Commands | Confirmed in existing project | Current docs indicate default 300 and bounds 10-3600. |
| VR-009 | Input validation | Command status filters must use `pending`, `accepted`, `rejected`, `expired`, or `cancelled`. | Commands | Confirmed in existing project | Enum and tests exist. |
| VR-010 | Security validation | Gateway request route ID must match authenticated gateway principal ID. | Gateway | Confirmed in existing project | `_require_matching_gateway`. |
| VR-011 | Security validation | LiveKit webhook requests must pass authorization, body hash, timestamp freshness, and replay checks. | LiveKit webhooks | Confirmed in existing project | Covered in webhook tests. |
| VR-012 | Rate limit | Viewer token, gateway ingest token, and admin mutations are rate limited. | Security | Confirmed in existing project | Configured in `.env.example`. |
| VR-013 | Edge validation | Per-camera RTSP credential files must be valid JSON, versioned, and use valid RTSP settings. | Edge agent | Confirmed in existing project | Covered by `test_camera_credentials.py`. |
| VR-014 | Edge validation | Linux credential files must use restrictive permissions. | Edge agent | Confirmed in existing project | 0600 check; skipped on Windows. |

## Rules Needing Team Confirmation

| Item | Reason |
|---|---|
| Auditor and SuperAdmin as separate roles | UX docs mention personas, but code seeds only `admin` and `viewer`. |
| Exact frontend status labels and display copy | UX docs define message intent, but no UI implementation exists. |
| DSR workflow frontend ownership | Backend API and frontend wiring exist; browser workflow still needs smoke and E2E evidence. |
| Backup status acceptance criteria | Endpoint is stubbed and R2 operations are documented separately. |

