# 13 - Change Log

| Date | Files created | Files updated | Summary | Basis |
|---|---|---|---|---|
| 2026-05-14 | `docs/system-analysis/README.md`, `01-system-analysis.md` through `13-change-log.md` | `docs/index.md` | Created a new system-analysis documentation set and linked it from the documentation index. | Existing documentation, source code inspection, database inspection, UI inspection, API inspection, test inspection, analyst recommendation |

## Major Improvements

- Added a dedicated system-analysis folder instead of mixing analyst output into existing planning/runbook documents.
- Distinguished implemented backend/edge/database behavior from missing frontend and hardware-dependent work.
- Documented functional and non-functional requirements with explicit status labels.
- Added use cases, business rules, validation rules, data dictionary, screen requirements, API requirements, report requirements, test scenarios, gap analysis, and traceability.
- Recorded the known camera source type documentation mismatch.
- Marked uncertain areas as `Needs Team Confirmation`.

## Inspection Basis

| Inspection type | Evidence used |
|---|---|
| Existing documentation | `README.md`, `PROGRESS.md`, `HANDOFF.md`, `IMPLEMENTATION_GUIDE.md`, `MANUAL_TESTING.md`, existing `docs/` files |
| Source code inspection | `apps/api/src/cctv_api/`, `apps/cctv-edge/agent/src/panoptix_edge_agent/` |
| Database inspection | SQLAlchemy models and Alembic migrations under `apps/api/` |
| UI inspection | `apps/web/README.md`, `docs/frontend/` |
| API inspection | FastAPI routers under `apps/api/src/cctv_api/api/` |
| Test inspection | `apps/api/tests/`, `apps/cctv-edge/agent/tests/`, `docs/implementation/test-plan.md` |
| Analyst recommendation | Gap analysis, recommended future enhancements, traceability matrix |
| Needs team confirmation | Auditor/SuperAdmin roles, backup status shape, re-enable/update lifecycle policies |

