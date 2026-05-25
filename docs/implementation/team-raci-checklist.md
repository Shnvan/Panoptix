# Team RACI and Implementation Checklist

<!-- PE-FIX: Added ownership checklist required by council audit -->

This checklist maps the agreed three-person team split into concrete responsibilities.

## Implementation Ownership Boundary

> **Important context for all sessions and contributors:**
>
> - **Frontend implementation** (`cctv-web`, React + Vite UI, React components, Tailwind styling, LiveKit JS viewer) is owned by the **frontend coworker**. The system owner must not implement frontend code.
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
- Build React routes for dashboard, admin, privacy, and emergency shell.
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

## Coordination gates

### When database work should merge with backend

Database work can merge into the backend workstream when these are true:

- The database coworker has implemented the required schema/migrations in `database/`.
- The affected backend contract is already documented in `docs/implementation/api-reference.md` or agreed with the system owner.
- The schema supports the backend feature being integrated, such as sessions, gateway assignments, camera metadata, stream grants, audit events, or DSR records.
- Migration, rollback, and seed/dev-data instructions are documented by the database coworker.
- The backend can connect using environment variables only, with no hardcoded credentials.
- Tests exist for the database-owned behavior, and backend integration tests can be added without changing database ownership.

Do not merge database changes into backend-dependent features when the backend would need to invent schema, migrations, indexes, triggers, or DB roles. Those remain database coworker responsibilities.

### When frontend work can start before backend is finished

Frontend work can start before the backend is complete when these are true:

- The frontend coworker uses only contracts in `docs/implementation/api-reference.md`.
- Screens, states, and accessibility behavior come from `docs/frontend/ux-product-spec.md`.
- Backend endpoints may still be placeholders, but their paths, request shapes, response shapes, and error shapes are stable enough to mock.
- The frontend uses mock data, fixtures, or local API adapters until real backend routes are ready.
- Auth/session behavior is treated as Cloudflare Access protected and same-origin; frontend code must not create its own auth model.
- LiveKit frontend code is viewer-subscribe only and never handles gateway-publish tokens.
- Any contract gap is raised to the system owner instead of being guessed in frontend code.

Frontend changes should wait if the screen depends on an undecided API contract, unknown permission model, unknown camera state machine, or database fields that are not yet agreed.

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
