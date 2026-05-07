# Security Policy

<!-- PE-FIX: Added security policy required by council audit -->

Panoptix is a security-first CCTV monitoring system. No feature ships if it weakens the documented security invariants.

## Supported reporting channel

Until a public disclosure process is approved, report security issues privately to the system owner.

Do not file public issues containing:

- Secrets or tokens.
- Camera/network details.
- Exploit steps against a real deployment.
- Personal data or screenshots of live video.

## Security invariants

- Cloudflare Access protects the public custom domain.
- FastAPI verifies Cloudflare Access JWTs fail-closed on protected routes.
- Browsers are viewers only.
- No browser camera/microphone publishing.
- No MVP recording, snapshots, or playback.
- Camera credentials stay only on the on-site gateway.
- Gateway has zero inbound WAN ports.
- Gateway start/stop commands use outbound WebSocket with heartbeat fallback.
- Stream tokens are short-lived and kind-distinct.
- Audit logs are append-only and HMAC-chained.

## Dependency and supply-chain policy

- Dependencies are exact-pinned per ADR 0007.
- Lockfile-only installs are required.
- Semgrep, osv-scanner, Trivy, gitleaks, browser bundle scans, and SBOM generation are CI gates.
- Critical/high findings block release unless explicitly accepted in an ADR.

## Secret handling

- No secrets in source, docs, screenshots, or issue trackers.
- Use Railway/environment secret stores for control plane secrets.
- Use separate media/gateway secret stores.
- Rotate credentials after break-glass use, suspected leak, or gateway compromise.

## Incident response

Use `docs/runbooks/deploy-rollback.md`, `docs/runbooks/cf-access-rollback.md`, `docs/runbooks/gateway-control-channel.md`, and `docs/runbooks/backup-restore.md` as the starting operational runbooks.
