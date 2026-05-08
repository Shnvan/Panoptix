from __future__ import annotations

import enum
import hashlib
import json
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from cctv_api.models.enums import ActorType
from cctv_api.models.tables import AuditHmacKey, AuditLog

PLACEHOLDER_AUDIT_HMAC_KEY_VERSION = 0
PLACEHOLDER_AUDIT_HMAC_KEY = b"minimal-audit-placeholder"
SENSITIVE_PAYLOAD_KEY_FRAGMENTS = (
    "token",
    "jwt",
    "secret",
    "password",
    "credential",
    "authorization",
    "cookie",
    "api_key",
    "key_enc",
)
REDACTED_VALUE = "[REDACTED]"


class AuditLogError(RuntimeError):
    pass


def record_audit_event(
    db: DbSession,
    *,
    actor_type: ActorType,
    action: str,
    resource: str,
    actor_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    ip: str | None = None,
    ua: str | None = None,
) -> AuditLog:
    scrubbed_payload = scrub_audit_payload(payload) if payload is not None else None
    placeholder_hash = build_placeholder_audit_hash(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource=resource,
        payload=scrubbed_payload,
    )
    try:
        _ensure_placeholder_hmac_key(db)
        audit_log = AuditLog(
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource=resource,
            ip=ip,
            ua=ua,
            prev_hash=None,
            hash=placeholder_hash,
            hmac_key_version=PLACEHOLDER_AUDIT_HMAC_KEY_VERSION,
            payload=scrubbed_payload,
        )
        _assign_sqlite_audit_id(db, audit_log)
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        return audit_log
    except Exception as exc:
        db.rollback()
        raise AuditLogError("audit-log-write-failed") from exc


def scrub_audit_payload(value: Any) -> Any:
    if isinstance(value, dict):
        scrubbed: dict[str, Any] = {}
        for key, item in value.items():
            key_as_text = str(key)
            if _is_sensitive_payload_key(key_as_text):
                scrubbed[key_as_text] = REDACTED_VALUE
            else:
                scrubbed[key_as_text] = scrub_audit_payload(item)
        return scrubbed
    if isinstance(value, list):
        return [scrub_audit_payload(item) for item in value]
    if isinstance(value, tuple):
        return [scrub_audit_payload(item) for item in value]
    if isinstance(value, uuid.UUID | datetime | date):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    return value


def build_placeholder_audit_hash(
    *,
    actor_type: ActorType,
    action: str,
    resource: str,
    actor_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> str:
    material = {
        "actor_id": str(actor_id) if actor_id is not None else None,
        "actor_type": actor_type.value,
        "action": action,
        "resource": resource,
        "payload": payload,
        "hmac_key_version": PLACEHOLDER_AUDIT_HMAC_KEY_VERSION,
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_sensitive_payload_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in SENSITIVE_PAYLOAD_KEY_FRAGMENTS)


def _ensure_placeholder_hmac_key(db: DbSession) -> None:
    existing = db.get(AuditHmacKey, PLACEHOLDER_AUDIT_HMAC_KEY_VERSION)
    if existing is None:
        db.add(
            AuditHmacKey(
                version=PLACEHOLDER_AUDIT_HMAC_KEY_VERSION,
                key_enc=PLACEHOLDER_AUDIT_HMAC_KEY,
            )
        )
        db.flush()


def _assign_sqlite_audit_id(db: DbSession, audit_log: AuditLog) -> None:
    bind = db.get_bind()
    if bind.dialect.name != "sqlite":
        return
    next_id = db.execute(select(func.coalesce(func.max(AuditLog.id), 0) + 1)).scalar_one()
    audit_log.id = int(next_id)
