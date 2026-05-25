# Runbook: Uptime Monitoring

## Monitoring Setup

Staging is monitored by a GitHub Actions cron job that runs every 15 minutes:
`.github/workflows/staging-healthcheck.yml`

Actions page: `https://github.com/<org>/panoptix/actions/workflows/staging-healthcheck.yml`

Two endpoints are checked on each run:

| Endpoint | Pass Condition |
| --- | --- |
| `GET https://staging.panoptix.site/health` | HTTP 200 with body `{"status":"ok"}` |
| `GET https://staging.panoptix.site/api/v1/admin/health/deep` | HTTP 200 with valid JSON containing `status` field |

On failure the workflow opens a GitHub Issue titled **"Staging health check failed"** (deduped — one open issue at a time).

---

## Alert Response

**Step 1 — Confirm the alert.**
Check GitHub Issues for an open "Staging health check failed" issue. Read the failure table in the issue body to identify which endpoint(s) failed.

**Step 2 — Reproduce manually.**
```bash
curl -i https://staging.panoptix.site/health
curl -i https://staging.panoptix.site/api/v1/admin/health/deep
```
Note the HTTP status and response body.

**Step 3 — Check Railway.**
Open the Railway dashboard → panoptix staging service. Look for:
- Service in crash loop or stopped state
- Recent failed deploy (check deploy logs)
- Memory / CPU saturation

**Step 4 — 401 / 403 returned.**
If either endpoint returns 401 or 403, the Cloudflare Access policy may have changed. Check the Cloudflare Access → Policies page and the Access audit log for recent policy edits or token expiry.

**Step 5 — Deep health fails but `/health` passes.**
The shallow health endpoint bypasses the database. If only the deep check fails, suspect Neon (PostgreSQL):
- Check [Neon status page](https://neonstatus.com/)
- Check connection pool exhaustion in Neon console
- Review Railway service logs for `sqlalchemy` / connection errors

**Step 6 — Escalate.**
If the issue is not resolved within **15 minutes** of the alert, escalate to the on-call engineer via the team's agreed channel (Slack / PagerDuty). Share the GitHub Issue URL and the raw `curl` output.

---

## SLA / Uptime Targets

| Environment | Target | Window / Gate |
| --- | --- | --- |
| Staging | Best-effort | 7-day green window required before production promotion |
| Production | 99.5% uptime | _Not yet deployed — placeholder_ |

---

## Closing an Alert

1. Fix the underlying issue.
2. Re-run the healthcheck workflow manually (`workflow_dispatch`) to verify both checks pass.
3. Close the GitHub Issue.
4. Add a comment to the closed issue with: **root cause**, **fix applied**, and **time to resolution**.
