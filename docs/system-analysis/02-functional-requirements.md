# 02 - Functional Requirements

## Status Labels

`Existing`, `Partially Existing`, `Missing`, and `Needs Team Confirmation` are based on repository evidence.

## Authentication, Sessions, And User Identity

| ID | Requirement | Module | Actor | Priority | Current status |
|---|---|---|---|---|---|
| FR-001 | The system shall require authenticated identity for browser API routes except public health and explicitly internal monitor routes. | Auth | Viewer/Admin | High | Existing |
| FR-002 | The system shall support Cloudflare Access JWT verification for staging/production. | Auth | Viewer/Admin | High | Existing |
| FR-003 | The system shall support development-only header auth when `APP_ENV=development` and `ALLOW_DEV_AUTH=true`. | Auth | Developer | Medium | Existing |
| FR-004 | The system shall create and validate signed session cookies and CSRF tokens for browser sessions. | Sessions | Viewer/Admin | High | Existing |
| FR-005 | The system shall list active sessions for the authenticated user. | Sessions | Viewer/Admin | Medium | Existing |
| FR-006 | The system shall allow a user to revoke owned sessions and allow admins to revoke any session. | Sessions | Viewer/Admin | Medium | Existing |

## Viewer Camera Access

| ID | Requirement | Module | Actor | Priority | Current status |
|---|---|---|---|---|---|
| FR-007 | The system shall list only non-retired cameras with active ACLs for the authenticated viewer. | Cameras | Viewer | High | Existing |
| FR-008 | The system shall issue short-lived LiveKit subscriber tokens only for cameras the viewer may access. | Streaming | Viewer | High | Existing |
| FR-009 | The system shall reject viewer token requests for disabled users, missing cameras, retired cameras, or missing ACLs. | Streaming | Viewer | High | Existing |
| FR-010 | The system shall expose camera status events to authorized viewers. | Camera events | Viewer | Medium | Existing |
| FR-011 | The frontend shall display camera grid layouts, states, and fullscreen viewing. | Frontend | Viewer | High | Missing |

## Admin User Management

| ID | Requirement | Module | Actor | Priority | Current status |
|---|---|---|---|---|---|
| FR-012 | The system shall allow admins to list users with roles and disabled state. | Admin users | Admin | High | Existing |
| FR-013 | The system shall allow admins to grant and revoke roles. | Admin users | Admin | High | Existing |
| FR-014 | The system shall allow admins to disable users, revoke sessions, and remove LiveKit viewer participants. | Admin users | Admin | High | Existing |
| FR-015 | The system shall record admin-mediated MFA reset evidence. | Admin users | Admin | Medium | Existing |
| FR-016 | The system shall automate GitHub organization user invite flow and prepare local Panoptix roles. | Admin users | Admin | Medium | Existing |

## Camera Management

| ID | Requirement | Module | Actor | Priority | Current status |
|---|---|---|---|---|---|
| FR-017 | The system shall allow admins to create cameras with display name, source type, and LiveKit room name. | Cameras | Admin | High | Existing |
| FR-018 | The system shall prevent duplicate LiveKit room names. | Cameras | Admin | High | Existing |
| FR-019 | The system shall allow admins to grant and revoke user-camera ACLs. | Cameras | Admin | High | Existing |
| FR-020 | The system shall allow admins to retire cameras and remove active viewer participants. | Cameras | Admin | High | Existing |
| FR-021 | The system shall support camera update/rename and re-enable flows after creation or retirement. | Cameras | Admin | Medium | Existing |
| FR-022 | The system shall onboard real camera hardware and validate RTSP publishing. | Cameras | Admin/Gateway | High | Partially Existing |

## Gateway And Edge Agent

| ID | Requirement | Module | Actor | Priority | Current status |
|---|---|---|---|---|---|
| FR-023 | The system shall allow admins to create gateways, update gateway metadata, and return a one-time service token on creation. | Gateway | Admin | High | Existing |
| FR-024 | The system shall store only hashed gateway service tokens. | Gateway | Admin/Gateway | High | Existing |
| FR-025 | The system shall allow admins to disable and re-enable gateways, and remove active publisher participants on disable. | Gateway | Admin | High | Existing |
| FR-026 | The system shall allow admins to rotate gateway credentials. | Gateway | Admin | High | Existing |
| FR-027 | The system shall allow admins to grant and revoke gateway-camera assignments. | Gateway | Admin | High | Existing |
| FR-028 | The gateway shall authenticate to backend HTTP and WebSocket routes using gateway identity. | Gateway | Gateway | High | Existing |
| FR-029 | The edge agent shall verify signed commands before executing them. | Edge agent | Gateway | High | Existing |
| FR-030 | The edge agent shall publish real camera video to LiveKit in production. | Edge agent | Gateway | High | Partially Existing |

## Gateway Command Queue

| ID | Requirement | Module | Actor | Priority | Current status |
|---|---|---|---|---|---|
| FR-031 | The system shall enqueue gateway commands with kind, payload, expiry, and status. | Commands | Admin/System | High | Existing |
| FR-032 | The system shall deliver pending commands through WebSocket and heartbeat fallback. | Commands | Gateway | High | Existing |
| FR-033 | The system shall allow admins to list and filter gateway commands. | Commands | Admin | Medium | Existing |
| FR-034 | The system shall allow admins to cancel pending commands. | Commands | Admin | Medium | Existing |
| FR-035 | The system shall expire stale pending commands. | Commands | Admin/System | Medium | Existing |

## Audit, Compliance, And Operations

| ID | Requirement | Module | Actor | Priority | Current status |
|---|---|---|---|---|---|
| FR-036 | The system shall write HMAC-chained audit records for sensitive actions. | Audit | System | High | Existing |
| FR-037 | The system shall allow admins to list, verify, and export scrubbed audit records. | Audit | Admin | High | Existing |
| FR-038 | The system shall support bounded break-glass open/close with audit and rotation checklist. | Break-glass | Admin | High | Existing |
| FR-039 | The system shall expose basic and deep health endpoints. | Operations | Admin/Platform | Medium | Existing |
| FR-040 | The system shall run maintenance cleanup for stale commands and due publish stops. | Operations | Admin/System | Medium | Existing |
| FR-041 | The system shall export DPA artifacts and record signage attestations. | Compliance | Admin | Medium | Existing |
| FR-042 | The system shall manage DSR requests end to end. | Compliance | Admin/Auditor | Medium | Partially Existing |
| FR-043 | The system shall return backup status from `/api/v1/admin/backups/status`. | Operations | Admin | Medium | Existing |

