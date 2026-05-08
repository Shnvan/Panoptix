from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cctv_api.models.base import Base
from cctv_api.models.enums import (
    ActorType,
    BackupUploadStatus,
    CameraEventKind,
    CameraSourceType,
    DpaKind,
    EventSource,
    GatewayStatus,
    RequestType,
    StreamKind,
    SubjectType,
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    idp_subject: Mapped[str | None] = mapped_column(String(255))
    role_default: Mapped[str] = mapped_column(String(64), server_default=text("'none'"), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (UniqueConstraint("action", "resource", name="uq_permissions_action_resource"),)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cf_jti: Mapped[str | None] = mapped_column(String(255))
    ua_fp: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(512))
    bystander_signage_attested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EdgeGateway(Base):
    __tablename__ = "edge_gateways"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[GatewayStatus] = mapped_column(
        Enum(GatewayStatus, name="gateway_status"), nullable=False, server_default=text("'enabled'")
    )
    service_token_hash: Mapped[str | None] = mapped_column(String(255))
    mtls_fingerprint: Mapped[str | None] = mapped_column(String(255))
    cert_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[CameraSourceType] = mapped_column(
        Enum(CameraSourceType, name="camera_source_type"), nullable=False
    )
    room_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    livekit_room_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    gateway_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("edge_gateways.id"))
    site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sites.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CameraAcl(Base):
    __tablename__ = "camera_acl"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=text("now()")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_camera_acl_active_user_camera",
            "user_id",
            "camera_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class GatewayCameraAssignment(Base):
    __tablename__ = "gateway_camera_assignments"

    gateway_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_gateways.id", ondelete="CASCADE"), primary_key=True
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=text("now()")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_gateway_camera_assignments_active",
            "gateway_id",
            "camera_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class CameraEvent(Base):
    __tablename__ = "camera_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False)
    gateway_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("edge_gateways.id"))
    kind: Mapped[CameraEventKind] = mapped_column(
        Enum(CameraEventKind, name="camera_event_kind"), nullable=False
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[EventSource] = mapped_column(Enum(EventSource, name="event_source"), nullable=False)

    __table_args__ = (Index("ix_camera_events_camera_at", "camera_id", "at"),)


class StreamGrant(Base):
    __tablename__ = "stream_grants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    gateway_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("edge_gateways.id", ondelete="SET NULL"))
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"))
    camera_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False)
    jti: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[StreamKind] = mapped_column(Enum(StreamKind, name="stream_kind"), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    denied_reason: Mapped[str | None] = mapped_column(String(128))

    __table_args__ = (Index("ix_stream_grants_camera_issued_at", "camera_id", "issued_at"),)


class AuditHmacKey(Base):
    __tablename__ = "audit_hmac_keys"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType, name="actor_type"), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[str] = mapped_column(String(256), nullable=False)
    ip: Mapped[str | None] = mapped_column(INET)
    ua: Mapped[str | None] = mapped_column(String(512))
    prev_hash: Mapped[str | None] = mapped_column(String(128))
    hash: Mapped[str] = mapped_column(String(128), nullable=False)
    hmac_key_version: Mapped[int] = mapped_column(ForeignKey("audit_hmac_keys.version"), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (Index("ix_audit_log_ts", "ts"),)


class BreakGlassUsage(Base):
    __tablename__ = "break_glass_usage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opened_by_reason: Mapped[str | None] = mapped_column(String(512))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_reason: Mapped[str | None] = mapped_column(String(512))
    auto_disable_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotation_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_break_glass_usage_opened_at", "opened_at"),)


class PrivacyNoticeAcceptance(Base):
    __tablename__ = "privacy_notice_acceptances"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    notice_version: Mapped[str] = mapped_column(String(64), primary_key=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DpaArtifact(Base):
    __tablename__ = "dpa_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[DpaKind] = mapped_column(Enum(DpaKind, name="dpa_kind"), nullable=False)
    path_to_r2: Mapped[str | None] = mapped_column(String(512))
    signed_hash: Mapped[str | None] = mapped_column(String(128))
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DsrRequest(Base):
    __tablename__ = "dsr_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requester_contact: Mapped[str] = mapped_column(String(320), nullable=False)
    subject_type: Mapped[SubjectType] = mapped_column(Enum(SubjectType, name="subject_type"), nullable=False)
    request_type: Mapped[RequestType] = mapped_column(Enum(RequestType, name="request_type"), nullable=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"))
    camera_scope_note: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str | None] = mapped_column(Text)
    artefact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("dpa_artifacts.id", ondelete="SET NULL"))

    __table_args__ = (Index("ix_dsr_requests_due_at", "due_at"),)


class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(String(512), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BackupRun(Base):
    __tablename__ = "backup_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    restore_format_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    restore_schema_ok: Mapped[bool | None] = mapped_column(Boolean)
    row_count_estimate: Mapped[int | None] = mapped_column(BigInteger)
    upload_status: Mapped[BackupUploadStatus] = mapped_column(
        Enum(BackupUploadStatus, name="backup_upload_status"),
        nullable=False,
        server_default=text("'pending'"),
    )
    notes: Mapped[str | None] = mapped_column(Text)


class WebhookReplayCache(Base):
    __tablename__ = "webhook_replay_cache"

    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    signature: Mapped[str] = mapped_column(String(256), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
