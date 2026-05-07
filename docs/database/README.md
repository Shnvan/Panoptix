# Database Documentation

This folder contains docs owned by or primarily used by the database coworker.

## Files in this folder

| File | Purpose |
|---|---|
| [Database Guardrails](database-guardrails.md) | Things database work must not do because they break auth, audit, API, gateway behavior, or future operations. |

## Shared docs database must also read

| File | Purpose |
|---|---|
| [API Reference](../implementation/api-reference.md) | API shapes and fields the schema must support. |
| [ERD Diagram](../architecture/erd.mmd) | Entity-relationship diagram with schema constraints. |
| [Core Features](../planning/cctv-core-functionality-features.md) | MVP features that drive the data model. |
| [Future Functionality Catalog](../planning/cctv-future-functionality-features.md) | Future features that may require schema changes later. |
| [Team RACI](../implementation/team-raci-checklist.md) | Database ownership and coordination rules. |
| [Development Setup](../implementation/development-setup.md) | Local development and DB setup workflow. |
| [Test Plan](../implementation/test-plan.md) | Database-related test phases and quality gates. |
| [Postgres Tier ADR](../adrs/0003-postgres-tier.md) | Postgres provider, tier, and role strategy. |
