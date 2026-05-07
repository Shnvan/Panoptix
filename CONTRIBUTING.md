# Contributing

<!-- PE-FIX: Added contribution guide required by council audit -->

Panoptix is currently pre-development. Contributions must preserve the documented security and privacy invariants.

## Workstream ownership

Use `docs/implementation/team-raci-checklist.md` before starting work. Frontend, database, backend/security, DevOps, QA, procurement, and compliance changes must match the assigned responsibilities.

## Required reading before implementation

- `README.md`
- `docs/index.md`
- `docs/planning/secure-cctv-monitoring-system-v4.md`
- `docs/implementation/api-reference.md`
- `docs/implementation/development-setup.md`
- Relevant ADRs in `docs/adrs/`

## Pull request expectations

Every PR must include:

- Summary of change.
- Affected docs/code/config.
- Security impact.
- Tests or verification evidence.
- Confirmation that CCTV-only invariant is preserved.

## Prohibited changes without ADR

- Browser or phone camera publishing.
- Recording, snapshots, playback, or media storage.
- Gateway inbound WAN ports.
- Long-lived browser auth tokens.
- Gateway-publish tokens returned to browsers.
- RTSP credentials in backend API responses or frontend bundles.
- Weakening Cloudflare Access JWT verification.

## Documentation changes

If changing architecture, update all affected docs and diagrams in the same PR. If two documents conflict, resolve the conflict and cite the authoritative ADR.
