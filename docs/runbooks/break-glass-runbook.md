# Runbook: Break-Glass Emergency Access

## Purpose

Provide emergency admin access when the primary IdP (Google Workspace) is unavailable, the primary admin's MFA device is lost, or normal admin login is otherwise impossible — while Cloudflare Access and DNS routing remain healthy.

## Scope

Break-glass covers IdP/user/MFA failures only. It does **not** recover from:

- Broad Cloudflare Access policy misconfiguration → use `cf-access-rollback.md`
- DNS routing failure → use `cf-access-rollback.md`
- Cloudflare account lockout → use provider-console recovery
- Total database outage → use Railway console + `backup-restore.md`

## Prerequisites

- Hardware security key for `break-glass-prime@<domain>`
- Password from password manager or sealed offline copy (§20.19 bus-factor)
- Cloudflare Access App C configured at `/admin-emergency`
- Backend API running and database reachable

## Steps

### 1. Authenticate via CF Access App C

Navigate to the `/admin-emergency` path. Cloudflare Access will challenge with the hardware security key policy. Only the `break-glass-prime@<domain>` identity is permitted.

### 2. Open the break-glass window

```
POST /api/v1/admin/break-glass/open
Content-Type: application/json

{"reason": "<describe the emergency, e.g. 'IdP outage — Google Workspace 503'>"}
```

Expected response:

```json
{
  "window_id": "uuid",
  "opened_at": "2026-05-13T...",
  "auto_disable_at": "2026-05-13T..."
}
```

The window is **90 minutes**. After `auto_disable_at`, all requests on the emergency path are denied automatically (request-time enforcement, no scheduler dependency).

### 3. Perform recovery actions

Within the 90-minute window, perform the needed admin operations:

- Unlock a locked-out admin account
- Reset a user's MFA enrollment (via IdP admin or `POST /api/v1/admin/users/:id/mfa/reset`)
- Review audit logs for suspicious activity during the outage
- Adjust camera/gateway/user configuration as needed

### 4. Close the break-glass window

Close the window as soon as recovery is complete. Do not let it expire silently.

```
POST /api/v1/admin/break-glass/close
Content-Type: application/json

{"reason": "<describe resolution, e.g. 'IdP restored, admin MFA re-enrolled'>"}
```

Expected response includes a `rotation_required` checklist.

### 5. Execute mandatory post-close rotation

**This is a hard requirement, not a suggestion.** Rotate all of the following within 24 hours:

| # | Credential | How |
|---|-----------|-----|
| 1 | Audit HMAC key | Increment `AUDIT_HMAC_KEY_VERSION`, generate new key, redeploy |
| 2 | LiveKit API keys | Rotate in LiveKit Cloud dashboard, update Railway env vars |
| 3 | CF Access service tokens | Regenerate in Cloudflare dashboard, update Railway env vars |
| 4 | All gateway credentials | Rotate via `POST /api/v1/admin/gateways/:id/rotate-credential` |

### 6. Verify rotation

- Confirm `system.break_glass.closed` audit event exists
- Confirm rotation events appear in audit within 24 hours
- Confirm external monitor at `GET /api/v1/admin/internal/break-glass-status` shows `{"active": false}`

## If the window expires before recovery is complete

Open a new window (audited). Each window is independently time-bounded. The post-close rotation obligation applies after the **last** window is closed.

## Monitoring

External monitor (UptimeRobot / Better Stack) polls `GET /api/v1/admin/internal/break-glass-status` every 5 minutes. Alert fires if `active: true` and `auto_disable_at` is in the past.

## References

- ADR 0005 — Break-Glass Emergency Access Pattern
- v4 plan §16.6 (Break-glass administration)
- v4 plan §20.19 (Bus-factor runbook — hardware key escrow)
- `docs/runbooks/lost-mfa-recovery.md`
- `docs/runbooks/idp-outage-recovery.md`
