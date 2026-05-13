# Runbook: Bus-Factor Recovery

## Purpose

Ensure the Panoptix system can be maintained and recovered if the sole system owner (primary developer / operator) becomes unavailable — whether temporarily (illness, leave) or permanently (departure, incapacitation).

## Scope

This runbook covers recovery of operational control. It does **not** cover business continuity planning, HR processes, or legal succession.

## Prerequisites

Before this runbook is needed, the following must be in place:

| # | Prerequisite | Location | Who Sets Up |
|---|-------------|----------|-------------|
| 1 | Sealed-envelope hardware key for `break-glass-prime@<domain>` | Physical safe or bank safety deposit box | System owner |
| 2 | Password manager vault delegation (shared vault or emergency access) | 1Password / Bitwarden emergency access | System owner |
| 3 | GitHub repository admin access for at least one other team member | GitHub org settings | System owner |
| 4 | Railway team membership for at least one other member | Railway dashboard | System owner |
| 5 | Cloudflare account with at least two named members | Cloudflare dashboard | System owner |
| 6 | Neon database console access for at least one other member | Neon dashboard | System owner |
| 7 | This runbook reviewed and understood by the designated backup person | This file | System owner + backup |

## Critical Environment Variables

All secrets are stored in Railway environment variables. The backup person needs Railway team access to view/rotate them.

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `AUDIT_HMAC_KEY` | HMAC key for audit hash chain integrity |
| `AUDIT_HMAC_KEY_VERSION` | Current HMAC key version number |
| `SESSION_SIGNING_KEY` | Session cookie signing key |
| `CSRF_SECRET` | CSRF token secret |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | LiveKit Cloud credentials |
| `CF_ACCESS_TEAM_DOMAIN` / `CF_ACCESS_AUD` | Cloudflare Access JWT verification |

## Recovery Steps

### Step 1: Establish access

1. Retrieve the sealed-envelope hardware key from its physical location.
2. Use password manager emergency access to obtain credentials.
3. Log into GitHub, Railway, Cloudflare, and Neon with the backup person's own credentials or the emergency credentials.

### Step 2: Verify system health

```
GET /health              → basic health check (unauthenticated)
GET /api/v1/admin/health/deep → detailed health (requires admin auth)
GET /api/v1/admin/internal/break-glass-status → break-glass monitor (unauthenticated)
```

### Step 3: If admin access is needed urgently

Follow `break-glass-runbook.md`:

1. Authenticate via CF Access App C with the hardware key.
2. Open a break-glass window.
3. Perform needed admin actions.
4. Close the window and execute the mandatory rotation checklist.

### Step 4: Establish ongoing operations

1. **Grant admin role** to the backup person's regular account via `POST /api/v1/admin/users/:id/role`.
2. **Rotate all credentials** as a precautionary measure (follow break-glass rotation checklist).
3. **Review recent audit logs** for any anomalies: `GET /api/v1/admin/audit`.
4. **Verify CI pipeline** is green on the `backend` branch.
5. **Test deployment** — push a trivial change and confirm Railway auto-deploys.

### Step 5: Knowledge transfer

Key documentation for the new operator:

| Document | Purpose |
|----------|---------|
| `HANDOFF.md` | Full project context for new IDE/LLM sessions |
| `PROGRESS.md` | Current status and next steps |
| `IMPLEMENTATION_GUIDE.md` | How each component works |
| `MANUAL_TESTING.md` | How to verify each feature |
| `docs/implementation/api-reference.md` | Complete API contract |
| `docs/implementation/team-raci-checklist.md` | Who owns what |
| `docs/runbooks/` | All operational runbooks |

## Prevention Checklist

To minimize bus-factor risk **before** an emergency:

- [ ] At least two people have GitHub admin access
- [ ] At least two people have Railway team access
- [ ] At least two people have Cloudflare account membership
- [ ] At least two people have Neon console access
- [ ] Hardware key sealed envelope is physically accessible to at least two people
- [ ] Password manager emergency access is configured for at least one backup person
- [ ] This runbook has been reviewed by the backup person within the last 90 days
- [ ] Break-glass flow has been drilled (dry-run) within the last 90 days

## References

- `docs/runbooks/break-glass-runbook.md`
- `docs/runbooks/lost-mfa-recovery.md`
- v4 plan §20.19 (Bus-factor — hardware key escrow)
- v4 plan §16.6 (Break-glass administration)
