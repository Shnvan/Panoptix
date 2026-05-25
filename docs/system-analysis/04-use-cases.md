# 04 - Use Cases

## Actors

| Actor | Description | Status |
|---|---|---|
| Viewer | Authenticated user with camera ACLs | Existing |
| Admin | User with `admin` role | Existing |
| Gateway | Edge gateway machine identity | Existing |
| LiveKit | External media service and webhook sender | Existing integration |
| Auditor | Audit/compliance reader persona | Needs Team Confirmation |

## UC-001 - Authenticate And Bootstrap App

| Field | Details |
|---|---|
| Actor | Viewer/Admin |
| Goal | Access the app with a verified identity and retrieve principal details. |
| Preconditions | Cloudflare Access or local dev auth is configured. |
| Basic flow | User opens app; backend validates identity; backend creates/refreshes session; frontend calls `GET /api/v1/me`; backend returns principal details. |
| Alternative flows | In development, approved dev headers may supply identity. |
| Exceptions | Missing/invalid identity returns authentication error; dev auth outside development is rejected. |
| Postconditions | User identity and role information are available to the frontend. |
| Related files/routes | `security/cloudflare_access.py`, `security/dependencies.py`, `GET /api/v1/me`, `apps/api/tests/test_security.py` |

## UC-002 - View Assigned Cameras

| Field | Details |
|---|---|
| Actor | Viewer |
| Goal | See cameras assigned to the viewer. |
| Preconditions | User is authenticated and has active `camera_acl` rows. |
| Basic flow | Viewer calls `GET /api/v1/cameras`; backend joins cameras and ACLs; retired or revoked rows are excluded; response returns paginated camera summaries. |
| Alternative flows | Empty response when no cameras are assigned. |
| Exceptions | Unauthenticated request is rejected. |
| Postconditions | Frontend can render assigned camera list/grid. |
| Related files/routes | `api/router.py`, `Camera`, `CameraAcl`, `apps/api/tests/test_cameras.py` |

## UC-003 - Start Viewing A Camera

| Field | Details |
|---|---|
| Actor | Viewer |
| Goal | Receive a LiveKit subscriber token for an assigned camera. |
| Preconditions | Viewer has active ACL; camera is not retired; LiveKit config is valid. |
| Basic flow | Viewer calls `GET /api/v1/cameras/{camera_id}/view-token`; backend checks user, camera, ACL, rate limit; backend mints subscriber token and records stream grant. |
| Alternative flows | LiveKit webhooks may trigger gateway start-publish commands when a participant joins. |
| Exceptions | Disabled user, missing camera, missing ACL, invalid LiveKit config, or rate limit returns an error. |
| Postconditions | Viewer can connect to LiveKit as subscriber only. |
| Related files/routes | `security/livekit_tokens.py`, `security/stream_access.py`, `GET /api/v1/cameras/{camera_id}/view-token`, `test_livekit_tokens.py` |

## UC-004 - Manage Camera ACL

| Field | Details |
|---|---|
| Actor | Admin |
| Goal | Grant or revoke a user's access to a camera. |
| Preconditions | Admin is authenticated; camera exists. |
| Basic flow | Admin submits `POST /api/v1/admin/cameras/{camera_id}/acl`; backend validates action and camera; user row is found or created; ACL is granted or revoked; audit is written. |
| Alternative flows | Revoke marks active ACL with `revoked_at`; historical rows remain. |
| Exceptions | Invalid action, missing camera, duplicate active ACL, or missing active ACL returns error. |
| Postconditions | Viewer access changes on subsequent camera list/token requests. |
| Related files/routes | `CameraAcl`, `POST /api/v1/admin/cameras/{camera_id}/acl`, `test_cameras.py` |

## UC-005 - Register And Assign Gateway

| Field | Details |
|---|---|
| Actor | Admin |
| Goal | Add a gateway and assign cameras it may publish. |
| Preconditions | Admin role is present; camera rows exist for assignment. |
| Basic flow | Admin creates gateway; backend returns one-time service token and stores hash; admin grants gateway-camera assignment. |
| Alternative flows | Credential rotation can issue a new one-time service token. |
| Exceptions | Missing camera/gateway, duplicate assignment, invalid action, or retired camera returns error. |
| Postconditions | Gateway can authenticate and request publish tokens only for assigned cameras. |
| Related files/routes | `EdgeGateway`, `GatewayCameraAssignment`, admin gateway routes, `test_admin_gateways.py`, `test_gateway_credentials.py` |

## UC-006 - Gateway Heartbeat And Command Delivery

| Field | Details |
|---|---|
| Actor | Gateway |
| Goal | Report liveness and receive pending signed commands. |
| Preconditions | Gateway has valid identity and service token/dev identity. |
| Basic flow | Gateway posts heartbeat; backend verifies gateway identity; backend updates `last_seen_at`; pending commands are signed and returned. |
| Alternative flows | Gateway may use `/api/v1/gateway-control/ws` for outbound WebSocket command channel. |
| Exceptions | Gateway mismatch, disabled gateway, or signing failure returns an error or closes WebSocket. |
| Postconditions | Gateway can execute verified pending commands and ACK results. |
| Related files/routes | `api/gateways.py`, `gateway/command_queue.py`, edge `control.py`, `commands.py`, `test_gateway.py`, `test_control.py` |

## UC-007 - Handle LiveKit Room Presence

| Field | Details |
|---|---|
| Actor | LiveKit |
| Goal | Trigger gateway publishing only while viewers are present. |
| Preconditions | LiveKit webhook secret/config is valid; camera room exists; gateway assignment exists. |
| Basic flow | LiveKit sends webhook; backend validates signature/replay; participant joined enqueues start-publish; zero viewer count or room finished schedules/enqueues stop-publish. |
| Alternative flows | Rejoin during grace cancels pending stop. |
| Exceptions | Unknown room, disabled gateway, revoked assignment, duplicate replay, stale signature, invalid body hash. |
| Postconditions | `camera_publish_states`, `gateway_command_queue`, `stream_grants`, and `camera_events` reflect workflow. |
| Related files/routes | `api/livekit_webhooks.py`, `gateway/publish_state.py`, `POST /api/v1/webhooks/livekit`, `test_livekit_webhooks.py` |

## UC-008 - Audit Review And Export

| Field | Details |
|---|---|
| Actor | Admin/Auditor |
| Goal | Review, verify, and export audit records. |
| Preconditions | Admin role; audit HMAC key configured. |
| Basic flow | Admin lists audit rows, verifies chain, or exports signed scrubbed data. |
| Alternative flows | Optional ID bounds and action filters are supported where implemented. |
| Exceptions | Placeholder/invalid audit key returns fail-closed errors. |
| Postconditions | Audit evidence is available for review. |
| Related files/routes | `security/audit.py`, `/api/v1/admin/audit*`, `test_audit.py` |

## UC-009 - Break-Glass Emergency Access

| Field | Details |
|---|---|
| Actor | Admin |
| Goal | Open and close a bounded emergency access window. |
| Preconditions | Admin role; no active unexpired break-glass window. |
| Basic flow | Admin opens window with reason; system records auto-disable time; admin closes window with reason; response returns rotation checklist. |
| Alternative flows | Expired but unclosed window can be closed. |
| Exceptions | Duplicate active window returns conflict. |
| Postconditions | Audit rows and `break_glass_usage` rows record emergency access lifecycle. |
| Related files/routes | `security/break_glass.py`, `/api/v1/admin/break-glass/*`, `test_break_glass.py` |

## UC-010 - Recommended: Complete Frontend Dashboard

| Field | Details |
|---|---|
| Actor | Viewer/Admin |
| Goal | Use implemented backend flows through a production web UI. |
| Preconditions | Frontend implementation is created in `apps/web/`. |
| Basic flow | Build dashboard, privacy notice gate, camera grid, admin screens, audit/compliance screens, and session management against documented APIs. |
| Alternative flows | Placeholder/mock UI can be used until hardware streams are available. |
| Exceptions | API errors should be rendered with user-safe messages. |
| Postconditions | MVP becomes usable by human users. |
| Related files/routes | `apps/web/README.md`, `docs/frontend/*`, `docs/implementation/api-reference.md` |
| Status | Recommended |

