# Procurement Guide Skeleton

This guide records procurement-time criteria for selecting accounts, vendors, gateway hardware, cameras, and domain resources for the secure CCTV monitoring system.

## 1. Decisions to make first

| ID | Decision | Required before | Notes |
|---|---|---|---|
| D-01 | Primary IdP | ADR 0002, Phase 2 auth | Must support phishing-resistant MFA |
| D-02 | Paid Postgres tier | ADR 0003, pilot | PITR required before pilot |
| D-03 | On-call model | Observability ADR/runbooks | MVP solo/pair owner; pilot two named responders |
| D-04 | Pen-test modality | Phase 6 readiness | Internal review for MVP; grey-box external before pilot if budget allows |
| D-05 | Continuous-stream default | LiveKit cost model | Presence-driven gateway publish |
| D-06 | Gateway identity tier | ADR 0008 | Service-token MVP + mTLS pre-pilot |
| D-07 | Account email | All vendor accounts | Dedicated project/admin email |

## 2. Account setup checklist

| Account | Required settings | Notes |
|---|---|---|
| GitHub org/repo | Private repo, branch protection, signed commits, Dependabot | First repo commit after Phase 0 ready |
| Cloudflare | DNS, Access, R2 object lock, Zero Trust seats | Verify Free vs paid tier |
| Railway | Project/workspace, billing, environments, custom domain support | Control-plane `cctv-api` Python service; temporary URL `https://panoptix-control-production.up.railway.app` |
| LiveKit fallback host | UDP/media-port support, TCP/TLS:443 fallback, separate secrets | DigitalOcean Singapore first candidate; equivalent APAC UDP-capable provider fallback |
| LiveKit Cloud | APAC project, API keys, webhook secret | Primary media plane |
| Postgres provider | Region, PITR, private networking where possible | Free tier only for prototype |
| Observability | Better Stack, Sentry, UptimeRobot | PII scrubbing required |
| Domain registrar | Domain + DNS delegation to Cloudflare | Required early |

## 3. IdP selection criteria

Minimum requirements:

- WebAuthn/passkey or hardware security key support.
- Admin-controlled MFA enforcement.
- IdP logs export or review access.
- Processor DPA availability.
- Reasonable account recovery controls.
- No SMS-only MFA.
- Cloudflare Access federation support.

Candidate comparison:

| Provider | MFA | DPA | Cost | Fit | Decision |
|---|---|---|---|---|---|
| Google Workspace | WebAuthn/passkey/hardware key | Available | Per seat | Strong if school already uses Google | Selected |
| Microsoft Entra ID | WebAuthn/hardware key/Auth app | Available | Free/paid tiers | Strong if M365 exists | Rejected for MVP |
| GitHub | WebAuthn/TOTP | Available | Low/free | Dev-centric, limited identity domain | Rejected for school/operator users |
| Okta | WebAuthn/FIDO2 | Available | Paid | Enterprise | Rejected for cost |
| Cloudflare OTP | Email OTP only | CF processor | Included | Fallback only | Not primary |

## 4. Postgres provider criteria

Minimum requirements for pilot:

- PITR.
- No cold-start behaviour for production pilot.
- TLS required (`sslmode=require`).
- Least-privilege runtime role support.
- Logical backups/export allowed.
- Region/latency compatible with the Railway control-plane region and APAC/Philippines users.
- Clear DPA and cross-border transfer basis.

Candidate comparison:

| Provider | PITR | Region | Private networking | Cost | Notes | Decision |
|---|---|---|---|---|---|---|
| Neon Free | No pilot-grade PITR | Region/latency to verify | Verify | Free | Prototype/MVP only | Selected for prototype |
| Neon Launch / paid equivalent | Yes | APAC availability to verify | Verify | ~$19/mo | Primary pilot candidate | Selected for pilot if checks pass |
| Supabase Pro | Yes | APAC to verify | Verify | ~$25/mo | Broad ecosystem | Fallback |
| Railway Postgres / selected Railway-compatible PG | PITR/backup model to verify | Region to verify | App-adjacent if chosen | To quote | Must meet pilot PITR/no-cold-start requirements | Alternative |
| Crunchy Bridge / Aiven / RDS / Cloud SQL | Yes | Region varies | Strong | Higher | Enterprise-grade | Later if needed |

## 5. Gateway hardware criteria

Production standard: x86_64 NUC-class mini-PC.

Minimum:

- x86_64 quad-core CPU with AES-NI.
- 8 GB RAM.
- 128 GB SSD.
- 1 x GbE NIC.
- Ubuntu 22.04 LTS support.
- BIOS auto-power-on after power loss.

Recommended:

- Intel N100/N305 or Ryzen 5xxx U-series.
- 16 GB RAM.
- 256 GB NVMe.
- 2 x GbE NICs.
- UPS-backed power.
- Fanless/low-noise design for occupied spaces.

Shortlist table:

| SKU | CPU | RAM | Storage | NICs | Price | Ubuntu support | Notes | Decision |
|---|---|---|---|---|---|---|---|---|
| Beelink Mini S / Intel N100-class | Intel N100-class | 8-16 GB | 128-256 GB SSD | 1 GbE, 2 preferred | To quote | Verify Ubuntu 22.04 LTS | First procurement candidate | Selected candidate |
| Intel NUC-class | x86_64 quad-core+ | 8-16 GB | 128-256 GB SSD | 1-2 GbE | To quote | Verify Ubuntu 22.04 LTS | Reference class | Fallback candidate |
| MeLE Quieter-class | x86_64 | 8-16 GB | 128-256 GB SSD | 1-2 GbE | To quote | Verify Ubuntu 22.04 LTS | Fanless | Fallback candidate |

## 6. Camera / NVR criteria

Minimum:

- RTSP support confirmed in datasheet.
- ONVIF Profile S/T support preferred, but RTSP is mandatory.
- Static IP or DHCP reservation support.
- Local credentials under operator control.
- Ability to disable vendor cloud/P2P features.
- H.264 stream support.
- Stable 720p/1080p at 15 fps.
- No requirement for internet access after setup.

Reject cameras that:

- Require vendor cloud for RTSP access.
- Require internet route to function.
- Do not support RTSP or NVR RTSP output.
- Cannot set unique strong local credentials.
- Cannot disable UPnP/P2P/cloud pairing.

Shortlist table:

| Vendor/model | RTSP | ONVIF Profile | H.264 | Local-only mode | Price | Notes | Decision |
|---|---|---|---|---|---|---|---|
| `<model>` | Yes/No | S/T/None | Yes/No | Yes/No | `<price>` | `<notes>` | Pending |

## 7. Network equipment criteria

Per-site needs:

- VLAN-capable switch if cameras are not already isolated.
- Enough PoE ports if cameras use PoE.
- Ability to block camera VLAN -> internet.
- Ability to block camera VLAN <-> operator LAN.
- UPS support for switch + gateway.

Checklist:

| Item | Required | Selected SKU | Notes |
|---|---|---|---|
| Managed switch | Yes if no existing VLAN switch | Site-specific | VLAN/ACL support |
| PoE budget | Site-specific | Pending | Sum camera wattage |
| UPS | Recommended | Site-specific | Gateway + switch |
| Patch cabling | Site-specific | Pending | Label camera VLAN |

## 8. Vendor DPA checklist

For each vendor, collect:

- DPA / data-processing terms.
- Sub-processor list.
- Region / residency information.
- Security documentation (SOC 2 / ISO 27001 / whitepaper).
- Breach notification terms.
- Deletion/export terms.
- Cross-border transfer basis.

Record each as a `dpa_artifacts` entry.

## 9. Procurement acceptance gates

Phase 0 ready requires:

- D-01..D-07 decided as recorded in this guide.
- Domain purchased and DNS delegated to Cloudflare.
- Vendor accounts created with dedicated project email.
- ADRs 0001..0014 complete and accepted.
- Gateway hardware shortlist prepared.
- At least one RTSP camera/NVR candidate identified.
- Legal/privacy owner naming deferred by current project decision.
- Counsel path deferred by current project decision.

Pilot ready requires:

- Paid Postgres tier selected with PITR.
- Processor DPAs recorded for all vendors.
- Cross-border transfer basis recorded.
- Gateway hardware procured and imaged.
- At least one real camera tested through RTSP gateway.
- Signage and PIA artefacts complete for pilot site.
- mTLS plan for gateways finalized or deployed per ADR 0008; internal project CA is the default unless Cloudflare mTLS proves simpler and equivalent.

## 10. Open procurement log

| Date | Item | Owner | Status | Notes |
|---|---|---|---|---|
| `<date>` | `<item>` | `<owner>` | Open | `<notes>` |

