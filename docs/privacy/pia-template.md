# Privacy Impact Assessment Template

This template supports a lightweight MVP PIA and a fuller pilot PIA for the secure CCTV monitoring system. It is not legal advice and must be reviewed by the DPO and Philippine data-privacy counsel before pilot deployment.

## 1. Assessment metadata

| Field | Value |
|---|---|
| Project | Secure CCTV Monitoring System |
| Assessment type | Lightweight MVP / Full pilot |
| Version | `<version>` |
| Date | `<date>` |
| Controller | `<Controller>` |
| DPO | `<DPO name/email>` |
| System owner | `<name>` |
| Counsel reviewed | Yes / No / Pending |
| Sites covered | `<site list>` |
| Minor-site deployment | Yes / No |

## 2. Processing summary

Describe the processing in plain language:

```text
The system provides authenticated live viewing of fixed IP camera/NVR feeds through an edge gateway and LiveKit media plane. MVP does not record footage, take snapshots, provide playback, or support browser/phone/laptop camera publishing. Browsers are viewers only.
```

## 3. Purpose and lawful basis

| Purpose | Data subjects | Data categories | Lawful basis / justification |
|---|---|---|---|
| Live CCTV monitoring | Bystanders, site occupants | Live video in frame | `<basis>` |
| User access control | Operators/admins | Email, IdP subject, roles, sessions | `<basis>` |
| Audit and security | Operators/admins/gateways | Audit events, IP/user-agent metadata | `<basis>` |
| System monitoring | Operators/admins/gateways | Scrubbed logs/alerts | `<basis>` |
| Compliance evidence | Bystanders/site admins | Signage attestations, DPA artefacts | `<basis>` |

## 4. Data inventory

| Data item | Source | Storage location | Retention | Access |
|---|---|---|---|---|
| User email | IdP / CF Access | Postgres | Account lifetime + policy | Admins |
| IdP subject | CF Access JWT | Postgres | Account lifetime + policy | Admins |
| Session metadata | Browser | Postgres | 30 days | Admin/security |
| Camera metadata | Admin entry | Postgres | Camera lifetime + audit retention | Admins/viewers as authorized |
| RTSP credentials | Site camera config | Gateway only | Until rotation/removal | Gateway service user only |
| Live media | Camera/gateway | Transient in LiveKit | Not recorded in MVP | Authorized viewers only |
| Audit log | App/gateway/admin events | Postgres + archive | 365 days active, then archive/prune | Admin/auditor |
| Backups | Postgres export | R2 encrypted | Per backup policy | Ops/admin |
| Signage attestation | Admin evidence | Postgres / artefact store | Policy-defined | Admin/DPO |
| Error telemetry | App/runtime | Sentry/Better Stack | Vendor policy | Ops |

## 5. Data-flow summary

1. Browser authenticates through Cloudflare Access and selected IdP.
2. `cctv-api` verifies CF JWT and establishes an app session.
3. Viewer requests a camera view token.
4. `cctv-api` checks camera ACL and mints a short-lived viewer-subscribe token.
5. Browser subscribes to LiveKit directly.
6. Gateway receives gateway-publish token only for assigned cameras.
7. Gateway pulls RTSP from cameras on the camera VLAN and publishes to LiveKit.
8. LiveKit sends signed webhooks to `cctv-api`.
9. `cctv-api` writes audit events and operational metadata to Postgres.
10. Backups/audit archives are encrypted and stored in R2 with object lock.

## 6. Privacy controls

| Control | Description | Evidence |
|---|---|---|
| CCTV-only ingest | No browser/phone/laptop camera publishing | ADR 0009, CI scans |
| No MVP recording | No server-side recording, snapshots, or playback | Plan invariant, tests |
| Access control | CF Access + RBAC + camera ACL | Authz tests |
| Short-lived tokens | Viewer/gateway media tokens â‰¤60 s | Token tests |
| Camera credential isolation | RTSP credentials stored only on gateway | T-62, gateway config review |
| Bystander signage | Signage at every entrance, attested per site | ADR 0011, DPA artefact |
| PII scrubbing | Sentry/logs/Telegram redaction | Log review |
| Audit integrity | Append-only audit + HMAC chain | Audit verifier |
| Encryption | TLS, encrypted backups, R2 object lock | Backup evidence |
| DSR channel | `dpa@<domain>`, 15-day initial SLA | DSR procedure |

## 7. Risk assessment

| Risk | Likelihood | Impact | Initial rating | Mitigation | Residual rating |
|---|---|---|---|---|---|
| Unauthorized viewer sees camera | Medium | High | High | CF Access, ACLs, short tokens, audit | Medium |
| Camera credentials leak | Low | High | High | Gateway-only credentials, no API exposure, T-62 | Low |
| Bystanders unaware of CCTV | Medium | Medium | Medium | Signage policy + attestation | Low |
| Minor-site notice inadequate | Medium | High | High | Counsel review + consent procedure deploy blocker | Medium |
| Vendor processes data outside PH | Medium | Medium | Medium | DPA + transfer basis artefact | Medium |
| Error logs leak PII | Medium | Medium | Medium | Scrubbing hooks + quarterly review | Low |
| LiveKit media-plane compromise | Low | High | High | Short-lived tokens, no recording, no DB access | Medium |
| Admin device compromise | Medium | High | High | MFA, WARP posture, re-auth, audit | Medium |
| Audit tampering | Low | High | High | DB immutability + HMAC chain + archive | Low |

## 8. Minor-site supplement

Complete this section for schools, daycare, after-school programs, paediatric clinics, youth centres, or similar sites.

| Field | Value |
|---|---|
| Site type | `<school/daycare/etc>` |
| Minors likely in frame | Yes / No |
| Counsel consulted | Yes / No / Pending |
| Parental notice required | Yes / No / Counsel to confirm |
| Consent required | Yes / No / Counsel to confirm |
| Procedure document location | `<link/path>` |
| Admin deploy blocker enabled | Yes / No |
| Legal review artefact recorded | Yes / No |

## 9. Processor / vendor register

| Vendor | Role | Data categories | Region | DPA status | Transfer basis | Notes |
|---|---|---|---|---|---|---|
| Cloudflare | Processor | Identity headers, DNS/tunnel metadata, R2 objects | `<region>` | Pending | Pending | Access/Tunnel/R2 |
| Railway | Processor | App/runtime data, secrets metadata | `<Railway region>` | Pending | Pending | Control-plane app hosting |
| Postgres provider | Processor | App DB, audit | `<region>` | Pending | Pending | Paid tier before pilot |
| IdP | Processor | Identity/MFA data | `<region>` | Pending | Pending | D-01 decision |
| LiveKit | Processor | Media transport metadata/live media | APAC | Pending | Pending | Primary SFU |
| Sentry | Processor | Scrubbed errors | `<region>` | Pending | Pending | PII scrub required |
| Better Stack | Processor | Logs/metrics | `<region>` | Pending | Pending | PII scrub required |
| UptimeRobot | Processor | Probe metadata | `<region>` | Pending | Pending | Service-token health checks |

## 10. Data-subject rights procedure

- DSR channel: `dpa@<domain>`.
- Initial response target: 15 days.
- Verify requester identity before disclosure.
- For bystanders, identify site/time/camera scope without exposing unrelated camera metadata.
- For MVP, no footage export exists because no recording is performed.
- Log DSR requests and outcomes in the DPA artefact register.

## 11. Acceptance criteria

MVP PIA may be accepted when:

- Controller and DPO are named.
- DSR channel exists.
- Bystander signage template is approved for MVP use.
- At least lightweight vendor register is complete.
- No MVP recording is confirmed.
- Minor-site deployments are either out of scope or have counsel-reviewed procedure.
- Risk table has owner-assigned mitigations.

Pilot PIA requires, in addition:

- Counsel review completed.
- Processor DPAs recorded for all vendors.
- Cross-border transfer basis recorded for all processors.
- Full site-by-site signage evidence.
- NPC registration assessment completed.
- Paid Postgres tier and retention controls finalized.

## 12. Open issues

| Issue | Owner | Due date | Status |
|---|---|---|---|
| `<issue>` | `<owner>` | `<date>` | Open |

## 13. Sign-off

| Role | Name | Date | Signature / approval record |
|---|---|---|---|
| System Owner | `<name>` | `<date>` | `<record>` |
| DPO | `<name>` | `<date>` | `<record>` |
| Counsel | `<name>` | `<date>` | `<record>` |

