# ADR 0003 â€” Postgres Provider and Tier Strategy

- **Status**: Accepted
- **Date**: 2026-05-07
- **Decision-makers**: System Owner, Software Architect, Database Architect
- **Decision**: Neon-first Postgres strategy
- **Supersedes**: None
- **Plan references**: Â§12 stack table; Â§14; Â§17.2; Â§20.7; Â§20.12; Â§21 Phase 1/5; Invariant 15

## Context

Postgres is the authoritative store for the control plane. It stores users, sessions, camera ACLs, gateway assignments, stream grants, DPA artefacts, backup evidence, and the append-only audit log.

The database tier must support:

- TLS-enforced connections.
- Least-privilege runtime roles.
- Audit-log immutability controls.
- Backup/export workflows.
- Pilot-grade recovery posture, including PITR.
- Region/latency reasonably compatible with the Railway control-plane region and APAC/Philippines users.
- Processor DPA and cross-border transfer documentation.

The v4.1 plan separates prototype and pilot requirements. Free tiers are acceptable for early development, but production pilot requires PITR and no cold-start behaviour.

## Decision

**Use a Neon-first strategy: Neon Free for prototype/MVP development, then upgrade to a Neon paid tier before pilot if PITR, APAC region, and no-cold-start requirements check out. Supabase Pro is the fallback if Neon fails those procurement checks.**

This is intentionally staged:

1. **Prototype / early MVP development**: Neon Free.
2. **Pilot readiness**: Neon paid tier, expected target Neon Launch or current equivalent.
3. **Fallback**: Supabase Pro if Neon cannot meet region, PITR, availability, DPA, or operational requirements at procurement time.

## Requirements

### Prototype tier requirements

Neon Free may be used only while the system is not handling a real pilot deployment.

Prototype must still enforce:

- `sslmode=require`.
- Separate migration/admin role and runtime app role.
- Least-privilege runtime grants.
- Audit schema and immutability triggers, even if recovery SLA is weaker.
- Daily logical backup flow exercised, even if PITR is unavailable.

Prototype limitations accepted:

- Cold-starts.
- No pilot-grade PITR.
- No production SLA.

### Pilot tier requirements

Before pilot, the Postgres tier must provide:

- PITR enabled and tested.
- No cold-start behaviour for normal application traffic.
- TLS required.
- Least-privilege role support.
- Ability to run migrations safely.
- `pg_dump` export for encrypted backup to R2.
- Restore drill support.
- Processor DPA available.
- Cross-border transfer basis documented.
- Region/latency compatible with the Railway control-plane region and APAC/Philippines users.

## Database security posture

### Role model

- **Migration/admin role**: used only in CI/deploy migration step; can create/alter tables, triggers, indexes.
- **Runtime app role**: used by `cctv-api`; cannot disable triggers, drop tables, truncate tables, or bypass audit immutability.
- **Read/export role** (optional pilot+): scoped to audit/DPA exports if separation becomes necessary.

### Runtime restrictions

The runtime role must not be able to:

- Disable triggers.
- Drop tables.
- `TRUNCATE` tables.
- Write audit fields outside the trigger-controlled path.
- Update or delete immutable audit rows.

This implements Invariant 15.

### Audit-log implications

The audit chain remains in Postgres as the authoritative active store. Integrity is enforced through:

- Append-only triggers.
- HMAC-SHA-256 chain per row.
- `hmac_key_version` per row.
- 5-minute verifier job in pilot.
- Daily signed archive to R2 with object lock.
- Weekly chain-integrity sweep across sampled windows.

The provider does not need provider-specific audit features for MVP. The design relies on portable Postgres features plus app-level HMAC verification.

## Backup and recovery

### MVP/prototype

- Daily `pg_dump`.
- `age` encryption before upload.
- Store encrypted backup in Cloudflare R2 with object lock.
- Record backup metadata in `backup_runs`.
- Run post-backup `pg_restore --list` integrity check.

### Pilot

- PITR enabled on the paid provider tier.
- Daily logical backup still retained for provider-exit and audit evidence.
- Weekly restore drill.
- Restore drill records:
  - backup object ID
  - checksum
  - `pg_restore --list` result
  - row-count estimate
  - integration query result
  - `backup_runs.restore_schema_ok`

## Provider comparison

| Provider | Fit | Pros | Cons | Decision |
|---|---|---|---|---|
| Neon Free | Prototype | Free, fast start, Postgres-compatible | Cold-starts, no pilot-grade PITR | Use for prototype only |
| Neon paid tier | Pilot target | PITR available, Postgres-compatible, low cost if requirements check out | Region/feature details must be verified at procurement | Primary pilot candidate |
| Supabase Pro | Fallback | PITR, mature dashboard/ecosystem, predictable pricing | Slightly higher baseline cost; extra platform surface | Fallback |
| Railway Postgres / Railway-compatible PG | Alternative | App-adjacent if chosen, simple procurement path | PITR/no-cold-start/region posture must be verified before pilot | Not primary unless Neon/Supabase fail checks |
| Crunchy Bridge / Aiven / RDS / Cloud SQL | Alternative | Strong managed Postgres posture | Potentially higher cost/complexity | Later if needed |

## Consequences

### Positive

- **Lowest practical start cost**: Neon Free supports early development without paid database spend.
- **Clear upgrade gate**: pilot cannot proceed until paid PITR/no-cold-start requirements are met.
- **Provider portability**: schema, SQLAlchemy/Alembic migrations, `pg_dump`, and portable triggers avoid provider lock-in.
- **Fallback identified**: Supabase Pro is pre-selected as fallback if Neon procurement checks fail.

### Negative

- **Two-stage migration**: moving from Neon Free to paid tier or another provider must be planned and tested.
- **Cold-starts during prototype**: early dev/staging may see latency spikes.
- **Procurement verification still required**: exact Neon tier names/features/pricing can change and must be verified live before pilot.

### Risks accepted

- Prototype data may not have pilot-grade recovery guarantees. This is acceptable only before real pilot use. The system must not handle pilot data until paid PITR and restore-drill acceptance are complete.

## Alternatives considered

### A. Supabase Pro as primary

- **Rejected for now**: strong option, but Neon-first is lower-friction and likely lower cost for the staged prototype-to-pilot path. Supabase remains the fallback.

### B. Platform-attached Postgres as primary

- **Rejected for now**: app-adjacent Postgres can simplify procurement, but PITR, no-cold-start behaviour, region/latency, and recovery posture must be verified. Neon-first managed Postgres with Supabase Pro fallback is preferred.

### C. Stay on free tier through pilot

- **Rejected**: free-tier cold-starts and lack of pilot-grade PITR conflict with audit durability, recovery, and availability requirements.

### D. SQLite or embedded DB for MVP

- **Rejected**: fails multi-instance control-plane deployment, audit-chain durability, RBAC, backup/restore, and future provider-exit requirements.

## Verification

Before pilot:

- PITR enabled and documented.
- Restore drill passes from both provider PITR and encrypted R2 logical backup.
- Runtime role cannot disable triggers, drop tables, truncate, or mutate protected audit fields.
- `sslmode=require` verified.
- Daily backup job writes `backup_runs` row and passes `pg_restore --list`.
- Weekly restore drill sets `restore_schema_ok = true`.
- DPA and cross-border transfer basis recorded for the selected provider.

## Operational follow-up

- Create Neon account under the dedicated project email.
- Start with Neon Free only for prototype/dev data.
- Verify APAC region availability and latency to Railway control-plane region.
- Verify current paid tier name, PITR behaviour, no-cold-start posture, and pricing.
- Record Neon DPA and cross-border transfer basis.
- Define migration path from Neon Free to paid tier.
- Keep Supabase Pro as documented fallback if Neon checks fail.

## References

- v4 plan Â§12 (Technology Stack â€” database rows)
- v4 plan Â§14 (Data Model & Database Design)
- v4 plan Â§17.2 (Audit integrity)
- v4 plan Â§20.7 (Backup / restore plan)
- v4 plan Â§20.12 (DB restore runbook)
- v4 plan Â§21 Phase 1 / Phase 5
- Invariant 15 (DB least-privilege)

