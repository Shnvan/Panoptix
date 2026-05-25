# Secure CCTV Web Monitoring System - Production Plan (v4, CCTV-only)

A self-contained 29-section production plan that supersedes v3 by removing every webcam / browser-camera / phone-publisher path, promoting the edge gateway from Phase-12 future work to MVP, and applying the Critical/High fixes from the v3 expert diagnosis - the system is now strictly **IP camera / NVR -> RTSP -> edge gateway -> authenticated media ingest -> LiveKit Cloud (primary) or self-hosted LiveKit (fallback) -> authenticated web CCTV dashboard**, with browsers acting only as viewers/admins and never as camera publishers.

> **Supersedes**: `secure-cctv-monitoring-system-v3-801515.md`. The v3 "browser publisher is temporary" invariant and phone-publisher MVP path are revoked permanently. v3 is preserved with a SUPERSEDED banner; do not follow it.

---

## Non-Negotiable Invariants

These are architectural invariants. Any change requires an ADR and threat-model re-review. **The CCTV-only invariant (Inv 5) is product-defining: any feature, demo, lab, fallback, or test path that violates it is cut, not redesigned.**

1. **Security-first**: no feature ships if it weakens the controls below.
2. **Always-on managed cloud hosting**: >=2 redundant compute instances. **Laptop / dorm-room / home-PC hosting forbidden at every phase.**
3. **Origin non-exposure of the control plane (REQ-SEC-01)**: the supported user entry point is Cloudflare Access in front of the Railway app. Direct Railway-origin access to protected routes fails closed without a valid CF Access JWT. Verified by T-30 and T-56.
4. **Control-plane vs media-plane separation (REQ-SEC-01b)**: WebRTC media does not traverse the control plane or Cloudflare Access/Tunnel. Media flows directly to LiveKit Cloud (primary) or to a self-hosted LiveKit fallback that exposes only media ports and shares no trust with the control plane. Verified by T-45.
5. **CCTV-only ingest (REQ-CCTV-01)** *(replaces v3 Inv 5)*: the system does not support webcam, phone-camera, laptop-camera, or browser-based publishing. **All camera feeds must originate from an approved IP camera, NVR, RTSP source, or authorized edge gateway.** Browsers are viewers only. No browser route may request camera permission, call `getUserMedia`, call `MediaRecorder`, or publish media as a camera source. No demo, lab, internal, fallback, compatibility, or test path may violate this. Forbidden terms appear only in Section 29.
6. **Edge gateway is MVP-critical** *(replaces v3 Inv 6)*: because the browser publisher is removed, the edge gateway (`mediamtx` RTSP-first) is no longer Phase-12 work. MVP does not ship without a gateway path that ingests at least one RTSP source (real or `synthetic_rtsp_test_source`) and republishes to LiveKit under server-minted gateway-publish tokens.
7. **Deny-by-default authorization**: every route, every resource, every ACL check is deny-unless-explicitly-granted.
8. **Short-lived, kind-distinct stream tokens**: **viewer-subscribe** (browser users, <=60s, subscriber-only, bound to `user_id` + `session_id` + `camera_id`) and **gateway-publish** (edge gateways, <=60s, publisher-only, bound to `gateway_id` + `camera_id` via `gateway_camera_assignments`). A browser session can never receive a gateway-publish token. Both replay-detected via `jti`.
9. **Append-only audit with versioned tamper evidence**: DB-enforced immutability + HMAC chain + external immutable archive. Every audit row carries `hmac_key_version`; key rotation preserves chain continuity.
10. **No MVP recording**: no server-side recording, no snapshots, no playback. Technical enforcement: no LiveKit Egress, no media bucket, no `MediaRecorder`, no recording UI (CI-gated; Section 24).
11. **No passwords in the application**: federated to an external IdP via Cloudflare Access; the app trusts only validated CF JWTs (`aud`+`iss` pinned, `exp`/`nbf` validated against `CLOCK_SKEW_SECONDS = 30`).
12. **Stable, locked framework versions**: exact pinned Python/FastAPI/Pydantic/SQLAlchemy/Alembic versions; experimental APIs banned in security-critical paths; lockfile pins; pin Python Docker/runtime base to exact patch where containerized (no floating tags); Dependabot/Renovate enabled.
13. **Provider-exit boundaries**: IAP / app hosting / database / media each replaceable independently via runbook + config; no code-level vendor abstractions.
14. **Origin-binding (REQ-SEC-01c)** *(new, fixes v3-review F-001)*: protected FastAPI routes accept identity only from a verified Cloudflare Access JWT. `Cf-Access-*`, `Cf-Connecting-IP`, and forwarding headers are ignored unless JWT verification succeeds. Direct Railway-origin requests fail closed. Verified by T-56.
15. **DB least-privilege** *(new, fixes v3-review F-010)*: runtime DB role cannot disable triggers, drop tables, `TRUNCATE`, or write to `audit_log` columns outside the trigger-controlled path. Verified by T-57.
16. **Estimates are procurement-time**: every dollar figure is indicative; verify against live provider pricing.

---

## 0. Locked Constraints

| Constraint | Value | Implication |
|---|---|---|
| Control-plane IAP | Cloudflare Access in front of Railway custom domain | Supported user entry point is Cloudflare-protected; app still verifies CF JWT fail-closed. |
| IdP | Google Workspace through Cloudflare Access; Cloudflare OTP fallback only | WebAuthn/passkey or hardware-key MFA required for CCTV users. |
| Camera ingest | **RTSP-first via `mediamtx` edge gateway**; ONVIF Profile S/T conditional on Section 13.3 spike | Camera credentials live on the gateway; never reach the browser or `cctv-api`. |
| Media-plane primary | **LiveKit Cloud (APAC)**, direct connection from gateways/viewers, bypasses control plane | UDP preferred, TCP/TLS:443 fallback. |
| Media-plane fallback | Self-hosted LiveKit on DigitalOcean Singapore or equivalent UDP-capable APAC host, only media ports public | Provider verified before fallback activation; T-37 expanded. |
| Jurisdiction | Philippines (RA 10173 / NPC) | APAC compute (`sin`); processor DPAs required. |
| Budget | <= ~US$50/mo MVP, <= ~US$200/mo pilot (procurement-time) | Free/low-cost where it does not weaken controls. |
| Threat posture | Worst case (unauth attacker + insider + compromised endpoint + grey-box pen-tester) | Layered controls. |
| Hosting | Railway for control plane; managed/cloud services only; **laptop forbidden at every phase** | Railway health checks + external probes; alternate-host DR path. |
| Named security constants | `CLOCK_SKEW_SECONDS = 30`; `BREAK_GLASS_WINDOW_MINUTES = 90`; viewer-token TTL `= 60s`; gateway-ingest-token TTL `= 60s` | Hard-coded named constants, **not** env vars. Changes require ADR. |

---

## 0.1 Revision History (v4 -> v4.1)

In-place revision of v4 closing every actionable finding from the external diagnosis (C-01..C-04, H-01..H-09, M-01..M-14) plus four additional improvements (N-01..N-04). v4 stays the canonical plan; v4.1 is **not** a successor.

**Numbering convention for new Section 13 subsections**: append-only - existing Section 13.4 (Self-hosted LiveKit fallback), Section 13.5 (Hard rules), Section 13.6 (References) keep their content and number. New camera-plane subsections become Section 13.7..Section 13.10. All cross-references to Section 13.5 and Section 13.6 from the rest of the document remain valid.

| Finding | Severity | Where applied | Status |
|---|---|---|---|
| **C-01** Gateway location ambiguity (dev/CI vs production) | Critical | Section 12 stack table; new Section 13.8 Camera Site Hardware; new Section 13.9 Camera Network Design; Phase 4 exit; Phase 0 P0-13; ADR 0013 stub in Section 22 | **Closed** - production = on-site NUC-class mini-PC; dev/CI gateway = synthetic only |
| **C-02** `synthetic_rtsp_test_source` undefined | Critical | New Section 13.7 Synthetic RTSP test source; Section 25.1 scaffold reference; Section 25.4 local-dev workflow | **Closed** - defined as FFmpeg sidecar (`testsrc` + `sine` -> RTSP) |
| **C-03** Break-glass scheduler dependence | Critical | (no edit) | **Reviewed, no change** - v4 Section 16.6 already specifies request-time enforcement as authoritative; reviewer misread |
| **C-04** Audit export trust model | Critical | Section 15.1 audit export; Section 17.2 trust-model subsection | **Closed** - export bundle includes per-row `prev_hash`/`hash`/`hmac_key_version` + `audit_hmac_keys` snapshot for independent HMAC verification |
| **H-01** CF OTP fails phishing-resistant MFA | High | Section 11.2; Section 22 ADR 0002 description | **Closed** - CF OTP dropped from primary IdP options; retained only as IdP-outage fallback |
| **H-02** On-site gateway secret store | High | Section 11.5; Section 20.14 | **Closed** - `/etc/cctv-gateway/gateway.env` mode `0600`, owner `cctv-gateway`, systemd `EnvironmentFile=` |
| **H-03** Camera VLAN design | High | New Section 13.9 Camera Network Design; Section 22 ADR 0012 stub | **Closed** - dedicated camera VLAN, two-NIC or VLAN-aware single-NIC, outbound 443 only |
| **H-04** `stream_grants` cleanup home | High | Section 14.3; T-50 update | **Closed** - scheduled cleanup job every 5 min; external-cron fallback documented |
| **H-05** LiveKit room model | High | New Section 13.10 LiveKit Room Model; `cameras.livekit_room_name` in Section 14.1 | **Closed** - one room per camera, presence-driven publish, 10-s grace on last-viewer |
| **H-06** `mediamtx` version pin | High | Section 22 ADR 0007 rename; Section 12 stack table | **Closed** - covered by ADR 0007; Renovate watcher for `bluenviron/mediamtx` |
| **H-07** CSP nonce | High | Section 16.5 | **Closed** - React + Vite-compatible strict CSP and nonce/hash strategy specified |
| **H-08** Webhook replay window + CORS | High | Section 13.5 hard rule 13; Section 15.1 webhook receiver; Section 16.13 CORS; new T-63 | **Closed** - 60-s window; webhook empty allow-origin; preflight 405 |
| **H-09** `pg_dump` backup host | High | Section 20.7 | **Closed** - scheduled backup job separate from web process |
| **M-01** Bus-factor runbook | Medium | New Section 20.19 | **Closed** |
| **M-02** Camera procurement guidance | Medium | Phase 0 P0-14 | **Closed** |
| **M-03** RBAC expansion path | Medium | Section 16.3 | **Closed** - schema supports additional roles without migration |
| **M-04** `pg_dump` integrity (daily vs weekly) | Medium | Section 14.1 `backup_runs`; Section 20.7 | **Closed** - `restore_format_ok` (daily) + `restore_schema_ok` (weekly) |
| **M-05** NPC registration in T-46 | Medium | T-46 sub-item | **Closed** |
| **M-06** Viewer-identity watermark at MVP | Medium | New Section 16.19 | **Closed** - CSS overlay (deterrence at MVP); video-embedded watermark deferred to pilot |
| **M-07** Telegram alert PII | Medium | Section 16.15; Section 17.4 | **Closed** - opaque IDs only |
| **M-08** Dynamic CSP `connect-src` for fallback | Medium | Section 16.5; Section 20.10 cross-ref | **Closed** - Middleware reads `system_config.media_plane_mode` per request |
| **M-09** Phase 0 timeline | Medium | Section 21 Phase 0 | **Closed** - `5-10 business days` with day-by-day sequence |
| **M-10** `nrt` DR scope | Medium | Section 10.4; Section 20.7 | **Closed** - `nrt` DR labelled pilot+; MVP DR = backup-restore-to-`sin` only |
| **M-11** `jti` replay scope clarification | Medium | Section 11.4; Section 14.1 `stream_grants`; T-50 | **Closed** - distinguishes app token-mint replay (jti) from LiveKit-side defense (60-s TTL) |
| **M-12** `mediamtx` HTTP API auth | Medium | Section 13.8; Section 20.14 | **Closed** - bound to `127.0.0.1:9997` only OR disabled; banned on camera VLAN/WAN |
| **M-13** Token-theft anomaly detection | Medium | Section 17.3; new audit event `system.gateway.anomaly.detected` | **Closed** |
| **M-14** Minor consent for school sites | Medium | Section 16.12; T-46 DPA bundle | **Closed** - RA 10173 + NPC Circular 16-01 conditional |
| **N-01** SBOM in CI | Addition | Section 20.2 | **Closed** - Syft / CycloneDX / sigstore-signed |
| **N-02** CT-log monitoring | Addition | New Section 16.20; Section 20.6 | **Closed** |
| **N-03** Trusted-header policy | Addition | Section 11.6; new T-64 | **Closed** - explicit allow-list; deny/ignore forged `cf-access-*` |
| **N-04** Local-dev workflow | Addition | New Section 25.4; Section 25.1 scaffold reference | **Closed** - `docker-compose up`; fake-CF-Access middleware gated by `APP_ENV` + `ALLOW_DEV_AUTH=1` |

**Counts after v4.1**: acceptance criteria 1..38; risk register 1..18; ADRs 0001..0013; tests T-1..T-64; Phase 0 tasks P0-01..P0-14.

---

## 1. Project Understanding

- **What**: A web-based CCTV monitoring console where authorized operators view >=2 live IP-camera feeds. Cameras are reached via an edge gateway running `mediamtx` that pulls RTSP and republishes to LiveKit. **Browsers are viewers only.**
- **For**: 4 named operators now; extensible to schools, government offices, warehouses, private security teams.
- **Problem**: Self-rolled CCTV web viewers routinely leak streams, expose admin panels, lack phishing-resistant MFA, mix camera credentials into frontend code, and don't survive basic recon.
- **Why CCTV-only**: browser publishers are a category of attack surface (camera-permission prompts, fingerprintable device APIs, lab/demo routes that drift to production) the operator's IP-camera system does not need. Eliminating them entirely is a category-eliminating control.
- **Why the edge gateway is in MVP**: under Inv 5 it is the only ingest path. Shipping MVP without it leaves the system unable to display any camera. RTSP-first via `mediamtx` works against virtually any IP camera/NVR.
- **Why control plane and media plane are separated**: HTTP control and WebRTC media have fundamentally different networking and security requirements. Direct media is correct; security is preserved by short-lived kind-distinct tokens and a hard isolation boundary.

### 1.1 Primary success criteria

| ID | Criterion | Acceptance test |
|---|---|---|
| **REQ-SEC-01** | Control-plane origin non-exposure | T-30 |
| **REQ-SEC-01b** | Media-plane scoping (only LiveKit media ports on the media host) | T-45 |
| **REQ-SEC-01c** | Origin-binding (protected routes require verified CF Access JWT; direct Railway origin rejects) | T-56 |
| **REQ-CCTV-01** | CCTV-only ingest (no browser/phone/webcam publish; no `getUserMedia`/`MediaRecorder`; no browser publisher token) | T-58 (CI grep) + T-59 (browser-bundle scan) + T-60 (token-mint authorization) + T-61 (gateway auth) + T-62 (no camera credentials in bundle) |
| REQ-SEC-02 | Unauthorized visitor sees no app content / version / user-enumeration signal | T-2, T-3, T-4 |
| REQ-SEC-03 | Stream URL leak - copying URL to another browser denies within <=60 s | T-6 |
| REQ-SEC-04 | Audit append-only + tamper-evident **+ chain integrity across HMAC key rotation** | T-23, T-24, T-31, **T-49** |
| REQ-AV-01 | >=99.5% MVP, >=99.9% pilot | Uptime probes 30 d |
| REQ-QA-01 | OWASP ASVS L2 in-scope met | Section 19 |
| REQ-PRIV-01 | PH DPA (PIA, ROPA, DPO, notice, processor DPAs, retention, **bystander signage**) | Section 16.11 + Section 16.12 |

---

## 2. Expert Roles

| Role | Why | Key decisions |
|---|---|---|
| Product Manager | Scope discipline | MVP boundary, demo script, no drift back to "webcam app" |
| Software Architect | Greenfield stack | Monolith vs split, API shape, version policy |
| Cybersecurity Architect | Adversarial evaluator | Threat model, plane separation, gateway identity |
| Network Security Engineer | Camera VLAN, control-plane ingress, media networking | VLAN, egress, DNS hygiene, UDP/TCP fallback |
| Identity Architect | IdP + gateway identity CA | Federation choice, MFA, break-glass, gateway certificate authority |
| Video Streaming Engineer | WebRTC / RTSP / mediamtx | SFU topology, token TTL, gateway ingest, dedicated IPv4 |
| QA Engineer | Evidence | Test plan, automation, network-layer tests, CCTV-only invariant tests |
| DevOps + SRE | Always-on | CI/CD, IaC, runbooks, rollback, drift, gateway lifecycle |
| Cloud Architect | Region & cost & exit | Provider, region, exit ADRs |
| Database Architect | Audit integrity, least-privilege roles | Schema, indexes, retention, key versioning |
| Privacy Specialist (PH DPA) | RA 10173 | PIA, retention, DSR, notice, **bystander signage** |
| Compliance Specialist | Future ISO / SOC 2-lite | Control mapping, cross-border transfer |
| Edge / Camera Infra | RTSP first; ONVIF spike; gateway ops | Gateway design, hardware spike, gateway rotation |
| Incident Response | Realistic attacker | Runbook, comms, severity matrix |
| Technical Writer | Demo & ops | Runbooks, README, demo script, **bystander notice template** |
| Red-Team-Aware Reviewer | Pre-pen-test self-attack | Gap log, T-30, T-45, T-56, browser-bundle scan |
| Access Control Specialist | Deny-by-default | RBAC, IDOR prevention, break-glass |

---

## 3. Finalized MVP/Pilot Decisions

- **IdP**: Google Workspace through Cloudflare Access; Cloudflare OTP is fallback only for IdP outage (Section 11.2).
- **Paid managed Postgres**: Neon-first; Neon Free only for prototype/MVP, Neon paid before pilot if PITR/no-cold-start/DPA/latency checks pass; Supabase Pro fallback (Section 12).
- **Project account email**: use a dedicated project/admin email for Railway, Cloudflare, LiveKit, Neon, GitHub, domain registrar, and observability accounts.
- **User role overlap**: default no user has both viewer and admin roles unless explicitly approved; least privilege remains the baseline.
- **NPC PIA**: lightweight PIA for MVP; full PIA before pilot.
- **Bystander population**: assume mixed minors/employees/visitors/public -> strict signage policy (Section 16.12).
- **Latency target**: <=2 s glass-to-glass remains the MVP target.
- **Pen-test modality**: internal security review for MVP; grey-box external review before pilot if budget allows, otherwise explicit risk acceptance.
- **On-call expectation**: solo/pair owner for MVP; at least two named responders before pilot.
- **Continuous streaming**: gateway publishes only while an authorized viewer is present in the LiveKit room (A6'); any always-on streaming change is ADR-gated.
- **Gateway identity**: service-token bootstrap for MVP; mTLS required before pilot with internal project CA unless Cloudflare mTLS is selected during implementation.
- **Production camera gateway**: real-camera gateways are on-site physical NUC-class x86_64 mini-PCs only; virtual/cloud gateways are allowed only for dev/CI synthetic RTSP and never for real cameras.

---

## 4. Assumptions

| # | Assumption | Risk if wrong |
|---|---|---|
| A1 | 2 camera feeds MVP | Over/under-engineering |
| A2 | 4 named users MVP | Capacity mismatch |
| A3 | Responsive web (no native); browsers are **viewers only** | Mobile UX gaps |
| **A4** | **Camera source is exclusively IP camera / NVR / RTSP / approved edge gateway (Inv 5)** | Drift to "webcam app" - prevented by CI grep (Section 24) and browser-bundle scan |
| A5 | Future ONVIF requires hardware-validation spike (Section 13.3) | Spike surprises |
| A6 | Always-on application (Inv 2) | Demo outage |
| **A6'** | **Gateway publishes a camera to LiveKit only while an authorized viewer is present** (room-presence-driven ingress via LiveKit webhooks) | Wrong bandwidth model; surprise bill |
| A7 | No public registration | Account abuse |
| A8 | Control-plane origin invisible (REQ-SEC-01) | Breach |
| A8' | Media plane bypasses control plane; if self-hosted, only media ports public (Inv 4) | Broken streaming or coupled blast radius |
| **A8''** | **Protected app routes fail closed without verified CF Access JWT (Inv 14)** | Spoofable trusted headers (F-001/F-002) |
| A9 | Audit tamper-evident, **versioned HMAC keys**, chain survives rotation | Forensic gap |
| A10 | Skilled adversary | Weak controls |
| A11 | Tight budget; procurement-time estimates | Overrun |
| A12 | Greenfield, no reuse | Wrong stack |
| A13 | Production-grade from day 1 | Rewrite / demo failure |
| A14 | APAC region (`sin` preferred; `nrt` DR) | Latency |
| A15 | CF Zero Trust tier verified at procurement | Surprise bill |
| A16 | LiveKit quotas verified at procurement; A6' keeps usage modest | Throttling |
| A17 | No recording in MVP (Inv 9) | User expects playback |
| A18 | Single developer | Bus factor 1 |
| A19 | IdP decision is Phase-0 deliverable | Wrong MFA lock-in |
| A20 | Neon free is prototype-only; pilot uses Neon paid PG with PITR if procurement checks pass; Supabase Pro fallback | Data loss |
| A21 | "CF bot/WAF protections available on selected plan" wording | Plan-tier variability |
| A22 | Phase-2.5 architecture checkpoint decides split vs monolith | Premature/delayed split |
| A23 | Self-hosted LiveKit fallback uses DigitalOcean Singapore or equivalent UDP-capable APAC host after UDP/media-port + TCP/TLS:443 verification | Broken fallback at activation |
| A24 | Pinned Python/FastAPI/Pydantic/SQLAlchemy versions; experimental APIs banned in security-critical paths | Auth/API drift |
| A25 | Provider-exit ADRs are the abstraction | Lock-in |
| A26 | No coupling between control plane and media plane | Lateral blast radius |
| **A27** | **Edge gateway is MVP-critical (Inv 6)** - RTSP-first via `mediamtx`; ships with at least one RTSP ingest before MVP exit | MVP cannot display any camera |
| **A28** | **Gateway identity bootstrap = strong service token + pinned fingerprint for MVP; mTLS required before pilot** (ADR 0008) | Gateway impersonation |
| **A29** | **Camera credentials never reach the browser or `cctv-api`'s general API surface** | Credential leak |
| **A30** | **Bystander privacy signage at every site** | PH DPA non-compliance |
| **A31** | **Temporary Railway generated URL is `https://panoptix-control-production.up.railway.app`; final user-facing URL remains Cloudflare Access protected custom domain** | Users bypass intended access path if Railway URL is treated as production entry point |

---

## 5. Product Requirements

Priority: **M**=MVP must, **P**=pilot, **F**=full prod, **X**=out-of-scope MVP, **N**=Not Supported (permanently, see Section 29).

### 5.1 Core viewer & admin

Live view of registered IP cameras - **M** · Grid 1x1 / 2x1 / 2x2 - **M** · Fullscreen - **M** · Camera online/offline/last-seen - **M** · States: reconnecting, unavailable, permission-denied, gateway-unavailable - **M** · Watermark viewer identity - **P** · Snapshots - **F** (ADR-gated) · Recording / playback - **F** (ADR-gated) · Motion detection - **F** · Privacy masking - **F**.

### 5.2 Security

- CF Access in front of every authed control-plane route - **M**
- Phishing-resistant MFA (WebAuthn/passkeys) via chosen IdP - **M**
- Device posture (e.g., WARP) for admins - **M**
- App-layer RBAC, deny-by-default - **M**
- **Two distinct token kinds** (viewer-subscribe / gateway-publish; browser sessions cannot mint gateway-publish) - **M**
- App session bound to CF JWT `sub` + low-risk device fingerprint (UA + Accept-Language only; Section 16.14) - **M**
- Strict CSP with nonces; no `unsafe-*`; `connect-src` pinned to specific LiveKit regional hosts - **M**
- Full security headers (HSTS preload, COOP/COEP/CORP, Referrer-Policy, **Permissions-Policy locking down camera/microphone**, X-Content-Type-Options) - **M**
- CSRF (double-submit + SameSite=Strict + Origin check) - **M**
- **Explicit CORS policy** (no wildcard on authenticated APIs; gateway APIs not browser-callable; Section 16.13) - **M**
- **Rate limits** (CF + app, Section 16.17 table) - **M**
- "CF bot/WAF protections available on the selected plan" - **M**
- **Audit hash chain with versioned HMAC keys** + DB-enforced immutability - **M**
- Secrets in managed stores; **separate secret store on the media-plane host and on the gateway** - **M**
- SCA (Dependabot + osv-scanner), SAST (Semgrep), container scan (Trivy), secret scan (gitleaks) - **M**
- IaC scan (tfsec / checkov) - **P**
- Pen-test gap log - **M**
- **External-exposure test (REQ-SEC-01)** - **M**
- **Origin-binding test (REQ-SEC-01c)** - **M**
- **Media-plane isolation test (REQ-SEC-01b)** - **M**
- **CCTV-only enforcement test set (REQ-CCTV-01)** - **M**
- **Break-glass admin** with `BREAK_GLASS_WINDOW_MINUTES = 90` and request-time enforcement - **M** (Section 16.6)
- **Lost-MFA recovery** (admin-mediated) - **M** (Section 16.7)
- **CF Access rollback runbook** - **M** (Section 20.9)
- **LiveKit quota-fallback runbook** with network-layer acceptance - **M** (Section 20.10)
- **Gateway lifecycle runbook** (register, rotate credential, disable, retire) - **M** (Section 20.14)
- **Provider-exit playbook** - **P** (Section 20.13)

### 5.3 Camera & gateway (MVP)

- **Edge gateway running `mediamtx`**, RTSP-first ingest from IP cameras / NVRs - **M**
- **Camera registry** (name, source type, assigned gateway, ACL) - **M**
- **Gateway registry** (name, identity, status, assigned cameras) - **M**
- **`gateway_camera_assignments`** join table (authoritative scope for gateway-publish tokens) - **M**
- **Gateway heartbeat** + camera online/offline/last-seen - **M**
- **Camera ACL** (per-user, per-camera) - **M**
- **Disable / retire camera** - **M** (immediate denial of new viewer tokens; existing rooms terminated within 10 s)
- **Disable gateway** - **M** (immediate denial of new ingest tokens; existing publish terminated within 10 s)
- **`synthetic_rtsp_test_source`** for development / CI - **M** (`mediamtx` test pattern)
- Offline alert - **P**
- **ONVIF Profile S/T** - **F** (conditional on Section 13.3 spike)
- **Production camera path documented and shipped (RTSP gateway in MVP)** - **M**
- **No browser/phone/webcam camera publishing** - **N** (Section 29)

### 5.4 User & admin

- List users, role assignment, camera ACL - **M**
- Disable user (immediate session kill **+ LiveKit room termination <=10 s** - see Section 13.5 hard rule 11) - **M**
- Invite via CF Access / IdP - **M**
- Audit log view with filter - **M**
- **Synchronous signed JSONL export** (no async `export_jobs` queue in MVP - see Section 21) - **M**

### 5.5 Audit & monitoring

- Append-only `audit_log` + HMAC chain + `hmac_key_version` per row - **M**
- All security events (Section 17) - **M**
- Daily archive to immutable object storage - **P**
- Tamper-check job (5-min cadence) - **P**
- **Backup integrity verification** (decrypt + `pg_restore --list` + checksum recorded in `backup_runs`) - **M**

### 5.6 Alerting (pilot unless flagged)

Failed-login burst, off-hours admin action, audit chain break, **camera offline >2 min**, **gateway offline >2 min**, error-rate spike, **LiveKit quota threshold**, **CF Access policy change**, **media-plane health degraded**, **gateway certificate expiring <=14 d**, **break-glass opened (M)**, **rate-limit anomaly**, **CSP violation**, **CORS rejection spike**.

### 5.7 Session

Idle 15 min; absolute 8 h; re-auth for admin - **M**; revoke-on-disable + LiveKit room termination - **M**; "active sessions" UI - **P**.

### 5.8 Data & privacy (PH DPA)

- PII minimisation - **M**
- Retention: audit 365 d / sessions 30 d / privacy-notice acceptances 7 yrs - **M**
- **Operator privacy notice on first login** - **M** (Section 16.11)
- **Bystander signage policy & template** at sites - **M** (Section 16.12)
- DPA / NPC Circular 16-01 checklist - **M** artefacts; **P** full execution
- DSR email channel with 15-day SLA - **P**
- **No-Recording-in-MVP policy doc** with technical enforcement - **M**
- **Cross-border transfer basis** documented per processor (CF, Railway, paid PG, IdP, LiveKit, R2, Sentry, Better Stack) - **M**

### 5.9 Performance / availability

TTFB <300 ms p50 / <800 ms p95 from PH - **M** · WebRTC glass-to-glass <2 s p95 - **M** · 99.5% MVP / 99.9% pilot / 99.95% full prod (control plane). Media plane tracked separately.

### 5.10 Operations

Runbooks (deploy, rollback, incident, restore, **CF Access rollback**, **LiveKit quota fallback**, **break-glass**, **lost-MFA**, **IdP outage**, **provider-exit per plane**, **DR to `nrt`**, **gateway lifecycle**, **gateway certificate rotation**) - **M / P** as scoped. Daily DB backup + weekly restore drill + **post-backup integrity check** - **M**.

### 5.11 Out of scope MVP

Recording / playback / analytics / multi-site / native app / SMS MFA / self-registration / self-service MFA reset / marketing page / continuous cloud streaming / experimental FastAPI/Pydantic/SQLAlchemy/LiveKit APIs in security-critical paths / `webauthn_metadata` mirror table / async `export_jobs` queue.

### 5.12 Permanently Not Supported (see Section 29)

Webcam · phone camera · laptop camera · browser camera · browser publisher · phone publisher · demo publisher · lab publisher · temporary publisher · compatibility publisher · `getUserMedia` · `MediaRecorder` · `navigator.mediaDevices` · `/publish` · `/demo-publisher` · `/lab-publisher` · `/webcam` · `/phone-publisher` - as feature, demo, internal, fallback, test, **and** compatibility paths.

---

## 6. Recommended Feature Set (challenged)

| Feature | Rec | Reason | Sec | Cmpx | MVP | Prod |
|---|---|---|---|---|---|---|
| Live viewing of registered IP cameras | Include | Core | H | M | yes | yes |
| Multi-cam dashboard | Include | Core UX | M | M | yes | yes |
| Fullscreen | Include | Trivial | L | S | yes | yes |
| Camera/gateway status (heartbeat + last-seen) | Include | Trust signal | M | S | yes | yes |
| **Edge gateway (`mediamtx`, RTSP-first)** | **Include - MVP** | Only ingest path under Inv 5 | H | M | yes | yes |
| **Camera registry + ACL** | **Include - MVP** | Authz/audit | M | S | yes | yes |
| **Gateway registry + assignments** | **Include - MVP** | Authz scope for publish tokens | H | S | yes | yes |
| **Synthetic RTSP test source** | **Include - MVP** | Dev/CI without hardware | L | S | yes | yes |
| **Camera/gateway health dashboard** | **Include - MVP** | Operator trust | M | S | yes | yes |
| Motion detection | Defer | Cost + storage | M | L | no | yes |
| Recording | **Defer; MVP forbids** | Blast radius + DPA | H | L | no | F |
| Playback | Defer | Needs recording | M | M | no | yes |
| Snapshots | F (ADR-gated) | DPA scope | M | S | no | yes |
| RBAC | Include | Mandatory | H | M | yes | yes |
| Audit logs (versioned HMAC) | Include | Mandatory | H | M | yes | yes |
| Login history | Include | Cheap / high value | M | S | yes | yes |
| Session mgmt UI + LiveKit room kill on disable | Include | Real-time revocation (F-003) | H | M | yes | yes |
| Device trust (WARP for admins) | Include | Strong defence | H | S | yes | yes |
| MFA via IdP | Mandatory | Phishing resistance | H | S | yes | yes |
| Admin panel (separate route + policy) | Include | Mandatory | H | M | yes | yes |
| Alerting | Pilot | Needs baseline | M | M | no | yes |
| Tamper detection (5-min) | Pilot | Hash-chain verifier | H | M | no | yes |
| Watermark (viewer email overlay) | Pilot | Deters screen-record exfil | M | S | no | yes |
| Synchronous signed JSONL audit export | Include | Cheap; sufficient at 4-user scale | H | S | yes | yes |
| **Async `export_jobs` queue** | **Drop from MVP** | Premature for 4 users | L | M | no | yes |
| **`webauthn_metadata` mirror** | **Drop from MVP** | IdP holds source of truth | L | S | no | yes |
| **Break-glass admin (90-min fixed window)** | Include | Recovery | H | M | yes | yes |
| **Lost-MFA recovery (admin-mediated)** | Include | Not self-service | H | S | yes | yes |
| **CF Access rollback runbook** | Include | Fast revert | H | S | yes | yes |
| **LiveKit quota-fallback runbook + T-37** | Include | Predictable migrate | H | M | yes | yes |
| **Gateway lifecycle (register / rotate / disable / retire)** | Include | Inv 6 needs ops glue | H | M | yes | yes |
| **Provider-exit playbook (per plane)** | Include | Pricing/quota/security drift | M | M | yes | yes |
| Account lockout via IdP | Include | IdP handles | H | 0 | yes | yes |
| Suspicious login detection | Pilot | CF + app heuristics | H | M | no | yes |
| **Edge gateway certificate rotation (mTLS, before pilot)** | Pilot | ADR 0008 | H | M | no | yes |
| Camera inventory | Include | ACL needs it | L | S | yes | yes |
| Firmware inventory | Future | Real cams only | M | M | no | F |
| NVR integration (`nvr_rtsp` source type) | Pilot | Real customers | M | M | no | yes |
| Multi-site | Future | OOS MVP | M | L | no | F |
| **Webcam / phone / browser publisher (any flavor)** | **Permanently Not Supported** | Inv 5 | - | - | N | N |

---

## 7. User Roles & Permissions (deny-by-default)

| Role | Allowed | Blocked | Camera | Admin | Audit | Gateway-publish token? |
|---|---|---|---|---|---|---|
| **SuperAdmin** | All admin including delete admins; rotate secrets | Viewing streams unless explicit ACL | None default | Full | Full + export | **No** |
| **BreakGlass** (sealed, **90-min** auto-expire) | Emergency SuperAdmin-equivalent on App C | Everything outside the window | None | Emergency | Full + use-alert | **No** |
| **Admin** | Create/disable users, role assignment, camera ACL, register/disable cameras and gateways, audit | Delete SuperAdmin; change own role | None default (self-grant audited) | All except SA | Full read; gated export | **No** |
| **Auditor** | R/O audit, R/O user/camera/gateway lists | No streams, no mutations | None | R/O audit | Full read + export | **No** |
| **Viewer** | View ACL'd cameras only | Admin pages, audit, user list, **all gateway endpoints** | Per ACL | None | None | **No** |
| **Gateway** (machine identity) | Publish to LiveKit rooms for cameras explicitly assigned via `gateway_camera_assignments`; heartbeat; report camera status | All user-facing endpoints; all admin APIs; viewer-subscribe tokens | All assigned | None | None | **Yes (publisher-only, per assignment)** |

Rules:
- Default role on enrolment = **none**.
- Camera ACL is a separate join table; user role does not implicitly grant cameras.
- Admin routes behind a **second** CF Access policy (admin group + WARP + recent re-auth).
- **BreakGlass** account: sealed offline, hardware security key, **`auto_disable_at = opened_at + 90 min` enforced at request time** even if scheduler fails (Section 16.6).
- **Gateway** authenticates with a service token (MVP) or mTLS client cert (pilot). Never granted any user-role permission, never receives a viewer-subscribe token.

---

## 8. User Stories

### 8.1 Viewer

- **US-1** Sign in with passkey/MFA via chosen IdP and see only ACL'd cameras.
- **US-2** Watch up to 2 simultaneous live streams with <2 s p95 glass-to-glass latency, with clear states for online / offline / reconnecting / unavailable / gateway-unavailable.
- **US-3** See a clear "offline" or "gateway unavailable" state for unhealthy cameras instead of a hung `<video>` element.
- **US-4** Be unable to reach `/admin` or any admin API; copies of stream URLs fail in a different browser within 60 s.
- **US-5** See the operator privacy notice on first login (and on material change), with acceptance recorded.

### 8.2 Admin

- **US-6** Manage users: invite via IdP, assign role, disable, reset MFA (admin-mediated).
- **US-7** **Register a camera** (name, gateway, ACL); **register a gateway** (name, identity); assign cameras to gateways.
- **US-8** Read full audit log; filter by user/action/time; export signed JSONL synchronously.
- **US-9** Re-authenticate for sensitive actions (delete, role change, secret rotate, gateway credential rotate).
- **US-27** **View gateway health** (heartbeat, last-seen, certificate expiry if mTLS) and **camera health** on a single dashboard.
- **US-28** **Disable a gateway** and observe its publish sessions terminated within 10 s; **disable a camera** and observe viewer rooms terminated within 10 s.

### 8.3 SuperAdmin

- **US-10** **Rotate audit-chain HMAC** (creates a new `audit_hmac_keys` row; new audit rows carry the new `hmac_key_version`; the chain remains verifiable end-to-end across the rotation boundary).
- **US-11** Configure system policy (session TTLs, retention, alert thresholds, **media-plane mode**, **gateway-identity tier**).
- **US-29** **Rotate a gateway's credential** (service token MVP, mTLS leaf cert pilot+) with a documented runbook; old credential revoked; audit `gateway.credential.rotated`.

### 8.4 Operator (security)

- **US-12** Run T-30 external-exposure on demand.
- **US-13** Run T-45 media-plane isolation on demand.
- **US-14** Run **T-56 origin-binding** on demand.
- **US-15** Toggle the LiveKit fallback feature flag and observe automatic reconnection within 60 s.
- **US-16** Open break-glass; window auto-denies after 90 minutes even if the worker/cron is restarted (T-52).

### 8.5 Privacy / DPA

- **US-22** New user sees the operator privacy notice on first login; acceptance recorded.
- **US-23** Admin generates DPA artefact bundle for NPC inquiry (synchronous signed JSONL).
- **US-30** Admin records that physical signage is posted at each camera site (`dpa_artifacts.kind = 'bystander_signage_attestation'`).

### 8.6 Edge / camera infra

- **US-24** Operator deploys a new gateway: registers it in admin UI, receives a one-time enrolment service token (MVP) or mTLS leaf certificate (pilot+), brings up `mediamtx` with the assigned cameras' RTSP credentials (camera credentials live exclusively on the gateway).
- **US-25** Self-hosted LiveKit fallback verified end-to-end at the network layer (UDP from a normal home/mobile network, TCP/TLS:443 fallback when UDP is blocked, no app endpoints reachable on the media host).
- **US-26** Provider pricing/quota change triggers a provider-exit ADR per the playbook.
- **US-31** Gateway certificate (pilot+) approaches expiry; alert at <=14 d; rotation runbook executes; audit captures issuance/deployment/fingerprint update.

---

## 9. Recommended MVP

**Goal**: a live 2-camera viewer fed exclusively by an `mediamtx` edge gateway pulling RTSP, that survives a hostile evaluator, runs always-on without a developer laptop, proves every control with logs and tests, separates control plane from media plane cleanly, and is DPA-ready including bystander signage.

**Included**:

1. Cloudflare Access on three policies (App A `/dashboard`, App B `/admin`, App C `/admin-emergency`) in front of the Railway-hosted control plane. **Google Workspace is the primary IdP (Section 11.2).**
2. Same-domain control-plane services: React + Vite frontend for `/dashboard`, `/admin`, `/admin-emergency`, and `/privacy`; FastAPI backend for `/api/v1/*` and `/health`.
3. Postgres (Neon free = prototype only; **paid managed Postgres before pilot** per Section 12).
4. **Media plane: LiveKit Cloud (APAC) primary**; **self-hosted LiveKit fallback on DigitalOcean Singapore or equivalent UDP-capable APAC host** (only media ports public, no shared trust with control plane).
5. **Edge gateway** (dev/CI synthetic host or on-site Linux) running `mediamtx`, RTSP-first; in MVP it ingests one real RTSP camera **and** one `synthetic_rtsp_test_source` for CI/dev.
6. RBAC: SuperAdmin / BreakGlass / Admin / Auditor / Viewer / **Gateway**.
7. Audit hash chain with `hmac_key_version` + verifier endpoint + immutable archive + chain-rotation test (T-49).
8. Health: `/health` behind CF Access **service token** returning only `{"status":"ok"}`; `/api/v1/admin/health/deep` admin-only; Better Stack heartbeat with service-token header; UptimeRobot external probe with service-token header. **Media-plane probe separate.**
9. CI/CD: GH Actions -> Trivy + Semgrep + osv-scanner + gitleaks -> Railway deploy. **T-30 + T-45 + T-56 + T-58 + T-59 in CI.**
10. Runbooks: deploy, rollback, incident, restore, CF Access rollback, LiveKit quota fallback (with network-layer acceptance), break-glass, lost-MFA, IdP outage, provider-exit per plane, DR to `nrt`, **gateway lifecycle**, **gateway credential rotation**.
11. Privacy notice + bystander signage attestation + DPA artefact bundle.
12. Demo script (CCTV-only; no browser-publisher demos).

**Explicitly excluded** (Inv 9 + Inv 5):
- No LiveKit Egress configured.
- No object-storage bucket for media.
- No `/snapshots` or `/recordings` UI route.
- No server-side frame capture code path.
- No client-side `MediaRecorder`.
- **No `/publish`, `/demo-publisher`, `/lab-publisher`, `/webcam`, `/phone-publisher` route.**
- **No `getUserMedia`, `navigator.mediaDevices`, browser-camera permission request.**
- **No publisher token issuable to a browser session.**
- **No camera credential exposed to any browser-fetched bundle or API response.**

**MVP success metrics**:

- 100% pre-pen-test checklist green (Section 19).
- 0 critical/high in self-attack + T-30 + T-45 + T-56 + T-58 + T-59 + T-60 + T-61 + T-62.
- p95 WebRTC latency <2 s.
- 7-day staging uptime >=99%.
- Audit hash chain verifies cleanly across an HMAC rotation (T-49).
- DPA artefact bundle complete; bystander signage attestation present.
- T-37 expanded rehearsed at least once with viewer + gateway reconnection <=60 s after fallback flip.

**MVP launch risks** (quantified Section 23):

- LiveKit quota gap or surprise bill (mitigated by A6' + alarms + fallback rehearsed).
- Self-hosted fallback fails at network layer (mitigated by UDP-capable provider verification + T-37 + TCP/TLS:443).
- Railway app/platform outage (health checks + external probes + rollback/redeploy/alternate-host DR path).
- CF Access policy misconfig exposing origin (IaC + drift detector + post-deploy T-30).
- Neon free cold-start at demo (keep-alive; paid tier upgrade at pilot).
- **Gateway credential leak / impersonation** (service-token bootstrap + fingerprint pin + mTLS before pilot + rotation runbook).
- **Camera RTSP credential leak** (gateway-only secret scope + CI grep on browser bundle for `rtsp://` and known cred-env names).

---

## 10. System Architecture

### 10.1 Logical diagram (control plane vs media plane vs camera plane)

```
                              [ Public Internet ]
                                      |
   ============== CONTROL PLANE (HTTP only, behind CF Access) =========== |
                                      |                                   |
                       DNS (orange-cloud) -> CF anycast                    |
                                      |                                   |
       +----------- Cloudflare Edge (HTTP/HTTPS) -----------+             |
       | DNS · WAF · bot · rate-limit (per selected plan)   |             |
       | Cloudflare Access (IAP - gateway only, not IdP)    |             |
       |   App A /dashboard /api/v1/{me,cameras,sessions}   |             |
       |   App B /admin /api/v1/admin/*                     |             |
       |   App C /admin-emergency  (break-glass)            |             |
       |   Service-Token policy -> /health (monitor probes)  |             |
       | Federates to IdP (Phase 0 Section 11.2)                   |             |
       | Forwards valid Access JWT to supported app domain  |             |
       +----------------------------------------------------+             |
                                      | HTTPS to supported custom domain |
                                      v                                  |
       +------ Railway Control Plane (same-domain services) -------------+
       | Inv 14: protected routes fail closed without valid CF Access JWT |
       |  - Cf-* headers ignored unless JWT verification succeeds         |
       |  - verify Cf-Access-Jwt-Assertion vs CF JWKS (aud+iss pinned;    |
       |    exp/nbf with CLOCK_SKEW_SECONDS = 30; fail-closed JWKS cache) |
       |  - React + Vite/Tailwind frontend for UI routes                  |
       |  - FastAPI + SQLAlchemy/Alembic backend for /api/v1/*            |
       |  - mints VIEWER tokens (<=60 s, subscriber-only, jti, session-bd) |
       |  - mints GATEWAY tokens (<=60 s, publisher-only, gateway+camera)  |
       |  - LiveKit room API: terminate participant on user/gateway disable
       |  - writes hash-chained audit_log with hmac_key_version           |
       +------------------------------------------------------------------+
              |                    |                       |
              v                    v                       v
   +------------------+  +-----------------------+  +--------------------+
   | Managed Postgres |  | Cloudflare R2 (objlock)| | Better Stack /     |
   |  Neon free=proto |  |  DB backups (age-enc) |  | Sentry / UptimeRobot|
   |  paid pilot+PITR |  |  Audit log archives   |  | Service-token probes|
   |  least-priv role |  |  Backup_runs ledger   |  | (PII scrubbed)     |
   +------------------+  +-----------------------+  +--------------------+

   ============== MEDIA PLANE (WebRTC, NOT through control plane) =======
                                                                       |
        [ LiveKit Cloud (APAC) - PRIMARY; UDP preferred, TCP/TLS:443 ] |
                                                                       |
                          --- OR (fallback flag on) ---                |
                                                                       |
        [ Self-hosted LiveKit fallback - DigitalOcean SG or equivalent ]|
        | Provider must support UDP/media ports + TCP/TLS:443 fallback   |
       | Only LiveKit media ports exposed; NO app/admin/DB             |
       | Separate media-plane secrets; no DB egress                    |
       | LiveKit webhook -> cctv-api /api/v1/webhooks/livekit (signed)  |

   ============== CAMERA PLANE (RTSP, on-site / VLAN) ==================
                                                                       |
   [ IP camera / NVR ] <---RTSP---> [ Edge Gateway (`mediamtx`) ]         |
                                  | Auth to cctv-api /api/v1/gateways/* |
                                  |   service-token (MVP)               |
                                  |   mTLS client cert (pilot+)         |
                                  | Receives short-lived gateway-publish|
                                  |   token (<=60 s)                     |
                                  | Publishes to LiveKit when a viewer  |
                                  |   is present in the room (A6')      |
                                  | Camera credentials NEVER leave gw   |

   PUBLISHERS: ONLY edge gateways. NO browsers. NO phones. NO laptops.
   VIEWERS:    Authenticated browsers via LiveKit subscriber tokens.
```

### 10.2 Component responsibilities

- **Cloudflare Access (IAP)** - control-plane identity-aware proxy. Federates to the IdP. WAF / bot per selected plan. Issues a **Service-Token policy** for the `/health` endpoint used by external monitors (Better Stack / UptimeRobot).
- **Railway-hosted React + Vite frontend** - dashboard, admin, emergency, privacy, camera-grid, status, forms, and LiveKit viewer components. It displays state and calls same-origin `/api/v1/*`; it never decides authorization, mints stream tokens, stores long-lived auth tokens, or receives camera RTSP credentials.
- **Railway-hosted FastAPI backend (cctv-api)** - API, authz, session validation, viewer-token + gateway-token minting, audit writes, LiveKit room management on user/gateway disable, LiveKit webhook receiver, gateway endpoints, and database access. Origin-bound by fail-closed CF Access JWT verification (Inv 14 / ADR 0010). JWKS cache 10 min, **fail-closed with bounded staleness**. No passwords. No self-service MFA reset. No recording.
- **Postgres** - primary store; audit hash-chained with DB-enforced immutability + `hmac_key_version`. **Runtime role least-priv** (Inv 15). Neon free = prototype; paid managed PG with PITR for pilot.
- **LiveKit Cloud (primary media plane)** - public TURN/SFU; gateways and viewers connect directly; `iceTransportPolicy: 'relay'` enforced server-side on minted tokens (F-009 fix); 60-second tokens minted by the control plane.
- **Self-hosted LiveKit fallback** - separate UDP-capable media host, with DigitalOcean Singapore as the first procurement candidate and equivalent APAC VPS/provider as fallback; only LiveKit media ports + TCP/TLS:443 fallback. **No app endpoints. No DB egress. Separate secret store.** Activated by feature flag after provider verification.
- **Edge gateway (production on-site physical NUC-class mini-PC; dev/CI synthetic host allowed only for fake RTSP)** - `mediamtx` ingests RTSP from IP cameras, holds camera credentials in its own secret store, publishes to LiveKit only with a current gateway-publish token, posts heartbeat + camera status to `cctv-api` over CF Access service-token (or mTLS in pilot+). Real cameras are never connected through a virtual/cloud gateway.
- **R2** - encrypted archives with object lock (compliance mode); also stores `backup_runs` evidence.
- **Better Stack / Sentry / UptimeRobot** - observability with separate tags `plane=control|media|camera`. **Sentry payloads PII-scrubbed** (email, user_id, idp_subject, IP, UA, camera/gateway names hashed; Section 16.15).

### 10.3 Data flows

- **User auth flow**: Browser -> CF Access -> chosen IdP (challenge + MFA) -> IdP redirect -> CF mints JWT -> Railway-hosted React + Vite frontend renders UI; same-origin FastAPI backend verifies CF JWT (`aud`+`iss` pinned, `exp`/`nbf` ± `CLOCK_SKEW_SECONDS`) on protected API routes.
- **Viewer-token issuance**: viewer requests `GET /api/v1/cameras/:id/view-token` -> app authorizes against `camera_acl` AND camera-not-retired AND user-not-disabled AND session-not-revoked -> mints LiveKit JWT (<=60 s, subscriber-only, opaque room UUID, `jti` recorded in `stream_grants`) -> returns to client.
- **Gateway-ingest issuance**: gateway calls `POST /api/v1/gateways/:id/ingest-token` with service-token / mTLS client cert -> app validates gateway identity, gateway-not-disabled, camera-not-retired, `gateway_camera_assignments` row exists and not revoked -> mints LiveKit JWT (<=60 s, publisher-only, opaque room UUID, `jti` recorded) -> returns to gateway.
- **Media flow (direct, bypasses control plane)**: gateway and viewer use their tokens to connect directly to LiveKit Cloud or fallback. Tokens refresh every <=60 s. **Camera credentials never leave the gateway.**
- **URL-leak failure mode**: copied URL (a) lacks the CF Access cookie for the control plane and (b) carries an expired media token within 60 s.
- **Disable-propagation flow**: admin disables user -> app revokes session(s) -> app calls LiveKit room API to remove participant for that user -> audit `auth.session.revoked` + `livekit.participant.removed` (<=10 s SLO; T-49-equivalent integration test in Section 18).
- **Webhook flow**: LiveKit fires room/participant events -> `POST /api/v1/webhooks/livekit` (signed; replay-protected by timestamp + HMAC check) -> app updates `camera_events` and dashboard SSE stream.

### 10.4 Failure handling & DR

- **CF Access misconfiguration** -> rollback runbook (Section 20.9).
- **LiveKit Cloud quota / outage** -> fallback runbook (Section 20.10) flips feature flag; viewers + gateway reconnect <=60 s.
- **IdP outage** -> CF one-time-PIN secondary policy enabled (Section 20.11).
- **Break-glass** -> admin-emergency CF Access app + sealed credential + 90-min auto-disable (Section 16.6).
- **Provider-exit** (CF / Railway / PG / LiveKit) -> per-plane migration playbook (Section 20.13).
- **Region/platform outage** -> **MVP DR = restore/redeploy to the selected Railway region/environment after provider recovery or to an alternate container-compatible host**. Cross-region hot standby is pilot+ (M-10). Media plane fails over independently to LiveKit Cloud's regional alt or self-hosted instance.
- **Gateway offline** -> camera shown as "gateway unavailable"; viewer cannot mint view-token (or token mints but room is empty); alert at 2-minute threshold.
- **Gateway credential compromise** -> admin disables gateway -> existing publish revoked within 10 s -> rotation runbook re-issues credential.
- **DR targets**: RPO <=24h MVP / <=1h pilot (PITR); RTO <=4h MVP / <=1h pilot. Restore-drill runs an integration query post-restore (F-011 fix). MVP RTO assumes restore to the same region; `nrt` cross-region DR (pilot+) tightens this.

---

## 11. Access & Identity Architecture

### 11.1 Access gateway decision

Cloudflare Access is retained as the **control-plane** IAP. Cloudflare Tunnel is no longer assumed for the Railway-hosted control plane. Tunnel remains HTTP-only and is explicitly not used for WebRTC media. Inv 14 is enforced by fail-closed CF Access JWT verification on every protected FastAPI route plus Railway/Cloudflare ingress hardening where available.

### 11.2 Primary IdP decision (locked)

**Primary IdP MUST support phishing-resistant MFA (WebAuthn/passkey, FIDO2, hardware keys). Email-OTP-only providers are not eligible as the primary IdP** (H-01 - RA 10173 + NIST SP 800-63B AAL2 alignment).

| Option | MFA | Fit | DPA | Cost (procurement-time est.) | Pros | Cons | Eligible as **primary**? |
|---|---|---|---|---|---|---|---|
| **Google Workspace** | WebAuthn passkey, hardware keys, push | Common for PH schools | Well-understood DPA | Existing seat; else ~$6/user/mo | Strong MFA | Adds processor | **done Yes** |
| **Microsoft Entra ID** | WebAuthn, hardware keys, Authenticator | If on M365 | Processor DPA available | Free tier available | Strong MFA; conditional access | Complex if not on M365 | **done Yes** |
| **GitHub** | WebAuthn, TOTP | Devs only | Processor DPA available | $0 | Dev-friendly | GH-only identities | **done Yes** |
| **Okta** | WebAuthn, FIDO2, push | Enterprise-ready | Processor DPA available | Paid per user | Most mature | Cost overhead | **done Yes** |
| **CF one-time-PIN** | Email OTP only | Easiest | CF already a processor | $0 incremental | Zero new vendor | **OTP only - not phishing-resistant** | **No No** - fallback only (Section 20.11) |

**Decision**: Google Workspace is the primary IdP through Cloudflare Access. **Passkey/WebAuthn required**; SMS MFA prohibited (NIST SP 800-63B). **CF one-time-PIN is retained only as the IdP-outage fallback (Section 20.11), where it is constrained, alarmed, and time-boxed.** **Decision artefact: ADR 0002**.

### 11.3 Layered access policies

- **App A** `/dashboard`, `/api/v1/{me,cameras/*,sessions/*}` - users group + MFA via IdP.
- **App B** `/admin`, `/api/v1/admin/*` - admin group + WARP device posture + recent re-auth <=5 min + (pilot) mTLS client cert.
- **App C** `/admin-emergency` - break-glass account only + hardware security key; window auto-disabled at `opened_at + BREAK_GLASS_WINDOW_MINUTES = 90 minutes` (Section 16.6).
- **Service-Token policy** (App D) `/health` - single-purpose, monitor-only; rotated quarterly; audit on rotation.
- **Service-Token policy** (App E) `/api/v1/gateways/*` (MVP) - gateway-only; one service token per gateway; rotated on credential rotation; replaced by mTLS client cert in pilot+.

### 11.4 JWT validation (anti-forgery, F-002 fix included)

- Validate every request's `Cf-Access-Jwt-Assertion` against CF JWKS.
- Verify `iss` (pinned to a single CF team domain), `aud` (= the app's CF Access AUD tag), `exp` and `nbf` with **`CLOCK_SKEW_SECONDS = 30`** (named constant, hard-coded). Skew is intentionally kept small (30 s tolerates routine NTP drift; multi-minute tolerance would weaken replay protection).
- **Railway origin-binding (Inv 14 + F-002 fix)** - protected routes reject unless the `Cf-Access-Jwt-Assertion` verifies successfully. `Cf-Connecting-IP` and other Cloudflare/forwarding headers are used only as metadata after JWT verification succeeds; otherwise they are ignored/stripped.
- JWKS cache: 10 minutes, **fail-closed with bounded staleness** (if refresh fails, requests are rejected after the staleness window expires; never fail-open).
- Unit + integration tests:
  - **T-47** `nbf = now + 25s` -> accepted.
  - **T-48** `nbf = now + 60s` -> rejected.
  - Expired token outside tolerance -> rejected.
  - Invalid `iss` / `aud` / signature -> rejected.
- Semgrep rule `require-cf-jwt-verification` ensures no route skips verification.
- **`jti` replay-protection scope (M-11)**: `jti` is captured in `stream_grants` to prevent replay of the **app's token-mint API call** (a viewer/gateway re-submitting the same mint request to extract another media token). **It is not a media-token replay defense at LiveKit** - LiveKit does not consult an external `jti` blocklist. Media-token replay defense is the 60-s TTL: a stolen media token expires before it can be reused at scale. Tests T-50 / T-60 / T-61 verify the right protection at the right layer.

### 11.5 Gateway identity (ADR 0008 - Edge Gateway Identity and mTLS CA Design)

**MVP (bootstrap)** - strong service-token + pinned fingerprint:

- One service token per gateway, generated server-side, delivered to the gateway out-of-band over an authenticated channel (admin enrolment UI download; one-shot retrieval).
- Stored on the app side as `edge_gateways.service_token_hash` (Argon2id of the token; raw token never persisted server-side after issuance).
- Stored on the gateway as a 0600-mode file:
  - **On-site mini-PC (production, Section 13.8)**: `/etc/cctv-gateway/gateway.env`, mode `0600`, owner `cctv-gateway:cctv-gateway`, loaded via `systemd EnvironmentFile=` directive on the `cctv-gateway.service` unit. Never embedded in code, never logged, never readable by other system users. Rotation procedure in Section 20.14.
  - **Dev/CI synthetic gateway**: secret loaded into the process environment of the chosen dev/CI host; same handler logic, different storage backend.
- Every gateway request must present `Authorization: Bearer <service-token>` over a CF Access service-token-policy-protected route.
- App validates: token hash matches, gateway not disabled, request path is gateway-scoped only.
- Rotation runbook (Section 20.14): generate new token -> deliver to gateway -> switch over -> revoke old -> audit `gateway.credential.rotated`.

**Pilot+ (mTLS client cert)** - ADR 0008 minimum design:

- **CA**: self-managed internal CA (offline root + online intermediate) seeded during Phase 0; root key escrowed in sealed envelope (dual control). Alternative: Cloudflare mTLS - chosen at procurement; ADR 0008 records the decision.
- **Trusted CA root** stored on the app side as a configuration/secret under Railway secrets or the selected secret manager; root rotation procedure documented separately.
- **Gateway leaf certificates** are 90-day, issued from the intermediate CA, with CN = gateway ID, SAN = gateway hostname.
- **Fingerprint pinning**: `edge_gateways.mtls_fingerprint` stores the SHA-256 fingerprint of the leaf cert; every gateway request validates: trusted CA chain -> certificate fingerprint matches -> gateway enabled -> request scoped to assigned cameras.
- **Cert expiry tracking**: `edge_gateways.cert_expires_at` stored on issuance.
- **Rotation alert**: alert fires at `cert_expires_at - 14 days`; runbook (Section 20.14) issues a new leaf, deploys to the gateway, updates the fingerprint row, audits issuance + deployment + fingerprint update.
- **Server endpoint verification**: gateway pins the app's TLS leaf or its issuer chain; ADR 0008 records which.
- **Revocation**: compromised gateway credentials -> admin disables gateway -> fingerprint marked revoked -> existing publish terminated within 10 s -> rotation runbook issues replacement.
- **Audit events**: `gateway.cert.issued`, `gateway.cert.deployed`, `gateway.cert.fingerprint.updated`, `gateway.cert.revoked`, `gateway.cert.expiring_soon_alert`, `gateway.credential.rotated`.

ADR 0008 is created during Phase 1 and updated when the procurement-time CA decision is made. **mTLS is required before pilot.**

### 11.6 Trusted-header policy (F-002 fix)

Only a verified `Cf-Access-Jwt-Assertion` establishes identity (Inv 14). Headers such as `Cf-Connecting-IP`, `Cf-Ray`, `X-Forwarded-For`, and `X-Real-IP` are treated as metadata only after JWT verification succeeds. If verification fails, those headers are ignored or stripped before any handler reads them. T-56 verifies this end-to-end.

**Trusted-header allow-list policy (N-03)** - second layer of defense:

- FastAPI middleware explicitly allow-lists the Cloudflare/request headers it will use: `cf-access-jwt-assertion`, `cf-ray`, `cf-connecting-ip`, plus standard request headers (`host`, `user-agent`, `accept`, `accept-encoding`, `accept-language`, `content-type`, `content-length`, `cookie`, `authorization`).
- **Any other `cf-*` or `cf-access-*` header is ignored before route handler identity construction**.
- This means a request cannot smuggle a forged `cf-access-*` extension header.
- **T-64** verifies that injecting a forged `cf-access-jwt-assertion` or arbitrary `cf-access-username-override`-style header is rejected/ignored.

---

## 12. Technology Stack Recommendation

*All pricing figures are procurement-time estimates. Verify before committing.*

| Layer | Choice | Why | Security notes |
|---|---|---|---|
| Frontend framework | **Railway-hosted React + Vite + Tailwind** (pinned exact versions) | Dedicated frontend owner gets a clear UI surface for dashboard/admin/video components. | Frontend is not security authority; no browser-stored auth tokens; bundle scan bans publisher APIs and RTSP secrets. |
| Backend framework | **Railway-hosted Python FastAPI** (pinned exact versions) | FastAPI provides explicit API routes, Pydantic validation, and clear auth middleware. | Security-critical paths avoid experimental APIs; protected API routes verify CF Access JWT fail-closed. |
| Browser video client | **LiveKit JavaScript client inside React viewer components only** | Browser still needs JS for WebRTC playback. | Viewer-only; no browser publishing; Permissions-Policy denies camera/microphone. |
| API style | FastAPI route handlers with Pydantic schemas; same-domain `/api/v1/*` routing from React frontend paths. | Explicit Python API surface ships quickly and is easy to test. | Same-origin by default to avoid CORS complexity; FastAPI remains the security authority. |
| Database (prototype) | **Neon Postgres free tier (APAC)** - prototype only | Free; fine for early dev | Cold-starts + no PITR disqualify it from production pilot. |
| Database (pilot, pick one) | **Neon Launch / paid equivalent** (~$19/mo, PITR, no cold-starts) primary if checks pass · **Supabase Pro** (~$25/mo, PITR) fallback · Railway-compatible PG or enterprise PG later if needed | Production needs PITR + no cold-starts + SLA | `sslmode=require`; **least-privilege app role (Inv 15)**; audit table grants `INSERT/SELECT` only. |
| ORM | SQLAlchemy 2.x + Alembic | Standard Python Postgres stack; migrations are explicit. | Prepared statements; no raw SQL in handlers except reviewed migrations. |
| Cache | None for MVP | 4 users doesn't justify Redis | - |
| Queue | None for MVP | No async jobs (sync JSONL export instead) | - |
| Identity (IAP) | Cloudflare Access (see Section 11.2) | Phishing-resistant once federated to passkey IdP | JWT + JWKS verification; `aud` + `iss` pinning. |
| Media plane (primary) | LiveKit Cloud (APAC) | Mature SFU; client connects directly; UDP + TCP/TLS:443 | 60 s tokens; viewer/gateway distinct; `iceTransportPolicy: 'relay'` enforced; no media via Tunnel. |
| Media plane (fallback) | Self-hosted LiveKit on **DigitalOcean Singapore or equivalent UDP-capable APAC host** | Same SDKs and room model; provider-exit path. | Railway is not selected for fallback; only media ports public; T-37 + T-45 acceptance. |
| **Edge camera gateway** | **`mediamtx vX.Y.Z`** (exact version pinned in ADR 0007 at Phase 0 exit; Renovate watcher tracks `bluenviron/mediamtx` releases) in camera VLAN - **RTSP-first**; ONVIF after spike (Section 13.3) | Mature; single Go binary | Read-only FS; outbound-only auth to control plane; no inbound RTSP from internet; HTTP API bound to `127.0.0.1:9997` only OR disabled (Section 13.8 / Section 20.14). |
| Control-plane ingress | Cloudflare Access in front of Railway custom domain | Identity-aware gate before app; app still verifies CF JWT fail-closed. | Railway origin URL is not a supported entry point; direct origin requests reject protected routes. |
| Hosting (control plane app) | Railway control-plane services: `cctv-web` React + Vite frontend + `cctv-api` FastAPI backend | Matches team split while keeping Railway as the control-plane host. | Inv 14: protected API routes require verified CF Access JWT; public user entry remains Cloudflare Access custom domain. |
| Hosting (media plane fallback) | DigitalOcean Singapore first candidate; equivalent UDP-capable APAC VPS/provider fallback | LiveKit fallback needs media networking not guaranteed by Railway. | Public on media ports only. |
| Hosting (edge gateway - **dev / CI / synthetic only**) | Chosen dev/CI host, FFmpeg synthetic-RTSP source (Section 13.7) | Consistent tests; no real cameras | Outbound-only auth to `cctv-api`; LiveKit publish; **never connected to real cameras**; CI artefacts only. |
| **Hosting (edge gateway - production)** | **On-site NUC-class mini-PC**, Ubuntu 22.04 LTS x86_64, single Docker image; per-site box (Section 13.8); ADR 0013 | Co-located with cameras; LAN-side RTSP; survives WAN flap | Outbound-only auth to `cctv-api`; LiveKit publish; RTSP pull from camera VLAN only; no inbound WAN ports; secret store at `/etc/cctv-gateway/gateway.env` 0600 + systemd EnvironmentFile (Section 11.5). |
| CI/CD | GitHub Actions -> Railway deploy for frontend and backend services | Repeatable deploys; Railway secrets/environment managed per env. | Branch protection; signed commits; lockfile-only installs; frontend bundle scan; Cosign image signing where containers are used. |
| Testing | pytest, Playwright, ZAP baseline, k6, network-layer scripts, browser-bundle scanner | Python-native backend tests + browser E2E. | All CI-gated. |
| Security scanning | Semgrep, osv-scanner, Trivy, gitleaks | Free, well-maintained | Fail-on-high gates. |
| Container | `python:3.12.x-slim-bookworm` or Railway-supported Python runtime pinned to exact patch/digest where containerized | Minimal attack surface; Inv 12 | Non-root UID where containerized; Dependabot/Renovate tracks patch updates. |
| IaC | Terraform/config-as-code (Cloudflare + Railway + Postgres + R2 + LiveKit fallback where supported) | Declarative where provider support exists | `tfsec` / `checkov` in CI. |
| Monitoring | Better Stack + UptimeRobot first; Sentry optional when app error tracking is needed | Generous free tiers (verify); paid for pilot | Plane-tagged; **PII scrubbed in Sentry payloads (Section 16.15)**; email-first alerts; Telegram optional with token inventory + rotation runbook (Section 20.16). |
| Logging | App -> stdout -> Railway logs / Better Stack | Centralized; queryable | Audit logs remain in Postgres (authoritative). |
| Secrets | Railway environment/secrets for control plane + separate media/gateway secret stores | Encrypted at rest; **separate stores per plane and per gateway** | Rotation runbook. |
| Backup | GitHub Actions scheduled job: `pg_dump` -> `age` encrypt -> R2 (object lock); **post-backup `pg_restore --list` integrity check** + checksum + row-count estimate recorded in `backup_runs`; alert on failure | Reproducible, immutable, **verified** | Keys in GitHub Actions backup-job secrets or selected scheduler secret store; weekly restore drill. |
| Incident response | Email-first (MVP); Telegram optional; at least two named responders before pilot | Simple, free | Runbooks in repo; **Telegram bot token rotation runbook + leak-response runbook (Section 20.16)** if Telegram is enabled. |

### 12.1 Cost sketch (monthly, USD, procurement-time estimates - verify before committing)

| Item | MVP | Pilot | Full prod |
|---|---|---|---|
| Cloudflare (DNS/WAF/Access/R2) + Zero Trust seats | free tier (verify) | small paid tier if plan changes | tier for full prod |
| Railway control-plane app | **free/low tier first** | paid tier only if required later for reliability | scales with usage |
| Self-hosted LiveKit fallback host | DigitalOcean Singapore / equivalent APAC VPS quote after UDP-capable provider check | To quote | To quote |
| Dev/CI synthetic gateway host | free/low tier where possible | low paid if needed | per CI needs |
| Managed Postgres | $0 (Neon free, prototype) | **~$19-30 (paid; mandatory for pilot)** | ~$60-100 |
| LiveKit Cloud (A6' - gateway publishes only when viewer present) | verify quota; likely free for MVP | possibly free or low paid; budget ~$0-50 | depends on usage |
| Observability stack | free tiers | ~$25 | ~$60 |
| Domain | ~$1 | ~$1 | ~$1 |
| IdP seats | Google Workspace existing seats if covered; otherwise per-seat | per-seat | per-seat |
| **Total (indicative)** | **Use free tiers first where possible** | **To quote later** | **To quote later** |

Current project decision: use free tiers first for the prototype. The cost sketch is re-verified later only when the project moves beyond prototype/free-tier development.

### 12.2 Provider-exit considerations (per plane)

| Plane | Primary | Realistic alternates if exit triggered (Section 20.13) | Migration handle |
|---|---|---|---|
| Control-plane IAP | Cloudflare Access | Tailscale/Headscale + nginx + IdP-direct; AWS ALB + Cognito + WAF; Pomerium | DNS/policy swap; app still verifies upstream identity |
| App hosting | Railway | Render / DigitalOcean / AWS App Runner or another Python/container-compatible host | Container/runtime-portable; secrets re-provisioned |
| Postgres | Chosen paid tier (ADR 0003) | Any Postgres-compatible managed service | `pg_dump` + `pg_restore` runbook |
| Media plane | LiveKit Cloud -> self-hosted LiveKit fallback | mediamtx WebRTC; another SFU vendor | Feature-flag swap; client SDK changes if vendor changed |
| Edge gateway | `mediamtx` on dev/CI host / on-site | Other RTSP-WebRTC bridges (e.g., GStreamer pipeline, Janus, Pion-based) | Per-site re-imaging |

The four+one planes are deliberately decoupled by configuration and runbook, not code-level interface abstractions, to avoid over-engineering at this scale.

---

## 13. Video Streaming Design

### 13.1 Protocol / topology comparison

| Option | Latency | Sec risks | Complexity | MVP fit | Prod fit |
|---|---|---|---|---|---|
| **WebRTC SFU - LiveKit Cloud** (direct, bypasses CF) | 100-500 ms | Token leakage if TTL too long | M | **done Primary** | done |
| WebRTC SFU - self-hosted LiveKit on DigitalOcean Singapore or equivalent UDP-capable APAC host | 100-500 ms | Same + ops burden | H | **done Fallback after host verification** | done at scale |
| **`mediamtx` RTSP->WebRTC at edge** | 100-500 ms | RTSP cred handling on gateway only | M | **done MVP edge gateway** | yes |
| HLS / LL-HLS | 2-30 s | Segment URL leakage if unsigned | M | no too slow | yes for recording (future) |
| RTSP relay to browser | - | Browsers unsupported | - | no | no |
| **Browser publisher (`getUserMedia`)** | - | **Forbidden by Inv 5** | - | **N** | **N** |

### 13.2 Media-usage model (revised - A6')

- The application is **24/7 reachable**; viewers can authenticate at any time.
- **The edge gateway publishes a camera to LiveKit only while an authorized viewer is present in the room** (room-presence-driven ingress, signalled by LiveKit room/participant webhooks).
- IP cameras may stream RTSP **continuously and locally** to the gateway; the gateway only republishes to the cloud media plane on viewer presence.
- This keeps LiveKit minutes proportional to viewer demand. Quota alarms still mandatory at 70 / 90 % of whichever quota is verified.
- ADR-gated change: continuous cloud streaming or recording would invalidate this and require Inv 9 + DPA re-review.
- Self-hosted fallback remains a required provider-exit path, with host selection gated by UDP/media-port verification.

### 13.3 Camera ingest scope (RTSP first; ONVIF via spike)

- **MVP**: `mediamtx` RTSP-pull on the camera VLAN. Works with virtually all IP cameras and NVRs. Camera credentials live on the gateway, never on the app, never in the browser.
- **`synthetic_rtsp_test_source`**: an `mediamtx` test pattern source for CI / dev / demo without hardware. Treated as a real camera for ACL/audit purposes; flagged in admin UI as `synthetic` so operators do not confuse it with production.
- **NVR (`nvr_rtsp`)**: same protocol, different secret-handling pattern (per-camera channel URL); pilot+ feature for real customer sites.
- **ONVIF Profile S/T (conditional on hardware spike)**: 7-day soak with one representative camera. Spike scope: Profile S (RTSP), Profile T (H.264/H.265), basic vs digest auth, WS-Discovery, reconnect after gateway restart, clock-skew tolerance, event channel stability. Exit criteria: reconnect >=99 %, no credential leak in captures, stable mediamtx behaviour, vendor-specific config documented. If the spike fails for a vendor, fall back to RTSP-only for that vendor (T-43, T-44).

### 13.4 Self-hosted LiveKit fallback - networking model

Mandatory:

- UDP/media-port support on the selected fallback host; dedicated public endpoint/IP if required by that provider.
- UDP media ports as primary transport.
- TCP/TLS:443 fallback for clients on networks that block UDP.
- No HTTP application surface on the media host. Only LiveKit's media protocol surface.
- Separate media-plane secret store, separate observability tags, no DB egress.
- The media host is not behind Cloudflare Access and is not part of the control-plane ingress path.
- TURN over TLS:443 is part of the LiveKit configuration.

Acceptance is gated by **T-37 (expanded)** and **T-45**.

### 13.5 Hard rules (non-negotiable)

1. Camera feeds are never exposed at unauthenticated URLs.
2. **Two distinct token kinds**: viewer-subscribe (<=60 s, subscriber-only) and gateway-publish (<=60 s, publisher-only). Browser sessions can never mint gateway-publish.
3. Tokens are server-minted, server-authorized, replay-detected via `jti` recorded in `stream_grants`.
4. Copied stream URL fails in a different browser/session within 60 s.
5. **Camera/NVR credentials never reach a browser, the app's general API surface, or the audit log payload.**
6. TURN over TLS:443 (LiveKit default).
7. Room names are opaque UUIDs.
8. **WebRTC media must not route through Cloudflare Access/Tunnel or the control plane.**
9. **The media plane host (fallback) exposes only media ports** and shares no trust with the control plane.
10. **`iceTransportPolicy: 'relay'` enforced server-side on all minted tokens** (no host-candidate leakage of private IPs; F-009 fix).
11. **User disable propagates to LiveKit <=10 s**: the app calls LiveKit room API to remove the disabled user's participant; gateway disable similarly terminates the gateway's publish (F-003 fix).
12. **No browser route may request camera permission, call `getUserMedia`, call `MediaRecorder`, or publish media** (Inv 5).
13. **LiveKit webhook receiver authenticates with shared secret + replay-protected timestamp** (F-012 fix). **Timestamp window = 60 seconds**: webhooks where `abs(now - webhook.createdAt) > 60s` are rejected with HTTP 400 and audit `livekit.webhook.replay_rejected`. Webhook is server-to-server only - see CORS rules in Section 16.13. T-63 verifies.
14. **CSP `connect-src` is pinned to specific LiveKit regional hostnames** (no `wss://*.livekit.cloud` wildcard; F-008 fix). When the fallback flag flips, the CSP header dynamically adds the fallback domain.

### 13.6 References

- W3C WebRTC Security Architecture (RFC 8826 / 8827).
- LiveKit "Authentication" + "Webhooks" docs (verify at procurement).
- IETF RFC 7519 (JWT validation).
- ONVIF Profile S / T specifications.
- Selected fallback host UDP/media-port documentation.
- `mediamtx` documentation (RTSP, WebRTC publish, HTTP API for events).

### 13.7 Synthetic RTSP test source (C-02)

`synthetic_rtsp_test_source` is the named ingest type used in dev / CI / staging where no real camera exists. It is implemented as an FFmpeg sidecar generating a deterministic test pattern + audio tone, published to a local `mediamtx` instance over RTSP.

**Reference command** (final Docker image baked into `cctv-edge`):

```bash
ffmpeg -re \
  -f lavfi -i "testsrc=size=1280x720:rate=15" \
  -f lavfi -i "sine=frequency=1000" \
  -c:v libx264 -tune zerolatency -preset veryfast -g 30 \
  -c:a aac -ar 44100 -b:a 64k \
  -f rtsp rtsp://localhost:8554/synthetic_cam_01
```

**Properties**:

- **Deterministic**: same FFmpeg flags -> same SMPTE-style colour bars + 1 kHz tone; reproducible CI artefacts.
- **Bandwidth bounded**: 720p15 ~700 kbps target; predictable LiveKit minute consumption.
- **No real PII**: synthetic content; safe for screenshots in pen-test reports.
- **Always-on in dev**: started by `docker-compose up` and by the selected dev/CI gateway job/service.
- **CI gate**: Phase 4 exit asserts an authenticated viewer can subscribe to `synthetic_cam_01` over LiveKit Cloud and decode the test pattern; latency probe < 2 s p95 (Section 21 Phase 3 / 4).
- **Schema enforcement**: `cameras.source_type = 'synthetic_rtsp_test_source'` is the only enum value the dev/CI gateway is authorized to publish (Section 14.4).
- **Production guard**: a check in the gateway boot script refuses to start the FFmpeg sidecar when the gateway's identity record indicates a production site (Section 13.8). Prevents accidental synthetic publishes at real sites.

Referenced from Section 25.1 scaffold (`docker-compose.yml`) and Section 25.4 local-development workflow.

### 13.8 Camera Site Hardware (production) (C-01)

Production sites run the edge gateway on **on-site hardware**, not on Railway or any cloud app. The dev/CI gateway is synthetic only (Section 12 stack table). ADR 0013 records the standardized hardware class.

**Standard SKU class - NUC-class mini-PC (x86_64)**:

| Spec | Minimum | Recommended | Notes |
|---|---|---|---|
| Form factor | NUC / mini-PC | Same | Intel NUC, Beelink Mini S, MeLE Quieter, ASUS PN-series, Minisforum UM-series |
| CPU | x86_64 quad-core, AES-NI | Intel N100 / N305 or Ryzen 5xxx U-series | Single arch - single Docker image |
| RAM | 8 GB | 16 GB | Sufficient for `mediamtx` + agent + headroom |
| Storage | 128 GB SSD | 256 GB NVMe | OS + Docker; no recording on box |
| NIC | 1 x GbE | 2 x GbE | Two-NIC option preferred for camera-VLAN isolation (Section 13.9) |
| Power | Standard mains | UPS-backed | UPS strongly recommended for camera VLAN switch + gateway |
| OS | Ubuntu 22.04 LTS Server x86_64 | Same | No GUI; minimal install |
| Hostname | `cctv-gw-<site-slug>` | Same | Used as enrolment label |

**Software baseline**:

- **Single Docker image** (x86_64-only) shipped from CI; image tag pinned per release; no per-site image divergence.
- **`mediamtx`** version pinned (Section 12 stack table; ADR 0007).
- **Gateway agent** runs in the same image, talks outbound to `cctv-api` for token mint, heartbeat, and an outbound control channel for signed start/stop commands.
- Both run under **systemd unit `cctv-gateway.service`**, user `cctv-gateway` (uid:gid `cctv-gateway:cctv-gateway`), no shell, no sudo, `NoNewPrivileges=yes`, `ProtectSystem=strict`, `ProtectHome=yes`, `ReadWritePaths=/var/lib/cctv-gateway`.
- **Secrets** at `/etc/cctv-gateway/gateway.env` mode `0600` owned by `cctv-gateway`, loaded via `EnvironmentFile=` (Section 11.5).
- **`mediamtx` HTTP API** (M-12): bound to `127.0.0.1:9997` only **OR** disabled entirely (`api: no` in `mediamtx.yml`) if the gateway agent does not consume it. **Banned**: exposing the API to the camera VLAN or to the WAN. Verified by site-bring-up checklist + a probe in T-61.
- **No GUI, no GUI packages, no remote desktop, no SSH from the WAN**. SSH allowed only from the operator's WARP-protected admin laptop subnet (firewall rule).
- **No inbound WAN ports** - zero. All app traffic is outbound (CF Access service-token, gateway control WebSocket/heartbeat fallback, and LiveKit publish).
- **Read-only root filesystem** where feasible (Docker `--read-only`); writable bind mount only for `mediamtx` runtime state and gateway agent log buffer.
- **Auto-update strategy**: `unattended-upgrades` for OS security patches; container image updates pulled by a watchdog timer that checks the pinned tag in CI's release manifest, never `:latest`.

**Procurement**: `P0-13` in Phase 0 picks the SKU and assembles the Ubuntu image; Section 20.14 covers the lifecycle runbook.

**Pi note**: Raspberry Pi-class ARM SBCs were considered and rejected as the *production* standard - they would require a second container image (arm64), have weaker AES-NI / video pipeline support, and most candidate sites already have x86_64 mini-PCs available. ARM is not banned, but production = mini-PC unless ADR 0013 is reopened.

### 13.9 Camera Network Design (H-03)

Cameras live on a **dedicated camera VLAN**, isolated from the operator's general LAN. ADR 0012 records per-site network topology.

**Reference design (per site)**:

| Element | Setting |
|---|---|
| Camera VLAN | `192.168.10.0/24` *(example; per-site assignment in ADR 0012)* |
| Operator LAN | `192.168.1.0/24` *(example)* |
| WAN uplink | ISP-provided; no static public IP required |
| Gateway interface 1 (camera-side) | `192.168.10.2/24`, no default gateway, RTSP/554 + ICMP only |
| Gateway interface 2 (WAN-side) | DHCP from operator router |
| Camera default gateway | None or VLAN-local; cameras have **no internet route** |

**Two-NIC option (preferred)**: gateway has two physical NICs; one cabled to the camera VLAN switch, the other to the operator LAN / WAN. Hardware-level isolation; simplest to audit.

**Single-NIC option**: gateway has one NIC; switch is VLAN-aware; gateway uses tagged VLAN sub-interfaces. ACL on the switch enforces isolation. Acceptable when two-NIC hardware is not available.

**Firewall rules (per site, enforced at gateway and at switch)**:

| Direction | From | To | Allowed |
|---|---|---|---|
| Outbound (gateway -> WAN) | gateway WAN iface | LiveKit Cloud, `cctv-api`, CF Access endpoints, `archive.ubuntu.com`, `*.docker.io` (for image pulls) | **TCP 443 only** |
| Inbound (WAN -> gateway) | any | gateway | **None** - no port forwards, no NAT loopback |
| Inbound (camera VLAN -> gateway) | cameras | gateway camera-side iface | **TCP 554 (RTSP) + ICMP** only |
| Outbound (gateway -> camera VLAN) | gateway camera-side iface | cameras | TCP 554 + ICMP only; no DNS, no HTTP camera-config UI traffic |
| Camera VLAN <-> operator LAN | n/a | n/a | **Blocked at switch** - cameras cannot see operator workstations |
| Camera VLAN -> internet | cameras | any | **Blocked** - cameras have no internet route |

**Camera credential handling**: each camera's RTSP password is stored only in the gateway's `mediamtx.yml` (mode `0600`), loaded via the gateway's secret store (Section 11.5). Never reaches `cctv-api`, never reaches the browser, never written to logs (T-62 verifies).

**Operational checklist (site bring-up)**:

1. Inventory cameras: model, serial, RTSP path, ONVIF profile (Phase 4 -> Phase 12 if ONVIF).
2. Apply VLAN config to switch.
3. Verify camera can reach gateway camera-side iface.
4. Verify camera **cannot** reach `8.8.8.8` (no internet route).
5. Verify gateway can reach `cctv-api` and LiveKit Cloud over WAN.
6. Run `mediamtx` config test - RTSP pull succeeds.
7. Bind-test: confirm `mediamtx` HTTP API not reachable from camera VLAN or WAN (M-12).
8. Enrol gateway via admin UI (Section 20.14).
9. Verify viewer can subscribe end-to-end with < 2 s p95 latency.
10. Bystander signage attested (Section 16.12).

### 13.10 LiveKit Room Model (H-05)

LiveKit room topology and presence-driven publish (A6').

**Topology**: **one LiveKit room per camera**. No multi-camera rooms; no shared rooms across sites.

**Room naming**:

- Room name format: `camera_<short_uuid_8>` where `<short_uuid_8>` is the first 8 hex chars of `cameras.id` (stripped of dashes).
- Stored on the row as `cameras.livekit_room_name VARCHAR(32) NOT NULL UNIQUE` (Section 14.1).
- Room names are opaque from a viewer's perspective - they are not the camera's display name and reveal no operator-meaningful information (Inv 5; Section 13.5 hard rule 7).
- A camera deleted (retired) keeps its row + room name forever (audit anchor); a new camera mints a fresh UUID.

**Presence-driven publish flow (A6')**:

1. **Gateway control channel online** -> each enabled gateway opens an outbound TLS WebSocket to `cctv-api` after authenticating with its service token (MVP) or mTLS client certificate (pilot+). The channel carries signed command envelopes only; it does not expose an inbound gateway API. If the WebSocket is unavailable, the gateway falls back to heartbeat/polling command pickup on its existing outbound HTTPS heartbeat.
2. **Viewer joins** -> viewer-subscribe token minted by `cctv-api` for `room = cameras.livekit_room_name`, scoped subscriber-only, TTL 60 s. Viewer SDK joins the room.
3. **First-participant webhook** (`participant_joined` from LiveKit) hits `/api/v1/webhooks/livekit` with shared-secret HMAC + 60-s timestamp window (Section 13.5 rule 13). `cctv-api` checks: is the room currently publishing? If no -> mint a **gateway-publish** token for the gateway assigned to that camera (via `gateway_camera_assignments`), TTL 60 s, scoped to that one room, publisher-only.
4. `cctv-api` sends `gateway.command.start_publish` over the gateway's outbound WebSocket with the minted token, command ID, timestamp, expiry, camera ID, and room name. Gateway validates the command signature/freshness and passes the token to `mediamtx`, which begins publishing to LiveKit. If the WebSocket is down, `cctv-api` queues the command for pickup on the next heartbeat response.
5. Subsequent viewers receive the existing live track - no second publish, no extra LiveKit minutes.
6. **Last-participant-left webhook** (`participant_left`, `participant_count == 0`) -> `cctv-api` starts a **10-second grace timer** (handles brief refreshes / reconnects). On grace expiry, `cctv-api` sends `gateway.command.stop_publish` over the outbound WebSocket; the heartbeat fallback carries the same command if the WebSocket is down.
7. **LiveKit auto-disposes** an empty room with no publisher after its idle timeout (LiveKit default; verify in ADR 0007 / procurement).

**Gateway command and publish-token validation**:

- Gateway receives start/stop commands only over its outbound WebSocket or heartbeat fallback. It validates command signature, `command_id` idempotency, timestamp freshness, target `gateway_id`, target `camera_id`, and command expiry before touching `mediamtx`.
- For start commands, the gateway also validates the publish token: token signature (matches LiveKit publish-key), `iss == cctv-api`, `aud == livekit`, `exp <= now + 60s`, `room == cameras.livekit_room_name`, `permissions.canPublish == true`, `permissions.canSubscribe == false`.
- On any mismatch, gateway rejects the command, ACKs failure to `cctv-api`, and `cctv-api` writes audit `gateway.publish.command_rejected` or `gateway.publish.token_rejected`.

**Edge cases**:

- **Webhook lost** -> `cctv-api` reconciliation loop polls LiveKit room state every 30 s and corrects drift (terminate orphan publish, restart on missed first-viewer).
- **Gateway WebSocket down** -> gateway status becomes degraded after missed ping/heartbeat threshold; pending start/stop commands are delivered via heartbeat fallback. If neither channel is available, camera state becomes gateway-unavailable and token minting fails closed.
- **Gateway slow to stop** -> LiveKit-side participant timeout still cleans up the publisher; alert if grace + LiveKit timeout both elapse without a stop ack.
- **User disabled mid-watch** -> Section 13.5 rule 11: LiveKit participant removed <= 10 s; the participant_left webhook then triggers the grace+stop flow if they were the last viewer.

---

## 14. Data Model & Database Design

Schema (control plane only). DDL is illustrative; final migration is owned by the Database Architect during Phase 2.

### 14.1 Tables

- `users(id, email, idp_subject, role_default='none', disabled_at, created_at)`.
- `roles(id, name)`, `permissions(id, action, resource)`, `role_permissions(role_id, permission_id)` with composite PK, `user_roles(user_id, role_id)` with composite PK. MVP seed roles are `viewer`, `admin`, `auditor`; `super_admin` is represented as a high-risk permission flag/seeded permission, not an ad-hoc UI-only concept.
- `sites(id, name, address, bystander_signage_attested_at)` - site address + signage attestation timestamp (PH DPA Section 16.12).
- **`cameras(id, name, source_type, room_uuid, livekit_room_name VARCHAR(32) NOT NULL UNIQUE, gateway_id, site_id, created_at, retired_at)`** where `source_type ENUM('rtsp','nvr_rtsp','onvif_profile_s','onvif_profile_t','synthetic_rtsp_test_source')`. **`'phone'`, `'webcam'`, `'browser'`, `'browser_publisher'`, `'user_device'`, `'mobile_camera'` are explicitly not part of the enum** and a CHECK constraint enforces it. ONVIF values usable only after Section 13.3 spike passes. **`livekit_room_name`** = `camera_<short_uuid_8>` (first 8 hex chars of `id`); referenced from Section 13.10 LiveKit Room Model.
- `camera_acl(user_id, camera_id, granted_by, granted_at, revoked_at)` with composite PK `(user_id, camera_id, granted_at)` and partial unique index for one active grant per `(user_id, camera_id)` where `revoked_at IS NULL`.
- **`edge_gateways(id, name, status ENUM('enabled','disabled','retired') NOT NULL DEFAULT 'enabled', service_token_hash NULL, mtls_fingerprint NULL, cert_expires_at NULL, last_seen_at, created_at, disabled_at)`**. Nullability allows MVP shipping with service-token-only while keeping mTLS columns ready for pilot. CHECK: `service_token_hash IS NOT NULL OR mtls_fingerprint IS NOT NULL` after Phase-3 enrolment.
- **`gateway_camera_assignments(gateway_id, camera_id, granted_by, granted_at, revoked_at)`** with composite PK `(gateway_id, camera_id, granted_at)` and partial unique index for one active assignment per `(gateway_id, camera_id)` where `revoked_at IS NULL` - authoritative scope for gateway-publish tokens.
- `camera_events(id, camera_id, gateway_id, kind ENUM('online','offline','degraded','reconnecting','retired'), at, source ENUM('heartbeat','livekit_webhook','mediamtx_callback','admin_action'))`.
- `sessions(id, user_id, cf_jti, ua_fp, ip, created_at, last_seen_at, revoked_at)`.
- **`stream_grants(id, user_id NULL, gateway_id NULL, session_id NULL REFERENCES sessions(id), camera_id, jti, kind ENUM('viewer_subscribe','gateway_publish'), issued_at, expires_at, denied_reason NULL)`** - **scope (M-11)**: replay detection for the **app's token-mint API call** (a viewer/gateway re-submitting the same mint request). **Not** a media-token replay defense at LiveKit - LiveKit does not consult an external `jti` blocklist; media-token replay defense is the 60-s TTL (Section 11.4). CHECK: `(kind = 'viewer_subscribe' AND user_id IS NOT NULL AND session_id IS NOT NULL AND gateway_id IS NULL) OR (kind = 'gateway_publish' AND gateway_id IS NOT NULL AND user_id IS NULL AND session_id IS NULL)`. **Denied issuance attempts are logged to `audit_log` and recorded with `denied_reason` (no row issued)**.
- **`audit_log(id, ts, actor_id, actor_type ENUM('user','gateway','system','break_glass','service_token_monitor'), action, resource, ip NULL, ua NULL, prev_hash, hash, hmac_key_version INTEGER NOT NULL, payload jsonb)`** - append-only via DB triggers; HMAC chain.
- **`audit_hmac_keys(version INTEGER PRIMARY KEY, key_enc bytea NOT NULL, created_at, retired_at NULL)`** - encrypted-at-rest key material; the verifier loads the row matching each audit row's `hmac_key_version`.
- `system_config(key, value, updated_by, updated_at)`.
- `incident_reports(id, ...)` (pilot+).
- `break_glass_usage(id, opened_at, opened_by_reason, closed_at, closed_reason, auto_disable_at, rotation_completed_at)` - `auto_disable_at = opened_at + interval '90 minutes'` enforced at request time (Section 16.6).
- `privacy_notice_acceptances(user_id, notice_version, accepted_at)` with composite PK `(user_id, notice_version)` - IP **not duplicated** here; the `sessions` and `audit_log` rows around the acceptance carry IP if needed (your Section 10 review). Documented in ROPA.
- `dpa_artifacts(kind ENUM('ropa','processor_dpa','pia','breach_log','retention_policy','bystander_signage_attestation','cross_border_transfer_basis'), path_to_r2, signed_hash, effective_at, superseded_at)`.
- **`backup_runs(id, started_at, finished_at, size_bytes, sha256, restore_format_ok BOOL, restore_schema_ok BOOL NULL, row_count_estimate BIGINT NULL, upload_status ENUM('pending','uploaded','failed'), notes)`** - backup-integrity ledger (Section 18 + Section 20.7). **`restore_format_ok`** populated by the daily `pg_restore --list` archive-format check (M-04). **`restore_schema_ok`** populated by the weekly schema-restore drill (NULL on days without a drill). Both must be `true` for the most recent successful run on the relevant cadence; alert on `false` or stale.
- `dsr_requests(id, requester_contact, subject_type ENUM('user','bystander','site_contact'), request_type ENUM('access','correction','deletion','objection','restriction','other'), site_id NULL, camera_scope_note NULL, received_at, due_at, verified_at NULL, status, outcome, artefact_id NULL REFERENCES dpa_artifacts(id))` - DSR tracking and evidence ledger for PIA/ROPA obligations.
- `webhook_replay_cache(provider, signature, ts, expires_at)` with composite PK `(provider, signature)` - LiveKit webhook replay protection (TTL ~5 min).

**Removed from MVP** (reduces surface; reintroduce only with explicit ADR):
- `webauthn_metadata` - IdP holds the source of truth at 4-user scale.
- `export_jobs` - synchronous signed JSONL export is sufficient.

### 14.2 Indexes

- `audit_log (ts)`, `audit_log (actor_id, ts)`, `audit_log (resource, ts)`, `audit_log (hmac_key_version)`.
- `role_permissions (role_id, permission_id)` composite unique.
- `user_roles (user_id, role_id)` composite unique.
- `camera_acl (user_id, camera_id) WHERE revoked_at IS NULL` unique active grant.
- `gateway_camera_assignments (gateway_id, camera_id) WHERE revoked_at IS NULL` unique active assignment.
- **`stream_grants (jti, expires_at)` composite (replay-check fast under realistic volume)**.
- `stream_grants (user_id, expires_at) WHERE kind = 'viewer_subscribe'`.
- `stream_grants (gateway_id, expires_at) WHERE kind = 'gateway_publish'`.
- `camera_events (camera_id, at DESC)`.
- `sessions (user_id, revoked_at)`.
- `edge_gateways (status, last_seen_at)`.
- `webhook_replay_cache (provider, signature)`.
- `dsr_requests (status, due_at)`, `dsr_requests (site_id, received_at)`.

### 14.3 Constraints / mechanisms

- DB-enforced append-only on `audit_log` (BEFORE UPDATE/DELETE triggers raise EXCEPTION). `hmac_key_version` is required NOT NULL.
- HMAC-SHA-256 chain: `hash = HMAC(key_for_version(hmac_key_version), prev_hash || row_canonical_json)`. The verifier walks rows, reading `hmac_key_version` per row to select the correct key.
- **Key rotation preserves chain continuity**: when SuperAdmin rotates, the system inserts a new `audit_hmac_keys` row, then writes a single audit row marking the rotation; that row's `hmac_key_version` is the **new** version, but its `prev_hash` still references the final hash signed under the old version. T-49 verifies that the chain is continuous across the boundary.
- **Cleanup (H-04)**: deletes `stream_grants` where `expires_at < now() - interval '1 hour'`. Runs as a scheduled job separate from the web process (Railway scheduled job, GitHub Actions schedule with locked secrets, or equivalent), invoked every 5 minutes. The cleanup job runs the delete query against Postgres, writes an audit row `system.cleanup.stream_grants.completed` with the row count, and exits. **External-cron fallback**: UptimeRobot or Better Stack hits `POST /api/v1/admin/internal/cleanup-grants` on `cctv-api` every 5 min with a CF Access service-token; same query, same audit row. T-50 verifies the cleanup mechanism actually runs (not just that the query works) by injecting a synthetic expired row + asserting it is deleted within 6 minutes. Alert fires if `stream_grants` row count exceeds expected ceiling (signals replay attack or token leak).
- Row-level security on `camera_acl` and `gateway_camera_assignments`.
- Retention jobs: audit 365 d archive-then-prune (segmented chain across boundary; F-005 fix); sessions 30 d; soft-disable revokes immediately + LiveKit room termination <=10 s.
- **Backups**: nightly `pg_dump` -> `age` encrypted -> R2 (object lock); **post-backup `pg_restore --list` decrypted-validity check** + checksum + row-count estimate stored in `backup_runs.restore_format_ok` (M-04); weekly schema-restore drill populates `backup_runs.restore_schema_ok`; alert on either being `false` or stale (Section 20.7).
- **DB least-privilege role (Inv 15)**: `cctv_app_runtime` has `SELECT/INSERT/UPDATE/DELETE` only on the explicit application tables; **no `ALTER`, no `TRUNCATE`, no `pg_catalog` write, no trigger disabling**, and `audit_log` grants are restricted so that direct UPDATE/DELETE are denied even before the trigger runs (defence in depth). T-57 introspects privileges.

### 14.4 Source-type enforcement

```sql
CREATE TYPE camera_source_type AS ENUM (
  'rtsp', 'nvr_rtsp', 'onvif_profile_s', 'onvif_profile_t', 'synthetic_rtsp_test_source'
);
-- 'phone', 'webcam', 'browser', 'browser_publisher', 'user_device', 'mobile_camera'
-- are explicitly excluded by Inv 5. A migration that adds any of those values requires
-- an ADR overturning Inv 5 (which would re-architect the product).
```

CI grep (Section 24) and a schema/migration lint ensure no application code references those forbidden source-type strings outside the Section 29 documentation appendix.

---

## 15. API Design

Conventions:

- Versioned `/api/v1/...`; FastAPI route handlers internally.
- All protected routes verify `Cf-Access-Jwt-Assertion` (`aud`+`iss` pinned, `exp`/`nbf` ± `CLOCK_SKEW_SECONDS = 30`) and fail closed without a valid CF Access JWT (Inv 14, F-002).
- Pydantic schema validation; cursor pagination; RFC 9457 Problem Details for errors; no framework banners.
- Idempotency on POSTs that create resources.
- **Explicit CORS policy** (Section 16.13): same-origin only; no wildcard `Access-Control-Allow-Origin` on authenticated APIs; gateway APIs are **not browser-callable** by design.
- **Rate limits** per Section 16.17 table.

### 15.1 Surface

| Method | Path | AuthZ | Purpose |
|---|---|---|---|
| GET | `/health` | **CF Access service token** (App D) | Returns exactly `{"status":"ok"}` with no version, framework, env, hostname, or DB info. No PII. |
| GET | `/api/v1/admin/health/deep` | admin (App B) | Deep health: DB ping, LiveKit reachability, queue (none in MVP), R2 reachability, mediamtx control-plane reachability. Admin-only. |
| GET | `/api/v1/me` | any authed | Current user + roles + ACL'd cameras. |
| GET | `/api/v1/cameras` | viewer (filtered to ACL) | List authorized cameras with online/offline/last-seen state. |
| **GET** | **`/api/v1/cameras/:id/view-token`** | **viewer with ACL** | **Mint short-lived viewer-subscribe LiveKit token** (<=60 s, subscriber-only, bound to `user_id` + `session_id` + `camera_id`; `jti` recorded; `iceTransportPolicy: 'relay'` enforced). Chooses Cloud or fallback URL based on feature flag. |
| GET | `/api/v1/cameras/events` | viewer | **SSE stream** of camera/gateway state changes (online/offline/last-seen) for cameras the user is ACL'd to. Polling fallback at 30 s if SSE unavailable. |
| GET | `/api/v1/sessions/active` | self | Own active sessions. |
| POST | `/api/v1/sessions/revoke` | self / admin | Revoke session; triggers LiveKit participant removal <=10 s. |
| **POST** | **`/api/v1/gateways/:id/ingest-token`** | **gateway-authenticated** (service token MVP / mTLS pilot+) | **Mint short-lived gateway-publish LiveKit token** (<=60 s, publisher-only, bound to `gateway_id` + `camera_id` via `gateway_camera_assignments`; `jti` recorded). **Rejected with 401/403 + audit if requester is a browser session.** |
| **POST** | **`/api/v1/gateways/:id/heartbeat`** | gateway-authenticated | Liveness + version + camera-by-camera health. Updates `edge_gateways.last_seen_at`. |
| **POST** | **`/api/v1/gateways/:id/cameras/:cameraId/status`** | gateway-authenticated | Updates `camera_events` (online/offline/degraded/reconnecting). Pushes to SSE. |
| **POST** | **`/api/v1/webhooks/livekit`** | shared-secret HMAC + 60-s timestamp window (Section 13.5 hard rule 13); CORS empty Allow-Origin + preflight 405 (Section 16.13) | Receives LiveKit room/participant events; updates `camera_events`; instructs the gateway to start/stop publishing per A6'. Server-to-server only - not browser-callable. T-63 verifies stale-timestamp rejection. |
| GET | `/api/v1/admin/users` | admin | List users. |
| POST | `/api/v1/admin/users/:id/role` | admin | Assign role. |
| POST | `/api/v1/admin/users/:id/disable` | admin | Disable user **+** revoke sessions **+** call LiveKit room API to remove user's participant <=10 s (F-003 fix). |
| POST | `/api/v1/admin/users/:id/mfa/reset` | SuperAdmin | Admin-mediated MFA reset. |
| POST | `/api/v1/admin/cameras` | admin | Register camera (name, source_type, gateway_id, site_id). |
| POST | `/api/v1/admin/cameras/:id/acl` | admin | Grant/revoke camera ACL. |
| POST | `/api/v1/admin/cameras/:id/disable` | admin | Disable/retire camera + terminate viewer rooms <=10 s. |
| POST | `/api/v1/admin/gateways` | admin | Register gateway (name, identity tier). Returns one-time service token (MVP) or mTLS leaf cert (pilot+). |
| POST | `/api/v1/admin/gateways/:id/disable` | admin | Disable gateway + terminate publish <=10 s. |
| POST | `/api/v1/admin/gateways/:id/rotate-credential` | SuperAdmin | Rotate service token / re-issue mTLS leaf cert. |
| POST | `/api/v1/admin/gateways/:id/cameras` | admin | Add/remove `gateway_camera_assignments` row. |
| GET | `/api/v1/admin/audit` | admin/auditor | Query audit. |
| GET | `/api/v1/admin/audit/verify` | admin/auditor | Verify hash chain end-to-end across all `hmac_key_version`s (T-49). |
| GET | `/api/v1/admin/audit/export` | admin/auditor | **Synchronous signed JSONL export bundle (C-04)**: includes (a) signed JSONL of audit rows, (b) per-row `prev_hash` + `hash` + `hmac_key_version`, (c) snapshot of `audit_hmac_keys` (encrypted material redacted; metadata included). Recipient verifies the HMAC chain independently of the export signature - see Section 17.2 trust model. No async queue in MVP. |
| POST | `/api/v1/admin/break-glass/open` | break-glass account | Open emergency window; sets `auto_disable_at = now() + 90 min`. |
| POST | `/api/v1/admin/break-glass/close` | break-glass / SuperAdmin | Close window + rotation checklist. |
| GET | `/api/v1/admin/exposure-check` | admin/auditor | Last T-30 report. |
| GET | `/api/v1/admin/media-isolation-check` | admin/auditor | Last T-45 report. |
| GET | `/api/v1/admin/origin-binding-check` | admin/auditor | Last T-56 report. |
| GET | `/api/v1/privacy/notice` | any authed | Current operator notice version. |
| POST | `/api/v1/privacy/notice/accept` | any authed | Record acceptance. |
| POST | `/api/v1/admin/dpa/export` | admin | Synchronous signed DPA artefact bundle (incl. bystander signage attestations). |
| POST | `/api/v1/admin/sites/:id/signage-attest` | admin | Records bystander signage posted at site (Section 16.12). |
| POST | `/api/v1/admin/livekit/fallback` | SuperAdmin | Flip feature flag (control surface for Section 20.10). |

### 15.2 Removed routes (Inv 5)

Permanently absent - no code, no route handler, no test path:

- `POST /api/v1/publish/:cameraId/token` (browser publisher token mint).
- `/publish` page route.
- `/demo-publisher`, `/lab-publisher`, `/webcam`, `/phone-publisher` page routes.
- Any route that requests browser camera permission, calls `getUserMedia`, or instantiates `MediaRecorder`.
- Any route that returns RTSP/NVR/ONVIF credentials in its response payload.

### 15.3 Token-mint authorization summary (T-60)

| Endpoint | Required identity | Required scope checks | Token kind minted |
|---|---|---|---|
| `GET /api/v1/cameras/:id/view-token` | Browser session (CF JWT) | user not disabled · session not revoked · `camera_acl(user_id, camera_id)` row · camera not retired | viewer-subscribe (<=60 s, subscriber-only) |
| `POST /api/v1/gateways/:id/ingest-token` | Gateway (service-token MVP / mTLS pilot+) | gateway not disabled · gateway identity matches `:id` · `gateway_camera_assignments(gateway_id, camera_id)` row · camera not retired | gateway-publish (<=60 s, publisher-only) |

The two endpoints **do not share** a token-mint code path. A browser session calling the gateway endpoint is rejected with 401/403 + audit `gateway.ingest.denied.browser_session`. A gateway calling the viewer endpoint is rejected with 401/403 + audit `viewer.token.denied.gateway_identity`.

---

## 16. Security Plan

### 16.1 Threat model highlights (STRIDE-lite)

- **External attacker** -> IAP denies at edge (T-30); protected routes reject direct Railway-origin access without valid CF JWT (Inv 3, Inv 14, T-56); no browser-publisher attack surface (Inv 5).
- **Account compromise** -> phishing-resistant MFA (passkey); short sessions; anomaly alert; admin re-auth; break-glass boxed at 90 min.
- **Endpoint compromise of admin device** -> WARP device posture; session TTL; admin-panel-only risky actions; sensitive ops require re-auth.
- **Insider (viewer)** -> viewer-subscribe tokens only; cannot mint gateway-publish; watermark; full audit.
- **Insider (admin)** -> SoD (SuperAdmin required for delete-admin); audit chain with versioned HMAC; break-glass requires rotation on close.
- **Network** -> TLS 1.2+; HSTS preload; DNSSEC; CF anycast bot/WAF per plan; direct media networking via LiveKit (no Tunnel routing media); `iceTransportPolicy: 'relay'` prevents host-IP leakage.
- **Media plane compromise** -> separate media host, separate secrets, no DB egress, only media ports public (T-45).
- **Origin-bypass attempt** -> direct Railway-origin request fails closed without verified CF Access JWT; trusted headers ignored on unverified requests (T-56; F-001, F-002).
- **Gateway impersonation** -> service-token hash pinning (MVP), mTLS fingerprint pinning (pilot+); `gateway_camera_assignments` is the only scope; credential rotation runbook (Section 20.14).
- **Camera credential exfiltration** -> credentials only on the gateway; never returned from app APIs; CI grep on browser bundle (T-62).
- **Supply chain** -> pinned deps, Dependabot, osv-scanner, Trivy, gitleaks, Cosign-signed images.
- **DoS** -> CF + app-layer rate limits (Section 16.17); cost alarms; fallback runbook.
- **Webhook spoofing** -> shared-secret HMAC + timestamp window + replay cache (F-012).

### 16.2 Authentication

- CF Access JWT required on every protected route (Section 11.4); F-002 trusted-header policy (Section 11.6).
- App session = signed cookie bound to CF JWT `sub` + `session_id` + low-risk device fingerprint (Section 16.14); idle 15 min; absolute 8 h.
- MFA enforced at IdP; WebAuthn/passkey preferred; SMS prohibited.
- No password fields anywhere in the app.

### 16.3 Authorization

- Policy module: `(actor, action, resource) -> allow|deny`; deny-by-default.
- Per-request context: actor identity, resolved roles, camera ACL intersection, gateway assignments, session validity.
- Admin mutations: re-auth <=5 min required + audit + (pilot) mTLS client cert.
- `gateway_camera_assignments` is the sole authority for gateway-publish scope; `camera_acl` is the sole authority for viewer-subscribe scope.
- **Two-tier RBAC (`viewer` / `admin`) is intentional for MVP (M-03)**. Schema (`roles`, `permissions`, `role_permissions`, `user_roles`) supports adding `site_admin`, `camera_manager`, `auditor`, or per-site role variants **without migration** - only seed-data changes and a policy-module update. Pilot evaluates whether finer-grained roles are needed; SuperAdmin (delete-admin authority) is a separate flag, not a role row.

### 16.4 Session

- Cookie: `Secure`, `HttpOnly`, `SameSite=Strict`, host-only, short path.
- Server stores `sessions`; on disable: delete session + terminate LiveKit participant <=10 s.
- Idle 15 min, absolute 8 h; admin re-auth <=5 min.

### 16.5 Transport & headers

- TLS 1.2+ only; HSTS preload.
- Strict CSP with nonces: no `unsafe-inline`, no `unsafe-eval`, no wildcard domains; `connect-src` enumerated with specific LiveKit regional hosts (F-008); `media-src blob:` limited to LiveKit SDK origin; Trusted Types required on script sinks.
- **`Permissions-Policy: camera=(), microphone=(), geolocation=(), autoplay=(self), display-capture=()`** - camera and microphone explicitly denied site-wide (Inv 5 defence in depth).
- COOP `same-origin`, COEP `require-corp`, CORP, Referrer-Policy `no-referrer`.
- `X-Content-Type-Options: nosniff`; no `Server`/`X-Powered-By` banners; no version endpoint.

**CSP mechanism (React + Vite + FastAPI, H-07)**:

- React + Vite frontend responses and FastAPI backend responses both emit the strict security-header set.
- Frontend route middleware or the selected Railway/Cloudflare header layer generates a cryptographically random nonce or approved hash policy for each HTML response and passes it only to allowed framework script/style outputs.
- FastAPI emits compatible CSP headers on API/error responses and never relaxes the policy for API routes.
- **CSP spike** (Phase 2 sub-task): assert the selected Vite build mode can enforce strict CSP without `unsafe-inline` or `unsafe-eval`; assert LiveKit JS works with the `connect-src` / `media-src` restrictions; assert the approach matches the exact React/Vite/Tailwind versions locked in ADR 0007.
- **No `'unsafe-inline'` fallback** even temporarily - CI fails the build if the response CSP header contains `'unsafe-inline'` for `script-src` or `style-src`.

**Dynamic `connect-src` for media-plane fallback (M-08)**:

- Middleware reads `system_config.media_plane_mode` per request (`'cloud'` | `'fallback'`); the **active LiveKit origin** is included in `connect-src` for that response.
- **Both** the LiveKit Cloud regional host(s) **and** the self-hosted fallback host (`wss://livekit.<app-domain>`) are pre-approved values **in code** - the Middleware chooses which to emit; it never accepts a runtime-supplied origin.
- Switching from Cloud to fallback is a DB flag flip via `POST /api/v1/admin/livekit/fallback` (Section 20.10); no redeploy needed; the next request gets a CSP that allows the fallback origin.
- Cross-reference: Section 20.10 LiveKit fallback runbook describes the operator flow.

### 16.6 Break-glass administration (fixed 90-minute window, request-time enforced)

- **Sealed account** (`break-glass-prime@<domain>`), hardware security key, password-manager-stored + sealed offline copy.
- **CF Access App C** `/admin-emergency` - one allowed identity + hardware-key policy.
- **Window enforcement** (F-006 fix):
  - On open, write `break_glass_usage` row with `auto_disable_at = opened_at + interval '90 minutes'` (named constant `BREAK_GLASS_WINDOW_MINUTES = 90`).
  - **Request-time authorization check**: every request on App C calls `assertBreakGlassActive(now())` which rejects once `now() >= auto_disable_at`. **This is the authoritative gate** - the scheduled disabler is a belt-and-braces measure.
  - **External scheduled monitor** (provider-neutral) hits a control endpoint every 5 min to verify no expired window is still accessible; alerts if yes.
  - **No database-level scheduled trigger** is relied upon (avoids provider-specific pg cron assumptions).
- **Close runbook** mandates rotation: audit HMAC key -> LiveKit API keys -> CF Access service tokens -> gateway credentials (all).
- **Test (T-52)**: open window, advance clock 91 min (simulated), restart app worker, attempt admin request -> must be denied.

### 16.7 Lost-MFA recovery (admin-mediated, not self-service)

- **Trigger**: user reports lost device; opens support request.
- **Admin workflow**:
  1. Verify identity out-of-band (voice callback on file, or physical attestation).
  2. Reset MFA via IdP admin console (removes old passkey).
  3. Invite user to re-enrol during a time-boxed window (<=24 h).
  4. Audit `mfa.reset.admin_mediated` with admin actor, user, method, verification channel.
- **No self-service "reset my MFA" endpoint.**

### 16.8 Secrets & keys

- Railway secrets/environment for the control plane + separate media/gateway secret stores; **separate stores per plane and per gateway**.
- Env vars via Railway/selected secret manager; never in source, never in image.
- Rotation schedule: LiveKit API keys 90 d, JWT signing (LiveKit tokens) 30 d, cookie key 90 d, audit HMAC quarterly or on incident, CF Access service tokens on incident/routine schedule, gateway credentials quarterly or on incident.
- **Telegram bot token** (Section 20.16) - rotation runbook + leak-response runbook; documented in secret inventory.

### 16.9 Input validation

- Pydantic schemas on all inputs (body, query, params, headers).
- No raw SQL in handlers; SQLAlchemy 2.x prepared parameter binding; raw SQL only in reviewed migrations.
- HTML/attribute escaping by default in templates; no unsafe template rendering.
- File uploads disallowed in MVP.

### 16.10 Origin / control-plane exposure controls (REQ-SEC-01 + REQ-SEC-01c)

- Railway app uses Cloudflare-protected custom domain as the supported entry point; protected routes fail closed without valid CF Access JWT. Platform ingress restrictions are enabled where available.
- DNS entirely through Cloudflare; orange-cloud enabled.
- **T-30 external-exposure checklist**:
  1. Railway-origin URL, if reachable, rejects protected routes without valid CF Access JWT.
  2. CF challenge -> 1111-series for unauth.
  3. Cert-transparency leak -> only CF-issued certs.
  4. Subdomain enum -> no origin leaks.
  5. Shodan/Censys lookups show no unsupported origin endpoint as the documented user entry point.
  6. Zone-transfer attempt -> refused.
- **T-45 media-plane isolation**:
  1. Media host public endpoints scanned -> only LiveKit media ports reachable.
  2. HTTP `/`, `/admin`, `/api/*` on media host -> connection refused.
  3. DB connection from media host -> blocked by network policy.
  4. Media-host secrets store scoped to media-plane only.
- **T-56 origin-binding**:
  1. Direct request to Railway-origin URL without CF Access JWT -> rejected.
  2. Forged `Cf-Access-Jwt-Assertion` with invalid signature/audience/issuer -> rejected.
  3. `Cf-Connecting-IP` / forwarding headers spoofed without valid JWT -> ignored.
  4. Request through Cloudflare Access with valid JWT -> accepted.

### 16.11 Privacy - operators (PH DPA, RA 10173)

- **Notice** (`/privacy/notice`) shown on first login and on material change; acceptance recorded in `privacy_notice_acceptances`.
- Controller/processor roles, rights, retention, transfer bases, DPO contact (NPC-registered) documented.
- **DSR channel**: `dpa@<domain>` -> 15-day initial response SLA.
- **PIA**: lightweight for MVP (template + scoped risks); full PIA before pilot. NPC registration per NPC Circular 17-01 timeline.
- **Processor DPAs** with: CF, Railway, chosen PG, IdP, LiveKit, R2, Sentry, Better Stack, UptimeRobot.
- **Retention**: audit 365 d -> archive then prune; sessions 30 d; privacy-notice acceptances 7 yrs.
- **Cross-border transfer basis** recorded per processor (`dpa_artifacts.kind = 'cross_border_transfer_basis'`).

### 16.12 Privacy - bystanders (PH DPA + NPC Circular 16-01, F-004 fix)

- **Lawful-basis transparency requires notifying data subjects in frame.**
- **Signage policy** (template provided under `/docs/privacy/bystander-signage-template.md` at repo-scaffolding time):
  - Sign posted at every entrance of an area where a camera films.
  - Sign text (EN + Filipino): "This area is under CCTV surveillance by <Controller>. For privacy inquiries, contact <DPO email>. This system does not record footage in MVP."
  - Camera-ID and operator name on the controller's private site plan, not on the public sign.
- **Admin attestation**: per site, admin records `POST /api/v1/admin/sites/:id/signage-attest`; creates a `dpa_artifacts(kind='bystander_signage_attestation', ...)` row with a photograph hash.
- **Signage verification** on onsite visit at least quarterly; attestations re-signed annually.
- **Alert**: camera registered to a site without signage attestation in the last 12 months -> admin dashboard warning.
- **Minor consent for school sites (M-14)**: sites where minors are likely in frame (schools, daycare, after-school programs, paediatric clinics, youth centres) require, in addition to the standard signage above:
  - **Parental notice or consent procedure** documented per RA 10173 + NPC Circular 16-01.
  - Site admin records the procedure as a `dpa_artifacts(kind='bystander_signage_attestation', notes='minor_consent: <procedure>')` row at site bring-up.
  - **Consult Philippine data-privacy counsel** before deploying at such a site; the legal review outcome is itself a `dpa_artifacts` row and surfaced in T-46.
  - This is a **deploy-blocker** - admin UI refuses to enrol a camera at a flagged minor-site without the consent procedure on file.

### 16.13 CORS policy

- Same-origin by default: the React + Vite frontend and FastAPI backend are exposed under the same Cloudflare-protected app domain, with browser calls to `/api/v1/*`.
- Authenticated API routes set:
  - `Access-Control-Allow-Origin: https://<app-domain>` (exact).
  - `Access-Control-Allow-Credentials: true`.
  - `Access-Control-Allow-Methods: GET, POST` (others per route).
- **No wildcard `*` on any authenticated API.**
- A separate API subdomain is not selected for MVP. If introduced later, it requires an ADR and stricter CORS/cookie/CSRF review.
- `/api/v1/gateways/*` endpoints set `Access-Control-Allow-Origin` to an empty/disallow response for browser pre-flights -> **gateway APIs are not browser-callable**.
- **Webhook endpoint `/api/v1/webhooks/livekit` (H-08)**: server-to-server only.
  - `Access-Control-Allow-Origin` header is **empty** in responses (`Access-Control-Allow-Origin: ` - no value).
  - Browser preflight (`OPTIONS`) is rejected with **HTTP 405 Method Not Allowed** (no Allow-Origin emitted).
  - Documents in API spec that this route is invoked by LiveKit's webhook system over a server-to-server HMAC channel and has no browser callers.
- T-54 verifies: cross-origin token request rejected; same-origin succeeds; gateway API pre-flight from the browser denied; webhook preflight denied with 405.

### 16.14 Device fingerprint policy (F-007 fix)

- **What we collect**: `User-Agent`, `Accept-Language`. That is all.
- **What we do not collect**: canvas fingerprint, WebGL fingerprint, audio fingerprint, font list, screen resolution, time zone, battery, hardware concurrency, `plugins[]`, any browser-fingerprinting-library output.
- **How we use it**: hash(UA + Accept-Language) stored on `sessions.ua_fp` at login; compared on each request.
- **Mismatch policy**: log `auth.session.fingerprint.mismatch`; **do not kill the session**; require re-auth on the next sensitive action (admin mutation, token mint for a new camera). Rationale: mobile-network UA churn and language-switching are common; killing on mismatch yields false positives.
- Documented in ROPA.

### 16.15 PII-scrub policy for error tracking / logs / alerts

- **Sentry `beforeSend` hook**:
  - Strip `email`, `idp_subject`, `user.id`, `sub`.
  - Hash `ip` (SHA-256 with rotating salt; 30-day salt rotation).
  - Redact `Authorization`, `Cookie`, `Cf-Access-Jwt-Assertion`, `X-Gateway-Token`.
  - Hash `camera.id`, `camera.name`, `gateway.id`, `gateway.name` so operational support can still correlate without exposing the name to the vendor.
  - Drop any key matching regex `/secret|token|password|cred|key/i` (case-insensitive) except hash outputs.
- **App stdout logs**: same redaction rules.
- **Telegram alert messages (M-07)** - same scrub plus stricter rules because Telegram channels are the highest-leak-risk surface:
  - **No raw camera names**, **no raw camera IDs**: use opaque hashes `cam_<8-hex>` derived from `camera.id`.
  - **No raw gateway names or IDs**: use `gw_<8-hex>`.
  - **No user emails**, **no IdP subjects**, **no IPs**: use `user_<8-hex>` derived from `user.id` (or `unauth`).
  - **No site addresses, no admin contact details, no DPO email** in alert text.
  - Alert format example: `Warning: gateway gw_abc12345 offline >2min @ 2026-05-07T04:33Z (sev:high) -> runbook Section 20.14`.
  - Operator looks up the opaque ID in the admin dashboard (server-side, audited) to map back to the real entity. Telegram never sees the mapping table.
- **Audit log**: authoritative store; **not** sent to Sentry, **not** sent to Telegram. PII lives in audit with DB-enforced access control.
- **Alert review**: quarterly sample of Sentry issues + Telegram channel for residual PII; runbook for redacting historical issues if found.

### 16.16 Gateway identity & mTLS (summary; full spec Section 11.5 / ADR 0008)

- MVP: service token + Argon2id hash + pinned fingerprint + rotation runbook.
- Pilot+: mTLS leaf cert (90-day) from internal CA (offline root + online intermediate) + fingerprint pinned in `edge_gateways.mtls_fingerprint` + server pins app's TLS; rotation runbook.
- Alert: `cert_expires_at - 14 days`.
- Revocation on compromise: admin disables gateway -> existing publish terminated <=10 s -> rotation runbook re-issues.
- Audit events: `gateway.cert.issued|deployed|fingerprint.updated|revoked|expiring_soon_alert|credential.rotated`.

### 16.17 Rate limits

Applied at the CF edge (by IP/ASN and per-IdP-subject) where possible, and at the app layer (by `user.id`, `session.id`, `gateway.id`, and source IP fallback):

| Endpoint / class | Window | Limit | Burst | Key | On exceed |
|---|---|---|---|---|---|
| `GET /api/v1/cameras/:id/view-token` | 1 min | 30 | 10 | `user.id` | 429 + `Retry-After` + audit `viewer.token.rate_limited` |
| `POST /api/v1/gateways/:id/ingest-token` | 1 min | 60 | 20 | `gateway.id` | 429 + `Retry-After` + audit `gateway.ingest.rate_limited` |
| `POST /api/v1/gateways/:id/heartbeat` | 1 min | 12 | 4 | `gateway.id` | 429 + `Retry-After` |
| `POST /api/v1/gateways/:id/cameras/*/status` | 1 min | 120 | 30 | `gateway.id` | 429 + `Retry-After` |
| `POST /api/v1/webhooks/livekit` | 1 min | 600 | 120 | source IP | 429 |
| `POST /api/v1/admin/*` mutations | 1 min | 60 | 20 | `user.id` | 429 + audit |
| `GET /api/v1/admin/audit/export` | 15 min | 3 | 1 | `user.id` | 429 + audit |
| `POST /api/v1/admin/break-glass/open` | 10 min | 2 | 1 | source IP + identity | 429 + audit `break_glass.rate_limited` |
| `POST /api/v1/privacy/notice/accept` | 1 min | 10 | 3 | `user.id` | 429 |
| Global per-IP unauth | 1 min | 30 | 10 | source IP | CF challenge |

Breach behaviour: returns `429` with `Retry-After` header; anomaly alert fires if any key exceeds its limit for 3 consecutive windows (Section 17). T-53 exercises limits on view-token mint and gateway ingest-token mint.

### 16.18 Incident response & alerts (pilot unless flagged)

- Alerts wired to email + Telegram (MVP) / PagerDuty (pilot): failed-login burst, off-hours admin, audit chain break, camera offline >2 min, gateway offline >2 min, error-rate spike, LiveKit quota approaching threshold, CF Access policy change, media-plane health degraded, **gateway cert expiring <=14 d**, **break-glass opened**, **rate-limit anomaly**, **CSP violation**, **CORS rejection spike**, **webhook-replay rejection spike**.
- Runbooks (Section 20.8 - Section 20.16).
- Legal: NPC 72-hour breach notification; internal logs for unauthorized access/change/loss.
- **External-monitor service-token** used for `/health` probes is rotated quarterly; rotation itself is audited.

### 16.19 Viewer-identity watermark (MVP) (M-06)

**MVP posture**: a CSS overlay watermark on every live video tile, providing visible deterrence against off-screen recording and screen-sharing leaks. Not tamper-proof - a determined insider can disable it with browser devtools - but raises the cost of casual leakage and provides forensic value if a screen recording surfaces.

**Implementation**:

- React component `<ViewerWatermark />` rendered as a sibling to each `<VideoTile />` inside the same positioned container.
- Content: `<email-prefix>@<domain> · <UTC ISO timestamp updated every 1 s> · cam <short_uuid_8>`. Example: `j.dela.cruz@school.edu.ph · 2026-05-07T04:33:21Z · cam abc12345`.
- Email is read from `/api/v1/me` (already authenticated); no extra fetches.
- Styles:
  - `position: absolute; top: 0; left: 0; right: 0; bottom: 0;`
  - `pointer-events: none;` (cannot intercept clicks on the underlying video)
  - `mix-blend-mode: difference;` (legible across light/dark scenes)
  - `font-family: ui-monospace; font-size: clamp(10px, 1.2vw, 14px); opacity: 0.7;`
  - Repeated diagonal text pattern at low opacity across the tile, plus a corner badge with the live timestamp.
- **No JS shielding** against devtools removal (futile; would only complicate review). Operator awareness training documents that the watermark is deterrence-grade, not tamper-proof.
- **Pilot+ upgrade path** (already in v4 Section 16): server-rendered video-embedded watermark via a media-pipeline overlay (LiveKit Egress + ffmpeg or a transcoder); requires recording infrastructure that is not in MVP. Tracked in pilot backlog.

### 16.20 Certificate Transparency monitoring (N-02)

**Goal**: detect any TLS certificate issued for the app domain by an unexpected CA (sign of mis-issuance, hostile re-routing attempt, or operator error).

**Mechanism**:

- Poll `crt.sh` for the app domain (`<app-domain>` and `*.<app-domain>`) hourly via the selected scheduler (Railway scheduled job, GitHub Actions schedule, or equivalent), or use Cloudflare's built-in CT monitoring if the selected CF tier exposes it via API.
- Maintain an allow-list of expected issuer organizations: **Cloudflare Inc ECC CA-3** (CF-managed certs), the LiveKit-fallback domain's expected issuer (e.g., Let's Encrypt), and any planned future issuers; the allow-list is in `/infra/ct-allowlist.json` and updated via PR.
- On detection of a cert outside the allow-list:
  - Alert via Telegram (PII-scrubbed per Section 16.15) and email to admin + DPO.
  - Audit `system.ct.unexpected_cert_detected` with cert serial + issuer + fingerprint.
  - Trigger Section 20.6 CT-incident runbook: validate the cert is legitimate (planned change) or treat as compromise indicator (rotate keys, contact CA, file revocation request, re-issue from CF).
- **CAA record** on the app domain pinned to the expected issuer(s); reviewed during Section 20.6 observability checklist.
- Runbook reference: Section 20.6.

---

## 17. Audit Logging & Monitoring

### 17.1 Events (representative; reject if absent)

- `auth.login.ok`, `auth.login.denied.mfa`, `auth.login.denied.policy`, `auth.login.denied.device_posture`.
- `auth.session.created`, `auth.session.revoked`, `auth.session.fingerprint.mismatch`.
- `mfa.reset.admin_mediated`.
- `user.disabled`, `user.role.changed`, `user.mfa.reset`.
- `camera.acl.granted`, `camera.acl.revoked`.
- `camera.created`, `camera.retired`, `camera.disabled`.
- **`viewer.token.issued`, `viewer.token.denied.acl`, `viewer.token.denied.disabled`, `viewer.token.denied.retired`, `viewer.token.denied.gateway_identity`, `viewer.token.rate_limited`**.
- **`gateway.registered`, `gateway.credential.issued`, `gateway.credential.rotated`, `gateway.disabled`, `gateway.retired`**.
- **`gateway.cert.issued`, `gateway.cert.deployed`, `gateway.cert.fingerprint.updated`, `gateway.cert.revoked`, `gateway.cert.expiring_soon_alert`**.
- **`gateway.ingest.token.issued`, `gateway.ingest.denied.unassigned`, `gateway.ingest.denied.disabled`, `gateway.ingest.denied.browser_session`, `gateway.ingest.rate_limited`**.
- **`gateway.heartbeat.ok`, `gateway.heartbeat.stale`, `gateway.camera.status.changed`**.
- `livekit.room.created`, `livekit.room.closed`, `livekit.participant.joined`, `livekit.participant.removed`, `livekit.webhook.received`, `livekit.webhook.replay_rejected`, `livekit.fallback.activated`, `livekit.fallback.deactivated`.
- `admin.action.*` (create, disable, role change, ACL change, gateway assignment change, secret rotation).
- `audit.export.signed` (includes export hash + requester).
- `audit.hmac.rotated` (records the rotation transition; `hmac_key_version` of this row is the new version; `prev_hash` links to the last hash signed under the old version).
- `break_glass.opened`, `break_glass.closed`, `break_glass.auto_disabled`, `break_glass.rotation_completed`.
- `privacy.notice.accepted`, `site.signage.attested`.
- `backup.run.ok`, `backup.run.failed`, `backup.integrity.ok`, `backup.integrity.failed`.
- `system.config.updated`.
- `exposure_check.passed`, `exposure_check.failed`, `media_isolation.passed`, `media_isolation.failed`, `origin_binding.passed`, `origin_binding.failed`.
- `rate_limit.anomaly.detected`.

Each row: who (actor + actor_type), what, when, where, why (payload), chain (prev_hash + hash + **hmac_key_version**).

### 17.2 Integrity

- Append-only triggers + HMAC-SHA-256 chain per row + version tag.
- 5-minute verifier job (pilot) walks the tail; on mismatch fires P0 alert + optional read-only mode.
- Daily signed archive to R2 (object lock, compliance mode).
- Weekly chain-integrity sweep reads a sampled window across all present `hmac_key_version`s.
- Retention 365 d in DB; archive kept 7 yrs; retention-driven prune is segmented across rotation boundaries so both before/after halves verify independently.

**Trust model for audit export (C-04)**:

The synchronous signed JSONL export at `GET /api/v1/admin/audit/export` (Section 15.1) ships three pieces of evidence:

1. **Signed JSONL** of the requested audit rows. The signature attests that the dump was produced by `cctv-api` at signing time - nothing more.
2. **Per-row chain fields**: `prev_hash`, `hash`, `hmac_key_version` for each row exactly as stored.
3. **`audit_hmac_keys` snapshot**: the rows of the keys table active at export time, with key material redacted but versions, creation/retire timestamps, and key-fingerprint hashes retained.

**What the export signature does NOT prove**:

- It does **not** prove that the underlying audit rows were not tampered with after their original write - only that they read this way at signing time.
- It does **not** authenticate `cctv-api` itself (a compromised app can sign anything).

**Independent verification path (recipient)**:

1. Recipient receives the bundle.
2. Recipient runs an offline verifier (open-source, repo'd in `/scripts/verify-audit-export.ts`) that walks the JSONL rows and re-computes `HMAC(key_for_version(hmac_key_version), prev_hash || row_canonical_json) == hash` for every row, using the keys snapshot.
3. Recipient checks the chain is continuous (each row's `prev_hash` matches the previous row's `hash`, including across `hmac_key_version` rotation boundaries per T-49).
4. Any mismatch -> the row was tampered with at-rest after write, *or* the keys snapshot was tampered with. Either way, **independent** of the export signature - a compromised `cctv-api` cannot fake this verification because it does not hold the recipient's own out-of-band knowledge of which key versions existed at export time.

**Pilot+ uplift**: external notary or a separate signing-key store (HSM) for the export signature - a stronger guarantee that the export bundle itself was not produced by a compromised app. Recommended before any external-auditor reliance.

### 17.3 Monitoring

- Uptime probes (external) to `/health` with service-token header (CF Access App D).
- Better Stack heartbeat with service-token; Sentry error tracking (PII-scrubbed, Section 16.15) tagged `plane=control|media|camera`.
- Admin-only `/api/v1/admin/health/deep` for DB/LiveKit/R2/mediamtx status.
- Dashboards: login trends, error rates, audit volume, WebRTC connect success, LiveKit quota usage, **camera heartbeat health**, **gateway heartbeat health**, **gateway cert expiry**, **`stream_grants` row count**, **CSP violation rate**, **CORS rejection rate**, **CT-log unexpected-cert events**, **gateway anomaly events**.
- LiveKit quota alarms at 70/90%.
- **Post-backup alerts**: `backup_runs.restore_format_ok = false` on the most recent daily; `backup_runs.restore_schema_ok = false` on the most recent weekly drill; or stale (no row in expected window) (M-04).

**Token-theft / gateway anomaly detection (M-13)**:

- **Per-`gateway_id` ingest-token mint-rate alert**: rolling 7-day baseline computed from `stream_grants WHERE kind='gateway_publish'`; alert if a gateway's 1-hour mint-rate exceeds **2x baseline** (subject to a minimum-volume floor to avoid noise on quiet gateways).
- **Per-`gateway_id` source-IP-change alert**: each gateway's authenticated source-IP is recorded on every `/heartbeat` and `/ingest-token` call; if the source-IP changes within a sliding 1-hour window, alert. Mobile-WAN false positives are dampened by also requiring the IP to fall outside the gateway's allow-listed ASN(s) (recorded at enrolment).
- **New audit event**: `system.gateway.anomaly.detected` with reason (`mint_rate_excess` | `source_ip_change` | `unassigned_camera_attempted`) and the gateway's recent activity window. Surfaces in the admin dashboard -> Section 20.14 lifecycle runbook covers response (verify with operator -> if unverified, disable + rotate).

### 17.4 Observability secret inventory (Section 20.16 cross-reference)

- Sentry DSN, Better Stack ingestion token, UptimeRobot API key, **Telegram bot token + chat ID**, CF Access service tokens (monitor + per-gateway).
- Rotation schedule + leak-response runbook in Section 20.16.
- Each secret has a named owner and a revocation channel.

**Telegram alert format (M-07)**: see Section 16.15. Alerts use opaque hashes (`gw_<8-hex>`, `cam_<8-hex>`, `user_<8-hex>`) with no raw names, emails, IPs, or addresses. Operator looks up the opaque ID in the admin dashboard server-side.

---

## 18. QA & Testing Plan

### 18.1 Test layers

| Layer | Tooling | Target coverage |
|---|---|---|
| Unit | pytest | Authz, JWT verify, hash chain math, token mint, CORS header emission, fingerprint, rate-limit logic, break-glass window check |
| Integration | pytest + testcontainers Postgres | DB migrations, triggers, retention, backup-integrity, disable propagation |
| E2E | Playwright | Critical user flows; visual diff on admin; **no browser publisher flow exists** |
| Security | ZAP baseline, Semgrep rules, osv-scanner, Trivy, gitleaks, **browser-bundle scanner** | High-risk code paths, deps, container, forbidden terms in bundle |
| Network-layer | Scripted `curl`/`nmap`/`tcpdump` harness | T-30, T-45, T-56, T-37-expanded |
| Load | k6 | Single-camera smoke, 10-viewer burst, gateway-heartbeat storm |
| WebRTC | LiveKit test harness + Playwright | Token lifecycle, reconnection, URL-leak denial |

### 18.2 Representative test matrix

| ID | Title | Layer | Notes |
|---|---|---|---|
| T-1 | Unauth on `/dashboard` gets CF Access challenge | E2E / net | - |
| T-2 | Unauth on `/` gets no app content | E2E | no banner |
| T-3 | Unauth on `/admin` gets challenge, not 404 leak | E2E | no enumeration |
| T-4 | No version banner on any response | E2E | grep headers + HTML |
| T-5 | Viewer sees only ACL'd cameras | Unit + E2E | - |
| T-6 | Copied stream URL denied in 60 s | Net / WebRTC | TTL expiry |
| T-7 | Admin mutation requires recent re-auth | E2E | - |
| T-8 | Role change audited | Int | - |
| T-9 | Disable user revokes session <=1 s | Int | - |
| T-10 | CSP blocks inline script | E2E | - |
| T-11 | CSRF double-submit enforced | E2E | - |
| T-12 | Rate limits return 429 on token mint | Load | viewer + gateway |
| T-13 | `camera_acl` respected on API | Unit | - |
| T-14 | `gateway_camera_assignments` respected on gateway token mint | Unit | - |
| T-15 | Secret scan clean | CI | gitleaks |
| T-16 | Container scan clean | CI | Trivy |
| T-17 | SAST clean (no high) | CI | Semgrep |
| T-18 | SCA clean (no high) | CI | osv-scanner |
| T-19 | ZAP baseline clean | CI | - |
| T-20 | 7-day uptime >=99% staging | SRE | - |
| T-21 | Audit chain verifier end-to-end | Int | - |
| T-22 | Backup restore drill passes integration query | SRE | F-011 |
| T-23 | `audit_log` UPDATE blocked | Int | trigger |
| T-24 | `audit_log` DELETE blocked | Int | trigger |
| T-25 | Idle session expires at 15 min | E2E | - |
| T-26 | Absolute session expires at 8 h | E2E | - |
| T-27 | MFA required at IdP on new device | E2E | depends on IdP |
| T-28 | Admin re-auth required <=5 min | E2E | - |
| T-29 | No sensitive data in error messages | Unit | - |
| T-30 | External-exposure checklist (REQ-SEC-01) | Net | all items pass |
| T-31 | Chain verifier detects a tampered row | Int | negative |
| T-32 | LiveKit token TTL <=60 s | Unit | - |
| T-33 | Viewer/gateway token roles distinct | Unit | scope |
| T-34 | Watermark shown in video (pilot) | E2E | pilot |
| T-35 | p95 latency <2 s glass-to-glass | Load/WebRTC | - |
| T-36 | Retention job prunes correctly | Int | - |
| T-37 | **LiveKit fallback - network-layer expanded**: UDP-preferred, TCP/TLS:443 fallback, viewer + gateway reconnection <=60 s, no plaintext creds on wire | Net / WebRTC | media fallback |
| T-38 | CF Access rollback runbook executes cleanly | SRE | - |
| T-39 | LiveKit quota approaching -> alert fires | SRE | - |
| T-40 | Phase-2.5 architecture checkpoint docs produced | Review | - |
| T-41 | Self-hosted LiveKit fallback deploy from cold state | SRE | - |
| T-42 | Lost-MFA recovery runbook | SRE | - |
| T-43 | **RTSP reconnection test** (camera reboot) - gateway resumes publish | WebRTC | - |
| T-44 | **RTSP credential-leak grep** on packet captures | Net | no cleartext |
| T-45 | **Media-plane isolation** (REQ-SEC-01b) | Net | - |
| T-46 | **DPA artefact bundle complete** (incl. bystander signage attestations + cross-border transfer bases) | Review | - |
| **T-47** | **JWT skew: `nbf = now + 25s` accepted** | Unit | CLOCK_SKEW_SECONDS = 30 |
| **T-48** | **JWT skew: `nbf = now + 60s` rejected** | Unit | - |
| **T-49** | **HMAC chain verifies across `hmac_key_version` rotation** (chain-continuity row after rotation) | Int | F-005 |
| **T-50** | **`stream_grants` cleanup removes expired rows**; replay check stays fast at realistic volume | Int + Load | - |
| **T-51** | **Monitor service-token reaches `/health`**; body is exactly `{"status":"ok"}`; no banner/version/DB info | Int | - |
| **T-52** | **Break-glass auto-denies after 91 minutes** even after app worker restart (scheduler-failure simulation) | Int / SRE | F-006 |
| **T-53** | **Rate-limit returns 429 + `Retry-After`** for viewer-token mint and gateway-ingest-token mint | Load | Section 16.17 |
| **T-54** | **CORS cross-origin token request rejected; same-origin succeeds**; gateway API pre-flight denied | E2E | Section 16.13 |
| **T-55** | **Gateway heartbeat / camera-status event updates dashboard SSE** (or polling) within target time | E2E | Section 15.1 |
| **T-56** | **Origin-binding** (REQ-SEC-01c): direct Railway-origin request rejected without valid CF Access JWT; trusted headers ignored on unverified requests | Net | F-001 + F-002 |
| **T-57** | **DB least-privilege introspection**: `cctv_app_runtime` cannot `ALTER`, `TRUNCATE`, disable triggers, or UPDATE/DELETE `audit_log` | Int | Inv 15 / F-010 |
| **T-58** | **CI forbidden-term grep**: `getUserMedia`, `MediaRecorder`, `/publish`, `/demo-publisher`, `/lab-publisher`, `/webcam`, `/phone-publisher` absent from active code (whitelisted only in `/docs/` and Section 29 of plan) | CI | REQ-CCTV-01 |
| **T-59** | **Browser-bundle scan**: built `.js`/`.mjs`/`.css` bundles contain no RTSP/ONVIF URLs, no `getUserMedia`, no `MediaRecorder`, no known cred-env names | CI | REQ-CCTV-01 |
| **T-60** | **Token-mint authorization** (Section 15.3): browser calling gateway ingest -> 401/403 + audit `gateway.ingest.denied.browser_session`; gateway calling viewer endpoint -> 401/403 + audit `viewer.token.denied.gateway_identity` | Int | REQ-CCTV-01 |
| **T-61** | **Gateway auth**: unregistered gateway rejected; disabled gateway rejected; expired/rotated credential rejected; correct credential accepted only for assigned cameras | Int | Inv 6 + ADR 0008 |
| **T-62** | **No camera credentials in browser bundle or any API response**: grep built assets for `rtsp://`, `ONVIF`, camera cred env-var names; assert API responses for `/api/v1/cameras*` and `/api/v1/cameras/:id/view-token` contain no credential fields | CI + Int | REQ-CCTV-01 + A29 |
| **T-63** | **Stale LiveKit webhook rejected**: webhook with `abs(now - webhook.createdAt) > 60s` returns HTTP 400; audit row `livekit.webhook.replay_rejected` is written with the offending timestamp; webhook within window succeeds | Int | H-08; Section 13.5 rule 13; Section 15.1 |
| **T-64** | **Forged `cf-access-jwt-assertion` rejected**: (a) injection via direct Railway-origin request -> rejected (re-asserts T-56); (b) injection of a forged extra `cf-access-*` header (e.g., `cf-access-username-override`) -> ignored before route handler identity construction per the explicit allow-list (Section 11.6) | Int + Net | N-03; Section 11.6 |

**T-50 expanded scope (M-11 / H-04)**: in addition to verifying that the cleanup query removes expired rows, T-50 also (i) verifies the cleanup **mechanism actually runs** by injecting a synthetic expired row and asserting it is deleted within 6 minutes by the selected scheduled cleanup job (or external-cron fallback), and (ii) verifies the `jti` replay-protection scope: a duplicate `jti` mint request is rejected at app token-mint, while a parallel test confirms LiveKit-side replay protection is the 60-s TTL only.

**T-46 sub-items (M-05 / M-14)**: the DPA artefact bundle export must include (in addition to the v4 baseline): (a) **NPC registration confirmation** OR a dated note explaining the Circular 17-01 timeline that defers it; (b) for each site flagged as a minor-frequented site (school, daycare, etc.), the **minor-consent procedure document** plus the legal-counsel review outcome.

**ID collision note**: the v3-review's T-47..T-53 findings are re-slotted to T-56..T-62 in v4 to preserve your Section 25 T-47..T-55 numbering intent. T-63 and T-64 are v4.1 additions.

### 18.3 Exit criteria

- All tests pass in CI.
- 0 critical/high in Semgrep / osv-scanner / Trivy / gitleaks / ZAP.
- 100% pre-pen-test checklist green (Section 19).
- T-30, T-45, T-56 all pass.
- T-58, T-59, T-60, T-61, T-62 all pass (CCTV-only invariant enforced).
- T-47, T-48, T-49, T-50, T-51, T-52, T-53, T-54, T-55 all pass.
- **T-63, T-64 pass (v4.1 additions: webhook replay window, trusted-header allow-list).**
- 7-day staging uptime >=99% on control plane.
- LiveKit fallback rehearsed (T-37 expanded).
- DPA artefact bundle present (T-46) incl. bystander signage.

---

## 19. Pen-test Readiness Checklist (pre-pen-test self-attack)

1. External-exposure checklist T-30 green.
2. Media-plane isolation T-45 green.
3. **Origin-binding T-56 green.**
4. **CCTV-only enforcement** T-58, T-59, T-60, T-61, T-62 green.
5. No marketing page, no public login page, no public signup route.
6. No user enumeration (identical response time + body for invalid vs valid email on any lookup).
7. Strict security headers verified (observatory.mozilla.org A+ equivalent).
8. CSP without `unsafe-*`; `connect-src` pinned to specific LiveKit regional hosts; `Permissions-Policy: camera=()` present.
9. No framework/version banner on any response.
10. CSRF enforced on every state-changing route.
11. Rate limits live at CF + app; 429 with `Retry-After`; anomaly alert (T-53).
12. CF Access policies validated (Apps A/B/C/D/E).
13. Audit log tamper test passes (T-31) and rotation-continuity test passes (T-49).
14. Backup restore drill passed; integration query runs against restored DB (T-22, F-011).
15. SCA/SAST/secret/container scans clean.
16. No secrets in source; Railway/media/gateway secrets inventory; Telegram bot token rotation runbook present (Section 20.16).
17. IAM deny-by-default verified on every route.
18. CSP violation reports wired to an alert.
19. Session revocation **+ LiveKit room termination <=10 s** verified.
20. Network policies (Railway control-plane ingress + media-plane isolation + DB ACL + Inv 15 least-priv) documented and tested.
21. DB role inventory verified (Inv 15 / T-57).
22. Break-glass window 90 min request-time enforced + rotation runbook (T-52).
23. Lost-MFA recovery runbook present (T-42).
24. CF Access rollback runbook present (T-38).
25. LiveKit quota-fallback runbook present with network-layer acceptance (T-37 expanded, T-41).
26. **Gateway lifecycle runbook** (Section 20.14) present; **gateway cert rotation runbook** (Section 20.15) present.
27. **Telegram bot token rotation / leak-response runbook** (Section 20.16) present.
28. Provider-exit playbook present per plane (Section 20.13).
29. Experimental FastAPI/Pydantic/SQLAlchemy/LiveKit APIs not used in security-critical paths (CI lint).
30. Python Docker base/runtime pinned to exact patch where containerized; CI fails on floating tag.
31. Dependabot (or equivalent) configured; SCA patch-update process documented.
32. DPA: PIA + ROPA + processor DPAs filed; DPO engaged; cross-border transfer basis recorded.
33. **Bystander signage** attested per site (Section 16.12).
34. **No recording enforcement**: no Egress, no media bucket, no `MediaRecorder`, no snapshot route - verified by T-58/T-59 + manual review.
35. **Bus-factor runbook** present (Section 20.19) and quarterly drill scheduled.
36. **CT-log monitoring** active (Section 16.20); CAA records present.
37. **SBOM (Syft / CycloneDX) generation** wired in CI; signed and attached to releases (N-01).

---

## 20. DevOps & Deployment Plan

### 20.1 Environments

- `dev` (local), `staging` (Railway environment), `prod` (Railway environment; DR to alternate container-compatible host is pilot+). Temporary Railway-generated URL: `https://panoptix-control-production.up.railway.app`; final user entry point is the Cloudflare Access protected custom domain.
- Separate CF Access policies per env; separate Railway environments/services; separate media/gateway secret scopes.
- **Separate secret stores per plane and per gateway**.

### 20.2 CI/CD pipeline

- GitHub Actions -> Railway deploy; avoid long-lived deploy tokens where Railway/GitHub integration supports it.
- Stages: lint -> typecheck -> unit -> integration (testcontainers) -> **browser-bundle scan (T-58 + T-59 + T-62)** -> Semgrep -> osv-scanner -> Trivy -> gitleaks -> **Docker-base pin check (T-58 extension)** -> **SBOM generation (Syft -> CycloneDX, sigstore-signed; N-01)** -> Playwright -> ZAP baseline -> build -> sign with Cosign -> staging deploy -> smoke -> (manual) prod rolling deploy.
- **SBOM (N-01)**: Syft generates CycloneDX-format SBOM per release artefact/container where applicable (`cctv-api`, dev/CI gateway, media fallback when selected); SBOM is sigstore-signed and **attached to the GitHub Release as a verifiable artefact**. SBOMs are diffed PR-to-PR in CI and surface significant dependency changes in the PR review checklist. Goal: regulator-ready supply-chain provenance + faster CVE triage when a transitive dep is disclosed.
- **CT-log monitoring (Section 16.20)** runs as a scheduled job on the selected scheduler (Railway cron/scheduled service, GitHub Actions schedule, or equivalent); alerts surface in the same channels as deploy alerts.
- **T-30 + T-45 + T-56 run as scheduled post-deploy jobs** (every 6 h) in staging and prod; alert on any regression.
- Branch protection; signed commits; required reviews on `main`.
- **Python Docker base floating-tag check**: CI fails if `Dockerfile` uses `python:3.12`, `python:3.12-slim`, or any tag without a patch version; only `python:<major>.<minor>.<patch>-<distro>` is accepted where containerized.
- **Dependabot** config present and required; weekly PRs.

### 20.3 IaC

- Terraform/config modules: `cloudflare` (Access apps A/B/C/D/E, DNS, WAF, rate-limit rules), `railway-app` or provider config (`cctv-api` Python service), `media-fallback` (DigitalOcean Singapore or equivalent UDP-capable APAC host), `dev-ci-gateway` (synthetic RTSP host if needed; never real cameras), `postgres` (Neon-first managed PG), `r2`, `livekit` (Cloud project and/or fallback config).
- `tfsec` / `checkov` in CI.
- Drift detector runs daily; auto-PR on drift.

### 20.4 Deploy strategy

- Railway deploy with health checks on `/health` (service-token protected where externally probed) and `/api/v1/admin/health/deep` (admin-only).
- DB migration policy: expand-migrate-contract.
- Rollback via previous image tag; rollback runbook (Section 20.8).

### 20.5 Runtime config

- Feature flags in `system_config` for: media-plane mode (cloud/fallback), gateway-identity tier (service-token/mtls), break-glass rotation items checklist, CCTV-only enforcement strictness (always on in MVP).

### 20.6 Observability

- Logs -> stdout -> Railway logs / Better Stack.
- Sentry is optional for MVP and enabled when error tracking is needed; if enabled, payloads are PII-scrubbed (Section 16.15) and tagged `plane=control|media|camera`.
- UptimeRobot pinging `/health` with service-token header (no public `/health`); email alerting first, Telegram optional.
- Dashboards per Section 17.3.
- **CT-log monitoring (Section 16.20)**: hourly poll of crt.sh (or CF CT API) for `<app-domain>` and `*.<app-domain>`; allow-list of expected issuers in `/infra/ct-allowlist.json`; on unexpected cert -> Telegram + email alert + audit `system.ct.unexpected_cert_detected` + run Section 20.6 CT-incident sub-runbook (validate planned vs. compromise; rotate, contact CA, file revocation if compromise; re-issue from CF). **CAA record** on the app domain pinned to the expected issuer(s); reviewed during this checklist.

### 20.7 Backups & DR

- **Backup host (H-09)**: backup runs as a GitHub Actions scheduled workflow with locked secrets for MVP, separate from the web process. Railway scheduled jobs or another selected scheduler may replace it later if operationally better. It is not a developer laptop. The job performs the backup, integrity check, R2 upload, writes `backup_runs`, and exits.
- Nightly `pg_dump | age -e -r <recipient> | rclone copy - r2:cctv-backups/...` - streamed encrypted upload; private key never present on backup machine.
- **Daily integrity check (M-04)**: same machine fetches the just-uploaded archive, decrypts (with the test recipient pubkey scoped to integrity checks only - NOT the production decryption key), runs `pg_restore --list` against the archive to validate it is structurally readable, records sha256 + row-count estimate in `backup_runs.restore_format_ok = true`. Alert on `restore_format_ok = false` or upload failure.
- **Weekly automated schema-restore drill**: same scheduled job restores the latest backup to an ephemeral Postgres/test environment, runs the integration-query (audit-chain verification + camera/gateway row counts - F-011), and writes `backup_runs.restore_schema_ok = true`. Alert on `restore_schema_ok = false` or stale (no successful drill in the last 8 days).
- **DR targets**: RPO <=24h MVP / <=1h pilot (PITR); RTO <=4h MVP / <=1h pilot.
- **MVP DR scope (M-10)**: restore/redeploy to the selected Railway environment after recovery, or to an alternate container-compatible host if Railway is unavailable. Cross-region hot standby is pilot+; MVP does not maintain a hot standby.

### 20.8 Deploy / incident runbooks (representative)

Each runbook lives at `/docs/runbooks/<slug>.md`; owner, oncall, communications template, rollback trigger, post-mortem template.

1. Deploy (Section 20.4).
2. Rollback: previous image tag, DB contract step reversal, notify users.
3. Incident triage / severity matrix (P0/P1/P2/P3), communications.
4. Restore from backup + integration-query verification.

### 20.9 CF Access rollback runbook

- Trigger: policy misconfig causes legitimate users to be locked out, or legitimate policy causes unexpected access path.
- Steps: identify last-known-good Terraform revision -> `terraform plan` on rollback -> **dry-run first** -> apply -> verify CF Access apps A/B/C/D/E with known-good identities -> run T-30 post-change.
- Communication: status page + email to affected users.
- Post-mortem template.

### 20.10 LiveKit quota-fallback runbook (with network-layer acceptance)

- Pre-conditions: self-hosted LiveKit fallback host selected, with DigitalOcean Singapore as first candidate or equivalent APAC UDP-capable provider, and verified for UDP/media ports + TCP/TLS:443, secrets provisioned, admin UI feature flag available.
- Activation: `POST /api/v1/admin/livekit/fallback` (SuperAdmin + re-auth).
- Control-plane switch: app starts issuing viewer + gateway tokens with fallback URL and updated CSP `connect-src` (includes fallback domain) **per the dynamic-CSP mechanism in Section 16.5 (M-08)** - the Middleware reads `system_config.media_plane_mode` per request; both Cloud and fallback origins are pre-approved values in code; switching is a DB flag flip, no redeploy.
- Acceptance: **T-37 expanded** - UDP preferred, TCP/TLS:443 fallback, viewer + gateway reconnection <=60 s, media-plane T-45 green.
- Rollback: flip flag back; audit both transitions.

### 20.11 IdP outage runbook

- Detection: CF Access challenge failures spike; IdP status page.
- Mitigation: activate CF one-time-PIN secondary policy (pre-configured on Apps A/B).
- Communication: email users with temporary auth instructions.
- Close-out: revert when IdP recovers; audit `auth.policy.degraded.opened` / `.closed`.

### 20.12 Lost-MFA recovery runbook

See Section 16.7. Steps: identify user -> verify out-of-band -> IdP console MFA reset -> user re-enrols within 24 h -> audit.

### 20.13 Provider-exit playbook (per plane)

- **Trigger criteria**: material pricing change (>50% MoM), SLA downgrade, security incident at the provider, geo/jurisdiction shift, quota-limit change that breaks the product, new legal requirement.
- **Per-plane playbooks**:
  - **IAP exit**: reconfigure DNS -> deploy alternate IAP (Tailscale/Headscale + nginx + IdP-direct, AWS ALB + Cognito + WAF, or Pomerium) -> re-verify T-30.
  - **App-hosting exit**: build deploys to alternate (Render/Fly/DO/App Runner); secrets re-provisioned; cut-over via DNS; re-verify T-56.
  - **Postgres exit**: `pg_dump` -> restore on target -> swap connection string -> monitor.
  - **Media-plane exit**: LiveKit Cloud -> self-hosted fallback (existing runbook 20.10) -> if long-term, evaluate alternate SFU vendor + client SDK swap (ADR-driven).
  - **Edge-gateway exit**: `mediamtx` -> alternate RTSP-WebRTC bridge; per-site re-imaging; gateway credentials re-issued.
- **Decision ADR** authored within 5 business days of trigger; migration within the SLA window documented in each runbook.

### 20.14 Gateway lifecycle runbook

- **Register**: admin creates `edge_gateways` row via admin UI -> app mints one-time service token (MVP) or issues mTLS leaf cert (pilot+) -> operator installs on gateway host -> gateway calls `/heartbeat` with credential -> row marked `enabled`.
- **Assign cameras**: admin adds `gateway_camera_assignments` rows -> gateway refreshes its camera list via heartbeat response.
- **Rotate credential** (MVP, on-site mini-PC, H-02):
  1. Admin clicks "rotate token" in UI -> server generates new token, computes Argon2id hash, persists hash, returns one-time-download with new raw token.
  2. Operator SSHes to the gateway host (admin laptop, WARP-protected subnet; SSH allowed only from this subnet).
  3. Operator writes the new token to `/etc/cctv-gateway/gateway.env` (mode `0600`, owner `cctv-gateway:cctv-gateway`); systemd `EnvironmentFile=` directive picks it up on service restart.
  4. `sudo systemctl restart cctv-gateway`.
  5. Operator confirms next heartbeat succeeds (admin UI shows green within ~30 s).
  6. Admin clicks "revoke old token" -> server marks old hash revoked.
  7. Audit row written: `gateway.credential.rotated` with operator user-id + gateway-id + old-token-fingerprint.
- **Rotate credential** (Pilot+, mTLS): issue new leaf cert from intermediate CA -> deploy to gateway -> verify handshake -> update `mtls_fingerprint` -> audit `gateway.cert.deployed` + `gateway.cert.fingerprint.updated` -> revoke previous leaf.
- **`mediamtx` HTTP API hardening (M-12)**: as part of every site bring-up and every quarterly review, runbook step verifies that `mediamtx.yml` either (a) sets `api: yes` with `apiAddress: 127.0.0.1:9997` (loopback only) **or** (b) sets `api: no`. Audit `gateway.mediamtx.api_check` records the chosen mode. **Failure mode**: any other binding (camera-VLAN IP, WAN IP, `0.0.0.0`) is treated as a security incident -> disable gateway -> reconfigure -> re-enable.
- **Anomaly response (M-13)**: when `system.gateway.anomaly.detected` fires, the on-call admin opens this runbook -> contacts the operator out-of-band to verify recent activity -> if unverified, disable + rotate credential -> if verified (e.g., legitimate IP change due to ISP swap), update the gateway's allow-listed ASN(s).
- **Disable** (temporary): admin sets `status='disabled'` -> ongoing publish terminated <=10 s -> gateway cannot mint new ingest tokens -> row retained for audit.
- **Retire** (permanent): admin sets `status='retired'` -> assignments revoked -> credential revoked -> audit trail preserved per retention policy.

### 20.15 Gateway certificate rotation runbook (pilot+)

- Trigger: alert `gateway.cert.expiring_soon_alert` at `cert_expires_at - 14 days`, or on compromise.
- Steps:
  1. Issue new leaf cert from intermediate CA (90-day).
  2. Deploy to gateway via secure channel (secret push for dev/CI gateway where applicable; signed bundle delivered out-of-band for on-site gateway).
  3. Gateway restarts `mediamtx` with new cert; old cert retained for <=5 min to avoid mid-call break.
  4. App receives next gateway handshake -> updates `mtls_fingerprint` + `cert_expires_at`.
  5. Audit `gateway.cert.issued` + `gateway.cert.deployed` + `gateway.cert.fingerprint.updated`.
  6. Revoke previous leaf in CA.
- Failure mode: if new cert handshake fails, gateway falls back to previous cert until window expires, then publish stops -> admin alerted -> manual intervention.

### 20.16 Telegram / observability secret rotation + leak-response runbook

- **Inventory**: Telegram bot token, Telegram chat ID, Sentry DSN, Better Stack ingestion token, UptimeRobot API key, CF Access monitor service token, CF Access per-gateway service tokens.
- **Rotation schedule**:
  - Telegram bot token - quarterly (routine) + immediately on suspected leak.
  - Sentry DSN - annually + on suspected leak.
  - Better Stack / UptimeRobot - annually + on suspected leak.
  - CF Access service tokens - quarterly (routine) + on leak.
- **Leak response**:
  1. Revoke token in vendor console (Telegram `/revoke`, Sentry "new DSN", Better Stack "rotate", UptimeRobot "new API key", CF Access "regenerate service token").
  2. Issue replacement; set Railway/media/gateway secret as applicable.
  3. Redeploy affected apps.
  4. Audit `system.secret.rotated`.
  5. Review access logs for abuse during the exposure window.
  6. Post-mortem.

### 20.17 Secrets & rotation summary (cross-reference)

- CF Access service tokens (monitor + per-gateway), Postgres URL, **audit HMAC keys (versioned)**, **LiveKit API key/secret** (Cloud **and** self-hosted), LiveKit webhook signing secret, cookie signing key, R2 keys, Railway deploy/project credentials, Sentry DSN, Better Stack token, UptimeRobot API key, Telegram bot token, Telegram chat ID, **per-gateway service tokens / mTLS CA intermediate key / per-gateway leaf cert**.
- Schedule per Section 16.8 + Section 20.16.

### 20.18 Capacity & cost

- Railway resource tier for `cctv-api` to be verified; self-hosted LiveKit fallback first candidate is DigitalOcean Singapore or equivalent UDP-capable APAC provider; dev/CI synthetic gateway host selected only if local/GitHub Actions synthetic testing is insufficient.
- CF Zero Trust free/paid tier per selected plan.
- Cost alarms at 70/90% of monthly budget.
- Neon free (prototype) / paid (pilot+).
- Quarterly cost review.

### 20.19 Bus-factor / continuity runbook (M-01)

**Goal**: ensure that if the primary developer is unavailable (illness, departure, key compromise, accident) the system can still be operated, recovered, and handed off without irreversible loss.

**Inventory of single-points-of-knowledge** (must each have a documented backup):

| Asset | Primary location | Continuity backup |
|---|---|---|
| Source repository | `github.com/<org>/cctv` | Read-only mirror to a second org account; weekly `git bundle` archived to R2 (encrypted) |
| Production secrets (Railway/control plane) | Railway project environment/secrets | Sealed-envelope copy of recovery procedure; **secrets themselves are NOT escrowed** - recovery is via Railway account/project access |
| Railway account access | Primary developer's account | A second admin on the project/org with billing + deploy access; emergency-only password in sealed envelope |
| Cloudflare account | Primary developer's account | Two CF account members with admin role; CF account password in sealed envelope |
| Postgres provider account | Primary developer's account | Two account members; password sealed |
| LiveKit Cloud account | Primary developer's account | Two account members; password sealed |
| R2 backup bucket | CF account | CF account access -> bucket access |
| Audit-export decrypt key | Sealed envelope | Dual-control split (Shamir 2-of-3) at pilot+ |
| Audit HMAC active key | Railway secret on `cctv-api` | Versioned in `audit_hmac_keys`; key material recoverable from sealed envelope copy of all-versions export |
| mTLS root CA private key (pilot+) | Offline air-gapped store | Sealed envelope, dual-control |
| Break-glass admin account | Hardware key + sealed envelope | Hardware key escrowed with second signatory; sealed-envelope password backup |
| Telegram bot ownership | Primary developer's Telegram | Bot transfer procedure documented; alternative bot pre-provisioned for fast-cutover |
| Domain registrar | Primary developer's account | Two account members; auto-renew + payment-method backup |

**Sealed envelope contents** (kept in a secure physical location - e.g., a safe at the Controller's registered office):

- Master recovery instructions document (`docs/runbooks/bus-factor-recovery.md`) - step-by-step instructions for the secondary admin.
- Break-glass admin recovery codes (printed).
- mTLS root CA private key (pilot+, sealed in a separate envelope, dual control).
- Railway deploy/project credential or recovery procedure (rotated quarterly if credential-based).
- Postgres URL with admin credentials.
- R2 backup-bucket access keys.
- Audit HMAC key versions (encrypted with the recovery passphrase; passphrase is itself in a separate sealed envelope held by a different signatory).

**Vendor support tiers + emergency contacts** (recorded in `docs/runbooks/vendor-contacts.md`, kept current):

- Cloudflare support tier + ticket URL + 24/7 phone (paid plans).
- Railway support tier + ticket URL.
- Postgres provider on-call procedure.
- LiveKit support email + Slack + procurement contact.
- DPO + legal counsel direct numbers.
- NPC breach-notification contact (PH).

**Recovery procedure** (when primary developer is unavailable):

1. Secondary admin retrieves the sealed envelope under dual-control witness.
2. Confirms audit - photo of the unsealed envelope, audit row `system.bus_factor.envelope.opened` written by the secondary admin via break-glass.
3. Follows the master recovery instructions: Railway login, CF login, validate `cctv-api` health, validate audit chain, etc.
4. Within 24 hours: rotate every credential listed in the envelope (because envelope-handling is a controlled-but-not-zero leak event).
5. Re-seal the envelope with the new credentials.
6. Document the bus-factor activation in the post-mortem template.

**Quarterly drill**: secondary admin executes the recovery procedure on a staging-clone (without opening the production sealed envelope) and confirms the steps still match reality. Drift in the runbook is logged + fixed.

---

## 21. Execution Roadmap

Each phase has an explicit **Exit Criteria**. Do not proceed to the next phase until its gate is green.

### Phase 0 - Decisions & procurement (**5-10 business days**, M-09)

- **P0-01** IdP decision (ADR 0002).
- **P0-02** Paid Postgres tier decision (ADR 0003).
- **P0-03** Confirm Philippine jurisdiction + sub-processor list; draft processor-DPA templates.
- **P0-04** Verify CF Zero Trust tier / features on the selected plan.
- **P0-05** Verify LiveKit Cloud quotas on the selected plan.
- **P0-06** Verify LiveKit fallback host options for UDP/media-port support; select provider or explicitly defer with risk acceptance.
- **P0-07** Architect pen-test modality (grey-box default).
- **P0-08** Decide continuous streaming default (A6': off).
- **P0-09** **Gateway-identity bootstrap decision (ADR 0008)**: service-token + fingerprint for MVP; CA design (self-managed intermediate vs CF mTLS) for pilot+; root key escrow plan.
- **P0-10** Lock Python/FastAPI/Pydantic/SQLAlchemy/Alembic versions; pin experimental-API exclusions; **pin `mediamtx` exact version** (ADR 0007 - framework + binary version pin policy).
- **P0-11** Procurement price sanity check (every cost line in Section 12.1 verified against live provider pricing).
- **P0-12** **Bystander signage policy + template drafted** (ADR 0011-equivalent); site inventory captured.
- **P0-13** **Production gateway hardware procurement (C-01, ADR 0013)**: pick NUC-class mini-PC SKU (Intel NUC / Beelink Mini S / MeLE Quieter / equivalent); confirm AES-NI; assemble Ubuntu 22.04 LTS x86_64 image; document baseline systemd unit + secret-store layout (Section 13.8). One-image-per-arch policy locked.
- **P0-14** **Camera procurement guidance (M-02)**: produce `/docs/procurement/camera-spec.md` listing recommended brands/models with confirmed RTSP Profile S support per datasheet; document that ONVIF-only cameras require the Section 13.3 spike before they can be enrolled in Phase 4; per-site pre-purchase checklist (model, firmware, RTSP path, credential rotation policy).
- **Exit**: all ADRs drafted (0001-0013) and open-questions log closed; mini-PC SKU + Ubuntu image baseline locked; camera spec doc landed; processor-DPA templates ready for signing; no blockers to Phase 1.

**Day-by-day sequence (suggested)**:

- **Days 1-2**: blocking decisions - IdP (P0-01), Postgres tier (P0-02), CF tier (P0-04), LiveKit quota (P0-05), fallback-host feasibility (P0-06).
- **Days 3-5**: ADR drafts 0001-0014 (one to three per day); P0-09 gateway-identity bootstrap detail; P0-10 framework + `mediamtx` version pin.
- **Days 6-8**: DPA template drafting (P0-03), bystander signage template (P0-12), site inventory, NPC registration check (M-05).
- **Days 9-10**: hardware procurement decisions (P0-13 mini-PC SKU; P0-14 camera spec doc); ADR 0012 + 0013; provider-DPA signing once templates are agreed.

### Phase 1 - Repo, IaC, and CI skeleton (2-4 days)

- Create monorepo: `/apps/web` (React + Vite frontend), `/apps/api` (FastAPI backend), `/apps/media-fallback` (DigitalOcean/equivalent UDP-capable LiveKit config), `/apps/cctv-edge` (`mediamtx` config + gateway agent), `/infra/terraform`, `/docs/{adrs,runbooks,privacy}`, `/scripts`.
- GitHub Actions: lint / typecheck / unit / integration / browser-bundle scan / SAST / SCA / container scan / secret scan / Docker-base pin check / Dependabot config.
- Base Dockerfile/runtime pinned to exact Python and Node.js patch versions where containerized; non-root UID where applicable; read-only FS where containerized; drop caps where containerized.
- Base Semgrep ruleset + custom rules (require-cf-jwt-verification, no-experimental-framework-apis-in-security-critical-paths, no-raw-sql, no-unsafe-template-rendering).
- **CI forbidden-term grep** (T-58) + smart whitelist for `/docs/` and Section 29 of plan.
- **Exit**: a placeholder page deploys through the pipeline to Railway staging behind Cloudflare Access; CF Access challenges it; all CI gates green.

### Phase 2 - Identity, session, authz (4-6 days)

- CF Access JWT verifier (aud+iss pinned, `CLOCK_SKEW_SECONDS = 30`, fail-closed JWKS cache).
- Railway-compatible origin-binding enforcement (Inv 14); T-56 harness.
- Trusted-header stripping/ignore policy (Section 11.6) for unverified requests.
- Signed cookie + session store + low-risk device fingerprint (Section 16.14).
- Policy module with deny-by-default; unit tests.
- Role/permission tables + seeds.
- **Exit**: T-1..T-4 + T-47 + T-48 + T-56 + T-57 pass in CI.

### Phase 2.5 - Architecture checkpoint (1 day)

- Review: does the same-domain React + Vite frontend + FastAPI backend split remain secure and worth the service-routing complexity?
- Validate: same-domain `/api/v1/*` routing, Cloudflare Access policy coverage, CSRF/cookie model, strict CSP feasibility, frontend bundle scan, and FastAPI fail-closed JWT verification.
- Output: ADR 0014 addendum if the routing/security model changes.
- **Exit**: same-domain split validation complete; any routing/security changes recorded.

### Phase 3 - Viewer flow + audit (4-6 days)

- Cameras registry + camera ACL.
- Viewer-subscribe token mint (`/api/v1/cameras/:id/view-token`) with replay protection, TTL <=60 s, ACL checks.
- Audit log with versioned HMAC chain + DB trigger; chain verifier endpoint.
- SSE `/api/v1/cameras/events` + polling fallback.
- **Exit**: T-5..T-14 + T-21 + T-32 + T-33 + T-49 + T-50 pass; p95 latency probe < 2 s on a synthetic-RTSP source.

### Phase 4 - Edge gateway + CCTV ingest (MVP-critical) (5-7 days)

- Dev/CI synthetic gateway host (FFmpeg synthetic-RTSP source per Section 13.7) **and** on-site mini-PC Ubuntu image (production; Section 13.8) with `mediamtx` pinned version.
- Gateway registry + `gateway_camera_assignments`.
- Gateway service-token bootstrap + one-time admin enrolment download (MVP).
- Gateway endpoints: `/ingest-token`, `/heartbeat`, `/cameras/:cameraId/status`.
- `mediamtx` configured with a real RTSP camera (production) + `synthetic_rtsp_test_source` (dev/CI).
- LiveKit webhook receiver `/api/v1/webhooks/livekit` (signed + 60-s replay window per H-08).
- Room-presence-driven gateway publish (A6'; Section 13.10 LiveKit Room Model).
- **Exit (revised, C-01)**: **synthetic-RTSP path runs end-to-end in CI** (RTSP -> dev/CI synthetic gateway -> LiveKit Cloud -> authenticated viewer with <2 s p95 latency); T-14 + T-43 + T-60 + T-61 + T-62 + T-55 + T-63 pass. **Production-camera path (real IP camera -> on-site mini-PC -> LiveKit Cloud)** is validated at the **first real-site cutover** rather than at MVP-exit - the on-site box is a procurement artefact, not a CI artefact.

### Phase 5 - Admin panel + user ops + DPA (4-5 days)

- Admin routes (CF Access App B); re-auth <=5 min.
- User CRUD, role assignment, camera ACL, gateway registration, gateway assignment.
- Disable user -> session revoke -> LiveKit participant removal <=10 s (F-003).
- Synchronous signed JSONL audit export.
- Privacy notice + acceptance flow; bystander signage attestation; DPA artefact bundle export.
- **Exit**: T-7..T-11 + T-23 + T-24 + T-28 + T-46 + T-54 pass.

### Phase 6 - Security hardening pass (3-5 days)

- Strict CSP + nonces; full header set; `Permissions-Policy: camera=()`.
- Rate limits (CF + app); 429 + `Retry-After`.
- CSRF double-submit on every state-changing route.
- ZAP baseline passes in CI.
- `/health` behind CF Access service token; T-51 integration test.
- PII scrub hook for Sentry + stdout logs (T-59).
- **Exit**: T-10..T-12 + T-15..T-19 + T-29 + T-51 + T-53 pass.

### Phase 7 - Media-plane fallback pre-build (2-3 days)

- Deploy self-hosted LiveKit fallback on selected UDP-capable host; only LiveKit media ports public; T-45.
- `POST /api/v1/admin/livekit/fallback` feature flag; CSP `connect-src` dynamic update.
- Feature-flag UI; rehearsed activation + deactivation.
- **Exit**: T-37 expanded + T-45 pass.

### Phase 8 - External exposure, origin-binding, pen-test-self-attack (2 days)

- Run T-30 checklist; close gaps (CF WAF rules, DNS hygiene, cert transparency).
- Run T-56 origin-binding tests; close gaps (Railway-origin rejection, trusted-header policy).
- Run full self pen-test checklist (Section 19).
- **Exit**: Section 19 at 100%.

### Phase 9 - SRE, observability, backup drill (2-3 days)

- Better Stack heartbeat, UptimeRobot probe to `/health` with service token, Sentry wired with PII scrub.
- Nightly backups + integrity check + `backup_runs`.
- Weekly restore drill.
- CF Access rollback + LiveKit quota fallback + break-glass + IdP outage runbooks exercised.
- **Exit**: T-20 + T-22 + T-38 + T-39 + T-41 + T-42 + T-52 pass.

### Phase 10 - Compliance, content, and demo (2-3 days)

- DPO contact; full PIA before pilot; NPC registration.
- Privacy page + security page + accessibility page.
- Runbooks polished.
- Demo script (CCTV-only) prepared.
- **Exit**: stakeholder sign-off.

### Phase 11 - Pilot onboarding (1 day)

- Upgrade Postgres to paid tier (ADR 0003).
- Migrate DNS/custom domain to production Cloudflare Access -> Railway path.
- Pen-test run (grey-box).
- Gateway mTLS activated before pilot using internal project CA unless Cloudflare mTLS is selected during implementation (ADR 0008).
- Pilot status page live.

### Phase 12 - ONVIF + optional multi-site (conditional)

- ONVIF hardware spike (Section 13.3).
- Multi-site extensions (new `sites` rows, per-site ACL, per-site signage attestation, per-site gateway).
- Alerting maturity.
- **Note**: the edge gateway itself is in Phase 4. Phase 12 is now only ONVIF-broadening and multi-site ops.

---

## 22. Task Backlog (representative)

- **Architecture**: write ADRs 0001 (Access gateway), 0002 (IdP - phishing-resistant MFA required for primary; CF OTP only as IdP-outage fallback per H-01), 0003 (Paid PG), 0004 (Monolith-vs-split), 0005 (LiveKit fallback), 0006 (Provider-exit criteria), **0007 (Framework + binary version pin policy - covers Python/FastAPI/Pydantic/SQLAlchemy, LiveKit client/server SDKs, and **`mediamtx`**, per H-06)**, **0008 (Edge gateway identity + mTLS CA)**, **0009 (CCTV-only invariant)**, **0010 (Origin-binding + trusted-header policy)**, **0011 (Bystander signage policy)**, **0012 (Camera Network Design - per-site VLAN topology, firewall rules; H-03)**, **0013 (Gateway hardware standard - NUC-class mini-PC, Ubuntu 22.04 LTS x86_64, single Docker image; C-01)**, **0014 (Railway + Python control plane)**.
- **Renovate / Dependabot** watcher for `bluenviron/mediamtx` GitHub releases (H-06).
- **Identity**: CF Access JWT verifier with `CLOCK_SKEW_SECONDS = 30`, JWKS cache fail-closed, Railway-compatible origin-binding, trusted-header stripping/ignore policy; break-glass (App C, 90-min); lost-MFA runbook.
- **Authz**: policy module with unit tests; admin re-auth <=5 min.
- **Schema**: users, roles, camera_acl, sites, **cameras with enum excluding forbidden values**, **edge_gateways**, **gateway_camera_assignments**, camera_events, sessions, **stream_grants with kind & CHECK**, **audit_log with hmac_key_version**, **audit_hmac_keys**, system_config, break_glass_usage, privacy_notice_acceptances, dpa_artifacts, **backup_runs**, webhook_replay_cache; append-only triggers; retention jobs; **DB least-privilege role (Inv 15)**.
- **API**: viewer view-token, gateway ingest-token, gateway heartbeat, gateway camera status, LiveKit webhook receiver, SSE camera events, admin CRUD, audit export, signage attestation, exposure-check / isolation-check / origin-binding-check endpoints.
- **Video**: LiveKit SDK integration, dynamic CSP connect-src, **60-s viewer token**, **60-s gateway token**, `iceTransportPolicy: 'relay'` on minted tokens, fallback switchover to DigitalOcean Singapore or equivalent UDP-capable APAC host; `mediamtx` config + `synthetic_rtsp_test_source`; RTSP reconnect watchdog on gateway.
- **Gateway lifecycle**: enrolment UI, one-time service-token download, credential rotation runbook, physical on-site NUC-class production gateway only for real cameras, mTLS cert issuance flow via internal project CA (pilot+), fingerprint pinning, expiry alerting.
- **Security**: strict CSP + nonces + `Permissions-Policy`, security headers, CSRF, **rate limits per Section 16.17**, **CORS per Section 16.13**, secrets store, ZAP in CI, **PII scrub in Sentry/logs**.
- **Audit**: triggers, HMAC chain with versioned keys, verifier endpoint, daily archive, rotation procedure, export API, chain-rotation continuity test (T-49).
- **Ops**: Terraform/config modules (Cloudflare + Railway app + DigitalOcean/equivalent media fallback + dev/CI synthetic gateway + Neon-first PG + LiveKit fallback); CI/CD; GitHub Actions scheduled backup + integrity + restore drill; runbooks Section 20.8-Section 20.16; email-first alerting with optional Telegram; observability secret inventory + rotation; T-30 + T-45 + T-56 schedulers.
- **Compliance**: PIA; ROPA; processor DPAs; DPO; retention; **cross-border transfer basis per processor**; **bystander signage policy + per-site attestation**; **no-recording-in-MVP policy doc**.
- **QA**: T-1..T-64 matrix in CI/CD as scoped.
- **Content**: /security, /privacy, /accessibility pages; demo script (CCTV-only); bystander signage template (EN + FIL); camera procurement spec (`/docs/procurement/camera-spec.md`, M-02).

---

## 23. Risk Register (top 18)

| # | Risk | L | I | Mitigation | Residual |
|---|---|---|---|---|---|
| 1 | Origin URL leak / control-plane exposure | L | H | CF Access + Inv 14 fail-closed Railway origin-binding + T-30 + T-56; drift detector | Low |
| 2 | Audit tamper / chain break across rotation | L | H | DB triggers + versioned HMAC + T-49 + 5-min verifier | Low |
| 3 | Backups unrestorable | M | H | Integrity check (T-22) + weekly drill + `backup_runs` (`restore_format_ok` + `restore_schema_ok`) | Low |
| 4 | Stream URL exfil by insider | M | M | 60-s tokens + kind-distinct scopes + jti replay (token-mint scope) + watermark (Section 16.19) + audit | Low-M |
| 5 | Phishing of an admin | L-M | H | Passkey MFA + WARP + admin re-auth + break-glass 90-min | Low |
| 6 | LiveKit quota hit mid-demo | M | M | A6' + alarms + pre-built fallback + T-37 expanded | Low |
| 7 | Self-hosted fallback fails at network layer | M | M | UDP-capable provider verification + TCP/TLS:443 + T-37 expanded + T-45 | Low |
| 8 | Railway app outage / platform incident | M | M | external probes + Railway health checks + redeploy/alternate-host DR path | Low-M |
| 9 | CF Access misconfig locks users out | L | H | IaC + drift detector + rollback runbook (Section 20.9) | Low |
| 10 | Neon free cold-start mid-demo | M | L | Keep-alive; paid tier before pilot | Low |
| 11 | LiveKit misconfig leaks host-candidate IPs | L | M | Server-enforced `iceTransportPolicy: 'relay'` (F-009) | Low |
| 12 | IdP outage prevents all login | L | H | CF one-time-PIN secondary (Section 20.11) | Low |
| 13 | **Gateway credential compromise / impersonation** | M | H | Service-token Argon2id hash + fingerprint pin (MVP); mTLS before pilot; rotation runbook; mint-rate + source-IP anomaly alerts (M-13) | Low |
| 14 | **Camera RTSP credential leaks to browser** | L | H | Gateway-only secret scope; T-62 bundle scan; app API response assertions | Low |
| 15 | **Break-glass window leaks past 90 min** | L | H | Request-time enforcement (F-006) + external monitor + T-52 | Low |
| 16 | **Primary IdP MFA not phishing-resistant (CF OTP)** | L | H | CF OTP dropped from primary IdP options (H-01); retained only as IdP-outage fallback; ADR 0002 enforces phishing-resistant primary | Low |
| 17 | **Stolen gateway token used to publish bogus video** | L | M | 60-s gateway-publish TTL bounds damage window; per-`gateway_id` mint-rate alert + source-IP-change alert (M-13); rotation runbook; CCTV-VLAN isolation prevents lateral movement | Low |
| 18 | **Hostile cert issued for app domain via different CA** | L | H | CT-log monitoring (Section 16.20, N-02) + CAA records pinned to expected issuers; alert + runbook on unexpected cert | Low |

---

## 24. Edge Cases & Failure Scenarios

- Clock skew on CF JWT -> tolerate up to `CLOCK_SKEW_SECONDS = 30`; reject beyond; T-47/T-48.
- JWKS refresh failure -> fail-closed with bounded staleness; alert.
- LiveKit outage -> activate fallback (Section 20.10); T-37 expanded.
- IdP outage -> CF one-time-PIN secondary (Section 20.11).
- Railway app health failure -> Railway health checks and external probes alert; rollback/redeploy or alternate-host DR path.
- Postgres outage -> read-only mode banner; backup job paused; alert.
- Sentry/Better Stack outage -> app continues; audit log authoritative.
- User disable mid-session -> revoke + **LiveKit participant removed <=10 s**.
- **Gateway disable mid-publish** -> **LiveKit publisher removed <=10 s**; camera shown offline.
- **Gateway heartbeat stale > 2 min** -> dashboard shows gateway offline; alert.
- **Camera rejoin after brief RTSP outage** -> mediamtx reconnects; gateway resumes publish; camera_events row.
- Admin disables self -> rejected with 409.
- Delete last SuperAdmin -> rejected with 409.
- Malformed tokens -> 401; no info leak.
- Stream URL leaked via screen-sharing -> 60-s TTL + watermark + audit.
- Break-glass opens and stays open past 90 min -> request-time denial; alert; post-mortem.
- **Self-hosted LiveKit fallback activates but UDP blocked on client network** -> TCP/TLS:443 fallback engages; T-37 expanded covers this.
- **mTLS cert expires during live session** -> grace period <=5 min while new cert deploys; alert at `cert_expires_at - 14 d`.
- **Webhook replay attack** -> HMAC + timestamp window + `webhook_replay_cache` -> rejected; audit.
- **Provider pricing/quota change blocks MVP** -> provider-exit playbook (Section 20.13) triggers ADR and migration.
- **Compromised monitoring credential (Telegram bot token leaked)** -> Section 20.16 leak-response runbook.
- **Floating Docker tag pulls new minor version with regressions** -> CI fails; Dependabot PR for pinned update.
- **Operator tries to use a browser camera to "just demo quickly"** -> there is no UI or API for this; CI grep + browser-bundle scan enforce it; Inv 5 is product-defining.

---

## 25. Execution (post-plan-approval)

Once this plan is approved, the following execution artefacts are produced **before any application code is written**. The repository is currently empty; these artefacts are the first commits of Phase 1.

### 25.1 Repo scaffold (illustrative; owned by the Software Architect)

```
/cctv/
  /apps/
    /web/                # React + Vite + Tailwind frontend
      /app/              # dashboard, admin, emergency, privacy routes
      /components/       # camera grid, video tiles, status panels, forms
      /lib/              # API client, LiveKit viewer helpers
      Dockerfile          # node:<exact patch>-<distro> where containerized
      railway.toml        # Railway frontend service config if used
    /api/                # FastAPI backend / security authority
      /app/
        /routes/          # viewer, admin, gateway, webhook, privacy, health API routes
        /services/        # authz, audit, jwt, csp, rate-limit, livekit, gateway auth
      /alembic/           # schema migrations
      Dockerfile          # python:<exact patch>-<distro> where containerized
      railway.toml        # Railway backend service config if used
    /media-fallback/      # DigitalOcean/equivalent UDP-capable LiveKit self-hosted config
      README.md           # UDP/media-port acceptance notes
    /cctv-edge/           # `mediamtx` container + gateway agent
      mediamtx.yml        # RTSP-first; synthetic_rtsp_test_source in dev (Section 13.7)
      gateway-agent/      # heartbeat + status + token refresh
      Dockerfile          # x86_64-only; single image (Section 13.8)
      deployment.md       # dev/CI synthetic only; production runs on on-site mini-PC
  /docker-compose.yml     # local-dev workflow (Section 25.4): web + api + Postgres + mediamtx + ffmpeg synthetic source + fake-CF-Access middleware
  /infra/
    /terraform/
      /cloudflare/        # Access apps A/B/C/D/E, DNS, WAF, rate-limit
      /railway-app/
      /media-fallback/
      /dev-ci-gateway/
      /postgres/
      /livekit/
  /docs/
    /adrs/                # 0001..0011 (see Section 22)
    /runbooks/            # deploy, rollback, CF rollback, LiveKit fallback, IdP outage,
                          # break-glass, lost-MFA, provider-exit, gateway-lifecycle,
                          # gateway-cert-rotation, telegram-rotation
    /privacy/
      pia-lightweight.md
      ropa.md
      bystander-signage-template.md    # EN + FIL
      cross-border-transfer-basis.md
    /security/
      threat-model.md
      csp-policy.md
      pen-test-readiness.md
  /scripts/
    exposure-check.sh      # T-30
    media-isolation-check.sh # T-45
    origin-binding-check.sh  # T-56
    browser-bundle-scan.sh   # T-58 + T-59 + T-62
    db-privilege-introspect.sh # T-57
  /.github/workflows/
    ci.yml                 # pipeline per Section 20.2
    dependabot.yml
  /README.md
  /CHANGELOG.md
```

### 25.2 Security artefacts first

Order of first commits:
1. `.github/workflows/ci.yml` + Dependabot + Semgrep/osv/Trivy/gitleaks gates + Docker-base pin check + `browser-bundle-scan.sh`.
2. `/docs/adrs/0001..0011` (stubs, full content before Phase 3).
3. `/docs/security/threat-model.md`.
4. `Dockerfile` or Railway runtime config with pinned Python base/runtime.
5. `/infra/terraform/` skeleton - apply to `staging` first with only the placeholder page.
6. CF Access policies A/B/C/D/E + service-token policies.
7. `/scripts/exposure-check.sh` + `/scripts/origin-binding-check.sh` + `/scripts/media-isolation-check.sh` + scheduled post-deploy runs.
8. Application code begins with identity verification (`app/security/cf_access.py` + origin-binding/trusted-header middleware) as the very first module.

### 25.3 Demo plan (Phase 10)

- One RTSP camera (real or synthetic) published via `cctv-edge`.
- Two authorized viewers (distinct CF Access identities).
- One unauthorized visitor (laptop not on CF Access).
- One admin walkthrough: register a gateway, register a camera, grant ACL, view audit, export JSONL, trigger a T-30 run.
- One fallback rehearsal: flip LiveKit feature flag live; viewers + gateway reconnect <=60 s.
- One break-glass rehearsal: open window, demonstrate 90-min enforcement (pre-scripted clock advance).
- **The demo does not and cannot involve a browser publishing camera; there is no UI for it.**

### 25.4 Local-development workflow (N-04)

**Goal**: a developer can clone the repo, run a single command, and have a working stack on their laptop - without exposing any production credential, without bypassing CF Access verification logic, and without a real camera.

**Stack** (defined in `/docker-compose.yml`):

- **`cctv-api`** - FastAPI dev server, hot-reload, talks to local Postgres.
- **Postgres 16** (containerized, ephemeral volume).
- **`mediamtx`** + **FFmpeg synthetic-RTSP sidecar** producing `rtsp://mediamtx:8554/synthetic_cam_01` (Section 13.7).
- **LiveKit** (optional): either a containerized local LiveKit dev image **or** a LiveKit Cloud dev project (configured via env). MVP recommends LiveKit Cloud dev tier to keep parity with prod.
- **Fake-CF-Access middleware** - a thin dev-only middleware that injects a `cf-access-jwt-assertion` header signed with a **dev-only key** loaded into the app, so the app's normal JWT verifier path runs against a JWT signed by a key it trusts in dev.

**Hard gating on the fake middleware** (no chance of accidentally shipping it):

- Loaded **only when `APP_ENV === 'development'` AND `ALLOW_DEV_AUTH === '1'`**. Both must be true; production sets neither.
- Build-time CI check: production bundles must not contain the dev-key file or the fake middleware code path (Semgrep rule + browser-bundle scanner).
- The dev key is generated locally on first dev bootstrap; gitignored; never committed.
- Audit row written every time the fake middleware activates (only ever in dev).
- **The CF JWT verifier itself is not bypassed** - the dev middleware injects a properly-signed JWT with a dev `iss` and dev `aud`; the verifier validates it against the dev signing key. This means the dev environment exercises the same code path as production, just with a different key set. This is the deliberate design (a verifier that is bypassed in dev does not catch real bugs).

**Developer commands**:

```bash
uv sync --locked                              # or poetry install --sync
cp .env.example .env.development             # populates ALLOW_DEV_AUTH=1, dev key paths, etc.
docker-compose up -d                         # postgres + mediamtx + ffmpeg synthetic
alembic upgrade head                         # database migrations
python scripts/seed_dev.py                   # dev users (alice@dev, bob@dev), one synthetic camera
uvicorn app.main:app --reload                # FastAPI dev server
```

Result: developer logs in as `alice@dev` (the fake middleware injects the dev JWT), sees one camera (`synthetic_cam_01`), can subscribe and watch the colour-bar test pattern. End-to-end with no production credentials, no real camera, no real CF account.

**What is NOT in the local dev stack**: real CF Access (the dev middleware substitutes for it), real LiveKit Cloud production project (a separate dev project is recommended), real cameras, real R2 backups, Sentry / Better Stack / Telegram (no-ops in dev).

---

## 26. Validation (self-review of v4)

Against the v3 deficiencies and the user's directive:

| Directive item | v3 status | v4 status | Where |
|---|---|---|---|
| Remove webcam/browser-publish from product | Still referenced as "temporary" | **Removed; Not Supported forever** | Inv 5, Section 5.12, Section 13.5 hard rule 12, Section 15.2, Section 29 |
| Edge gateway in MVP | Phase 12 future | **MVP-critical (Phase 4)** | Inv 6, A27, Section 9, Section 13.3, Section 21 Phase 4 |
| `hmac_key_version` + rotation continuity | Missing | **Added; T-49** | Section 14.1, Section 14.3, Section 17.2, Section 18.2 T-49 |
| `CLOCK_SKEW_SECONDS = 30` as named constant | Env-configurable | **Named constant** | Section 0, Section 11.4, Section 18.2 T-47 + T-48 |
| `BREAK_GLASS_WINDOW_MINUTES = 90` request-time | 4h, scheduler-dependent | **90 min, request-time + external monitor** | Section 16.6, T-52 |
| `stream_grants` two kinds + cleanup + alarms | Single kind | **Viewer-subscribe + gateway-publish; cleanup; alarms** | Section 14.1, Section 14.2, Section 14.3, T-50 |
| `edge_gateways` table with mTLS fingerprint reserved | Absent | **Added; nullable in MVP** | Section 14.1, ADR 0008 |
| `gateway_camera_assignments` authz scope | Absent | **Added** | Section 14.1, Section 16.3, T-61 |
| LiveKit webhook auth + replay | Unsecured receiver | **HMAC + timestamp + replay cache** | Section 13.5 hard rule 13, Section 14.1 `webhook_replay_cache` |
| Rate-limit table | Partial | **Full table** | Section 16.17, T-53 |
| CORS policy (no wildcard) | Partial | **Explicit; gateway APIs not browser-callable** | Section 16.13, T-54 |
| Device fingerprint policy | Undefined (F-007) | **UA + Accept-Language only; mismatch -> re-auth** | Section 16.14 |
| PII scrub in Sentry/logs | Undefined | **Sentry `beforeSend`; stdout same rules** | Section 16.15 |
| Permissions-Policy camera=() | Implicit | **Explicit site-wide** | Section 16.5 |
| Health endpoint behind service token | Public | **CF Access service token App D; `{"status":"ok"}` exactly** | Section 15.1, T-51 |
| Deep health admin-only | Absent | **`/api/v1/admin/health/deep`** | Section 15.1 |
| Origin-binding (F-001) | Missing | **Inv 14; T-56** | Section 11.4, Section 11.6, Section 16.10 |
| Trusted-header policy (F-002) | Missing | **Identity only from verified CF Access JWT; trusted headers ignored on unverified requests** | Section 11.6 |
| User-disable -> LiveKit kill <=10 s (F-003) | Missing | **Hard rule 11; integration test** | Section 13.5, Section 10.3 |
| Bystander signage (F-004) | Missing | **Section 16.12 + `dpa_artifacts` + attestation endpoint** | Section 16.12 |
| Audit rotation (F-005) | Single key | **Versioned; T-49** | Section 14.1 `audit_hmac_keys`, Section 17.2 |
| Break-glass (F-006) | 4h, scheduler | **90 min, request-time** | Section 16.6 |
| CSP wildcard livekit.cloud (F-008) | Wildcard | **Pinned regional hosts** | Section 16.5, Section 13.5 hard rule 14 |
| `iceTransportPolicy: 'relay'` (F-009) | Client-hinted | **Server-enforced on minted tokens** | Section 13.5 hard rule 10 |
| DB least-priv (F-010) | Partial | **Inv 15; T-57** | Section 14.3 |
| DR RPO/RTO (F-011) | Unstated | **MVP <=24h/<=4h, pilot <=1h/<=1h; restore-drill integration query** | Section 10.4, Section 20.7, T-22 |
| LiveKit webhook auth (F-012) | Unauthenticated | **HMAC + timestamp** | Section 13.5 hard rule 13 |
| Docker base/runtime pinned + Dependabot | Drifted floating tag | **Exact Python patch where containerized; CI fails on floating tag; Dependabot** | Section 12, Section 20.2 |
| `webauthn_metadata` mirror | Present | **Removed from MVP** | Section 5.11, Section 6, Section 14 (absent) |
| `export_jobs` async queue | Present | **Removed from MVP; sync signed JSONL** | Section 5.4, Section 6, Section 15.1 |
| Backup integrity verification | Implicit | **`backup_runs` + `pg_restore --list`** | Section 14.1, Section 20.7 |
| Telegram secret rotation | Missing | **Section 20.16 inventory + rotation + leak-response** | Section 20.16 |
| T-47..T-55 tests per user Section 25 | Absent | **Present at exact IDs** | Section 18.2 |
| CCTV-only enforcement tests | Absent | **T-58, T-59, T-60, T-61, T-62** | Section 18.2 |
| No browser-publisher routes anywhere | Still present | **Removed from Section 15; Section 29 appendix** | Section 15.2, Section 29 |
| UI reflects CCTV-only | Partial | **Admin cameras/gateways pages; viewer has no publish UI** | Section 15.1, Section 25.1 |
| ADRs 0008..0011 | Absent | **Added to Section 22 backlog** | Section 22, Section 21 Phase 0/1 |

No unresolved conflicts detected between the user's 29-section directive and this v4.

---

## 27. Acceptance Criteria

The v4 plan is accepted when every item below is present in the plan text **and** verifiable by inspection. This table is the authoritative hand-off checklist.

| # | Criterion | Where proved |
|---|---|---|
| 1 | No `/publish`, `/demo-publisher`, `/lab-publisher`, `/webcam`, `/phone-publisher` routes in MVP, pilot, or prod | Section 15.2; Section 29; Inv 5 |
| 2 | No `navigator.mediaDevices`, `getUserMedia`, `MediaRecorder`, browser camera permission flow | Inv 5; Section 5.2 `Permissions-Policy: camera=()`; Section 13.5 rule 12; Section 29; T-58; T-59 |
| 3 | Camera ingest via edge gateway authenticated with service token (MVP) / mTLS (pilot+) | Section 11.5; Section 14.1 `edge_gateways`; Section 15.1 `/api/v1/gateways/*`; T-61 |
| 4 | `cctv-api` does not hold camera credentials | A29; Section 13.3; Section 13.5 rule 5; T-62 |
| 5 | `/health` behind CF Access service token; body is `{"status":"ok"}` | Section 11.3 App D; Section 15.1; T-51 |
| 6 | Plan / docs / CI enforce CCTV-only posture | Section 24 forbidden-term grep; Section 16.5 `Permissions-Policy`; Section 25.1 `browser-bundle-scan.sh`; T-58 |
| 7 | Browser-bundle scan of built assets | Section 18.2 T-59; Section 20.2; T-62 |
| 8 | Versioned HMAC + `hmac_key_version` column + rotation procedure | Section 14.1 `audit_log`/`audit_hmac_keys`; Section 17.2; T-49 |
| 9 | `CLOCK_SKEW_SECONDS = 30` named constant | Section 0; Section 11.4; T-47; T-48 |
| 10 | `BREAK_GLASS_WINDOW_MINUTES = 90` + request-time enforcement + external monitor | Section 16.6; T-52 |
| 11 | `stream_grants` with `kind`, composite `(jti, expires_at)` index, cleanup, alarm | Section 14.1; Section 14.2; Section 14.3; T-50 |
| 12 | `edge_gateways.mtls_fingerprint` reserved; MVP ships without it | Section 14.1; Section 11.5 |
| 13 | `audit_log` retention segmented across rotation boundary | Section 14.3; Section 17.2 |
| 14 | Signed LiveKit webhook + replay cache | Section 13.5 rule 13; Section 14.1 `webhook_replay_cache`; Section 15.1 |
| 15 | Rate-limit table for all token-mint and gateway endpoints | Section 16.17; T-53 |
| 16 | CORS policy (no wildcard on authed APIs; gateway APIs not browser-callable) | Section 16.13; T-54 |
| 17 | Device-fingerprint policy documented (UA + Accept-Language only) | Section 16.14 |
| 18 | PII scrub in Sentry + stdout logs | Section 16.15 |
| 19 | `webauthn_metadata` and async `export_jobs` removed from MVP | Section 5.11; Section 6; Section 14 (absent) |
| 20 | ADR 0008 (gateway identity + mTLS), 0009 (CCTV-only), 0010 (origin-binding), 0011 (bystander signage) | Section 22; Section 21 P0-09 + P0-12 |
| 21 | Test matrix covers T-47..T-55 at those IDs | Section 18.2 |
| 22 | Gateway lifecycle runbook, gateway cert rotation runbook, Telegram rotation runbook | Section 20.14, Section 20.15, Section 20.16 |
| 23 | UI reflects CCTV-only: admin pages for cameras/gateways; viewer has no publisher UI | Section 15.1; Section 25.1 |
| 24 | Bystander signage policy + per-site attestation | Section 16.12; Section 14.1 `dpa_artifacts`; Section 15.1 signage-attest endpoint |
| 25 | Cross-border transfer basis per processor | Section 16.11; Section 14.1 `dpa_artifacts` |
| 26 | DR RPO <=24h MVP / <=1h pilot; RTO <=4h MVP / <=1h pilot; post-restore integration query | Section 10.4; Section 20.7; T-22 |
| 27 | Python Docker base/runtime pinned to exact patch where containerized; CI fails on floating tag | Section 12 row "Container"; Section 20.2 |
| 28 | Dependabot (or equivalent) enabled | Section 12 row "Container" / "Monitoring"; Section 20.2 |
| 29 | Demo script is CCTV-only (no browser-publisher steps anywhere) | Section 25.3; Section 21 Phase 10 |
| 30 | **Audit export bundle includes raw HMAC chain + `audit_hmac_keys` snapshot for independent verification** | Section 15.1; Section 17.2 trust-model subsection |
| 31 | **Production gateway is on-site NUC-class mini-PC; dev/CI gateway is synthetic only** | Section 12 stack table; Section 13.8; ADR 0013; Section 21 P0-13; Section 21 Phase 4 exit |
| 32 | **`synthetic_rtsp_test_source` has a defined FFmpeg implementation** | Section 13.7 |
| 33 | **`mediamtx` exact version pinned in ADR 0007 with Renovate watcher for `bluenviron/mediamtx`** | Section 22; Section 12 stack table |
| 34 | **LiveKit webhook timestamp window = 60 seconds; T-63 verifies stale-timestamp rejection** | Section 13.5 rule 13; Section 15.1; T-63 |
| 35 | **On-site gateway secret store specified** (`/etc/cctv-gateway/gateway.env` 0600 + systemd EnvironmentFile) | Section 11.5; Section 20.14 rotation steps |
| 36 | **Trusted-header allow-list documented; T-64 verifies forged-header rejection** | Section 11.6; T-64 |
| 37 | **SBOM (Syft / CycloneDX) generated in CI, sigstore-signed, attached to GitHub releases** | Section 20.2 |
| 38 | **CT-log monitoring active for app domain; CAA records pinned** | Section 16.20; Section 20.6 |

**v4.1 additional acceptance** (closed in this revision):

- 30: **C-04** closed (audit export trust model).
- 31: **C-01** closed (gateway location - production hardware locked).
- 32: **C-02** closed (synthetic RTSP defined).
- 33: **H-06** closed (mediamtx pin).
- 34: **H-08** closed (webhook window).
- 35: **H-02** closed (on-site secret store).
- 36: **N-03** closed (trusted-header policy).
- 37: **N-01** closed (SBOM).
- 38: **N-02** closed (CT-log monitoring).
- All other v4.1 findings (H-01, H-03, H-04, H-05, H-07, H-09, M-01..M-14) are tracked under criteria 1-29 plus the Section 0.1 revision history table for traceability.

---

## 28. Final Deliverables Summary

What this v4 hand-off contains and what the next phase will produce.

**Delivered now (planning):**

- This v4 plan file (`secure-cctv-monitoring-system-v4-ef15d0.md`) - 29 sections + Section 29 appendix + Section 0.1 revision history (v4.1); CCTV-only posture; diagnosis Critical/High fixes applied; **v4.1 in-place revision closing C-01..C-04 (C-03 reviewed, no change), H-01..H-09, M-01..M-14, N-01..N-04**; acceptance criteria table 1..38 (Section 27); risk register 1..18 (Section 23).
- SUPERSEDED banner on `secure-cctv-monitoring-system-v3-801515.md` (history preserved, path redirected).
- Work-plan file (`cctv-v4-rewrite-workplan-ef15d0.md`) - preserved for audit trail.
- v4.1 revision-plan and apply-execution-plan files in `/.windsurf/plans/` for audit trail.
- **Repository status**: `c:\Users\Ivan\Downloads\cctv-second-try` is empty; implementation has not started. Nothing in this hand-off changes repository files outside the `/.windsurf/plans/` folder.

**Not delivered (requires future execution phases):**

- Application code - begins in Phase 1 after ADRs land.
- ADR 0001..0011 full content - stubs in Phase 0, full text by Phase 3.
- Runbooks Section 20.8-Section 20.16 full content - stubbed Phase 1, finalized per phase.
- Terraform modules.
- CI workflow files.
- Test implementations (T-1..T-62) - implemented across Phases 2-9.
- Dockerfile.
- PIA / ROPA / processor-DPA documents - drafted during Phase 10.
- Bystander signage physical posting - operations activity, attested via API endpoint in Phase 5.

**Expected final-handoff artefacts at the end of implementation (Phase 10 exit)**, per your Section 28 directive:

1. Summary of changed files (this list grows once implementation begins).
2. Removed features/routes (Section 15.2; Section 29).
3. Added CCTV requirements (Section 5.3; Section 9; Section 13.3).
4. Diagnosis fixes mapped (Section 26 table; F-001..F-012).
5. Schema delta (Section 14).
6. Removed routes (Section 15.2).
7. Added routes (Section 15.1).
8. Added tests (Section 18.2 T-47..T-64).
9. Added CI checks (Section 20.2; Section 24 if code phase).
10. Any remaining CI/test commands required (none for this plan-only hand-off).
11. Any residual webcam mentions -> expected **only** in Section 29 (verified by Section 29 self-check grep below).
12. Remaining risks / TODOs (Section 23).
13. **Repository status**: "plan-correct only; implementation has not started."

---

## 29. Not Supported / Removed Scope (appendix)

> This appendix is the **only** place in the v4 plan where forbidden camera-publishing terms may appear. CI allowlists this section by path + by the marker comment below so the forbidden-term scan (T-58) can pass while this appendix documents what has been permanently cut.

<!-- cctv-allow-forbidden-terms: BEGIN (Section 29 Not Supported) -->

### 29.1 Permanently removed camera sources (Inv 5)

The following camera sources are **not** part of the product, today or in any future phase, unless an ADR overturns Invariant 5 and re-architects the product:

- **webcam** (laptop / desktop built-in camera)
- **phone camera** (browser-accessed mobile camera via `getUserMedia`)
- **laptop camera**
- **browser camera** (any camera reachable through browser device APIs)
- **user device camera** (any client-side capture surface)

`cameras.source_type` does not accept values representing these sources; a CHECK constraint enforces it (Section 14.4). CI grep (Section 24) blocks any code path that implies these sources.

### 29.2 Permanently removed publishing paths

- **browser publisher** - any UI or API that uploads media from a browser as a camera feed.
- **phone publisher** - mobile-browser version of the same.
- **demo publisher** - a "for the demo only" browser publisher.
- **lab publisher** - an "internal testing" browser publisher.
- **temporary publisher** - a "we'll remove it before pilot" publisher.
- **compatibility publisher** - a "for browsers that don't have the SDK" publisher.

Every phrase above, including "temporary" and "compatibility" framings, is rejected. The only publisher is the edge gateway (`mediamtx`).

### 29.3 Permanently removed browser APIs / code paths

- `navigator.mediaDevices`
- `getUserMedia`
- `MediaRecorder`
- browser camera-permission request
- browser screen-capture (`getDisplayMedia`) as a camera source

`Permissions-Policy: camera=(), microphone=(), display-capture=()` is set site-wide (Section 16.5) as defence in depth.

### 29.4 Permanently removed routes

- `/publish`
- `/publish/:cameraId`
- `/demo-publisher`
- `/lab-publisher`
- `/webcam`
- `/phone-publisher`
- `POST /api/v1/publish/:cameraId/token`

No handler exists for any of the above. Returning any response (including 404) is a CI failure if the path matches an active route table.

### 29.5 Permanently removed DB enum values

- `cameras.source_type = 'phone'`
- `cameras.source_type = 'webcam'`
- `cameras.source_type = 'browser'`
- `cameras.source_type = 'browser_publisher'`
- `cameras.source_type = 'user_device'`
- `cameras.source_type = 'mobile_camera'`

`camera_source_type` ENUM excludes all of the above; a migration that adds any requires an ADR overturning Inv 5.

### 29.6 Permanently removed marketing / framing

The plan rejects **any** wording that frames these items as temporary, experimental, demo, internal, lab, or compatibility paths. Such framing was a v3 defect; its removal is non-negotiable.

### 29.7 Recording / playback / snapshots / media-recorder - MVP posture

Recording, playback, snapshots, and any use of `MediaRecorder` are excluded from MVP (Inv 9). Snapshots and recording remain **F (full-prod, ADR-gated)** features subject to DPA re-scope and bystander notice update if ever added.

<!-- cctv-allow-forbidden-terms: END (Section 29 Not Supported) -->

---

*End of v4 plan.*


