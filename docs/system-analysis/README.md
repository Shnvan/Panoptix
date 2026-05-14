# Panoptix System Analysis Documentation

This folder contains the system analysis documentation set for the existing Panoptix project. It is based on repository inspection of source code, database models and migrations, tests, existing documentation, runbooks, and placeholders.

## Recommended Reading Order

1. [01-system-analysis.md](01-system-analysis.md) - project summary, scope, inventory, risks, and recommendations.
2. [02-functional-requirements.md](02-functional-requirements.md) - implemented, partial, missing, and confirmation-needed functional requirements.
3. [03-non-functional-requirements.md](03-non-functional-requirements.md) - security, reliability, performance, maintainability, data integrity, and operations requirements.
4. [04-use-cases.md](04-use-cases.md) - actor goals, flows, exceptions, and related evidence.
5. [05-business-rules-and-validation-rules.md](05-business-rules-and-validation-rules.md) - confirmed rules, implied rules, validation logic, and gaps.
6. [06-data-requirements-and-data-dictionary.md](06-data-requirements-and-data-dictionary.md) - database entities, relationships, and data dictionary.
7. [07-screen-page-requirements.md](07-screen-page-requirements.md) - required UI screens and current frontend implementation status.
8. [08-api-and-integration-requirements.md](08-api-and-integration-requirements.md) - API routes, integrations, auth, and unclear behavior.
9. [09-report-requirements.md](09-report-requirements.md) - audit, DPA, health, backup, and reporting/export requirements.
10. [10-acceptance-criteria-and-test-scenarios.md](10-acceptance-criteria-and-test-scenarios.md) - QA scenarios and test coverage comparison.
11. [11-gap-analysis-and-recommendations.md](11-gap-analysis-and-recommendations.md) - consolidated gaps, impact, recommendations, and team questions.
12. [12-requirements-traceability-matrix.md](12-requirements-traceability-matrix.md) - traceability across requirements, rules, APIs, data, source, and tests.
13. [13-change-log.md](13-change-log.md) - change log for this documentation set.

## Notes For Developers And Testers

- Status labels are evidence-based. `Existing` means source code, migrations, tests, or current documentation support the item.
- `Partially Existing` means a foundation, endpoint, placeholder, or scaffold exists but the complete workflow is not production-ready.
- `Missing` means no implemented support was found in the inspected project.
- `Needs Team Confirmation` means the repository does not contain enough authoritative information to finalize the requirement.
- `Recommended` means the item is analyst-proposed and should not be treated as committed scope until approved.

## Evidence Sources

Primary evidence came from `README.md`, `PROGRESS.md`, `HANDOFF.md`, `IMPLEMENTATION_GUIDE.md`, `MANUAL_TESTING.md`, `requirements.md`, `apps/api/src/cctv_api/`, `apps/api/alembic/`, `apps/api/tests/`, `apps/cctv-edge/agent/`, `apps/web/README.md`, and existing documentation under `docs/`.

