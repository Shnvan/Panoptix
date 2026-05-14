# Documentation Index

<!-- PE-FIX: Created central navigation map for all project documentation -->

Navigation map for the Panoptix CCTV monitoring system documentation.

---

## Core Planning

| Document | Description |
|----------|-------------|
| [Main System Plan](planning/secure-cctv-monitoring-system-v4.md) | Comprehensive v4.1 plan covering architecture, security, data model, API, testing, operations, and roadmap (~2300 lines) |
| [Core Features](planning/cctv-core-functionality-features.md) | User-facing overview of system features, roles, and MVP scope |
| [Future Functionality Catalog](planning/cctv-future-functionality-features.md) | Full idea catalog of possible future features beyond MVP (not approved unless marked) |
| [Tech Stack (Simple)](planning/tech-stack-simple.md) | Plain-language technology guide with rationale for each component |
| [Tech Stack (Superseded)](planning/tech-stack.md) | Pointer to current sources of truth; old Fly.io/Node.js content removed |
| [Glossary](reference/glossary.md) | Domain terminology reference |
| [Academic Manual Crosswalk](reference/academic-manual-crosswalk.md) | Maps COMP 012 lab manual concepts to Panoptix production system |
| [System Analysis Documentation](system-analysis/README.md) | Analyst handoff set covering requirements, rules, data, screens, APIs, reports, QA, gaps, and traceability |
| [API Reference](implementation/api-reference.md) | Frontend/backend/gateway API contract |
| [Development Setup](implementation/development-setup.md) | Local development workflow and dev-auth constraints |
| [Deployment Guide](implementation/deployment-guide.md) | Railway + Cloudflare same-domain routing and release gates |
| [Test Plan](implementation/test-plan.md) | Standalone QA strategy and traceability matrix |
| [UX/Product Spec](frontend/ux-product-spec.md) | UI states, screens, personas, and accessibility requirements |
| [Team RACI](implementation/team-raci-checklist.md) | Team ownership and implementation checklist |
| [Frontend Docs](frontend/README.md) | Frontend coworker documentation folder |
| [Frontend Integration Guide](frontend/INTEGRATION_GUIDE.md) | Auth flow, CSRF, LiveKit JS SDK, camera grid patterns, and error handling for frontend developers |
| [Frontend Guardrails](frontend/frontend-guardrails.md) | Things the frontend owner must not do because they break security, API, media, or operations |
| [Database Docs](database/README.md) | Database coworker documentation folder |
| [Database Guardrails](database/database-guardrails.md) | Things the database owner must not do because they break auth, audit, API, or gateway behavior |

---

## Architecture Decision Records (ADRs)

| ADR | Title | Status |
|-----|-------|--------|
| [0001](adrs/0001-plane-separation.md) | Control-Plane / Media-Plane / Camera-Plane Separation | Accepted |
| [0002](adrs/0002-idp-selection.md) | Primary Identity Provider Selection (Google Workspace planned; GitHub OAuth deployed) | Superseded in practice |
| [0003](adrs/0003-postgres-tier.md) | Postgres Provider and Tier Strategy (Neon-first) | Accepted |
| [0004](adrs/0004-livekit-fallback.md) | LiveKit Fallback Strategy | Accepted |
| [0005](adrs/0005-break-glass.md) | Break-Glass Emergency Access Pattern | Accepted |
| [0006](adrs/0006-reserved.md) | Reserved | Reserved |
| [0007](adrs/0007-version-pinning.md) | Framework and Binary Version Pinning Policy | Accepted |
| [0008](adrs/0008-gateway-identity.md) | Gateway Identity and mTLS CA Design | Accepted |
| [0009](adrs/0009-cctv-only-ingest.md) | CCTV-Only Ingest Invariant | Accepted |
| [0010](adrs/0010-origin-binding.md) | Origin-Binding and Trusted-Header Policy | Accepted |
| [0011](adrs/0011-bystander-signage-policy.md) | Bystander Signage Policy | Accepted |
| [0012](adrs/0012-camera-network-design.md) | Camera Network Design | Accepted |
| [0013](adrs/0013-gateway-hardware-standard.md) | Gateway Hardware Standard | Accepted |
| [0014](adrs/0014-railway-python-control-plane.md) | Railway + Python Control Plane | Accepted |

---

## Architecture Diagrams

All diagrams are in Mermaid format (`.mmd`).

| Diagram | Description |
|---------|-------------|
| [System Overview](architecture/system-overview.mmd) | High-level three-plane architecture with external actors and services |
| [Request Flow](architecture/request-flow.mmd) | User login through Cloudflare Access to dashboard and video stream |
| [Data Flow](architecture/data-flow.mmd) | Media, control, gateway, audit/backup, and webhook data paths |
| [Network Security](architecture/network-security.mmd) | Trust zones, network boundaries, and allowed/blocked traffic |
| [Entity-Relationship Diagram](architecture/erd.mmd) | Database schema — all tables, relationships, and key fields |
| [Sequence: Viewer Login](architecture/sequence-viewer-login.mmd) | Login flow through CF Access, Google Workspace, and FastAPI |
| [Sequence: Camera Stream](architecture/sequence-camera-stream.mmd) | Presence-driven publish — start, additional viewer, stop, edge cases |
| [Sequence: Admin Actions](architecture/sequence-admin-actions.mmd) | Admin login, camera/gateway registration, user assignment, credential rotation |

---

## Security

| Document | Description |
|----------|-------------|
| [STRIDE Threat Model](security/threat-model-stride.md) | Full STRIDE analysis across control, media, and camera planes |

---

## Privacy & Compliance

| Document | Description |
|----------|-------------|
| [PIA Template](privacy/pia-template.md) | Privacy Impact Assessment template (RA 10173) |
| [Vendor DPA Template](privacy/vendor-dpa-template.md) | Data Processing Agreement template for vendors/processors |
| [Bystander Signage Template](privacy/bystander-signage-template.md) | Physical CCTV notice signage templates (EN/FIL) |
| [Compliance Readiness Checklist](privacy/compliance-readiness-checklist.md) | Required pilot/privacy/legal readiness artifacts |

---

## Procurement

| Document | Description |
|----------|-------------|
| [Procurement Guide](procurement/procurement-guide.md) | Vendor selection criteria, hardware specs, account setup checklist, acceptance gates |
| [Camera Spec](procurement/camera-spec.md) | Camera, gateway, and site network procurement requirements |

---

## Operations Runbooks

| Runbook | Description |
|---------|-------------|
| [Gateway Control Channel](runbooks/gateway-control-channel.md) | Outbound WebSocket command channel and heartbeat fallback |
| [Edge Gateway Service](runbooks/edge-gateway-service.md) | Docs-only host/service runbook for Docker, Linux systemd, and Windows/NSSM edge supervisor operation |
| [Cloudflare Production Setup](runbooks/cloudflare-production-setup.md) | Docs-only Cloudflare Access, routing, JWT, and rollback preparation checklist |
| [CF Access Rollback](runbooks/cf-access-rollback.md) | Provider-console/Terraform recovery for CF Access/DNS policy issues |
| [Railway/Neon Staging Prep](runbooks/railway-neon-staging-prep.md) | Docs-only staging deployment prep for Railway compute and Neon Postgres |
| [Railway/Neon Production Prep](runbooks/railway-neon-production-prep.md) | Docs-only production deployment prep checklist (gated by 7-day staging uptime) |
| [Deploy and Rollback](runbooks/deploy-rollback.md) | Railway deploy, rollback triggers, and post-rollback checks |
| [Backup and Restore](runbooks/backup-restore.md) | Backup, restore, and restore-drill procedure |
| [Break-Glass Runbook](runbooks/break-glass-runbook.md) | Break-glass lifecycle: open, perform critical actions, close, mandatory rotation checklist |
| [Lost-MFA Recovery](runbooks/lost-mfa-recovery.md) | Admin-mediated MFA device reset with optional break-glass escalation path |
| [IdP Outage Recovery](runbooks/idp-outage-recovery.md) | GitHub OAuth outage detection, break-glass escalation, restoration verification, and post-incident review |
| [Bus Factor Recovery](runbooks/bus-factor.md) | Emergency recovery procedure if the sole system owner is unavailable |

---

## Review & Process

| Document | Description |
|----------|-------------|
| [Current Document Review Status](review/document-review-report-current.md) | Current post-execution summary of council-audit fixes and remaining human decisions |
