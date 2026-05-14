from __future__ import annotations

from dataclasses import dataclass

from cctv_api.models.enums import EventCategory, EventOutcome, EventSeverity


@dataclass(frozen=True)
class AuditEventDef:
    action: str
    severity: EventSeverity
    category: EventCategory
    default_outcome: EventOutcome


_REGISTRY: dict[str, AuditEventDef] = {}


def _r(
    action: str,
    severity: EventSeverity,
    category: EventCategory,
    default_outcome: EventOutcome,
) -> AuditEventDef:
    defn = AuditEventDef(
        action=action,
        severity=severity,
        category=category,
        default_outcome=default_outcome,
    )
    _REGISTRY[action] = defn
    return defn


S = EventSeverity
C = EventCategory
O = EventOutcome  # noqa: E741 - short registry alias kept with S/C for readability.

# --- Authentication ---

_r("viewer.token.issued", S.low, C.authentication, O.success)
_r("viewer.token.denied.user_disabled", S.medium, C.authentication, O.denied)
_r("viewer.token.denied.camera_not_found", S.low, C.authentication, O.denied)
_r("viewer.token.denied.access", S.medium, C.authentication, O.denied)
_r("viewer.token.denied.livekit_config", S.high, C.authentication, O.error)
_r("viewer.token.rate_limited", S.medium, C.authentication, O.denied)
_r("session.revoke.succeeded", S.low, C.authentication, O.success)
_r("session.revoke.not_found", S.low, C.authentication, O.failure)
_r("session.revoke.denied.not_owned", S.medium, C.authentication, O.denied)
_r("auth.session.created", S.informational, C.authentication, O.success)
_r("auth.session.expired", S.low, C.authentication, O.failure)
_r("auth.login.denied.jwt_invalid", S.medium, C.authentication, O.denied)
_r("auth.login.denied.jwt_missing", S.low, C.authentication, O.denied)
_r("auth.csrf.denied", S.high, C.authentication, O.denied)
_r("auth.gateway.denied.identity_missing", S.medium, C.authentication, O.denied)
_r("auth.gateway.denied.identity_invalid", S.medium, C.authentication, O.denied)
_r("auth.gateway.denied.disabled", S.high, C.authentication, O.denied)
_r("auth.gateway.denied.credential_invalid", S.high, C.authentication, O.denied)

# --- Authorization (role / ACL mutations) ---

_r("admin.user.role.granted", S.high, C.authorization, O.success)
_r("admin.user.role.revoked", S.high, C.authorization, O.success)
_r("camera.acl.grant", S.high, C.authorization, O.success)
_r("camera.acl.revoke", S.high, C.authorization, O.success)
_r("admin.rate_limited", S.medium, C.authorization, O.denied)

# --- Camera management ---

_r("camera.create", S.medium, C.data_access, O.success)
_r("camera.disable", S.high, C.data_access, O.success)

# --- Gateway operations ---

_r("gateway.create", S.high, C.system, O.success)
_r("gateway.disable", S.high, C.system, O.success)
_r("gateway.credential.rotated", S.high, C.system, O.success)
_r("gateway.camera.grant", S.medium, C.system, O.success)
_r("gateway.camera.revoke", S.medium, C.system, O.success)

_r("gateway.heartbeat.denied.gateway_mismatch", S.medium, C.system, O.denied)
_r("gateway.heartbeat.denied.signing_failed", S.high, C.system, O.denied)
_r("gateway.ingest.denied.gateway_mismatch", S.medium, C.system, O.denied)
_r("gateway.ingest.rate_limited", S.medium, C.system, O.denied)
_r("gateway.ingest.denied.disabled", S.high, C.system, O.denied)
_r("gateway.ingest.denied.camera_not_found", S.medium, C.system, O.denied)
_r("gateway.ingest.denied.unassigned", S.medium, C.system, O.denied)
_r("gateway.ingest.denied.livekit_config", S.high, C.system, O.error)
_r("gateway.ingest.token.issued", S.low, C.system, O.success)
_r("gateway.camera_status.denied.gateway_mismatch", S.medium, C.system, O.denied)
_r("gateway.camera_status.denied.disabled", S.high, C.system, O.denied)
_r("gateway.camera_status.denied.camera_not_found", S.medium, C.system, O.denied)
_r("gateway.camera_status.denied.unassigned", S.medium, C.system, O.denied)
_r("gateway.control.denied.unauthenticated", S.high, C.system, O.denied)
_r("gateway.control.denied.signing_failed", S.high, C.system, O.denied)
_r("gateway.control.ack.denied.invalid", S.medium, C.system, O.denied)
_r("gateway.control.ack.denied.gateway_mismatch", S.medium, C.system, O.denied)
_r("gateway.control.ack.denied.not_applied", S.medium, C.system, O.denied)

# --- Commands ---

_r("command.enqueue", S.low, C.admin, O.success)
_r("command.cancel", S.low, C.admin, O.success)
_r("commands.cleanup", S.low, C.system, O.success)

# --- Admin / user management ---

_r("admin.user.disabled", S.high, C.admin, O.success)
_r("admin.user.mfa_reset", S.critical, C.admin, O.success)
_r("admin.maintenance.run", S.low, C.admin, O.success)
_r("admin.dpa.export", S.medium, C.compliance, O.success)
_r("admin.signage.attest", S.medium, C.compliance, O.success)

# --- System ---

_r("system.break_glass.opened", S.critical, C.system, O.success)
_r("system.break_glass.closed", S.high, C.system, O.success)
_r("system.media_plane.switched_to_fallback", S.high, C.system, O.success)
_r("system.media_plane.switched_to_primary", S.high, C.system, O.success)
_r("system.maintenance.run", S.low, C.system, O.success)

# --- LiveKit ---

_r("livekit.webhook.received", S.informational, C.system, O.success)
_r("livekit.webhook.replay_rejected", S.medium, C.system, O.denied)
_r("livekit.publish.start_enqueued", S.low, C.system, O.success)
_r("livekit.publish.stop_enqueued", S.low, C.system, O.success)
_r("livekit.publish.stop_scheduled", S.low, C.system, O.success)
_r("livekit.publish.stop_cancelled", S.low, C.system, O.success)
_r("livekit.publish.command_skipped", S.low, C.system, O.success)

# --- Compliance ---

_r("privacy.notice.accepted", S.informational, C.compliance, O.success)
_r("audit.log.viewed", S.medium, C.compliance, O.success)
_r("audit.log.exported", S.high, C.compliance, O.success)
_r("audit.log.verified", S.high, C.compliance, O.success)

# --- Actor investigation ---

_r("admin.actor.profile.viewed", S.medium, C.compliance, O.success)
_r("admin.actor.activity.viewed", S.medium, C.compliance, O.success)

# Clean up module-level shorthand aliases.
del S, C, O


def classify_audit_event(action: str) -> AuditEventDef | None:
    """Look up the event definition for an action string.

    Returns None for unknown actions (fail-open for classification).
    """
    return _REGISTRY.get(action)


def all_registered_actions() -> frozenset[str]:
    """Return all registered action strings (useful for tests)."""
    return frozenset(_REGISTRY)
