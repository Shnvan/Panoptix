# Panoptix Frontend Handoff

You are the frontend coworker. Your job is to build the `cctv-web` Next.js frontend inside `apps/web/`.

## Read These Files First (In Order)

1. `docs/frontend/BACKEND_STATUS.md` — every implemented backend API, dev-auth setup, what you can build now, what is not ready yet
2. `docs/frontend/frontend-guardrails.md` — things you must not do
3. `docs/frontend/ux-product-spec.md` — screens, states, personas, layout, accessibility, error copy
4. `docs/frontend/README.md` — index of frontend docs and shared docs
5. `docs/implementation/api-reference.md` — full API contract (browser, admin, gateway, webhook)
6. `README.md` — high-level architecture and project structure
7. `CLAUDE.md` — AI coding guidance and security invariants

## Do NOT Read These Files

These are backend/edge-agent implementation docs. They will waste your context and are not relevant to frontend work:

- `PROGRESS.md` — backend milestone tracker
- `IMPLEMENTATION_GUIDE.md` — backend implementation history
- `MANUAL_TESTING.md` — backend manual testing with PowerShell/curl
- `HANDOFF.md` (root) — backend LLM handoff with DB models, gateway internals, edge agent details
- `apps/api/` — backend Python source (do not modify)
- `apps/cctv-edge/` — edge agent Python source (do not modify)
- `docs/runbooks/` — backend operational runbooks

## Your Scope

You own:

- `apps/web/` — Next.js app, React components, Tailwind styling
- Frontend routes, layouts, pages
- Camera grid and tile components
- Admin UI screens
- Viewer-only LiveKit subscription components (when ready)

You do NOT own:

- Backend API code (`apps/api/`)
- Edge agent code (`apps/cctv-edge/`)
- Database models or migrations
- Security decisions, token minting, audit integrity
- Gateway control or media publishing

## Tech Stack

- **Framework:** Next.js (App Router)
- **Styling:** Tailwind CSS
- **Components:** shadcn/ui
- **Icons:** Lucide
- **Language:** TypeScript
- **Video (later):** LiveKit JS SDK (subscriber-only)

## Local Development

### Backend Setup

The backend must be running locally for the frontend to work:

```powershell
cd apps/api
$env:PYTHONPATH = "src"
$env:ENVIRONMENT = "development"
$env:DEV_AUTH_ENABLED = "true"
python -m uvicorn cctv_api.main:app --reload --port 8000
```

### Frontend API Client

All API calls go to same-origin `/api/v1/*`. In local dev, proxy to `http://localhost:8000`.

For dev auth, send this header on every request:

```
X-Dev-Auth: admin@example.com
```

This gives you admin role. For viewer-only testing, use a non-admin email.

### Key API Endpoints To Start With

| Endpoint | Use |
|---|---|
| `GET /api/v1/me` | Bootstrap: get user identity, roles, permissions |
| `GET /api/v1/cameras` | Camera list for dashboard grid |
| `GET /api/v1/cameras/events` | SSE stream for live camera status updates |
| `GET /api/v1/cameras/{id}/view-token` | Get LiveKit viewer token (wire later) |
| `GET /api/v1/admin/audit` | Audit log viewer |
| `POST /api/v1/admin/cameras` | Create camera form |
| `POST /api/v1/admin/gateways` | Create gateway form |

See `docs/frontend/BACKEND_STATUS.md` for the full list with request/response shapes.

## First Milestone: Frontend MVP Shell

Build these in order:

1. **Next.js project setup** — App Router, Tailwind, shadcn/ui, TypeScript
2. **API client** — fetch wrapper with dev-auth header, error handling for Problem Details
3. **Auth-aware layout** — call `/api/v1/me`, show user identity, gate admin nav
4. **Camera dashboard** — grid from `/api/v1/cameras`, status badges from SSE events
5. **Placeholder video tile** — mock player card with camera name and status (real LiveKit later)
6. **Admin camera page** — create camera, grant/revoke ACL, disable camera
7. **Admin gateway page** — create gateway, assign cameras, disable gateway
8. **Audit log page** — paginated list with action filter

## Critical Rules

- **Browser is viewer-only** — never import `getUserMedia`, `MediaRecorder`, or LiveKit publisher SDK
- **No auth tokens in localStorage** — use session cookies only
- **All data from `/api/v1/*`** — never call the database, LiveKit admin API, or gateway endpoints directly
- **Error format is RFC 9457 Problem Details** — handle `status`, `detail`, `title` fields
- **Do not modify files outside `apps/web/` and `docs/frontend/`**
- **Camera online/offline status comes from SSE** — not from publish-state or command-queue internals
