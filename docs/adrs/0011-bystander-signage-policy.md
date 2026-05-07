# ADR 0011 — Bystander Signage Policy

- **Status**: Accepted
- **Date**: 2026-05-07
- **Decision-makers**: System Owner, DPO, Software Architect
- **Supersedes**: None
- **Plan references**: §16.11; §16.12; §18.2 T-46; §25.1; §25.3; §29

## Context

The system monitors live CCTV streams from fixed cameras. Even though MVP explicitly does **not** record footage, identifiable people may still appear in frame during live viewing. Under the Philippine Data Privacy Act (RA 10173) and NPC CCTV guidance, people in monitored areas must receive clear notice that CCTV monitoring is occurring and must have a way to contact the controller or DPO.

The plan therefore requires a bystander signage policy that is enforceable operationally and reflected in the product data model. The policy must also preserve camera security: public signs should notify people of surveillance, but should not expose camera IDs, exact internal names, RTSP paths, room names, or operational details that help an attacker map the camera estate.

## Decision

**Every physical area monitored by a camera must have visible CCTV notice signage at every entrance before the camera is enrolled for production use. The sign must identify the controller, provide a DPO/privacy contact, state the MVP non-recording posture, and be available in English and Filipino. Per-site signage attestation is required in the admin system and becomes a deploy gate for site bring-up.**

### Required sign content

The standard text is:

> This area is under CCTV surveillance by `<Controller>`. For privacy inquiries, contact `<DPO email>`. This system does not record footage in MVP.

A Filipino draft is maintained in `/docs/privacy/bystander-signage-template.md` and must be reviewed by Philippine data-privacy counsel before pilot use.

### Placement rules

- A sign is posted at **every entrance** to an area where a camera films.
- Signs must be visible before a person enters the monitored area.
- Signs must not be obscured by furniture, gates, posters, or seasonal decorations.
- Signs must be re-checked during each on-site verification visit.

### Public sign vs private site plan

Public signs must **not** include:

- Internal camera IDs
- LiveKit room names
- Gateway IDs
- RTSP URLs
- Exact camera network topology
- Credentials, vendor serials, or admin contact details beyond the DPO/privacy contact

Camera IDs and operator-readable names are kept on the controller's private site plan only.

### Admin attestation

For each site, an admin records signage attestation via:

```text
POST /api/v1/admin/sites/:id/signage-attest
```

The action creates a `dpa_artifacts` row:

```text
kind = 'bystander_signage_attestation'
site_id = <site>
photo_hash = <hash of sign photo>
notes = <placement notes / minor-consent notes if applicable>
created_by = <admin actor>
created_at = now()
```

The raw sign photo may be stored outside the database according to the privacy artefact storage policy; the database stores the hash and metadata as evidence.

### Renewal and verification

- On-site signage verification occurs at least quarterly.
- Attestations are re-signed annually.
- Admin dashboard warns when a site has no signage attestation in the last 12 months.
- Site bring-up checklist includes signage as a required item before any production camera is activated.

### Minor-site rule

Sites where minors are likely to appear in frame — including schools, daycare, after-school programs, paediatric clinics, youth centres, and similar locations — require an additional parental notice or consent procedure.

For such sites:

1. Philippine data-privacy counsel must review the planned deployment.
2. The parental notice or consent procedure is documented before deployment.
3. The legal review outcome is stored as a `dpa_artifacts` row.
4. Admin UI refuses to enrol a camera at a flagged minor-site unless the procedure is on file.

This is a deploy blocker, not a warning.

## Consequences

### Positive

- **Transparency**: people entering monitored areas receive clear notice.
- **Privacy evidence**: attestations create an audit trail showing that notice obligations were handled.
- **Security-aware notice**: public signage avoids leaking internal camera metadata.
- **Minor-site safety**: higher-risk sites receive counsel-reviewed consent/notice handling before deployment.

### Negative

- **Operational overhead**: every site needs photos, attestations, annual renewal, and quarterly verification.
- **Legal dependency**: final Filipino wording and minor-site procedure should be reviewed by counsel before pilot.
- **Deployment friction**: cameras cannot be enrolled at a site until signage is attested.

### Risks accepted

- MVP has no recording, but live monitoring can still process personal data. The signage must therefore describe surveillance even without recording. This is accepted and reflected in the required sign text.

## Alternatives considered

### A. Privacy notice only inside the web app

- **Rejected**: bystanders in frame are not app users and will never see the web notice. Physical signage is required.

### B. Put camera IDs on public signs

- **Rejected**: camera IDs help attackers correlate physical cameras with internal records or API responses. They belong on the private site plan, not public notices.

### C. Defer signage until pilot

- **Rejected**: site bring-up itself creates live monitoring. Notice must exist before production cameras are activated, not after.

### D. Use English-only signs

- **Rejected**: bilingual EN/FIL signage improves accessibility and aligns with the expected Philippine deployment context.

## Verification

- **T-46**: site cannot pass privacy acceptance if signage artefacts are missing or stale.
- **Admin dashboard**: warning appears if a site lacks signage attestation in the last 12 months.
- **Site bring-up checklist**: camera enrolment blocked until signage attestation is present.
- **Quarterly onsite check**: verifies sign placement and visibility.

## References

- v4 plan §16.11 (Privacy — operators)
- v4 plan §16.12 (Privacy — bystanders)
- v4 plan §18.2 T-46
- v4 plan §25.1 (Repository scaffold — privacy docs)
- Philippine Data Privacy Act of 2012 (RA 10173)
- NPC Circular 16-01 / 17-01
