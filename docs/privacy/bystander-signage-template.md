# Bystander CCTV Signage Template

This template provides English and Filipino draft CCTV notice wording for sites using the secure CCTV monitoring system. Counsel/DPO review is required before pilot deployment.

## Usage

Post a sign at every entrance to any area where a camera records or monitors people in frame. Signs must be visible before a person enters the monitored area.

Do **not** include internal camera IDs, LiveKit room names, gateway IDs, RTSP paths, site-network details, or camera credentials on public signs.

## Required placeholders

| Placeholder | Meaning | Example |
|---|---|---|
| `<Controller>` | Organization or person responsible for CCTV operation | Acme School, Inc. |
| `<DPO email>` | Privacy/DPO contact email | dpa@example.edu.ph |
| `<DPO phone>` | Optional privacy contact phone | +63 XXX XXX XXXX |
| `<Site name>` | Internal site name, not necessarily printed | Main Campus |
| `<Effective date>` | Date sign was posted or revised | 2026-05-07 |

## English — MVP non-recording version

```text
NOTICE: CCTV MONITORING

This area is under CCTV surveillance by <Controller>.

For privacy inquiries or requests, contact:
<DPO email>
<DPO phone optional>

This system does not record footage in MVP.
Live viewing is restricted to authorized personnel.
```

## Filipino — MVP non-recording draft

```text
PAUNAWA: CCTV MONITORING

Ang lugar na ito ay mino-monitor ng CCTV ng <Controller>.

Para sa mga katanungan o kahilingan tungkol sa privacy, makipag-ugnayan sa:
<DPO email>
<DPO phone optional>

Ang sistemang ito ay hindi nagre-record ng footage sa MVP.
Ang live viewing ay para lamang sa mga awtorisadong tauhan.
```

## English — future recording-enabled version

Use only if a future ADR explicitly adds recording support and the PIA/DPA artefacts are updated.

```text
NOTICE: CCTV MONITORING AND RECORDING

This area is under CCTV surveillance and recording by <Controller>.

For privacy inquiries or requests, contact:
<DPO email>
<DPO phone optional>

Live viewing and access to recordings are restricted to authorized personnel.
Retention period: <retention period>.
```

## Filipino — future recording-enabled draft

Use only if a future ADR explicitly adds recording support and the PIA/DPA artefacts are updated.

```text
PAUNAWA: CCTV MONITORING AT RECORDING

Ang lugar na ito ay mino-monitor at nire-record ng CCTV ng <Controller>.

Para sa mga katanungan o kahilingan tungkol sa privacy, makipag-ugnayan sa:
<DPO email>
<DPO phone optional>

Ang live viewing at access sa recordings ay para lamang sa mga awtorisadong tauhan.
Retention period: <retention period>.
```

## Minor-site supplement

For schools, daycare centres, youth programs, paediatric clinics, or any site where minors are likely to appear in frame, attach a site-specific parental notice or consent procedure reviewed by Philippine data-privacy counsel.

Minimum supplement fields:

```text
Minor-site supplement

Site: <Site name>
Controller: <Controller>
DPO contact: <DPO email>
Legal/counsel review date: <date>
Parental notice/consent procedure summary:
<summary>
Where notices are distributed:
<channels>
How consent/acknowledgement is recorded, if applicable:
<procedure>
```

## Attestation checklist

For each site, record the following in the admin UI:

- **Site name**: `<Site name>`
- **Date posted**: `<Effective date>`
- **Entrances covered**: list every entrance where signage is posted
- **Sign languages**: English / Filipino / both
- **Photo hash**: hash of signage photo evidence
- **Attesting admin**: admin actor
- **Minor-site flag**: yes/no
- **Minor consent procedure**: required if minor-site flag is yes
- **Next verification due**: quarterly onsite visit

## Public-sign exclusions

Do not print any of the following on signage:

- Camera IDs
- Camera internal names
- LiveKit room names
- RTSP URLs
- Gateway IDs
- IP addresses or VLAN details
- Admin dashboard URLs
- Service-token or mTLS details
- Camera credentials

## Counsel review notes

- Verify Filipino wording.
- Verify whether the exact non-recording wording is sufficient for live-view-only CCTV under the site context.
- Verify minor-site consent/notice obligations before any school/youth deployment.
- Verify whether NPC registration details must appear on signs for the specific controller.
