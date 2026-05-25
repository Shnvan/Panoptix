# Detailed Tech Stack — Superseded

> **Superseded — 2026-05-07:** This document previously described the old Fly.io + Next.js/Node.js plan. It has been intentionally replaced to avoid stale implementation guidance.

<!-- PE-FIX: Fixed corrupted filename reference and updated to current file path -->

The current source of truth is:

- `docs/planning/tech-stack-simple.md`
- `docs/adrs/0014-railway-python-control-plane.md`
- `docs/planning/secure-cctv-monitoring-system-v4.md` §12

Current control-plane stack:

- Railway-hosted React + Vite frontend service
- Railway-hosted Python/FastAPI backend service
- Tailwind UI for MVP
- SQLAlchemy 2.x + Alembic
- Cloudflare Access with GitHub OAuth IdP (staging); Google Workspace planned for production
- Neon-first Postgres strategy
- LiveKit Cloud primary media plane
- DigitalOcean Singapore or equivalent UDP-capable APAC host for self-hosted LiveKit fallback
- On-site physical NUC-class x86_64 mini-PC production camera gateway

Historical Fly.io/Next.js/Node.js content should not be used for implementation decisions. The frontend now uses React + Vite (not Next.js).
