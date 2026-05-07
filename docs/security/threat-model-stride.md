# STRIDE Threat Model â€” Secure CCTV Monitoring System

<!-- PE-FIX: Updated Fly.io/Next.js references to Railway/Python per ADR 0014 -->

This document captures the v4.1 STRIDE threat model for the secure CCTV monitoring system across the control plane, media plane, and camera plane.

## Scope

### In scope

- Control plane: Python/FastAPI app (Railway-hosted), Cloudflare Access, admin UI, viewer UI, API routes, sessions, RBAC, audit logging.
- Media plane: LiveKit Cloud primary, self-hosted LiveKit fallback, WebRTC viewer/gateway connections, LiveKit webhooks.
- Camera plane: on-site edge gateway, `mediamtx`, camera VLAN, RTSP camera/NVR credentials.
- Data stores: Postgres, R2 backups/audit archive, Railway secrets, gateway secret files.
- Operational flows: break-glass, gateway enrolment, credential rotation, audit export, backup/restore, DPA artefact export.

### Out of scope

- Browser publishing, webcam publishing, phone-camera ingest, `getUserMedia`, `MediaRecorder`.
- Server-side recording, snapshots, playback, media archive.
- Public unauthenticated camera URLs.
- Direct camera access by cloud app.

## Architecture boundaries

| Boundary | Description | Primary controls |
|---|---|---|
| Public internet â†’ Cloudflare edge | First ingress point for control plane | CF Access, WAF/rate limits, DNS orange-cloud |
| Cloudflare edge â†’ `cctv-api` | CF Access-protected control-plane ingress | Railway origin-binding (fail-closed CF JWT verification), trusted-header policy |
| Browser â†’ LiveKit | Viewer media subscription | viewer-subscribe JWT, â‰¤60 s TTL, subscriber-only |
| Gateway â†’ LiveKit | Camera media publish | gateway-publish JWT, â‰¤60 s TTL, publisher-only |
| Gateway â†’ Camera VLAN | RTSP pull from local cameras | VLAN isolation, firewall rules, local credentials |
| Control plane â†’ Postgres | Authoritative app/audit data | least-privilege DB role, audit immutability |
| Control plane â†’ R2 | Encrypted backups / archive | age encryption, object lock |

## Protected assets

| Asset | Sensitivity | Notes |
|---|---|---|
| Live camera feeds | High | Live personal data; no recording in MVP |
| Camera RTSP credentials | Critical | Stored only on gateway; never in app/browser/audit |
| CF Access JWTs / app sessions | Critical | Identity and authorization state |
| LiveKit API key/secret | Critical | Can mint/control media-plane tokens |
| Gateway service tokens / mTLS certs | Critical | Gateway identity |
| Audit HMAC keys | Critical | Tamper-evidence chain integrity |
| Postgres data | High | Users, ACLs, sessions, audit, DPA artefacts |
| R2 backup/archive objects | High | Encrypted, immutable backup evidence |
| DPA artefacts / signage attestations | Medium-High | Compliance evidence and site metadata |
| Error logs / alerts | Medium | Must be PII-scrubbed |

## Actors

| Actor | Description |
|---|---|
| External attacker | Internet-based attacker without credentials |
| Authenticated viewer | Valid user with viewer access to assigned cameras |
| Admin | Valid admin with management privileges |
| SuperAdmin | Admin with high-risk authority, e.g., fallback/break-glass close/delete-admin |
| Break-glass actor | Emergency account used only during incidents |
| Edge gateway | Machine identity authorized to publish assigned cameras |
| Compromised gateway | Gateway whose token/cert or host is stolen |
| Compromised media plane | LiveKit Cloud/fallback instance or its config compromised |
| Vendor/operator insider | Cloud/provider/operator employee or internal privileged user |
| Bystander | Person in camera frame, not an app user |

## STRIDE analysis

### 1. Spoofing identity

| Threat | Scenario | Controls | Verification |
|---|---|---|---|
| Forged CF Access identity | Attacker injects `Cf-Access-Jwt-Assertion` directly to origin | Railway origin-binding; identity comes only from verified CF Access JWT; caller-supplied `cf-*` headers ignored unless JWT validation succeeds; JWT `aud`/`iss`/signature validation | T-56, T-64 |
| Browser impersonates gateway | Browser calls gateway ingest endpoint to get publisher token | Gateway endpoint requires service-token/mTLS identity; browser sessions rejected | T-60 |
| Gateway impersonates viewer | Gateway calls viewer token endpoint | Viewer endpoint requires browser session + camera ACL; gateway identity rejected | T-60 |
| Stolen gateway credential | Attacker uses leaked service-token or cert | One credential per gateway, hash/fingerprint pinning, disable gateway, rotate credential | Gateway lifecycle tests |
| Spoofed LiveKit webhook | Attacker posts fake room/participant event | HMAC signature, timestamp window 60 s, replay cache | T-63 |
| Break-glass abuse | Attacker uses emergency account | Single identity, hardware key, 90-min request-time gate, audit + rotation | T-52 |

### 2. Tampering

| Threat | Scenario | Controls | Verification |
|---|---|---|---|
| Audit row modification | Admin or compromised app modifies prior audit entries | DB immutability triggers, HMAC chain, external archive, verifier job | Audit verifier tests |
| DB role escalates | Runtime DB role drops triggers/truncates audit | Least-privilege runtime role; no trigger-disable/drop/truncate grants | T-57 |
| LiveKit fallback config altered | Media host gains app/DB access | Separate media-plane service/secrets, no DB egress, media-only ports | T-45 |
| Gateway `mediamtx` API exposed | Attacker changes RTSP paths or publishes | API disabled or loopback-only; site probe | T-61 |
| Dependency tampering | Floating dependency pulls malicious package | Exact pins, lockfile, SBOM, Dependabot review, Trivy/osv scans | CI gates |
| DPA artefact tampering | Signage/legal artefacts altered after fact | Hash/photo hash, audit event, export bundle | DPA export check |

### 3. Repudiation

| Threat | Scenario | Controls | Verification |
|---|---|---|---|
| Admin denies privileged action | Admin changes ACLs or opens fallback | Append-only audit event with actor/session/IP/UA hash | Audit export |
| Viewer denies watching a camera | Viewer token minted and LiveKit participant joins | `stream_grants` row + LiveKit webhook + audit event | Integration tests |
| Gateway denies publishing | Gateway obtains publish token and starts stream | Gateway token grant + heartbeat/status + LiveKit event | Integration tests |
| Break-glass actor denies use | Emergency admin path used | `break_glass_usage` + audit open/close/actions | T-52 |
| Vendor artefact missing | Processor DPA not recorded | `dpa_artifacts` row required for processor readiness | DPA checklist |

### 4. Information disclosure

| Threat | Scenario | Controls | Verification |
|---|---|---|---|
| Origin IP leaks | Attacker reaches Railway app directly | Fail-closed CF JWT on all protected routes, DNS through CF, CT monitoring, Shodan/Censys checks | T-30, T-56 |
| Camera credentials leak to browser | API returns RTSP URL/password | No credential fields in API; bundle scanner; schema separation | T-62 |
| Host IP leakage via WebRTC | Browser/gateway exposes private IP candidates | `iceTransportPolicy: 'relay'` enforced in tokens | Media tests |
| PII leaks to Sentry/Telegram | Error payload includes email/IP/camera name | PII scrub hooks, opaque alert IDs, quarterly review | Log/alert review |
| Camera metadata on public signage | Sign reveals camera IDs or room names | Public sign template excludes internal identifiers | Signage review |
| Backup disclosure | R2 backup object read by attacker | age encryption, object lock, least-priv keys | Restore drill |

### 5. Denial of service

| Threat | Scenario | Controls | Verification |
|---|---|---|---|
| Token mint flood | Attacker or user repeatedly requests view/gateway tokens | CF/app rate limits, `Retry-After`, anomaly alert | T-53 |
| Gateway offline | Site loses power/WAN or box fails | Gateway offline alert after 2 min, site checklist, UPS recommended | Ops drill |
| LiveKit Cloud outage/quota | Primary media unavailable | Self-hosted fallback flag, reconnect â‰¤60 s | T-37, Â§20.10 drill |
| CF Access outage/misconfig | Control plane inaccessible | Rollback runbook, IdP outage fallback policy | Runbook drill |
| DB outage | Sessions/token grants/audit unavailable | Managed PG, backups, restore drill, fail-closed auth | Restore drill |
| Webhook flood | LiveKit/webhook endpoint spammed | HMAC validation, rate limit, CORS server-to-server only | T-54/T-63 |

### 6. Elevation of privilege

| Threat | Scenario | Controls | Verification |
|---|---|---|---|
| Viewer becomes admin | UI/API route misses RBAC check | Deny-by-default policy module, route-level authz tests | Authz tests |
| Viewer gets publisher token | Browser path shares token-mint logic | Separate endpoints/code paths; token kind distinction | T-60 |
| Admin deletes/changes high-risk config without re-auth | Stale session used for sensitive mutation | Admin re-auth â‰¤5 min; SuperAdmin gates | Admin tests |
| Compromised media host reaches DB | LiveKit fallback pivots to Postgres | No DB secret, egress block, separate app | T-45 |
| Gateway publishes unassigned camera | Gateway token minted outside assignment | `gateway_camera_assignments` sole authority | Integration tests |
| Break-glass window remains open | Scheduler fails to close emergency access | Request-time 90-min enforcement; external monitor | T-52 |

## Residual risks

| Risk | Residual exposure | Owner | Review trigger |
|---|---|---|---|
| Endpoint compromise of admin device | Valid admin session can perform allowed actions | System Owner | Pilot before production |
| Gateway physical theft | Token/cert and RTSP credentials may be extracted | Ops Owner | Site hardware procurement |
| LiveKit Cloud vendor compromise | Media metadata and live media path may be exposed | System Owner | Vendor DPA / security review |
| Region-wide outage | MVP DR is backup-restore to same region after recovery | System Owner | Pilot DR planning |
| Legal interpretation for minor sites | Consent/notice obligations vary by site | DPO / Counsel | Before school/youth deployment |

## Required follow-up artefacts

- ADR 0001 â€” Plane separation
- ADR 0004 â€” LiveKit fallback
- ADR 0005 â€” Break-glass
- ADR 0009 â€” CCTV-only ingest
- ADR 0010 â€” Origin-binding
- ADR 0011 â€” Bystander signage
- ADR 0012 â€” Camera network design
- ADR 0013 â€” Gateway hardware standard
- PIA template and full PIA before pilot
- Vendor DPA pack before pilot

## Review cadence

- Update this threat model when any non-negotiable invariant changes.
- Review before pen-test readiness gate.
- Review before pilot launch.
- Review after any security incident involving identity, gateway, media plane, audit integrity, or camera credentials.

