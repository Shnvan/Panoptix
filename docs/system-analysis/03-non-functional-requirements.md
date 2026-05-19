# 03 - Non-Functional Requirements

| ID | Category | Requirement | Current support |
|---|---|---|---|
| NFR-001 | Security | Browser users shall authenticate through Cloudflare Access or development-only local auth. | Existing |
| NFR-002 | Security | Authorization shall fail closed when roles, camera ACLs, or gateway assignments are missing. | Existing |
| NFR-003 | Security | Browser clients shall never receive RTSP URLs, camera credentials, gateway publish tokens, raw database URLs, or long-lived auth secrets. | Existing in backend contract; frontend missing |
| NFR-004 | Security | Unsafe browser mutations shall require CSRF protection. | Existing |
| NFR-005 | Security | Security headers shall be applied to success and error responses. | Existing |
| NFR-006 | Security | Gateway routes shall require gateway identity and route/principal ID matching. | Existing |
| NFR-007 | Security | Gateway commands shall be signed and verified before execution. | Existing |
| NFR-008 | Privacy | The system shall support privacy notice acceptance and compliance artifact tracking. | Existing |
| NFR-009 | Privacy | Recording, playback, and snapshots shall remain excluded from MVP unless approved by future ADR/scope change. | Existing in docs, not implemented |
| NFR-010 | Reliability | Gateway command delivery shall support WebSocket plus heartbeat fallback. | Existing |
| NFR-011 | Reliability | Stale commands and due publish stops shall be cleanable by maintenance jobs. | Existing |
| NFR-012 | Reliability | Real camera streaming shall be validated with physical hardware before release. | Missing validation |
| NFR-013 | Performance | Viewer and gateway token issuance shall be rate limited. | Existing |
| NFR-014 | Performance | Live viewing target latency shall be low enough for operational CCTV monitoring. | Needs Team Confirmation for measured target |
| NFR-015 | Maintainability | Backend and edge agent shall have lint, type check, compile, and test gates. | Existing |
| NFR-016 | Maintainability | API behavior shall be documented for frontend and QA handoff. | Existing, with known mismatch |
| NFR-017 | Scalability | Camera, user, gateway, command, and audit list endpoints shall paginate. | Existing where inspected |
| NFR-018 | Data integrity | Database constraints shall prevent duplicate active ACLs and gateway-camera assignments. | Existing |
| NFR-019 | Data integrity | Audit logs shall be tamper-evident through chained HMAC hashes. | Existing |
| NFR-020 | Auditability | Privileged state changes shall write audit events and fail closed where audit is required. | Existing |
| NFR-021 | Compatibility | Backend and edge agent shall run on Python 3.12+. | Existing |
| NFR-022 | Compatibility | Frontend planned stack shall be Next.js/React/TypeScript but not assumed implemented. | Missing implementation |
| NFR-023 | Backup and recovery | R2 backup/restore procedures shall exist and be drillable. | Partially Existing |
| NFR-024 | Backup and recovery | Backup status shall be available from admin API. | Missing |
| NFR-025 | Usability | Viewer UI shall show loading, offline, degraded, unavailable, denied, and no-camera states. | Missing frontend |
| NFR-026 | Usability | Admin UI shall show warnings for destructive or rotation-heavy actions. | Missing frontend |

