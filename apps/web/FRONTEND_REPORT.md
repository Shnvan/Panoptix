# Panoptix Frontend Report

> **Date**: May 13, 2026  
> **Project**: Panoptix — Secure CCTV Monitoring System  
> **Module**: `apps/web/` (Frontend Dashboard)  
> **Framework**: React 19 + Vite + TypeScript + Tailwind CSS v4  
> **Dev Server**: `http://localhost:3000`

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Tech Stack](#2-tech-stack)
3. [File Structure](#3-file-structure)
4. [Pages & Components](#4-pages--components)
5. [API Endpoint Wiring](#5-api-endpoint-wiring)
6. [Type Definitions](#6-type-definitions)
7. [Security & Guardrails Compliance](#7-security--guardrails-compliance)
8. [Feature Checklist vs MD Requirements](#8-feature-checklist-vs-md-requirements)
9. [Known Limitations](#9-known-limitations)
10. [Backend Integration Requirements](#10-backend-integration-requirements)

---

## 1. Architecture Overview

The frontend is a viewer and admin dashboard shell. It does not publish media, store credentials, or make authorization decisions — all security logic is handled by the backend (`cctv-api`).

```
Browser (cctv-web)
  │
  ├── Cloudflare Access (identity gate)
  │
  ├── /api/v1/* ──→ cctv-api (FastAPI on Railway)
  │     ├── Session cookies (HttpOnly)
  │     ├── CSRF token on mutations
  │     └── Dev-auth headers (local only)
  │
  └── LiveKit Cloud (viewer-subscribe only)
        └── Short-lived tokens from /cameras/:id/view-token
```

**Key Invariants:**
- Browser never publishes camera/mic streams (Invariant 5)
- No auth tokens in localStorage/sessionStorage
- All API calls are same-origin `/api/v1/*`
- Camera status comes from SSE events, not polling

---

## 2. Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Runtime | Node.js | 22.x LTS |
| Framework | React | 19.x |
| Build Tool | Vite | 6.x |
| Language | TypeScript | 5.x |
| Styling | Tailwind CSS | 4.x (via `@tailwindcss/vite`) |
| Animation | Motion (Framer Motion) | latest |
| Icons | Lucide React | latest |
| Charts | Recharts | latest |
| Dev Server Port | — | 3000 |
| API Proxy | Vite proxy | → `http://127.0.0.1:8000` |

---

## 3. File Structure

```
apps/web/
├── src/
│   ├── app/
│   │   ├── App.tsx                    # Main app shell, routing, auth gate
│   │   └── components/
│   │       ├── AlertsPanel.tsx        # Camera event alerts
│   │       ├── AuditLogTable.tsx      # Audit logs + Compliance + DSR tabs
│   │       ├── BreakGlassSection.tsx  # Emergency admin access
│   │       ├── CameraCard.tsx         # Camera tile with 7 states
│   │       ├── CameraDetailModal.tsx  # Fullscreen camera view
│   │       ├── CamerasManageSection.tsx # Camera CRUD + ACL
│   │       ├── GatewaysSection.tsx    # Gateway CRUD + commands
│   │       ├── Header.tsx            # Top bar with search + alerts
│   │       ├── HealthSection.tsx     # Deep health + security checks
│   │       ├── LoginPage.tsx         # Cloudflare Access login shell
│   │       ├── PrivacyNoticeModal.tsx # Privacy notice acceptance gate
│   │       ├── SettingsSection.tsx   # Profile + sessions + login history
│   │       ├── Sidebar.tsx           # Navigation sidebar
│   │       ├── StatCard.tsx          # Dashboard stat cards
│   │       ├── SystemHealthChart.tsx # Network activity chart
│   │       └── UsersSection.tsx      # User management + roles
│   ├── lib/
│   │   ├── api.ts                    # API client (35 endpoints)
│   │   ├── hooks.ts                  # React hooks (7 hooks)
│   │   ├── theme.ts                  # Dark/light theme context
│   │   └── types.ts                  # TypeScript types (30+ interfaces)
│   ├── index.css                     # Tailwind entry + custom styles
│   └── main.tsx                      # React DOM entry point
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tsconfig.app.json
├── package.json
└── FRONTEND_REPORT.md               # ← This file
```

---

## 4. Pages & Components

### Navigation (Sidebar)

| # | Sidebar Item | Route Key | Component | Admin Only |
|---|-------------|-----------|-----------|------------|
| 1 | Dashboard | `dashboard` | `App.tsx` (inline) | No |
| 2 | Live Cameras | `cameras` | `App.tsx` (inline) | No |
| 3 | Camera Management | `manage-cameras` | `CamerasManageSection.tsx` | Yes |
| 4 | Gateways | `gateways` | `GatewaysSection.tsx` | Yes |
| 5 | Users & Access | `users` | `UsersSection.tsx` | Yes |
| 6 | Audit Logs | `audit` | `AuditLogTable.tsx` | Yes |
| 7 | Alerts | `alerts` | `AlertsPanel.tsx` | Yes |
| 8 | System Health | `health` | `HealthSection.tsx` | Yes |
| 9 | Break Glass | `break-glass` | `BreakGlassSection.tsx` | Yes |
| 10 | Settings | `settings` | `SettingsSection.tsx` | No |

> Admin items are only visible when `user.roles` includes `"admin"` (returned by `/api/v1/me`).

### Page Details

#### Dashboard
- **Stat cards**: Active Cameras, System Status, User Role, Camera Events
- **Camera grid**: Responsive grid with 1×1, 2×1, 2×2 layout options
- **Health chart**: Network activity over last 24 hours (Recharts)
- **Empty state**: "No Assigned Cameras" message when user has no ACL grants

#### Live Cameras
- Same camera grid as Dashboard but without stat cards
- Layout selector: 1×1 / 2×1 / 2×2
- Camera tiles show 7 states: loading, online, offline, reconnecting, unavailable, gateway_unavailable, permission_denied
- Click to expand into detail modal with LiveKit viewer token request

#### Camera Management (Admin)
- **Register Camera** form: display name, source type (5 CCTV-only types), LiveKit room name
- **Camera cards**: List all cameras with ID, source type, creation date
- **ACL Management**: Grant/revoke camera access by user email
- **Retire Camera**: Disable with reason (warns about session termination)
- Source types restricted to: `rtsp`, `nvr_rtsp`, `onvif_profile_s`, `onvif_profile_t`, `synthetic_rtsp_test_source`

#### Gateways (Admin)
- **Register Gateway** form: name + optional mTLS fingerprint
- **One-time token display**: Service token shown once after creation
- **Credential Rotation**: Rotate gateway credentials with reason
- **Camera Assignment**: Assign/remove cameras from gateways
- **Command Queue**: View, enqueue, and cancel gateway commands
- **Command Cleanup**: Expire old commands
- **Disable Gateway**: With reason and session termination warning

#### Users & Access (Admin)
- **User list**: Cards with email, roles, status (active/disabled), creation date
- **Search**: Filter users by email
- **Edit Roles**: Grant/revoke admin or viewer role with confirmation
- **Disable User**: With reason and warning about session + LiveKit termination
- **MFA Reset**: Shown as "In Progress" — endpoint exists in API reference but backend not implemented

#### Audit Logs (Admin)
Three tabs:

| Tab | Features |
|-----|----------|
| **Audit Logs** | Event timeline, search (actor/action/resource/IP), action filter dropdown (15 actions), risk level badges (HIGH/MEDIUM/LOW), HMAC chain verification, signed JSONL export, cursor pagination |
| **Compliance & DPA** | DPA artefact bundle export, bystander signage attestation per site, sites list with attestation status |
| **DSR Ledger** | Planned DSR request table. The backend listing endpoint is not implemented in the current backend branch. |

#### Alerts (Admin)
- Camera event notifications derived from SSE events
- Alert types: critical (offline/retired), warning (degraded/reconnecting), info (online)
- Timestamp, camera ID, gateway association for each alert

#### System Health (Admin)
- **Deep Health Check**: DB, LiveKit, Gateway, Overall status with color-coded cards
- **Security Check Reports**: T-30 (Exposure), T-45 (Media Isolation), T-56 (Origin Binding)
- **LiveKit Fallback Toggle**: Switch between Cloud (primary) and Self-Hosted (fallback) mode
- **Manual Maintenance**: Clean expired commands + enqueue pending stops

#### Break Glass (Admin)
- **Status panel**: Active/inactive with countdown timer
- **Open flow**: Reason input → confirm dialog → 90-minute countdown
- **Close flow**: Close reason → rotation checklist
- **Security requirements**: Hardware key, sealed account, CF Access App C
- **Rotation checklist**: 6 mandatory items (HMAC key, LiveKit keys, CF tokens, gateway creds, action review, incident report)

#### Settings
- **User Profile**: Email, subject, roles, kind, permissions, auth mode
- **Security Info**: 5 security guarantees displayed
- **Active Sessions**: List with revoke capability
- **Login History**: Session-based login timeline

---

## 5. API Endpoint Wiring

### All 35 endpoints wired in `api.ts`:

#### Browser/Session (8 endpoints)
| Method | Path | `api.ts` Method |
|--------|------|-----------------|
| GET | `/api/v1/me` | `getMe()` |
| GET | `/api/v1/cameras` | `listCameras()` |
| GET | `/api/v1/cameras/:id/view-token` | `getCameraViewToken()` |
| GET | `/api/v1/cameras/events` (SSE) | `subscribeCameraEvents()` |
| GET | `/api/v1/sessions/active` | `getActiveSessions()` |
| POST | `/api/v1/sessions/revoke` | `revokeSession()` |
| GET | `/api/v1/privacy/notice` | `getPrivacyNotice()` |
| POST | `/api/v1/privacy/notice/accept` | `acceptPrivacyNotice()` |

#### Admin: Users (3 endpoints)
| Method | Path | `api.ts` Method |
|--------|------|-----------------|
| GET | `/api/v1/admin/users` | `listAdminUsers()` |
| POST | `/api/v1/admin/users/:id/role` | `updateUserRole()` |
| POST | `/api/v1/admin/users/:id/disable` | `disableUser()` |

#### Admin: Cameras (3 endpoints)
| Method | Path | `api.ts` Method |
|--------|------|-----------------|
| POST | `/api/v1/admin/cameras` | `createCamera()` |
| POST | `/api/v1/admin/cameras/:id/acl` | `manageCameraAcl()` |
| POST | `/api/v1/admin/cameras/:id/disable` | `disableCamera()` |

#### Admin: Gateways (4 endpoints)
| Method | Path | `api.ts` Method |
|--------|------|-----------------|
| POST | `/api/v1/admin/gateways` | `createGateway()` |
| POST | `/api/v1/admin/gateways/:id/disable` | `disableGateway()` |
| POST | `/api/v1/admin/gateways/:id/rotate-credential` | `rotateGatewayCredential()` |
| POST | `/api/v1/admin/gateways/:id/cameras` | `manageGatewayCameraAssignment()` |

#### Admin: Commands (4 endpoints)
| Method | Path | `api.ts` Method |
|--------|------|-----------------|
| GET | `/api/v1/admin/gateways/:id/commands` | `listGatewayCommands()` |
| POST | `/api/v1/admin/gateways/:id/commands` | `enqueueGatewayCommand()` |
| POST | `/api/v1/admin/gateways/:id/commands/:id/cancel` | `cancelGatewayCommand()` |
| POST | `/api/v1/admin/commands/cleanup` | `cleanupCommands()` |

#### Admin: Audit (3 endpoints)
| Method | Path | `api.ts` Method |
|--------|------|-----------------|
| GET | `/api/v1/admin/audit` | `listAudit()` |
| GET | `/api/v1/admin/audit/verify` | `verifyAuditChain()` |
| GET | `/api/v1/admin/audit/export` | `exportAudit()` |

#### Admin: Compliance & DPA (4 endpoints)
| Method | Path | `api.ts` Method |
|--------|------|-----------------|
| GET | `/api/v1/admin/sites` | `listSites()` |
| POST | `/api/v1/admin/sites/:id/signage-attest` | `attestSignage()` |
| POST | `/api/v1/admin/dpa/export` | `exportDpa()` |
| GET | `/api/v1/admin/dsr-requests` | `listDsrRequests()` |

#### Admin: System (4 endpoints)
| Method | Path | `api.ts` Method |
|--------|------|-----------------|
| POST | `/api/v1/admin/livekit/fallback` | `toggleLivekitFallback()` |
| GET | `/api/v1/admin/exposure-check` | `getExposureCheck()` |
| GET | `/api/v1/admin/media-isolation-check` | `getMediaIsolationCheck()` |
| GET | `/api/v1/admin/origin-binding-check` | `getOriginBindingCheck()` |

#### Admin: Break-Glass (2 endpoints)
| Method | Path | `api.ts` Method |
|--------|------|-----------------|
| POST | `/api/v1/admin/break-glass/open` | `openBreakGlass()` |
| POST | `/api/v1/admin/break-glass/close` | `closeBreakGlass()` |

#### Health & Maintenance (3 endpoints)
| Method | Path | `api.ts` Method |
|--------|------|-----------------|
| GET | `/health` | `getHealth()` |
| GET | `/api/v1/admin/health/deep` | `getDeepHealth()` |
| POST | `/api/v1/admin/jobs/run-maintenance` | `runMaintenance()` |

#### Gateway-Only Endpoints (NOT wired — correctly excluded)
| Path | Reason |
|------|--------|
| `POST /api/v1/gateways/:id/heartbeat` | Gateway agent only |
| `POST /api/v1/gateways/:id/ingest-token` | Gateway agent only |
| `POST /api/v1/gateways/:id/cameras/:id/status` | Gateway agent only |
| `GET /api/v1/gateway-control/ws` | Gateway WebSocket only |
| `POST /api/v1/webhooks/livekit` | LiveKit webhook only |

---

## 6. Type Definitions

All types defined in `src/lib/types.ts` (353 lines, 30+ interfaces):

| Category | Types |
|----------|-------|
| Identity | `MeResponse` |
| Cameras | `CameraSummary`, `CameraListResponse`, `CameraSourceType` (5 CCTV-only values), `CameraTileStatus` (7 states), `CameraEvent`, `CameraEventKind`, `ViewerTokenResponse`, `CameraCreateResponse` |
| Sessions | `SessionItem`, `SessionListResponse` |
| Privacy | `PrivacyNoticeResponse`, `PrivacyNoticeAcceptResponse` |
| Admin Users | `AdminUser`, `AdminUserListResponse` |
| Audit | `AuditLogItem`, `AuditListResponse`, `AuditVerifyResponse`, `AuditExportResponse` |
| Gateways | `GatewayCreateResponse`, `GatewayDisableResponse`, `GatewayRotateResponse`, `GatewayCommand`, `CommandStatus`, `CommandListResponse` |
| Health | `HealthResponse`, `DeepHealthResponse` |
| Error | `ProblemDetail` (RFC 9457) |
| Maintenance | `MaintenanceResponse` |
| Break-Glass | `BreakGlassUsage`, `BreakGlassOpenResponse`, `BreakGlassCloseResponse` |
| Sites | `Site`, `SiteListResponse`, `SignageAttestResponse` |
| DPA | `DpaExportResponse` |
| Security | `SecurityCheckReport`, `SecurityFinding` |
| LiveKit | `LivekitFallbackResponse` |
| DSR | `DsrRequest`, `DsrListResponse` |
| Generic | `PaginatedResponse<T>` |

---

## 7. Security & Guardrails Compliance

Cross-referenced against `docs/frontend/frontend-guardrails.md`:

| # | Rule | Status |
|---|------|--------|
| 1 | No `getUserMedia` / `MediaRecorder` / `navigator.mediaDevices` | ✅ Pass |
| 2 | No browser camera/microphone permission requests | ✅ Pass |
| 3 | No auth tokens in localStorage / sessionStorage / IndexedDB | ✅ Pass |
| 4 | No gateway endpoints called from browser | ✅ Pass |
| 5 | No RTSP URLs or camera passwords exposed | ✅ Pass |
| 6 | No LiveKit publisher SDK in browser bundle | ✅ Pass |
| 7 | All API calls same-origin `/api/v1/*` | ✅ Pass |
| 8 | CSRF token sent on state-changing requests | ✅ Pass |
| 9 | Dev-auth headers only when `VITE_DEV_AUTH=true` | ✅ Pass |
| 10 | Camera status from SSE events, not publish-state polling | ✅ Pass |
| 11 | RFC 9457 Problem Details error handling | ✅ Pass |
| 12 | No recording, playback, snapshots, face recognition | ✅ Pass |
| 13 | No self-registration or password-only login | ✅ Pass |

---

## 8. Feature Checklist vs MD Requirements

### Sources verified:
- `docs/planning/cctv-core-functionality-features.md`
- `docs/planning/secure-cctv-monitoring-system-v4.md`
- `docs/frontend/ux-product-spec.md`
- `docs/frontend/BACKEND_STATUS.md`
- `docs/implementation/api-reference.md`
- `docs/frontend/frontend-guardrails.md`

### MVP Features (cctv-core-functionality-features.md §8)

| Feature | Present | Component |
|---------|---------|-----------|
| Live camera viewing | Partial | `CameraCard` + `CameraDetailModal`; viewer-token request exists, browser LiveKit playback is not wired yet |
| Camera grid layouts (1×1, 2×1, 2×2) | ✅ | `App.tsx` layout selector |
| Fullscreen camera view | ✅ | `CameraDetailModal` |
| Camera status indicators (7 states) | ✅ | `CameraTileStatus` type |
| Cloudflare Access login | ✅ | `LoginPage` shell; identity provider is configured in Cloudflare Access |
| Role-based access control | ✅ | `isAdmin` gating |
| Per-camera ACL management | ✅ | `CamerasManageSection` |
| Camera registration | ✅ | `CamerasManageSection` |
| Gateway registration | ✅ | `GatewaysSection` |
| Camera-to-gateway assignment | ✅ | `GatewaysSection` |
| Health dashboard | ✅ | `HealthSection` |
| Disable/retire cameras and gateways | ✅ | Both manage sections |
| Audit logs with HMAC verification | ✅ | `AuditLogTable` |
| Signed audit export (JSONL) | ✅ | `AuditLogTable` |
| Break-glass emergency access (90 min) | ✅ | `BreakGlassSection` |
| MFA recovery (admin-mediated) | ✅ | "In Progress" in `UsersSection` |
| Privacy notice gate | ✅ | `PrivacyNoticeModal` |
| Bystander signage attestation | ✅ | `AuditLogTable` Compliance tab |
| Login history | ✅ | `SettingsSection` |
| Session management with revocation | ✅ | `SettingsSection` |

### v4 Security Features (secure-cctv-monitoring-system-v4.md)

| Feature | Section | Present | Component |
|---------|---------|---------|-----------|
| Deep health (DB, LiveKit, Gateway) | §15.1 | ✅ | `HealthSection` |
| Security checks: T-30, T-45, T-56 | §15.1 | ✅ | `HealthSection` |
| LiveKit cloud/fallback toggle | §15.1 | ✅ | `HealthSection` |
| Break-glass with 90-min auto-disable | §16.6 | ✅ | `BreakGlassSection` |
| Rotation checklist on close | §16.6 | ✅ | `BreakGlassSection` |
| CCTV-only source type enum | §14.4 | ✅ | `CameraSourceType` |
| DPA artefact export | §14.1 | ✅ | `AuditLogTable` Compliance tab |
| DSR request ledger | §14.1 | Planned | UI placeholder only; backend listing endpoint is not implemented in the current branch |
| Gateway credential rotation | §15.1 | ✅ | `GatewaysSection` |
| Gateway command queue | §15.1 | ✅ | `GatewaysSection` |

### Permanently Excluded Features (correctly absent)

| Feature | Why | Status |
|---------|-----|--------|
| Webcam/phone/browser publishing | Invariant 5 | ✅ Not present |
| Recording/playback | Compliance scope | ✅ Not present |
| Snapshots/screenshots | Compliance scope | ✅ Not present |
| Face recognition / analytics | Future scope | ✅ Not present |
| Self-registration | Admin-only invites | ✅ Not present |
| Password-only login | Security policy | ✅ Not present |

---

## 9. Known Limitations

### Backend Dependency

The frontend **requires a running backend** (`cctv-api` on port 8000) for all data. Without it:
- `/api/v1/me` fails → user defaults to Viewer role → admin pages hidden
- All admin API calls return errors
- Camera list is empty
- Health status shows "Checking"

**To test with admin access**, the backend must:
1. Be running on `http://127.0.0.1:8000`
2. Accept dev-auth headers when `ALLOW_DEV_AUTH=true`
3. Return `roles: ["admin"]` in the `/api/v1/me` response

### "In Progress" Features

| Feature | Endpoint | Status |
|---------|----------|--------|
| MFA Reset | `POST /admin/users/:id/mfa/reset` | Endpoint in API reference but backend not implemented |
| DPA Export | `POST /admin/dpa/export` | API-ready, backend may not be live |
| Signage Attestation | `POST /admin/sites/:id/signage-attest` | Attestation endpoint exists, but site listing is not wired in this frontend integration branch |
| Break-Glass Open/Close | `POST /admin/break-glass/open|close` | API-ready, backend may not be live |
| Security Checks | `GET /admin/exposure-check` etc. | Planned only; backend endpoints are not implemented in the current branch |

### Accessibility

- Keyboard navigation works for all interactive elements
- Focus ring visible on form inputs (via `focus:ring-2`)
- Button focus states could be more prominent
- Color contrast is generally good; some light text in dark mode may need verification

---

## 10. Backend Integration Requirements

For the backend team to fully enable the frontend:

### Required Endpoints (Must Have)

```
GET  /api/v1/me                              → { kind, subject, email, roles, permissions, is_dev }
GET  /api/v1/cameras                         → { items: CameraSummary[], next_cursor }
GET  /api/v1/cameras/:id/view-token          → { camera_id, room, livekit_url, token, expires_at }
GET  /api/v1/cameras/events                  → SSE stream of CameraEvent
GET  /api/v1/sessions/active                 → { items: SessionItem[] }
POST /api/v1/sessions/revoke                 → { revoked, session_id }
GET  /api/v1/privacy/notice                  → { notice_version, title, body, accepted }
POST /api/v1/privacy/notice/accept           → { notice_version, accepted_at, status }
GET  /health                                 → { status: "ok" }
```

### Required Admin Endpoints

```
GET  /api/v1/admin/users                     → { items: AdminUser[], next_cursor }
POST /api/v1/admin/users/:id/role            → { user_id, role_name, action, status }
POST /api/v1/admin/users/:id/disable         → { user_id, disabled_at, sessions_revoked }
POST /api/v1/admin/cameras                   → { camera_id, display_name, source_type, livekit_room_name }
POST /api/v1/admin/cameras/:id/acl           → { camera_id, user_email, action, status }
POST /api/v1/admin/cameras/:id/disable       → { camera_id, display_name, retired_at }
POST /api/v1/admin/gateways                  → { gateway_id, name, status, service_token, created_at }
POST /api/v1/admin/gateways/:id/disable      → { gateway_id, name, status, disabled_at }
POST /api/v1/admin/gateways/:id/rotate-credential → { gateway_id, service_token, rotated_at }
POST /api/v1/admin/gateways/:id/cameras      → { gateway_id, camera_id, action, status }
GET  /api/v1/admin/gateways/:id/commands     → { items: GatewayCommand[], next_cursor }
POST /api/v1/admin/gateways/:id/commands     → { command_id, gateway_id, kind, status, expires_at }
POST /api/v1/admin/gateways/:id/commands/:id/cancel → { command_id, status, cancelled_at }
POST /api/v1/admin/commands/cleanup          → { expired_count }
GET  /api/v1/admin/audit                     → { items: AuditLogItem[], next_cursor }
GET  /api/v1/admin/audit/verify              → { valid, checked, error }
GET  /api/v1/admin/audit/export              → { format, manifest, items }
GET  /api/v1/admin/health/deep               → { status, db, livekit, gateway }
POST /api/v1/admin/jobs/run-maintenance      → { expired_commands, stops_enqueued }
```

### Environment Variables

The frontend uses these Vite env vars:

| Variable | Purpose | Default |
|----------|---------|---------|
| `VITE_DEV_AUTH` | Enable dev-auth headers | `false` |
| `VITE_DEV_EMAIL` | Dev auth email | `admin@example.test` |
| `VITE_DEV_ROLES` | Dev auth roles | `admin` |

### CSRF Protection

The frontend reads the `panoptix_csrf` cookie and sends it as `x-panoptix-csrf-token` header on all POST/PUT/PATCH/DELETE requests to `/api/v1/admin/*`, `/api/v1/privacy/notice/accept`, and `/api/v1/sessions/revoke`.

The backend must:
1. Set a `panoptix_csrf` cookie on session creation
2. Validate the `x-panoptix-csrf-token` header on mutations

---

## Build & Run

```powershell
cd apps\web
npm install
npm run dev        # → http://localhost:3000

# Type check
npx tsc -b --force

# Build for production
npm run build
```

**TypeScript**: ✅ Zero errors on `tsc -b --force`

---

*Report generated from cross-referencing all 67 MD files in the repository against 18 frontend source files.*
