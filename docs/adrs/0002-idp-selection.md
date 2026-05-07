# ADR 0002 — Primary Identity Provider Selection

- **Status**: Accepted
- **Date**: 2026-05-07
- **Decision-makers**: System Owner, Software Architect
- **Decision**: Google Workspace as primary IdP
- **Supersedes**: None
- **Plan references**: §11.1–§11.4; §16.2; §16.7; §20.11; Invariant 11

## Context

The system does not implement passwords. All user authentication is delegated to Cloudflare Access, which federates to an external identity provider (IdP). The application trusts only Cloudflare Access JWTs after validating `iss`, `aud`, `exp`, `nbf`, signature, and origin-binding.

The primary IdP must support phishing-resistant MFA because the system protects live CCTV feeds, admin controls, audit export, gateway lifecycle actions, and privacy artefacts. Email-OTP-only providers are not eligible as primary IdP.

The available options considered were:

| Option | Cost posture | MFA posture | Fit |
|---|---|---|---|
| Google Workspace | Existing school account available | WebAuthn/passkeys, hardware keys, push | Strong school/operator fit |
| Microsoft Entra ID | Free tier available | WebAuthn/hardware keys/Auth app | Strong if M365 already exists |
| GitHub | Free for basic identity | WebAuthn/TOTP | Good for developers, weaker for school users |
| Okta | Paid | WebAuthn/FIDO2/push | Strong but costly |
| Cloudflare One-Time PIN | Included/free | Email OTP only | Fallback only, not primary |

The system owner confirmed that a school Google Workspace account already exists, making Google Workspace the lowest-friction and likely lowest-incremental-cost option for real operator users.

## Decision

**Use Google Workspace as the primary IdP for Cloudflare Access.**

Cloudflare Access remains the identity-aware proxy and access gateway for the control plane. Google Workspace is the upstream identity provider used by Cloudflare Access to authenticate users and enforce MFA.

Cloudflare One-Time PIN is retained only as a constrained IdP-outage fallback per §20.11, not as the primary IdP.

## Required configuration

### Google Workspace

- Enforce MFA for all CCTV system users.
- Prefer phishing-resistant MFA: passkeys/WebAuthn or hardware security keys.
- SMS MFA is prohibited for CCTV system access.
- Create Google groups or organizational units to map access policy:
  - `cctv-users`
  - `cctv-admins`
  - `cctv-superadmins` if needed for high-risk operations
- Use dedicated project/admin accounts where possible, not personal unmanaged accounts.
- Maintain account recovery procedures through the school's Google Workspace admin process.

### Cloudflare Access

- Configure Google Workspace as the IdP.
- App A: `/dashboard`, `/api/v1/{me,cameras/*,sessions/*}` → `cctv-users` + MFA.
- App B: `/admin`, `/api/v1/admin/*` → `cctv-admins` + re-auth requirements and WARP posture where available.
- App C: `/admin-emergency` → break-glass identity only + hardware key.
- App D: `/health` → external monitor service-token policy.
- App E: `/api/v1/gateways/*` → gateway service-token policy for MVP, mTLS pilot+.

### Application

- Validate `Cf-Access-Jwt-Assertion` on every protected route.
- Pin `iss` to the Cloudflare team domain.
- Pin `aud` to the relevant Cloudflare Access application AUD tag.
- Validate `exp` and `nbf` using `CLOCK_SKEW_SECONDS = 30`.
- Fail closed if JWKS refresh exceeds the bounded staleness window.
- Treat Google identity attributes as input to Cloudflare Access only; app authorization still uses local RBAC and camera ACLs.

## Consequences

### Positive

- **Low incremental cost**: the school already has Google Workspace, avoiding paid new IdP seats for MVP.
- **Strong user fit**: school operators are more likely to have Google Workspace accounts than GitHub accounts.
- **Phishing-resistant MFA support**: Google Workspace supports passkeys/WebAuthn and hardware security keys.
- **Good Cloudflare Access integration**: Google Workspace is a standard Cloudflare Access IdP.
- **Cleaner audit identities**: audit actors can map to school-managed email identities.

### Negative

- **Google becomes a processor**: Google Workspace must be included in the DPA/vendor register and cross-border transfer assessment.
- **School admin dependency**: user lifecycle and MFA enforcement depend on Google Workspace admin configuration.
- **Seat/licensing constraints**: if future non-school users need access, seats or external identity handling may require review.

### Risks accepted

- If the school's Google Workspace configuration allows weak MFA or unmanaged recovery flows, the CCTV system inherits that weakness. This is mitigated by explicitly requiring passkeys/WebAuthn or hardware keys for CCTV users and by retaining Cloudflare Access policy enforcement.

## Alternatives considered

### A. GitHub as primary IdP

- **Rejected for this project**: GitHub is low-cost and developer-friendly but less suitable for school/operator users. It is a good fallback for a developer-only MVP, but the confirmed Google Workspace account is a better fit.

### B. Microsoft Entra ID Free

- **Rejected for now**: Entra ID has a free tier and strong MFA options, but it adds complexity and is less attractive when the school already uses Google Workspace.

### C. Okta

- **Rejected for cost**: strong enterprise IdP, but unnecessary paid overhead for MVP.

### D. Cloudflare One-Time PIN as primary IdP

- **Rejected**: email OTP is not phishing-resistant and is explicitly ineligible as primary IdP. It remains acceptable only as a time-boxed, alarmed IdP-outage fallback.

## Verification

- Cloudflare Access login succeeds with a Google Workspace user in `cctv-users`.
- User outside the allowed Google group is denied by Cloudflare Access.
- MFA/passkey requirement is enforced for CCTV users.
- App validates CF JWT `iss`, `aud`, `exp`, `nbf`, and signature.
- T-47: `nbf = now + 25s` accepted.
- T-48: `nbf = now + 60s` rejected.
- Expired, invalid issuer, invalid audience, and invalid signature tokens are rejected.
- Cloudflare One-Time PIN is not enabled on App A/B as primary policy.

## Operational follow-up

- Record Google Workspace in the vendor DPA register.
- Record cross-border transfer basis for Google Workspace.
- Document Google admin account recovery procedure.
- Create initial Cloudflare Access group mapping.
- Confirm whether school Google Workspace licensing covers all intended MVP users.
- Reassess IdP before pilot if external/non-school operators must be added.

## References

- v4 plan §11.1 (Access gateway decision)
- v4 plan §11.2 (Primary IdP decision)
- v4 plan §11.3 (Layered access policies)
- v4 plan §11.4 (JWT validation)
- v4 plan §16.2 (Authentication)
- v4 plan §16.7 (Lost-MFA recovery)
- v4 plan §20.11 (IdP outage runbook)
- NIST SP 800-63B AAL2 guidance
