# ADR 0009 — CCTV-Only Ingest Invariant

- **Status**: Accepted
- **Date**: 2026-05-07
- **Decision-makers**: Software Architect, System Owner, Product Manager
- **Supersedes**: v3 plan Inv 5 (which described browser publishing as "temporary")
- **Plan references**: Invariant 5; §5.12; §13.1; §13.5 hard rules 1–6, 12; §14.4; §15.2; §18.2 T-58..T-62; §24; §29

## Context

The v3 plan included a browser-based camera publisher (`getUserMedia` → LiveKit publish) as a "temporary" or "demo-only" path. The v4 review identified this as a **category error**: a browser publisher is not a temporary convenience — it is a fundamentally different product with a fundamentally different threat model.

A browser publisher means:

- **Camera-permission prompts in the browser** — users can accidentally grant camera access; malware can abuse it; privacy regulators (under RA 10173 / GDPR) treat a system that *can* capture from user devices differently from one that only views fixed CCTV feeds.
- **`getUserMedia` / `MediaRecorder` in the client bundle** — these APIs are attack-surface for client-side exploits and leak the system's capabilities to any attacker who inspects the JavaScript bundle.
- **Browser as publisher** — the browser holds a publisher-role LiveKit token, meaning a compromised browser session can inject video into the system (spoofing a camera feed).
- **Blurred product identity** — "CCTV monitoring" becomes "video conferencing with extra steps"; the security posture, compliance stance, and user expectations all shift.

The system is a **fixed-camera, IP-camera-sourced, live-view CCTV monitoring application**. Every camera feed originates from an IP camera or NVR, ingested via an edge gateway running `mediamtx`. Browsers are viewers only.

## Decision

**The system does not support webcam, phone-camera, laptop-camera, or browser-based publishing of any kind. This is a permanent product constraint, not a temporary limitation. Any feature, demo, lab, internal, fallback, compatibility, or test path that violates this invariant is rejected at design time, at code review, at CI, and at runtime.**

### What is forbidden

1. **Camera sources**: webcam, phone camera, laptop camera, browser camera, user-device camera.
2. **Publishing paths**: browser publisher, phone publisher, demo publisher, lab publisher, temporary publisher, compatibility publisher.
3. **Browser APIs**: `navigator.mediaDevices`, `getUserMedia`, `MediaRecorder`, browser camera-permission requests, `getDisplayMedia` as a camera source.
4. **Routes**: `/publish`, `/publish/:cameraId`, `/demo-publisher`, `/lab-publisher`, `/webcam`, `/phone-publisher`, `POST /api/v1/publish/:cameraId/token`.
5. **DB enum values**: `cameras.source_type` does not accept `'phone'`, `'webcam'`, `'browser'`, `'browser_publisher'`, `'user_device'`, `'mobile_camera'`. A CHECK constraint enforces this.
6. **Framing**: any wording that describes these items as "temporary", "experimental", "internal", "for demo only", or "for compatibility" is itself a violation.

### What is permitted

- `cameras.source_type` accepts only: `'rtsp'`, `'nvr_rtsp'`, `'onvif_profile_s'`, `'onvif_profile_t'`, `'synthetic_rtsp_test_source'`.
- The sole publisher is the edge gateway (`mediamtx`).
- Browsers receive **subscriber-only** LiveKit tokens (≤60 s, bound to `user_id` + `session_id` + `camera_id`).
- A browser session can **never** receive a gateway-publish token (T-60 verifies).
- `Permissions-Policy: camera=(), microphone=(), display-capture=()` is set site-wide as defence in depth.

### Enforcement layers

| Layer | Mechanism | Test |
|---|---|---|
| **Design** | This ADR; Invariant 5 in the plan | Review |
| **Schema** | `camera_source_type` ENUM excludes forbidden values; CHECK constraint | Migration |
| **API** | Token-mint authorization: browser calling gateway-ingest → 403 + audit | T-60 |
| **CI (source)** | Forbidden-term grep: `getUserMedia`, `MediaRecorder`, `/publish`, `/demo-publisher`, etc. | T-58 |
| **CI (bundle)** | Browser-bundle scan: built `.js`/`.mjs`/`.css` scanned for forbidden APIs, RTSP URLs, cred env-var names | T-59 |
| **CI (API response)** | API responses for `/api/v1/cameras*` contain no credential fields | T-62 |
| **Runtime** | `Permissions-Policy: camera=()` header on every response | §16.5 |
| **Code review** | Any PR introducing a forbidden term requires an ADR overturning this one | Process |

### Overturning this ADR

Overturning Invariant 5 requires:

1. A new ADR authored by the System Owner with explicit justification.
2. Threat-model re-review addressing all the risks listed in §Context above.
3. Privacy-impact re-assessment under RA 10173 (browser camera capture changes the processing scope).
4. Update to the PIA, bystander signage, and DPA artefact bundle.
5. Removal of CI enforcement (T-58, T-59) and `Permissions-Policy` header — deliberate, audited, PR-reviewed.
6. Update to this ADR's status to "Superseded by ADR NNNN".

The barrier is intentionally high. The system's identity as a CCTV monitoring platform depends on this constraint.

## Consequences

### Positive

- **Reduced attack surface**: no `getUserMedia` in the bundle means no camera-permission exploits, no media-injection from compromised browsers.
- **Clear product identity**: stakeholders, auditors, and regulators see a CCTV system, not a video-conferencing platform.
- **Simplified token model**: only two token kinds (viewer-subscribe, gateway-publish), clearly separated. A browser can never hold a publisher token.
- **Privacy clarity**: the system processes fixed-camera CCTV feeds only; bystander signage, PIA, and DPA scope are well-defined.
- **CI-enforceable**: the constraint is machine-verifiable, not just a policy document.

### Negative

- **No browser-based demo path**: demonstrating the system requires an edge gateway (real or synthetic RTSP). The `synthetic_rtsp_test_source` (§13.7) mitigates this for dev/CI.
- **No "quick test" from a laptop camera**: developers must use the synthetic RTSP source or a real IP camera.
- **Higher MVP hardware dependency**: at least one gateway (dev/CI synthetic source or on-site mini-PC) is required for any end-to-end test.

### Risks accepted

- A stakeholder may request a browser demo path in the future. This ADR explicitly rejects that request unless the full overturn procedure is followed. The synthetic RTSP source provides a functionally equivalent demo without violating the invariant.

## Alternatives considered

### A. Allow browser publishing as a "temporary demo path"

- **Rejected**: this was the v3 approach. "Temporary" features become permanent. The browser publisher introduces a categorically different threat model and compliance posture. Removing it later is harder than never adding it.

### B. Allow browser publishing behind a feature flag (off by default)

- **Rejected**: the code would still exist in the bundle, the APIs would still be importable, and the flag could be flipped. The invariant must be enforced at the code-absence level, not the configuration level.

### C. Allow browser publishing only in development environments

- **Rejected**: dev environments share the same codebase. If `getUserMedia` is in the source, it can leak to production via a missed flag, a build misconfiguration, or a rushed PR. CI enforcement (T-58, T-59) catches this, but only if the code is truly absent, not conditionally compiled.

## Verification

- **T-58**: CI forbidden-term grep passes (no forbidden terms in active code).
- **T-59**: browser-bundle scan passes (no forbidden APIs/URLs/cred-env-names in built assets).
- **T-60**: browser calling gateway-ingest endpoint → 403 + audit row.
- **T-62**: API responses for camera endpoints contain no credential fields.
- **§14.4**: `camera_source_type` ENUM migration excludes forbidden values.
- **§16.5**: `Permissions-Policy: camera=()` header verified on every response.

## References

- v4 plan Invariant 5 (§ Non-Negotiable Invariants)
- v4 plan §5.12 (Explicitly out of scope — N tier)
- v4 plan §13.1 (Protocol / topology comparison — browser publisher row)
- v4 plan §13.5 hard rules 1–6, 12
- v4 plan §14.4 (Source-type enforcement)
- v4 plan §15.2 (Removed routes)
- v4 plan §18.2 T-58, T-59, T-60, T-62
- v4 plan §29 (Not Supported / Removed Scope appendix)
