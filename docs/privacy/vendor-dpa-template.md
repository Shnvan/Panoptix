# Vendor-Neutral Data Processing Agreement Template

This is a project template for processor DPAs related to the secure CCTV monitoring system. It is not legal advice and must be reviewed by Philippine data-privacy counsel before execution.

## 1. Parties

This Data Processing Agreement is entered into between:

- **Controller**: `<Controller legal name>`, located at `<Controller address>`.
- **Processor**: `<Processor legal name>`, located at `<Processor address>`.

The Controller determines the purposes and means of processing personal data. The Processor processes personal data only on documented instructions from the Controller.

## 2. System and processing context

The Controller operates a secure live-view CCTV monitoring system.

MVP scope:

- Live viewing of fixed IP camera / NVR feeds.
- No server-side recording.
- No snapshots.
- No playback.
- No browser, webcam, phone-camera, or laptop-camera publishing.

The Processor provides the following services:

```text
<Service description>
Example: hosting, identity, media transport, database, object storage, monitoring, error tracking, uptime monitoring.
```

## 3. Categories of data subjects

- Authorized operators / users of the CCTV monitoring application.
- Administrators and support personnel.
- Bystanders who may appear in camera frames.
- Gateway/site contacts, where applicable.

## 4. Categories of personal data

Potential categories include:

- User identity data: email address, IdP subject, role/permissions.
- Session data: timestamps, user agent, hashed low-risk device fingerprint.
- Audit data: actor, action, resource, timestamp, IP metadata, request metadata.
- CCTV live media packets or transient media metadata, if the processor handles media transport.
- Site metadata and signage attestations, if the processor stores privacy artefacts.
- Error/monitoring telemetry after PII scrubbing.

Processor-specific data actually processed:

```text
<List exact categories for this vendor>
```

## 5. Processing purposes

The Processor may process personal data only to provide the contracted service, including:

- Hosting application infrastructure.
- Enforcing identity-aware access.
- Transporting WebRTC media.
- Storing encrypted backups or audit archives.
- Storing or querying application data.
- Providing error tracking, monitoring, alerting, or uptime checks.
- Supporting security, reliability, incident response, and compliance.

No processing for advertising, profiling, training third-party AI models, or unrelated analytics is permitted unless separately authorized in writing by the Controller.

## 6. Duration

Processing begins on `<effective date>` and continues until termination of the service agreement or deletion/return of all personal data, whichever is later.

## 7. Processor obligations

The Processor shall:

1. Process personal data only on documented instructions from the Controller.
2. Ensure personnel authorized to process personal data are bound by confidentiality obligations.
3. Implement appropriate technical and organizational measures.
4. Assist the Controller in responding to data-subject requests.
5. Assist with security incidents, breach investigation, and regulatory notification obligations.
6. Delete or return personal data at the Controller's choice upon termination, unless retention is legally required.
7. Make available information reasonably necessary to demonstrate compliance.
8. Notify the Controller of any legally binding request for disclosure, unless prohibited by law.

## 8. Security measures

Minimum expected measures:

- Encryption in transit using TLS 1.2+.
- Encryption at rest where applicable.
- Access control with least privilege.
- Administrative MFA.
- Audit logging of administrative access.
- Vulnerability management and patching.
- Segregation of customer data.
- Incident response process.
- Backup and recovery controls, where applicable.

Project-specific security requirements:

```text
<Add vendor-specific requirements>
Example: object lock retention, region pinning, private networking, PII scrubbing, no media recording, no public bucket access.
```

## 9. Sub-processors

The Processor must disclose current sub-processors and provide advance notice of changes.

Sub-processor list:

| Sub-processor | Service | Location / region | Data categories | Transfer basis |
|---|---|---|---|---|
| `<name>` | `<service>` | `<region>` | `<data>` | `<basis>` |

The Controller may object to a new sub-processor on reasonable data-protection grounds.

## 10. Cross-border transfers

If personal data is transferred outside the Philippines, the Processor must identify the transfer location and the legal basis / safeguard used.

Transfer basis:

```text
<Describe cross-border transfer basis and safeguards>
```

This basis is recorded in the Controller's `dpa_artifacts` register as `kind = 'cross_border_transfer_basis'`.

## 11. Data-subject requests

The Processor shall provide reasonable assistance for:

- Access requests.
- Correction requests.
- Deletion requests, where applicable.
- Objection or restriction requests, where applicable.
- Requests related to CCTV notice and processing transparency.

The Controller's target initial response SLA is 15 days.

## 12. Breach notification

The Processor shall notify the Controller without undue delay after becoming aware of a personal data breach.

Notification should include, where available:

- Nature of the breach.
- Categories and approximate number of affected data subjects.
- Categories and approximate number of affected records.
- Likely consequences.
- Measures taken or proposed.
- Contact point for follow-up.

The Controller may have a 72-hour notification obligation to the NPC depending on breach severity and applicability.

## 13. Deletion and return

On termination, the Processor shall, at Controller's option:

- Delete all personal data and certify deletion; or
- Return all personal data in a structured, commonly used format, then delete remaining copies.

Backup deletion may follow the Processor's documented backup lifecycle, provided backups are protected and not restored except for continuity/security purposes.

## 14. Audit and evidence

The Processor shall provide one or more of:

- SOC 2 / ISO 27001 report.
- Security whitepaper.
- Sub-processor list.
- Data export / deletion documentation.
- Incident history, where contractually available.
- Reasonable responses to security questionnaire.

## 15. Processor-specific annex

### Vendor

```text
<Vendor name>
```

### Service

```text
<Service being used>
```

### Region / residency

```text
<Primary region; backup regions if any>
```

### Data categories processed

```text
<Exact list>
```

### Retention

```text
<Retention period or vendor policy>
```

### Security notes

```text
<Controls, certifications, settings>
```

### Sub-processors

```text
<Link or attached list>
```

### Open issues before pilot

```text
<List blockers>
```

## 16. Project vendor checklist

Complete one annex for each processor:

- Cloudflare — DNS, Access, Tunnel, WAF, R2.
- Railway — control-plane app hosting.
- Chosen Postgres provider — app DB and audit chain.
- Primary IdP — identity and MFA.
- LiveKit Cloud — WebRTC media transport.
- Sentry — error tracking.
- Better Stack — logs/monitoring.
- UptimeRobot — uptime probes.
- Email provider, if used for DSR or alerts.

## 17. Counsel review checklist

- Confirm controller/processor role classification.
- Confirm cross-border transfer basis.
- Confirm breach notification timing and escalation.
- Confirm sub-processor objection process.
- Confirm deletion/return language.
- Confirm whether media-plane transient packet handling requires additional clauses.
- Confirm whether minor-site deployments require additional consent/notice language.
