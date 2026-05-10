from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session as DbSession

from cctv_api.db import get_sessionmaker
from cctv_api.gateway.models import GatewayCommandAck, GatewayCommandEnvelope
from cctv_api.models.enums import CommandStatus
from cctv_api.models.tables import GatewayCommandQueue


@dataclass(frozen=True)
class AckSinkResult:
    applied: bool
    reason: str | None = None
    command_id: str | None = None


def enqueue_command(
    db: DbSession,
    *,
    gateway_id: uuid.UUID,
    kind: str,
    payload: dict,
    expires_at: datetime,
) -> GatewayCommandQueue:
    row = GatewayCommandQueue(
        gateway_id=gateway_id,
        kind=kind,
        payload=payload,
        expires_at=expires_at,
    )
    db.add(row)
    db.flush()
    return row


def expire_stale_commands(db: DbSession) -> int:
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(GatewayCommandQueue)
        .where(GatewayCommandQueue.status == CommandStatus.pending)
        .where(GatewayCommandQueue.expires_at <= now)
        .values(status=CommandStatus.expired)
    )
    db.flush()
    return result.rowcount  # type: ignore[attr-defined]


def db_command_provider(db: DbSession) -> Callable[[str], list[GatewayCommandEnvelope]]:
    def _provide(gateway_id: str) -> list[GatewayCommandEnvelope]:
        now = datetime.now(timezone.utc)
        query = (
            select(GatewayCommandQueue)
            .where(GatewayCommandQueue.gateway_id == gateway_id)
            .where(GatewayCommandQueue.status == CommandStatus.pending)
            .where(GatewayCommandQueue.expires_at > now)
            .order_by(GatewayCommandQueue.issued_at.asc())
        )
        rows = list(db.execute(query).scalars().all())
        return [
            GatewayCommandEnvelope(
                command_id=str(row.id),
                kind=row.kind,
                gateway_id=str(row.gateway_id),
                issued_at=row.issued_at,
                expires_at=row.expires_at,
                payload=row.payload,
                signature="",
            )
            for row in rows
        ]

    return _provide


def db_ack_sink(db: DbSession) -> Callable[[str, GatewayCommandAck], AckSinkResult]:
    def _sink(gateway_id: str, ack: GatewayCommandAck) -> AckSinkResult:
        if ack.command_id is None:
            return AckSinkResult(applied=False, reason="command-id-missing")
        try:
            uuid.UUID(ack.command_id)
        except ValueError:
            return AckSinkResult(applied=False, reason="command-id-invalid", command_id=ack.command_id)
        row = db.execute(
            select(GatewayCommandQueue)
            .where(GatewayCommandQueue.id == ack.command_id)
            .where(GatewayCommandQueue.gateway_id == gateway_id)
        ).scalar_one_or_none()
        if row is None:
            return AckSinkResult(applied=False, reason="command-not-found", command_id=ack.command_id)
        now = datetime.now(timezone.utc)
        if ack.status == "accepted":
            row.status = CommandStatus.accepted
        else:
            row.status = CommandStatus.rejected
            row.error = ack.error
        row.acked_at = now
        db.flush()
        return AckSinkResult(applied=True, command_id=ack.command_id)

    return _sink


def create_command_provider() -> Callable[[str], list[GatewayCommandEnvelope]]:
    def _provide(gateway_id: str) -> list[GatewayCommandEnvelope]:
        session = get_sessionmaker()()
        try:
            provider = db_command_provider(session)
            return provider(gateway_id)
        finally:
            session.close()

    return _provide


def create_ack_sink() -> Callable[[str, GatewayCommandAck], None]:
    def _sink(gateway_id: str, ack: GatewayCommandAck) -> None:
        session = get_sessionmaker()()
        try:
            sink = db_ack_sink(session)
            sink(gateway_id, ack)
            session.commit()
        finally:
            session.close()

    return _sink
