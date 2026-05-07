# Runbook: Deploy and Rollback

<!-- PE-FIX: Added standalone deploy/rollback runbook required by council audit -->

## Deploy prerequisites

- CI green.
- Secret scan clean.
- Browser bundle scan clean.
- API contract smoke tests pass.
- Staging smoke tests pass.
- No critical/high security scan findings.

## Deploy steps

1. Merge approved PR to protected branch.
2. CI builds `cctv-web` and `cctv-api` artifacts.
3. CI signs artifacts where applicable.
4. Deploy to Railway staging.
5. Run smoke tests and T-30/T-56 subset.
6. Promote to production after manual approval.
7. Verify health, login, API, gateway control channel, and dashboard.
8. Record deployment audit event/release note.

## Rollback triggers

- Auth failures for legitimate users.
- API 5xx spike.
- Gateway control-channel failures.
- Browser bundle violates forbidden terms.
- DB migration regression.
- Security headers missing or relaxed.

## Rollback steps

1. Stop ongoing rollout.
2. Roll `cctv-web` and/or `cctv-api` back to previous known-good Railway deployment.
3. If routing caused the issue, apply Cloudflare rollback runbook.
4. If DB migration caused the issue, use expand/contract compatible rollback only.
5. Run smoke tests and T-30/T-56.
6. Notify users/admins.
7. Open post-mortem.

## Post-rollback verification

- `/health` returns exact OK body.
- Dashboard loads through Cloudflare Access.
- `/api/v1/me` works for valid user.
- Direct Railway API protected routes fail closed.
- Gateway outbound WebSocket or heartbeat fallback works.
