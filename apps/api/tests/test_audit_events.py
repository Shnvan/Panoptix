from __future__ import annotations

import uuid

from sqlalchemy.orm import Session as DbSession

from cctv_api.models.enums import ActorType, EventCategory, EventOutcome, EventSeverity
from cctv_api.security.audit import record_audit_event
from cctv_api.security.audit_events import (
    AuditEventDef,
    all_registered_actions,
    classify_audit_event,
)

AUDIT_HMAC_KEY_VERSION = 1
AUDIT_HMAC_KEY = "test-audit-hmac-key-with-enough-entropy"


def test_classify_returns_correct_metadata_for_known_actions() -> None:
    defn = classify_audit_event("viewer.token.issued")
    assert defn is not None
    assert defn.severity == EventSeverity.low
    assert defn.category == EventCategory.authentication
    assert defn.default_outcome == EventOutcome.success

    defn2 = classify_audit_event("system.break_glass.opened")
    assert defn2 is not None
    assert defn2.severity == EventSeverity.critical
    assert defn2.category == EventCategory.system
    assert defn2.default_outcome == EventOutcome.success

    defn3 = classify_audit_event("viewer.token.denied.access")
    assert defn3 is not None
    assert defn3.severity == EventSeverity.medium
    assert defn3.default_outcome == EventOutcome.denied


def test_classify_returns_none_for_unknown_action() -> None:
    assert classify_audit_event("completely.unknown.action") is None
    assert classify_audit_event("") is None


def test_all_registered_actions_is_nonempty() -> None:
    actions = all_registered_actions()
    assert len(actions) > 30


def test_registry_has_no_duplicate_actions() -> None:
    actions = all_registered_actions()
    assert isinstance(actions, frozenset)


def test_every_registered_event_has_valid_fields() -> None:
    for action in all_registered_actions():
        defn = classify_audit_event(action)
        assert defn is not None, f"Missing definition for {action}"
        assert isinstance(defn, AuditEventDef)
        assert isinstance(defn.severity, EventSeverity)
        assert isinstance(defn.category, EventCategory)
        assert isinstance(defn.default_outcome, EventOutcome)
        assert defn.action == action


def test_auto_classification_populates_fields_when_none(test_db_session: DbSession) -> None:
    audit_log = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action="viewer.token.issued",
        resource="camera:test",
    )

    assert audit_log.event_severity == EventSeverity.low
    assert audit_log.event_outcome == EventOutcome.success
    assert audit_log.event_category == EventCategory.authentication


def test_explicit_values_override_auto_classification(test_db_session: DbSession) -> None:
    audit_log = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action="viewer.token.issued",
        resource="camera:test",
        event_severity=EventSeverity.critical,
        event_outcome=EventOutcome.error,
        event_category=EventCategory.system,
    )

    assert audit_log.event_severity == EventSeverity.critical
    assert audit_log.event_outcome == EventOutcome.error
    assert audit_log.event_category == EventCategory.system


def test_partial_explicit_values_fill_remaining_from_registry(test_db_session: DbSession) -> None:
    audit_log = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action="viewer.token.issued",
        resource="camera:test",
        event_severity=EventSeverity.critical,
    )

    assert audit_log.event_severity == EventSeverity.critical
    assert audit_log.event_outcome == EventOutcome.success
    assert audit_log.event_category == EventCategory.authentication


def test_unknown_action_leaves_metadata_as_none(test_db_session: DbSession) -> None:
    audit_log = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action="test.unregistered.action",
        resource="camera:test",
    )

    assert audit_log.event_severity is None
    assert audit_log.event_outcome is None
    assert audit_log.event_category is None


def test_session_id_flows_into_audit_record(test_db_session: DbSession) -> None:
    sid = uuid.uuid4()
    audit_log = record_audit_event(
        test_db_session,
        actor_type=ActorType.user,
        audit_hmac_key_version=AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=AUDIT_HMAC_KEY,
        action="viewer.token.issued",
        resource="camera:test",
        session_id=sid,
    )

    assert str(audit_log.session_id) == str(sid)
    assert audit_log.event_severity == EventSeverity.low


def test_denied_events_classified_correctly() -> None:
    denied_actions = [
        "viewer.token.denied.user_disabled",
        "viewer.token.denied.access",
        "admin.rate_limited",
        "gateway.control.denied.unauthenticated",
        "livekit.webhook.replay_rejected",
    ]
    for action in denied_actions:
        defn = classify_audit_event(action)
        assert defn is not None, f"Missing: {action}"
        assert defn.default_outcome == EventOutcome.denied, f"{action} should be denied"


def test_critical_events_classified_correctly() -> None:
    critical_actions = [
        "admin.user.mfa_reset",
        "system.break_glass.opened",
    ]
    for action in critical_actions:
        defn = classify_audit_event(action)
        assert defn is not None, f"Missing: {action}"
        assert defn.severity == EventSeverity.critical, f"{action} should be critical"


# --- Phase 3: Auth failure events, audit-of-audit, before/after ---


def test_auth_failure_events_registered() -> None:
    auth_failure_actions = [
        "auth.login.denied.jwt_invalid",
        "auth.login.denied.jwt_missing",
        "auth.csrf.denied",
        "auth.gateway.denied.identity_missing",
        "auth.gateway.denied.identity_invalid",
        "auth.gateway.denied.disabled",
        "auth.gateway.denied.credential_invalid",
    ]
    for action in auth_failure_actions:
        defn = classify_audit_event(action)
        assert defn is not None, f"Missing: {action}"
        assert defn.default_outcome == EventOutcome.denied, f"{action} should be denied"
        assert defn.category == EventCategory.authentication, f"{action} should be authentication"


def test_session_lifecycle_events_registered() -> None:
    defn = classify_audit_event("auth.session.created")
    assert defn is not None
    assert defn.severity == EventSeverity.informational
    assert defn.default_outcome == EventOutcome.success
    assert defn.category == EventCategory.authentication

    defn2 = classify_audit_event("auth.session.expired")
    assert defn2 is not None
    assert defn2.severity == EventSeverity.low
    assert defn2.default_outcome == EventOutcome.failure
    assert defn2.category == EventCategory.authentication


def test_audit_of_audit_events_registered() -> None:
    audit_actions = [
        ("audit.log.viewed", EventSeverity.medium),
        ("audit.log.exported", EventSeverity.high),
        ("audit.log.verified", EventSeverity.high),
    ]
    for action, expected_severity in audit_actions:
        defn = classify_audit_event(action)
        assert defn is not None, f"Missing: {action}"
        assert defn.severity == expected_severity, f"{action} severity mismatch"
        assert defn.category == EventCategory.compliance, f"{action} should be compliance"
        assert defn.default_outcome == EventOutcome.success, f"{action} should be success"


def test_csrf_failure_classified_as_high_severity() -> None:
    defn = classify_audit_event("auth.csrf.denied")
    assert defn is not None
    assert defn.severity == EventSeverity.high
    assert defn.default_outcome == EventOutcome.denied


def test_gateway_auth_failures_classified_correctly() -> None:
    high_severity_actions = [
        "auth.gateway.denied.disabled",
        "auth.gateway.denied.credential_invalid",
    ]
    for action in high_severity_actions:
        defn = classify_audit_event(action)
        assert defn is not None, f"Missing: {action}"
        assert defn.severity == EventSeverity.high, f"{action} should be high severity"

    medium_severity_actions = [
        "auth.gateway.denied.identity_missing",
        "auth.gateway.denied.identity_invalid",
    ]
    for action in medium_severity_actions:
        defn = classify_audit_event(action)
        assert defn is not None, f"Missing: {action}"
        assert defn.severity == EventSeverity.medium, f"{action} should be medium severity"
