# Runbook: Lost-MFA Recovery

## Purpose

Recover admin or user access when their MFA device (hardware key, phone, authenticator app) is lost, stolen, or broken — while Cloudflare Access and DNS remain healthy.

## Scope

This runbook covers MFA device loss for normal users and admins. It does **not** cover:

- Break-glass hardware key loss → see §20.19 bus-factor runbook (sealed envelope escrow)
- IdP outage → see `idp-outage-recovery.md`
- CF Access policy failure → see `cf-access-rollback.md`

## Prerequisites

- Another admin with active access, **or** break-glass access if no admin can log in
- IdP admin console access (Google Workspace Admin)

## Steps

### Scenario A: Another admin is available

1. **Affected user contacts available admin** via out-of-band channel (phone, in-person).

2. **Admin verifies identity** — confirm the request is legitimate (not social engineering). Use a pre-agreed verification method (e.g., video call, in-person, shared secret).

3. **Admin resets MFA in IdP** — in Google Workspace Admin Console:
   - Navigate to the user's account
   - Remove existing 2-Step Verification enrollment
   - User re-enrolls with a new device on next login

4. **Admin disables user sessions** (precautionary):
   ```
   POST /api/v1/admin/users/{user_id}/disable
   {"reason": "MFA device lost — precautionary session revoke"}
   ```

5. **Admin re-enables user** after MFA re-enrollment is confirmed:
   - Verify user can log in with new MFA device
   - Re-grant roles if needed via `POST /api/v1/admin/users/{user_id}/role`

6. **Audit review** — check audit log for suspicious activity during the window when the user's MFA was compromised:
   ```
   GET /api/v1/admin/audit?action=viewer.token.issued
   ```

### Scenario B: No admin available (break-glass required)

1. **Open break-glass window** — follow `break-glass-runbook.md` steps 1–2.

2. **Perform admin-mediated MFA reset** — follow Scenario A steps 2–6 using break-glass admin access.

3. **Close break-glass window** — follow `break-glass-runbook.md` steps 4–6 (including mandatory rotation).

## Important notes

- MFA reset is **not self-service** — it always requires admin mediation (Invariant 11: no passwords in the application).
- If the lost device is a hardware security key, treat it as potentially compromised. Revoke all sessions for the affected user immediately.
- Document the incident in the audit log via the reason field.

## References

- v4 plan §16.7 (Lost-MFA recovery)
- ADR 0005 — Break-Glass Emergency Access Pattern
- `docs/runbooks/break-glass-runbook.md`
- NIST SP 800-63B (authenticator lifecycle)
