# Compliance Readiness Checklist

<!-- PE-FIX: Added compliance pack checklist required by council audit -->

This checklist is retained for future reference. Per current project decision, it is **not a blocker for the prototype/free-tier implementation phase**. Revisit only if the project later connects real cameras to a real regulated site, starts a formal pilot, or needs external privacy/legal review.

## Required artifacts

| Artifact | Current prototype status | Future trigger | Owner |
|---|---|---|---|
| Controller identity | Deferred | Formal real-site pilot | System owner |
| DPO contact | Deferred | Formal real-site pilot | System owner |
| PIA | Deferred | Formal real-site pilot or external review | System owner |
| ROPA | Deferred | Formal real-site pilot | System owner |
| Vendor DPA annexes | Deferred | Paid vendor review or formal pilot | System owner |
| Cross-border transfer basis | Deferred | Formal real-site pilot | System owner |
| Retention policy | Deferred | Formal real-site pilot | System owner |
| Breach log template | Deferred | Formal real-site pilot | System owner |
| No-recording policy | Keep technical enforcement | Before any real camera recording/snapshot change | System owner |
| Bystander signage attestation | Deferred | Formal real-site pilot | System owner |
| Minor-site procedure | Deferred | School/youth/minor-frequented deployment | System owner |
| DSR procedure | Deferred | Formal real-site pilot | System owner |

## Processor register baseline

| Processor | Purpose | Required evidence |
|---|---|---|
| Cloudflare | DNS, Access, WAF, R2 | DPA, sub-processors, region/transfer basis. |
| Railway | `cctv-web` and `cctv-api` hosting | DPA, region/transfer basis, security documentation. |
| Postgres provider | App DB and audit chain | DPA, PITR/backup posture, region/transfer basis. |
| Google Workspace | IdP/MFA | DPA, admin control evidence, MFA policy. |
| LiveKit Cloud | WebRTC media transport | DPA, media metadata handling, APAC region. |
| DigitalOcean/equivalent | LiveKit fallback | DPA, region, security controls. |
| Sentry | Error tracking if enabled | DPA and PII scrub evidence. |
| Better Stack | Logs/monitoring | DPA and PII scrub evidence. |
| UptimeRobot | Health checks | DPA and probe data scope. |
| Email/Telegram | Alerts/DSR if used | Data minimization and breach terms. |

## Minor-site gate

Not a current blocker. If a future deployment site is a school, daycare, youth center, pediatric clinic, or similar:

- Counsel must confirm notice/consent basis.
- Parental notice/consent procedure must be documented where required.
- Signage wording must be site-appropriate.
- Admin deploy blocker must prevent pilot until legal review artifact is recorded.

## DSR operational requirements

- DSR channel exists, e.g. `dpa@<domain>`.
- Initial response target is 15 days.
- Requester identity verification is recorded.
- `dsr_requests` row tracks request type, due date, verification, status, outcome, and linked artifact.
- MVP has no footage export because there is no recording.

## Pilot readiness decision

Not active for the current free-tier prototype. If the project later enters a formal real-site pilot, revisit:

- PIA is signed or explicitly accepted by the DPO.
- DPAs and transfer bases are recorded for active processors.
- Bystander signage evidence is complete for the pilot site.
- Paid Postgres/PITR decision is complete.
- No-recording controls are verified by QA.
- Minor-site procedure is counsel-reviewed if applicable.
