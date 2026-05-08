# Panoptix API

FastAPI control-plane service owned by the system owner.

## Scope

This service is responsible for:

- Cloudflare Access JWT verification
- session and authorization control
- backend API endpoints
- LiveKit token minting
- gateway identity and command/control coordination
- audit/control-plane logic

## Out of scope

- frontend UI implementation
- database schema and migration ownership

Frontend and database implementation remain assigned to the respective coworkers in `docs/implementation/team-raci-checklist.md`.
