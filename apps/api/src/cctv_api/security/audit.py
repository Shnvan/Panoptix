from __future__ import annotations

import enum
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from cctv_api.models.enums import ActorType
from cctv_api.models.tables import AuditHmacKey, AuditLog

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


@dataclass(frozen=True)
class AuditChainVerificationResult:
    valid: bool
    checked: int
    error: str | None = None


def record_audit_event(
    db: DbSession,
    *,
    actor_type: ActorType,
    action: str,
    resource: str,
    audit_hmac_key_version: int,
    audit_hmac_key: str,
    actor_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    ip: str | None = None,
    ua: str | None = None,
) -> AuditLog:
    key_bytes = _validated_hmac_key(audit_hmac_key)
    scrubbed_payload = scrub_audit_payload(payload) if payload is not None else None
    try:
        _ensure_hmac_key(db, version=audit_hmac_key_version, key_bytes=key_bytes)
        prev_hash = _latest_audit_hash(db)
        ts = datetime.now(timezone.utc)
        audit_hash = build_audit_hmac(
            ts=ts,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            resource=resource,
            payload=scrubbed_payload,
            ip=ip,
            ua=ua,
            prev_hash=prev_hash,
            hmac_key_version=audit_hmac_key_version,
            hmac_key=audit_hmac_key,
        )
        audit_log = AuditLog(
            ts=ts,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource=resource,
            ip=ip,
            ua=ua,
            prev_hash=prev_hash,
            hash=audit_hash,
            hmac_key_version=audit_hmac_key_version,
            payload=scrubbed_payload,
        )
        _assign_sqlite_audit_id(db, audit_log)
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        return audit_log
    except AuditLogError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise AuditLogError("audit-log-write-failed") from exc


def verify_audit_log_row(
    row: AuditLog,
    *,
    audit_hmac_key: str,
    expected_prev_hash: str | None,
) -> AuditChainVerificationResult:
    if row.prev_hash != expected_prev_hash:
        return AuditChainVerificationResult(
            valid=False,
            checked=1,
            error="audit-chain-prev-hash-mismatch",
        )
    try:
        expected_hash = build_audit_hmac(
            ts=row.ts,
            actor_type=row.actor_type,
            actor_id=row.actor_id,
            action=row.action,
            resource=row.resource,
            payload=row.payload,
            ip=row.ip,
            ua=row.ua,
            prev_hash=row.prev_hash,
            hmac_key_version=row.hmac_key_version,
            hmac_key=audit_hmac_key,
        )
    except AuditLogError as exc:
        return AuditChainVerificationResult(valid=False, checked=1, error=str(exc))
    if not hmac.compare_digest(row.hash, expected_hash):
        return AuditChainVerificationResult(
            valid=False,
            checked=1,
            error="audit-chain-hash-mismatch",
        )
    return AuditChainVerificationResult(valid=True, checked=1)


def verify_audit_chain(
    rows: Iterable[AuditLog],
    *,
    audit_hmac_key: str,
    start_prev_hash: str | None = None,
) -> AuditChainVerificationResult:
    previous_hash = start_prev_hash
    checked = 0
    for row in rows:
        result = verify_audit_log_row(
            row,
            audit_hmac_key=audit_hmac_key,
            expected_prev_hash=previous_hash,
        )
        checked += 1
        if not result.valid:
            return AuditChainVerificationResult(valid=False, checked=checked, error=result.error)
        previous_hash = row.hash
    return AuditChainVerificationResult(valid=True, checked=checked)


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


def build_audit_hmac(
    *,
    ts: datetime,
    actor_type: ActorType,
    action: str,
    resource: str,
    hmac_key_version: int,
    hmac_key: str,
    actor_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    ip: str | None = None,
    ua: str | None = None,
    prev_hash: str | None = None,
) -> str:
    key_bytes = _validated_hmac_key(hmac_key)
    material = {
        "actor_id": str(actor_id) if actor_id is not None else None,
        "ts": _normalize_value(ts),
        "actor_type": actor_type.value,
        "action": action,
        "resource": resource,
        "payload": _normalize_value(payload),
        "ip": ip,
        "ua": ua,
        "prev_hash": prev_hash,
        "hmac_key_version": hmac_key_version,
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hmac.new(key_bytes, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="microseconds") + "Z"
    if isinstance(value, uuid.UUID | date):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    return value


def _is_sensitive_payload_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in SENSITIVE_PAYLOAD_KEY_FRAGMENTS)


def _validated_hmac_key(audit_hmac_key: str) -> bytes:
    key = audit_hmac_key.strip()
    if not key or key == "replace-me":
        raise AuditLogError("audit-hmac-key-invalid")
    return key.encode("utf-8")


def _ensure_hmac_key(db: DbSession, *, version: int, key_bytes: bytes) -> None:
    existing = db.get(AuditHmacKey, version)
    if existing is None:
        db.add(AuditHmacKey(version=version, key_enc=key_bytes))
        db.flush()
        return
    if bytes(existing.key_enc) != key_bytes:
        raise AuditLogError("audit-hmac-key-mismatch")


def _latest_audit_hash(db: DbSession) -> str | None:
    return db.execute(select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none()


def _assign_sqlite_audit_id(db: DbSession, audit_log: AuditLog) -> None:
    bind = db.get_bind()
    if bind.dialect.name != "sqlite":
        return
    next_id = db.execute(select(func.coalesce(func.max(AuditLog.id), 0) + 1)).scalar_one()
    audit_log.id = int(next_id)
