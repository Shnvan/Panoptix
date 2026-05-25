# Frontend Documentation

This folder contains docs owned by or primarily used by the frontend coworker.

> **READ FIRST FOR CURRENT WORK**: Start with [Frontend Coworker Handoff](FRONTEND_HANDOFF.md). It contains the current backend state, read order, next frontend tasks, local run flow, and hard security guardrails.

> **DESIGN RULES**: Before visual changes or UI redesign work, read [Panoptix Design System](PANOPTIX_DESIGN_SYSTEM.md). It defines the color philosophy, token values, and migration mapping that new and updated UI work should follow.

## Color Philosophy (TL;DR)

The Panoptix visual identity is derived from the BSIT 2-2 class site extraction. The core principles are:

1. **Pure dark backgrounds** - `#0A0A0A`, `#111111`, `#1A1A1A`. No blue-tinted slate colors.
2. **Single warm orange accent** - `#F07C1E`. No cyan, multi-color accents, or gradients.
3. **Sharp geometry** - `border-radius: 0`. Avoid rounded cards and rounded buttons in new design-system work.
4. **Neutral gray text** - `#F0EAD6` warm cream primary and `#666666` neutral secondary. Avoid blue-gray slate text.
5. **Solid dark borders** - `#222222`. Avoid transparent white overlay borders.

The current frontend still uses Tailwind's `slate-*` scale and some cyan accent colors. These should be replaced gradually when the assigned task is explicitly design-system migration.

## Files In This Folder

| File | Purpose |
|---|---|
| **[Frontend Coworker Handoff](FRONTEND_HANDOFF.md)** | **Primary for current work** - read order, current backend state, next frontend tasks, local run flow, and hard guardrails. |
| [Panoptix Design System](PANOPTIX_DESIGN_SYSTEM.md) | Complete color philosophy, design tokens, component guidance, Tailwind migration map, and acceptance checklist. Read before visual/UI redesign work. |
| [Integration Guide](INTEGRATION_GUIDE.md) | Auth flow, CSRF handling, LiveKit JS SDK integration, camera grid patterns, and error handling. |
| [Backend Status](BACKEND_STATUS.md) | Every implemented backend API, what frontend can build now, dev-auth setup, and conventions. |
| [Frontend Production TODO](FRONTEND_PRODUCTION_TODO.md) | Production-readiness checklist, remaining frontend blockers, and verification steps. |
| [Frontend Guardrails](frontend-guardrails.md) | Things frontend must not do because they break security, API, media, or operations. |
| [UX/Product Spec](ux-product-spec.md) | Frontend screens, states, personas, layout, accessibility, and error-copy requirements. |

## Shared Docs Frontend Must Also Read

| File | Purpose |
|---|---|
| [API Reference](../implementation/api-reference.md) | Backend API contract the frontend consumes. |
| [Core Features](../planning/cctv-core-functionality-features.md) | MVP features, future features, and permanently unsupported features. |
| [Future Functionality Catalog](../planning/cctv-future-functionality-features.md) | Future feature idea catalog. |
| [Team RACI](../implementation/team-raci-checklist.md) | Frontend ownership and coordination rules. |
| [Development Setup](../implementation/development-setup.md) | Local development workflow. |
| [Test Plan](../implementation/test-plan.md) | Frontend-related test phases and quality gates. |
