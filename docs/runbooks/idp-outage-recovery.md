# Runbook: IdP Outage Recovery

## Purpose

Maintain administrative access to Panoptix when the primary Identity Provider (GitHub OAuth) is experiencing an outage, preventing normal admin login.

## Scope

This runbook covers IdP unavailability while Cloudflare Access and DNS routing remain healthy. It does **not** cover:

- Cloudflare Access policy misconfiguration → see `cf-access-rollback.md`
- DNS routing failure → see `cf-access-rollback.md`
- Database outage → use Railway console + `backup-restore.md`

## Detection

- Admin login fails with IdP error (GitHub returns 5xx or OAuth callback timeout)
- [GitHub Status](https://www.githubstatus.com/) shows service disruption affecting Authentication or API/Webhooks
- Multiple users report inability to authenticate
- Cloudflare Access shows JWT verification failures in logs

## Prerequisites

- Hardware security key for `break-glass-prime@<domain>`
- Password from password manager or sealed offline copy
- Cloudflare Access App C configured at `/admin-emergency`
- Backend API running and database reachable

## Steps

### 1. Confirm IdP outage

Before using break-glass, confirm GitHub OAuth is actually down:

- Check [GitHub Status](https://www.githubstatus.com/) — look for incidents affecting Authentication or API/Webhooks
- Attempt login from a different network/device
- Check Cloudflare Access logs for JWT verification errors

### 2. Open break-glass window

Follow `break-glass-runbook.md` steps 1–2.

```
POST /api/v1/admin/break-glass/open
{"reason": "GitHub OAuth outage — githubstatus.com confirms service disruption"}
```

### 3. Perform critical admin actions

During the IdP outage, prioritize:

1. **Monitor system health** — check `GET /api/v1/admin/health/deep`
2. **Review active sessions** — existing sessions remain valid until they expire; no immediate user impact unless sessions time out during the outage
3. **Extend session timeouts if needed** — adjust `SESSION_IDLE_TIMEOUT_SECONDS` in Railway env vars if the outage is expected to be prolonged
4. **Do not disable users** unless there is evidence of compromise — IdP restoration will restore normal login

### 4. Monitor IdP restoration

- Watch [GitHub Status](https://www.githubstatus.com/) for recovery
- When IdP is restored, verify normal admin login works through `staging.panoptix.site`

### 5. Close break-glass window

Once IdP is restored and normal admin access is confirmed:

```
POST /api/v1/admin/break-glass/close
{"reason": "GitHub OAuth restored — normal admin login verified"}
```

### 6. Execute post-close rotation

Follow `break-glass-runbook.md` step 5 — mandatory rotation of all credentials within 24 hours.

### 7. Post-incident review

- Review audit log for all actions taken during the break-glass window
- Document the IdP outage duration and impact
- Verify no unauthorized access occurred during the outage
- Update incident log

## If the outage exceeds 90 minutes

Open a new break-glass window (audited). Each window is independently time-bounded. Rotation obligation applies after the last window is closed.

## References

- v4 plan §16.6 (Break-glass administration)
- ADR 0005 — Break-Glass Emergency Access Pattern
- ADR 0002 — Primary Identity Provider Selection (note: originally planned for Google Workspace; GitHub OAuth deployed for staging)
- `docs/runbooks/break-glass-runbook.md`
- `docs/runbooks/lost-mfa-recovery.md`
