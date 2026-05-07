# Database Guardrails

<!-- PE-FIX: Added database coworker guardrails to prevent cross-workstream breakage -->

This document tells the database owner what **not** to do so schema/migration work does not break backend security, frontend contracts, gateway/media flow, audit integrity, or future operations.

## Ownership boundary

Database owns:

- Postgres schema design.
- Alembic migrations.
- indexes and constraints.
- database roles/privileges.
- audit triggers and HMAC-chain storage support.
- backup/restore compatibility.

Database does **not** own frontend display contracts, backend authorization decisions, LiveKit token logic, gateway command routing, or Cloudflare Access verification.

## Do not bypass backend authorization

Do not implement database shortcuts that assume the UI is trusted.

Do not:

- Grant broad table access to frontend code.
- Create direct DB access paths for `cctv-web`.
- Let UI-selected role/camera fields directly determine access without backend policy checks.
- Replace backend RBAC/ACL checks with only database defaults.

The backend policy module remains the authority for per-request authorization.

## Do not weaken audit immutability

Do not:

- Allow `UPDATE` or `DELETE` on `audit_log`.
- Remove append-only triggers.
- Allow runtime roles to disable triggers.
- Allow runtime roles to `TRUNCATE` audit/security tables.
- Make `hmac_key_version` nullable.
- Recompute old audit hashes in place.
- Store audit HMAC plaintext keys in normal tables.

Audit chain continuity must survive key rotation.

## Do not change security-critical schema without coordination

Coordinate with the system owner before changing:

- `users`
- `roles`
- `permissions`
- `role_permissions`
- `user_roles`
- `camera_acl`
- `edge_gateways`
- `gateway_camera_assignments`
- `sessions`
- `stream_grants`
- `audit_log`
- `audit_hmac_keys`
- `webhook_replay_cache`
- `system_config`

These tables directly affect authorization, tokens, gateway control, audit, or routing behavior.

## Do not remove active-row uniqueness

Keep active-row uniqueness constraints for:

- one active camera ACL per `(user_id, camera_id)` where `revoked_at IS NULL`.
- one active gateway assignment per `(gateway_id, camera_id)` where `revoked_at IS NULL`.
- one privacy acceptance per `(user_id, notice_version)`.
- one replay-cache entry per `(provider, signature)`.

Removing these can create duplicate permissions, gateway ambiguity, or replay gaps.

## Do not add forbidden camera source types

Do not add enum values or seed data for:

- `phone`
- `webcam`
- `browser`
- `browser_publisher`
- `user_device`
- `mobile_camera`

Allowed source types remain CCTV/RTSP-oriented unless a future ADR changes the product.

## Do not store camera credentials in control-plane DB

Do not add fields for:

- RTSP username.
- RTSP password.
- full RTSP URL with credentials.
- ONVIF credentials.
- NVR admin password.

Camera credentials live only on the gateway secret/config file. The database may store camera display names, source type, gateway assignment, site, and opaque room names.

## Do not expose gateway-publish token state to users

Do not make gateway-publish token rows queryable by normal user-facing endpoints.

`stream_grants` may record metadata for replay/audit, but browser-facing API responses must never include gateway-publish JWTs or gateway secrets.

## Do not create destructive migrations casually

Do not use destructive migration steps without system-owner approval:

- dropping columns/tables.
- rewriting audit rows.
- changing enum values in place.
- deleting historical camera/gateway rows.
- converting soft-delete to hard-delete.
- changing primary keys after API work starts.

Use expand-migrate-contract for production-bound changes.

## Do not break frontend/API contracts unexpectedly

Before changing field names, enum values, nullability, or relationship behavior, check:

- `../api-reference.md`
- `../frontend/ux-product-spec.md`
- `../test-plan.md`
- frontend owner expectations

Breaking examples:

- Renaming camera status values.
- Making `livekit_room_name` nullable.
- Removing `last_seen_at` needed by dashboard state.
- Changing UUIDs to integers in API-visible resources.

## Do not weaken runtime least privilege

The runtime DB role used by `cctv-api` must not have:

- `ALTER`
- `DROP`
- `TRUNCATE`
- superuser
- trigger disabling
- broad schema ownership
- direct `UPDATE`/`DELETE` on `audit_log`

Migration/admin roles must be separate from runtime roles.

## Do not add compliance/data-retention behavior without approval

Do not add:

- footage tables.
- recording metadata.
- snapshot tables.
- biometric identifiers.
- analytics event tables for people/face/motion.
- longer retention defaults.

These change privacy scope and must be future-approved.

## Required coordination before merging database changes

Coordinate with the system owner before any migration that affects:

- auth/RBAC/ACL.
- gateway identity/assignment.
- stream token grants.
- audit chain.
- privacy/DSR artifacts.
- API-visible fields.
- retention/backup behavior.

Coordinate with the frontend coworker before schema changes that alter visible fields, filters, lists, camera states, or admin workflows.
