# Team RACI and Implementation Checklist

<!-- PE-FIX: Added ownership checklist required by council audit -->

This checklist maps the agreed three-person team split into concrete responsibilities.

## Implementation Ownership Boundary

> **Important context for all sessions and contributors:**
>
> - **Frontend implementation** (`cctv-web`, Next.js UI, React components, Tailwind styling, LiveKit JS viewer) is owned by the **frontend coworker**. The system owner must not implement frontend code.
> - **Database implementation** (schema design, Alembic migrations, triggers, indexes, DB roles) is owned by the **database coworker**. The system owner must not implement database code.
> - **System owner scope** covers: backend/control-plane (`cctv-api`), security/auth/RBAC, Cloudflare Access verification, LiveKit token minting, gateway command/control logic, audit logic, DevOps/Railway/deployment setup, runbooks, CI/CD, integration contracts, and coordination.
> - Frontend and database documentation may still be updated for coordination purposes, but actual implementation belongs to the assigned teammates.
> - When in doubt, check the RACI table below.

## Roles

| Workstream | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| Frontend UI (`cctv-web`) | Frontend coworker | System owner | System owner for API/security boundaries | Three-person team |
| Database schema/migrations | Database coworker | System owner | System owner for backend/security constraints | Three-person team |
| Backend API (`cctv-api`) | System owner | System owner | Frontend coworker, database coworker | Three-person team |
| Security architecture | System owner | System owner | Frontend coworker, database coworker where affected | Three-person team |
| Gateway agent | System owner | System owner | Database coworker for schema impacts | Three-person team |
| DevOps/Railway/Cloudflare | System owner | System owner | Frontend coworker and database coworker where affected | Three-person team |
| QA/test plan | System owner | System owner | Frontend coworker, database coworker | Three-person team |
| Compliance/privacy coordination | System owner | System owner | Future counsel/DPO only if later required | Three-person team |
| Procurement | System owner | System owner | Frontend/database only if affected | Three-person team |

## Frontend checklist

- Read `docs/frontend/frontend-guardrails.md` before implementation.
- Build Next.js routes for dashboard, admin, privacy, and emergency shell.
- Consume only `docs/implementation/api-reference.md` contracts.
- Implement camera tile states and responsive layouts from `docs/frontend/ux-product-spec.md`.
- Use LiveKit JS client for viewer-subscribe only.
- Pass browser bundle scans for forbidden APIs and secrets.

## Database checklist

- Read `docs/database/database-guardrails.md` before implementation.
- Convert §14 and ERD constraints into Alembic migrations.
- Enforce composite keys and active-row uniqueness.
- Implement append-only audit triggers and HMAC key version model.
- Implement DSR request ledger.
- Verify runtime least-privilege role.

## Backend/security checklist

- Implement CF Access JWT verifier fail-closed.
- Implement RBAC/ACL policy module.
- Implement same-origin API surface from `docs/implementation/api-reference.md`.
- Implement LiveKit viewer/gateway token minting with distinct code paths.
- Implement gateway outbound WebSocket command channel and heartbeat fallback.
- Implement audit flows; DPA export remains future/reference unless compliance work is reactivated.

## DevOps checklist

- Configure Cloudflare same-domain routing to `cctv-web` and `cctv-api`.
- Configure Railway staging/prod services.
- Implement CI gates from `docs/implementation/test-plan.md`.
- Add secret scanning, SAST/SCA, SBOM, bundle scans, and ZAP baseline.
- Exercise rollback and restore runbooks before a formal pilot; not a current prototype blocker.

## Compliance checklist

- Not a current prototype blocker.
- Legal/privacy owner naming is deferred.
- Deployment site classification is deferred.
- Compliance artifacts are retained as future reference only unless the project later connects real cameras to a real regulated site.
