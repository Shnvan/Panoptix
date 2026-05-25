# 09 - Report Requirements

## Existing Reports, Exports, And Dashboards

| Report/export | Purpose | User | Filters | Output format | Source data | Status |
|---|---|---|---|---|---|---|
| Audit list | Review security-sensitive events | Admin | Cursor, limit, action | JSON API | `audit_log` | Existing |
| Audit verification | Verify HMAC audit chain integrity | Admin | `start_id`, `end_id` | JSON API | `audit_log`, `audit_hmac_keys` | Existing |
| Audit export | Export scrubbed signed audit evidence | Admin/Auditor | `start_id`, `end_id` | Signed JSON response | `audit_log` | Existing |
| Admin dashboard summary | View aggregate operational counts | Admin | None found | JSON API | cameras, gateways, users, commands, publish states | Existing |
| Deep health | View DB, LiveKit, and gateway freshness | Admin | None found | JSON API | DB probe, LiveKit probe, gateway rows | Existing |
| DPA artifact export | Export compliance artifact metadata | Admin/Auditor | Optional kinds | JSON API | `dpa_artifacts` | Existing |
| Signage attestation result | Record and return signage artifact metadata | Admin | Site ID | JSON API | `sites`, `dpa_artifacts` | Existing |
| Backup status | Show backup health/status | Admin | None | JSON API | `backup_runs` | Existing |
| DSR ledger/report | Track data subject requests | Admin/Auditor | API list/detail available | Backend implemented; frontend wiring present; smoke pending | `dsr_requests` | Partially Existing |

## Report Field Requirements

| Report/export | Required fields |
|---|---|
| Audit list | ID, timestamp, actor type, actor ID, action, resource, IP, user agent, scrubbed payload |
| Audit verification | Valid flag, checked row count, error details when invalid |
| Audit export | Format, manifest, row items, digest/signature metadata |
| Admin dashboard | Camera total/active/retired, gateway total/enabled/disabled, user total/active/disabled, pending commands, active publishing |
| Deep health | Overall status, DB status, LiveKit status, gateway freshness status |
| DPA export | Artifact ID, kind, R2 path, signed hash, effective/superseded timestamps |
| Backup status | Recommended: last successful backup, last failed backup, size, SHA-256, restore validation flags, upload status, next scheduled check |
| DSR ledger | Recommended: requester, subject type, request type, site/scope, received/due/verified dates, status, outcome, artifact link |

## Report Gaps

| Gap | Impact | Recommendation |
|---|---|---|
| Restore drill evidence not recorded | Admin can inspect `backup_runs`, but production restore confidence still needs drill evidence | Run an isolated restore drill and record evidence without storing secrets or backup contents in Git |
| DSR report needs browser evidence | Compliance staff need a verified browser workflow | Smoke-test DSR UI backed by existing routes before relying on frontend for DSR handling |
| Audit UI missing | Existing export/list APIs are not accessible to users through product UI | Build admin audit screen in frontend |
| DPA export likely returns metadata, not full legal documents | Team may overestimate compliance completeness | Clarify whether artifacts are generated, uploaded, or manually maintained |

