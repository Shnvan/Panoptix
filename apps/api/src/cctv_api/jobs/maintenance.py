from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session as DbSession, sessionmaker

from cctv_api.core.config import Settings
from cctv_api.gateway.command_queue import expire_stale_commands
from cctv_api.gateway.publish_state import enqueue_due_publish_stops
from cctv_api.models.enums import ActorType
from cctv_api.security.audit import AuditLogError, record_audit_event
from cctv_api.security.visitor_visits import purge_expired_visitor_visits


@dataclass(frozen=True)
class MaintenanceJobResult:
    expired_commands: int
    stops_enqueued: int
    purged_visitor_visits: int
    error: str | None = None


AuditRecorder = Callable[[str, str, dict[str, object | None]], None]
SleepFn = Callable[[float], Awaitable[None]]


def run_admin_maintenance_job(
    db: DbSession,
    *,
    audit: AuditRecorder,
    visitor_retention_days: int = 30,
) -> MaintenanceJobResult:
    expired_count = expire_stale_commands(db)
    stop_results = enqueue_due_publish_stops(db, audit=audit)
    purged_visitor_visits = purge_expired_visitor_visits(
        db,
        retention_days=visitor_retention_days,
    )
    return MaintenanceJobResult(
        expired_commands=expired_count,
        stops_enqueued=len(stop_results),
        purged_visitor_visits=purged_visitor_visits,
    )


def run_scheduled_maintenance_job(
    db: DbSession,
    *,
    settings: Settings,
) -> MaintenanceJobResult:
    try:
        result = run_admin_maintenance_job(
            db,
            audit=lambda action, resource, payload: _record_system_audit(
                db,
                settings=settings,
                action=action,
                resource=resource,
                payload=payload,
            ),
            visitor_retention_days=settings.VISITOR_RETENTION_DAYS,
        )
        _record_system_audit(
            db,
            settings=settings,
            action="system.maintenance.run",
            resource="maintenance",
            payload={
                "expired_commands": result.expired_commands,
                "stops_enqueued": result.stops_enqueued,
                "purged_visitor_visits": result.purged_visitor_visits,
            },
        )
        db.commit()
        return result
    except AuditLogError as exc:
        db.rollback()
        return MaintenanceJobResult(
            expired_commands=0,
            stops_enqueued=0,
            purged_visitor_visits=0,
            error=str(exc),
        )
    except Exception:
        db.rollback()
        return MaintenanceJobResult(
            expired_commands=0,
            stops_enqueued=0,
            purged_visitor_visits=0,
            error="maintenance-job-failed",
        )


async def maintenance_scheduler_loop(
    session_factory: sessionmaker[DbSession],
    *,
    settings: Settings,
    sleep: SleepFn = asyncio.sleep,
) -> None:
    while True:
        session = session_factory()
        try:
            run_scheduled_maintenance_job(session, settings=settings)
        finally:
            session.close()
        await sleep(settings.MAINTENANCE_INTERVAL_SECONDS)


def should_start_maintenance_scheduler(settings: Settings) -> bool:
    return settings.ENABLE_MAINTENANCE_SCHEDULER and "replace-me" not in settings.DATABASE_URL


def _record_system_audit(
    db: DbSession,
    *,
    settings: Settings,
    action: str,
    resource: str,
    payload: dict[str, object | None],
) -> None:
    record_audit_event(
        db,
        actor_type=ActorType.system,
        audit_hmac_key_version=settings.AUDIT_HMAC_KEY_VERSION,
        audit_hmac_key=settings.AUDIT_HMAC_KEY,
        actor_id=None,
        action=action,
        resource=resource,
        payload=payload,
    )
