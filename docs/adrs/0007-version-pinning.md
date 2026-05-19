# ADR 0007 — Framework and Binary Version Pinning Policy

- **Status**: Accepted
- **Date**: 2026-05-07
- **Decision-makers**: Software Architect, System Owner
- **Supersedes**: None
- **Amended by**: ADR 0014 — Railway + Python Control Plane
- **Plan references**: Invariant 12; §12 stack table; §13.7 (mediamtx / FFmpeg); §16.8; §20.14; §20.16

## Context

The system is a security-critical CCTV monitoring platform. After ADR 0014, its runtime depends on:

- **Python** (control-plane runtime)
- **FastAPI** (control-plane framework)
- **Node.js** (frontend runtime/build runtime)
- **Next.js / React / Tailwind** (MVP UI)
- **LiveKit JavaScript client** (browser viewer only)
- **mediamtx** (edge gateway RTSP bridge — single Go binary)
- **FFmpeg** (synthetic RTSP source for dev/CI)
- **Docker base images** (container runtime)
- **Python packages** and frontend JavaScript packages

Using floating version tags or dependency ranges (e.g., `python:3.12-slim`, `latest`, `fastapi>=0.110`, `^14.0.0`) in a security-critical system creates three risks:

1. **Non-reproducible builds**: the same Dockerfile or `package.json` produces different binaries on different days. A security audit cannot verify "what ran in production" if the version floated between build and audit.
2. **Supply-chain attacks**: a compromised upstream release auto-deploys into the system via a floating tag or range specifier. The SolarWinds and `event-stream` incidents demonstrate this class of attack.
3. **Silent breaking changes**: a minor/patch version bump introduces an incompatibility or a new behaviour that weakens a security control (e.g., a FastAPI/Pydantic change affects request validation, a JWT library changes verification behaviour, or a `mediamtx` update changes auth behaviour).

Invariant 12 requires stable locked framework versions, experimental APIs banned in security-critical paths, lockfile pins, exact Docker base images, and Dependabot/Renovate enabled.

## Current implementation note

This ADR is the target supply-chain policy. The current repository has partial implementation:

- GitHub Actions are version-pinned.
- Dependabot covers backend pip, edge-agent pip, and GitHub Actions.
- CI currently runs tests, ruff, mypy, compile checks, Gitleaks, Semgrep, osv-scanner, Trivy, and Docker build checks.
- The repository does not yet have Python lockfiles, frontend lockfiles, SBOM generation/signing, browser bundle scans, Playwright, ZAP, or k6 gates.
- The backend Docker image currently uses `python:3.12-slim-bookworm`; exact digest pinning remains a future hardening task.

Until those gates are implemented, references below describe the accepted target policy rather than fully enforced current behavior.

## Decision

**Every runtime dependency — framework, binary, Docker base image, Python package, and required frontend package — is pinned to an exact version. Updates are managed through Dependabot/Renovate PRs, reviewed by a human, CI-gated, and merged deliberately. No floating tags, no broad version ranges in security-critical paths, no `latest` in Dockerfiles.**

### Pinning rules

| Artefact | Pin format | Example | Update mechanism |
|---|---|---|---|
| Python Docker base | Exact Python patch + digest | `python:3.12.7-slim-bookworm@sha256:abc...` | Dependabot PR; CI fails on floating tag |
| Node.js runtime | Exact major/minor/patch + digest where containerized | `node:22.11.0-bookworm-slim@sha256:abc...` | Dependabot/Renovate PR; CI fails on floating tag |
| Next.js | Exact version in frontend lockfile | `next x.y.z` | Dependabot/Renovate PR |
| React / React DOM | Exact versions in frontend lockfile | `react x.y.z`, `react-dom x.y.z` | Dependabot/Renovate PR |
| FastAPI | Exact version in lockfile | `fastapi==0.x.y` | Dependabot/Renovate PR |
| Pydantic | Exact version in lockfile | `pydantic==2.x.y` | Dependabot/Renovate PR |
| SQLAlchemy | Exact version in lockfile | `sqlalchemy==2.x.y` | Dependabot/Renovate PR |
| Alembic | Exact version in lockfile | `alembic==1.x.y` | Dependabot/Renovate PR |
| Python dependencies | Lockfile committed | `uv.lock` or Poetry lockfile | `uv sync --locked` / `poetry install --sync` in CI |
| Frontend dependencies | Lockfile committed | `pnpm-lock.yaml`, `package-lock.json`, or `yarn.lock` | lockfile-only install in CI |
| LiveKit JS client | Exact version in frontend lockfile | `livekit-client x.y.z` | Dependabot/Renovate PR |
| Tailwind tooling | Exact version in frontend lockfile | `tailwindcss x.y.z` | Dependabot/Renovate PR |
| mediamtx | Exact release tag in gateway Dockerfile/config | `mediamtx v1.9.1` | Renovate watcher on `bluenviron/mediamtx` releases; human review |
| FFmpeg | Exact version in synthetic-RTSP Dockerfile | `ffmpeg 6.1.1` | Renovate or manual; dev/CI only |
| LiveKit Python Server SDK | Exact version if used | `livekit-api==x.y.z` | Dependabot/Renovate PR |
| Terraform providers | Version constraint `= x.y.z` | `version = "= 4.44.0"` | Dependabot PR |
| GitHub Actions | Pinned to commit SHA | `uses: actions/checkout@abc123` | Dependabot PR |

### Target CI enforcement

1. **Floating-tag lint**: a CI step scans `Dockerfile*` for floating tags (`latest`, `slim` without a patch version, `python:3.12` without patch). Fails the build.
2. **Lockfile integrity**: Python dependencies install only from the committed lockfile. Frontend dependencies install only from the committed lockfile.
3. **Frontend dependency scanning**: Next.js/React dependencies are scanned with Dependabot/Renovate and osv/npm-audit-equivalent CI checks.
4. **Frontend bundle scan**: built browser bundles are scanned for forbidden camera-publisher APIs, RTSP credential strings, gateway-publish token paths, and accidental secrets.
5. **Semgrep rule `ban-experimental-imports`**: flags experimental or unstable framework/library APIs in security-critical paths (auth, token-mint, audit, gateway API).
6. **SBOM generation**: every release build produces an SBOM (CycloneDX or SPDX) listing all pinned versions. The SBOM is committed as a release artefact.

### Experimental API ban

Experimental or unstable APIs from FastAPI, Starlette, Pydantic, JWT/JWKS libraries, SQLAlchemy, LiveKit SDKs, Next.js/React routing/runtime features, or browser media libraries are **banned in security-critical code paths**:

- Authentication / JWT verification
- Token minting (viewer-subscribe, gateway-publish)
- Audit log writes
- Gateway identity validation
- Break-glass enforcement
- DB migration runners

Experimental APIs may be used in non-security-critical UI code only after explicit review and only if they do not affect the security control flow.

### Update workflow

1. **Dependabot / Renovate** opens a PR with the version bump.
2. **CI runs**: full test suite, security scans (Semgrep, osv-scanner, Trivy), bundle analysis.
3. **Human review**: reviewer checks the changelog for security-relevant changes, breaking changes, and behaviour differences.
4. **Merge**: only after CI green + human approval.
5. **Deploy**: standard deploy pipeline (canary if applicable at scale).

### Version decisions deferred to Phase 0 exit

The following exact versions are recorded in this ADR at Phase 0 exit (after procurement):

- Python patch version: `3.12.x` or current stable supported Railway version (to be determined)
- FastAPI / Pydantic / SQLAlchemy / Alembic exact versions (to be determined)
- LiveKit Python Server SDK exact version, if used (to be determined)
- Node.js exact version (to be determined)
- Next.js / React / React DOM exact versions (to be determined)
- Tailwind exact version (to be determined)
- LiveKit JavaScript client exact version (to be determined)
- mediamtx: `vX.Y.Z` (to be determined; latest stable at procurement)
- FFmpeg: `X.Y.Z` (to be determined)

This ADR records the **policy**; the specific versions are appended as an addendum when procurement decisions are finalized.

## Consequences

### Positive

- **Reproducible builds**: the same commit always produces the same binary. Auditors can verify exactly what ran in production.
- **Supply-chain defense**: a compromised upstream release does not auto-deploy. It arrives as a Dependabot PR, passes CI, and requires human approval.
- **No silent breakage**: version bumps are deliberate, reviewed, and tested.
- **SBOM traceability**: every release has a machine-readable inventory of all dependencies and their exact versions.

### Negative

- **Update fatigue**: Dependabot/Renovate will generate frequent PRs across Python and frontend packages. Mitigation: group minor/patch updates by ecosystem; prioritize security updates; batch non-security updates weekly.
- **Stale dependencies if neglected**: pinning without active updates creates a different risk (known vulnerabilities in old versions). Mitigation: osv-scanner in CI flags known CVEs; Dependabot security alerts are high-priority.
- **mediamtx lag**: `mediamtx` is a single-maintainer project. Critical fixes may require forking temporarily. Mitigation: Renovate watches releases; the gateway is isolated on the camera plane (ADR 0001), so a vulnerability in mediamtx does not directly compromise the control plane.

### Risks accepted

- A zero-day in a pinned version is not mitigated by pinning — only by the speed of the update workflow. Accepted because the alternative (floating tags) makes the zero-day situation worse, not better.

## Alternatives considered

### A. Broad version ranges for all packages

- **Rejected**: broad ranges allow dependency bumps without review. A malicious or buggy patch release can auto-install on the next build.

### B. Pin only security-critical packages, float the rest

- **Rejected**: transitive dependencies of "non-critical" packages can still introduce vulnerabilities. The lockfile pins everything uniformly; the overhead is in the lockfile, not in `package.json` maintenance.

### C. Use vulnerability scanning instead of pinning

- **Rejected**: vulnerability scanners detect known vulnerabilities after publication; they do not prevent a supply-chain attack that has not been reported yet. Pinning + human review catches behavioural changes that scanners may not flag.

### D. Distroless images (no OS package manager)

- **Partially adopted**: distroless or `-slim` images are preferred. But the exact image tag is still pinned by digest, not just by name. Distroless reduces the OS-level attack surface; digest pinning ensures reproducibility.

## Target Verification

- **CI floating-tag lint**: fails on any Dockerfile with a floating tag.
- **CI lockfile check**: Python/frontend installs fail if lockfiles are out of sync.
- **CI experimental-API lint**: Semgrep rule flags experimental imports in security paths.
- **SBOM diff on release**: release pipeline diffs the SBOM against the previous release and flags new or removed dependencies.
- **osv-scanner**: fails CI on known high/critical CVEs in pinned versions.

## References

- v4 plan Invariant 12 (Stable, locked framework versions)
- v4 plan §12 (Technology Stack — version pins per row)
- v4 plan §13.7 (Synthetic RTSP test source — FFmpeg + mediamtx versions)
- NIST SSDF PW.4.1 (Verify third-party components)
- SLSA Level 2 (Reproducible builds)
- CycloneDX / SPDX SBOM standards
