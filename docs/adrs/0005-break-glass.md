# ADR 0005 — Break-Glass Emergency Access Pattern

- **Status**: Accepted
- **Date**: 2026-05-07
- **Decision-makers**: Software Architect, System Owner
- **Supersedes**: v3 break-glass design (4-hour window, scheduler-dependent)
- **Plan references**: §16.6; §16.7; §16.8; §18.2 T-52; §20.19; Invariant 11

## Context

The system relies entirely on Cloudflare Access + an external IdP for authentication (Invariant 11 — no passwords in the application). This creates a dependency chain: if the IdP is down or the primary admin's MFA device is lost, no normal admin can log in to fix the problem. If Cloudflare Access itself is broadly misconfigured, the recovery path is the Cloudflare/Railway provider-console rollback runbook, not the in-app break-glass route.

A break-glass mechanism provides emergency admin access for IdP/user/MFA failures while maintaining strong authentication and a bounded exposure window. It does not bypass Cloudflare Access itself; it is a separate Cloudflare Access App C with tighter policy.

The v3 plan used a 4-hour break-glass window enforced by a database-level scheduled job (`pg_cron`). This had two problems:

1. **4 hours is too long**: an open break-glass window is a privileged session with reduced identity assurance. Minimizing the window minimizes risk.
2. **Scheduler dependency is fragile**: if `pg_cron` fails (or the provider doesn't support it), the window stays open indefinitely. The enforcement mechanism must not depend on an optional provider feature.

## Decision

**Break-glass access is provided through a dedicated CF Access App (App C) at `/admin-emergency`, protected by a hardware security key, with a fixed 90-minute window enforced at request time. The window auto-closes even if the application restarts, the scheduler fails, or the database is temporarily unreachable for writes.**

### Access control

- **Sealed account**: `break-glass-prime@<domain>`, hardware security key only (no OTP, no push, no SMS).
- **CF Access App C**: only this single identity is permitted. Policy requires hardware key challenge.
- **Password**: stored in a password manager + sealed offline copy (§20.19 bus-factor runbook).
- **No self-service**: the break-glass credential cannot be reset without physical access to the hardware key and the sealed envelope.

### Recovery scope

> [RESOLVED by Principal Engineer — see ADR 0005] Break-glass is scoped to IdP outage fallback, lost/admin MFA recovery, and normal admin lockout while Cloudflare Access and DNS routing remain healthy. It is not the recovery mechanism for a broad Cloudflare Access policy, DNS, or Cloudflare account lockout. Those scenarios use the CF Access rollback and provider-console recovery runbooks.

### Window lifecycle

1. **Open**: Admin authenticates via CF Access App C → app creates a `break_glass_usage` row:
   ```
   opened_at = now()
   auto_disable_at = opened_at + interval '90 minutes'
   closed_at = NULL
   actor = 'break-glass-prime@<domain>'
   ```
   Audit event: `system.break_glass.opened`.

2. **Active**: Every request on the `/admin-emergency` path calls `assert_break_glass_active(now)`:
   ```python
   # PE-FIX: Updated from TypeScript to Python per ADR 0014
   def assert_break_glass_active(now: datetime) -> None:
       usage = db.query(BreakGlassUsage).filter(
           BreakGlassUsage.closed_at.is_(None)
       ).order_by(BreakGlassUsage.opened_at.desc()).first()
       if not usage or now >= usage.auto_disable_at:
           raise HTTPException(status_code=403, detail="break-glass-expired")
   ```
   **This is the authoritative gate.** It runs on every request, reads from the database, and checks `now()` against `auto_disable_at`. No scheduler, no cron, no timer — just a comparison.

3. **Auto-close**: After 90 minutes, `assertBreakGlassActive` rejects all requests. The row remains open (`closed_at = NULL`) until a close operation runs, but no requests are permitted.

4. **Explicit close**: Admin (or automated close runbook) sets `closed_at = now()`. Audit event: `system.break_glass.closed`.

5. **Post-close rotation**: The close runbook mandates rotation of:
   - Audit HMAC key (new version)
   - LiveKit API keys
   - CF Access service tokens
   - All gateway credentials
   
   This is a **hard requirement**, not a suggestion. The break-glass window is a controlled-but-elevated-risk period; rotation afterward limits the blast radius of anything that may have been exposed during the window.

### Named constant

```python
# PE-FIX: Updated from TypeScript to Python per ADR 0014
BREAK_GLASS_WINDOW_MINUTES = 90
```

Hard-coded, not configurable via environment variable or database. Changing it requires a code change, a PR review, and a redeployment — deliberate friction.

### External monitor (belt-and-braces)

A provider-neutral external monitor (UptimeRobot or Better Stack) hits a control endpoint every 5 minutes:

- `GET /api/v1/admin/internal/break-glass-status` (CF Access service-token protected)
- Returns `{ "active": false }` or `{ "active": true, "auto_disable_at": "..." }`
- Alert fires if `active: true` and `auto_disable_at` is in the past — meaning the request-time check is working but the row hasn't been explicitly closed.

This is a secondary alert, not the enforcement mechanism.

## Consequences

### Positive

- **90 minutes, not 4 hours**: reduces the exposure window by 62%.
- **Request-time enforcement**: survives app restarts, scheduler failures, DB write outages (the read still works), and provider-specific `pg_cron` absence.
- **Hardware key required**: phishing-resistant authentication even in emergency.
- **Mandatory post-close rotation**: limits blast radius of the elevated-access period.
- **Audit trail**: every break-glass open, close, and in-window action is recorded.

### Negative

- **90 minutes may be tight**: a complex recovery (e.g., full DB restore + audit chain verification) might take longer. Mitigation: the admin can open a new window (audited) if the first expires. Each window is independently time-bounded.
- **Hardware key is a single physical artefact**: loss or theft is a risk. Mitigated by the bus-factor runbook (§20.19) which escrows the key with a second signatory.
- **Post-close rotation is operationally heavy**: rotating 4+ credential sets after every break-glass use. Accepted as the cost of the security guarantee.

### Risks accepted

- If the database is completely unreachable (not just slow), `assertBreakGlassActive` will throw an error, denying access. This is fail-closed by design — in a total DB outage, break-glass cannot be used. Recovery in that scenario requires Railway console access + DB restore, not break-glass.

## Alternatives considered

### A. Longer window (4 hours, as in v3)

- **Rejected**: 4 hours of elevated access is unnecessary for most recovery scenarios. 90 minutes is sufficient for common operations (user unlock, config fix, audit review). If more time is needed, a new window can be opened.

### B. Scheduler-enforced closure (`pg_cron` or `setInterval`)

- **Rejected**: scheduler is a separate failure domain. If the scheduler stops, the window stays open. Request-time enforcement has no such dependency.

### C. No break-glass — rely on normal admin recovery alone

- **Rejected**: IdP outage, primary-admin MFA loss, or normal admin lockout can still prevent administrative recovery while Cloudflare Access itself remains healthy. Break-glass covers those scenarios; CF Access platform misconfiguration is handled by the provider-console rollback runbook (§20.9).

### D. Time-based OTP instead of hardware key

- **Rejected**: TOTP is phishable. The break-glass is the highest-privilege access path; it must use the strongest available authentication. Hardware security key (FIDO2/WebAuthn) is non-negotiable.

### E. Configurable window via environment variable

- **Rejected**: an attacker who gains deployment secret/config write access could extend the window indefinitely. Hard-coded constant requires code change + review + redeploy.

## Verification

- **T-52**: open break-glass window → advance clock to 91 minutes (simulated) → restart app worker → attempt admin request → **denied**. Confirms request-time enforcement survives restart.
- **External monitor**: alert fires within 5 minutes if an expired window is still showing `active: true`.
- **Post-close rotation audit**: `system.break_glass.closed` event must be followed by rotation events for all listed credential types within 24 hours (operational check, not automated test).

## References

- v4 plan §16.6 (Break-glass administration)
- v4 plan §16.7 (Lost-MFA recovery)
- v4 plan §16.8 (Secrets & keys — rotation schedule)
- v4 plan §18.2 T-52
- v4 plan §20.19 (Bus-factor runbook — hardware key escrow)
- NIST SP 800-63B AAL3 (hardware authenticator requirement)
