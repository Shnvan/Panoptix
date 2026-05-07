# Panoptix — Secure CCTV Web Monitoring System

A live-view CCTV monitoring web application that connects IP cameras to authenticated browser viewers through a security-first, three-plane architecture.

> **Status:** Pre-development / documentation phase. No application code has been written yet.

---

## Architecture

The system is organized into three isolated planes:

| Plane | Purpose | Hosting |
|-------|---------|---------|
| **Control plane** | Login, dashboard, API, permissions, audit, database | Railway (Next.js frontend + Python/FastAPI backend) |
| **Media plane** | Live video delivery via WebRTC SFU | LiveKit Cloud (APAC) + self-hosted fallback |
| **Camera plane** | Physical cameras, local gateway, isolated camera network | On-site NUC-class mini-PC |

Browsers are **viewers only** — no webcam, phone-camera, or browser-based publishing is supported. This is a permanent product constraint, not a temporary limitation.

---

## Tech Stack

- **Frontend:** Next.js / React / Tailwind CSS / LiveKit JS client (viewer only)
- **Backend:** Python / FastAPI / SQLAlchemy 2.x / Alembic
- **Database:** Neon Postgres (prototype free tier; paid before pilot)
- **Identity:** Google Workspace (primary IdP) + Cloudflare Access (IAP)
- **Media:** LiveKit Cloud (primary) + self-hosted LiveKit (fallback)
- **Gateway:** Ubuntu Server + Docker + mediamtx on NUC-class mini-PC
- **Security:** Cloudflare WAF/DNS, RBAC, append-only HMAC-chained audit, break-glass emergency access
- **Privacy:** Philippine Data Privacy Act (RA 10173) compliant — PIA, DPA, bystander signage

---

## Documentation

All project documentation is in the [`docs/`](docs/) folder. See [`docs/index.md`](docs/index.md) for a full navigation map.

### Key documents

| Document | Description |
|----------|-------------|
| [Main Plan](docs/planning/secure-cctv-monitoring-system-v4.md) | Comprehensive system plan (~2300 lines) |
| [Core Features](docs/planning/cctv-core-functionality-features.md) | User-facing feature overview |
| [Tech Stack (Simple)](docs/planning/tech-stack-simple.md) | Plain-language technology guide |
| [API Reference](docs/implementation/api-reference.md) | Frontend/backend/gateway API contract |
| [Development Setup](docs/implementation/development-setup.md) | Local development and fake-CF-Access workflow |
| [Deployment Guide](docs/implementation/deployment-guide.md) | Railway + Cloudflare same-domain deployment model |
| [Test Plan](docs/implementation/test-plan.md) | QA gates and T-1..T-69 traceability |
| [UX/Product Spec](docs/frontend/ux-product-spec.md) | Frontend-ready screens, states, accessibility |
| [Team RACI](docs/implementation/team-raci-checklist.md) | Frontend/database/backend/security ownership |
| [Architecture Diagrams](docs/architecture/) | Mermaid diagrams for system topology and flows |
| [ADRs](docs/adrs/) | 14 Architecture Decision Records |
| [Security](docs/security/) | STRIDE threat model |
| [Privacy](docs/privacy/) | PIA, DPA, and bystander signage templates |
| [Compliance Readiness](docs/privacy/compliance-readiness-checklist.md) | Pilot privacy/legal readiness checklist |
| [Procurement](docs/procurement/) | Vendor selection, camera spec, and hardware procurement guide |
| [Runbooks](docs/runbooks/) | Operations procedures for deploy, rollback, backup, CF Access, and gateway control |
| [Glossary](docs/reference/glossary.md) | Domain terminology reference |

---

## Project Structure

```
panoptix-main/
  README.md                  # This file
  CLAUDE.md                  # AI assistant review instructions
  execute.md                 # Principal Engineer execution protocol
  CONTRIBUTING.md            # Contribution rules
  SECURITY.md                # Security policy
  LICENSE                    # Proprietary license
  .env.example               # Environment variable schema
  docs/
    index.md                              # Document navigation map
    planning/                             # Product and architecture planning docs
      secure-cctv-monitoring-system-v4.md # Main plan
      cctv-core-functionality-features.md # User-facing features
      cctv-future-functionality-features.md # Future feature idea catalog
      tech-stack-simple.md                # Tech stack guide
      tech-stack.md                       # Superseded pointer
    implementation/                       # Implementation-readiness docs
      api-reference.md                    # API contract
      development-setup.md                # Local setup
      deployment-guide.md                 # Deployment model
      test-plan.md                        # QA strategy
      team-raci-checklist.md              # Ownership checklist
    reference/                            # Reference docs
      glossary.md                         # Domain glossary
    frontend/                             # Frontend coworker docs
      README.md                           # Frontend reading guide
      frontend-guardrails.md              # Frontend guardrails
      ux-product-spec.md                  # UX/frontend spec
    database/                             # Database coworker docs
      README.md                           # Database reading guide
      database-guardrails.md              # Database guardrails
    review/                               # Current review/status docs
      document-review-report-current.md   # Current post-audit status
    adrs/                                 # Architecture Decision Records
      0001-plane-separation.md
      0002-idp-selection.md
      0003-postgres-tier.md
      0004-livekit-fallback.md
      0005-break-glass.md
      0006-reserved.md
      0007-version-pinning.md
      0008-gateway-identity.md
      0009-cctv-only-ingest.md
      0010-origin-binding.md
      0011-bystander-signage-policy.md
      0012-camera-network-design.md
      0013-gateway-hardware-standard.md
      0014-railway-python-control-plane.md
    architecture/                         # Mermaid diagrams
      system-overview.mmd
      request-flow.mmd
      data-flow.mmd
      network-security.mmd
      erd.mmd
      sequence-viewer-login.mmd
      sequence-camera-stream.mmd
      sequence-admin-actions.mmd
    security/
      threat-model-stride.md
    privacy/
      bystander-signage-template.md
      pia-template.md
      vendor-dpa-template.md
    procurement/
      procurement-guide.md
      camera-spec.md
    runbooks/
      gateway-control-channel.md
      cf-access-rollback.md
      deploy-rollback.md
      backup-restore.md
```

---

## Non-Negotiable Invariants

1. Security-first design — every feature evaluated for security impact before convenience
2. Always-on managed cloud hosting for the control plane
3. Origin non-exposure — control plane behind Cloudflare Access
4. Control-plane / media-plane separation
5. CCTV-only ingest — no browser/phone/laptop camera publishing (permanent)
6. Edge gateway is MVP-critical
7. Deny-by-default authorization
8. Short-lived, kind-distinct stream tokens (≤60 s)
9. Append-only audit with HMAC chain
10. No MVP recording — live-view only
11. No passwords in the application — federated identity only
12. Stable locked framework versions
13. Provider-exit boundaries

---

## License

Private / proprietary. Not open source.
