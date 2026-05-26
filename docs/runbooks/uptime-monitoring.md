# Runbook: Uptime Monitoring

## Monitoring Setup

Production is monitored by a GitHub Actions cron job that runs every 15 minutes:
`.github/workflows/production-healthcheck.yml`

Actions page: `https://github.com/<org>/panoptix/actions/workflows/production-healthcheck.yml`

Two endpoints are checked on each run:

| Endpoint | Pass Condition |
| --- | --- |
| `GET https://panoptix.site/health` | HTTP 200 with body `{"status":"ok"}` |
| `GET https://panoptix.site/api/v1/admin/health/deep` | HTTP 200 with valid JSON containing `status` field |

The workflow authenticates through Cloudflare Access with a dedicated production monitor service token. Store only the raw values in GitHub repository secrets:

- `PRODUCTION_CF_ACCESS_CLIENT_ID`
- `PRODUCTION_CF_ACCESS_CLIENT_SECRET`

The Cloudflare Access policy for this token must allow the two health URLs above. Do not paste header names, token values, screenshots of tokens, or service-token secrets into docs, commits, issues, or chat.

On failure the workflow opens a GitHub Issue titled **"Production health check failed"** (deduped - one open issue at a time). Issue creation uses the GitHub REST API directly, so the workflow does not depend on downloading `actions/github-script`.

---

## Alert Response

**Step 1 - Confirm the alert.**
Check GitHub Issues for an open "Production health check failed" issue. Read the failure table in the issue body to identify which endpoint(s) failed.

**Step 2 - Reproduce manually.**
```bash
curl -i \
  -H "CF-Access-Client-Id: <production-monitor-client-id>" \
  -H "CF-Access-Client-Secret: <production-monitor-client-secret>" \
  https://panoptix.site/health

curl -i \
  -H "CF-Access-Client-Id: <production-monitor-client-id>" \
  -H "CF-Access-Client-Secret: <production-monitor-client-secret>" \
  https://panoptix.site/api/v1/admin/health/deep
```
Note the HTTP status and response body. Do not paste token values into issue comments or test notes.

**Step 3 - Check Railway.**
Open the Railway dashboard for the production backend and frontend services. Look for:
- Service in crash loop or stopped state
- Recent failed deploy (check deploy logs)
- Memory / CPU saturation
- Custom domain or proxy errors affecting `panoptix.site`

**Step 4 - 302 / 401 / 403 returned.**
If either endpoint returns a Cloudflare Access redirect, 401, or 403, the production monitor service-token policy or GitHub repository secrets may have changed. Check the Cloudflare Access Policies page, Access audit log, and repository secret presence. A 302 usually means the request reached the Access login flow instead of being accepted as a service-token request.

**Step 5 - Deep health fails but `/health` passes.**
The shallow health endpoint bypasses the database. If only the deep check fails, suspect a production dependency:
- Check [Neon status page](https://neonstatus.com/)
- Check LiveKit Cloud status and credentials
- Check gateway heartbeat freshness when a physical gateway is enrolled
- Review Railway production service logs for `sqlalchemy`, LiveKit, or gateway health errors

**Step 6 - Escalate.**
If the issue is not resolved within **15 minutes** of the alert, escalate through the agreed operator channel. Share the GitHub Issue URL and sanitized `curl` output.

---

## SLA / Uptime Targets

| Environment | Target | Window / Gate |
| --- | --- | --- |
| Production | 99.5% uptime | Production live behind Cloudflare Access |
| Staging | Best-effort | Historical pre-production environment; no scheduled healthcheck after production promotion |

---

## Closing an Alert

1. Fix the underlying issue.
2. Re-run the production healthcheck workflow manually (`workflow_dispatch`) to verify both checks pass.
3. Close the GitHub Issue.
4. Add a comment to the closed issue with: **root cause**, **fix applied**, and **time to resolution**.
