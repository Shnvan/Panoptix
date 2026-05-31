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
from sqlalchemy.orm import Mapped, mapped_column

from cctv_api.models.base import Base
from cctv_api.models.enums import (
    ActorType,
    AlertCategory,
    AlertNotificationStatus,
    AlertSeverity,
    AlertStatus,
    BackupUploadStatus,
    CameraEventKind,
    CameraPublishStatus,
    CameraSourceType,
    CommandStatus,
    DpaKind,
    EventCategory,
    EventOutcome,
    EventSeverity,
    EventSource,
    GatewayStatus,
    RequestType,
    StreamKind,
    SubjectType,
    VisitorAccessRequestStatus,
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


class VisitorVisit(Base):
    __tablename__ = "visitor_visits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    page_path: Mapped[str] = mapped_column(String(512), nullable=False)
    notice_version: Mapped[str] = mapped_column(String(64), nullable=False)
    ip: Mapped[str | None] = mapped_column(INET)
    ua: Mapped[str | None] = mapped_column(String(512))
    screen_width: Mapped[int | None] = mapped_column(Integer)
    screen_height: Mapped[int | None] = mapped_column(Integer)
    browser_timezone: Mapped[str | None] = mapped_column(String(128))
    browser_language: Mapped[str | None] = mapped_column(String(64))
    ip_enrichment_status: Mapped[str] = mapped_column(String(32), nullable=False)
    ip_enrichment_provider: Mapped[str | None] = mapped_column(String(64))
    ip_enrichment: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
    browser_context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    network_context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    webrtc_context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    timing_context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    server_context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), unique=True
    )
    logged_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_visitor_visits_collected_at", "collected_at"),
        Index("ix_visitor_visits_user_id", "user_id"),
    )


class VisitorAccessRequest(Base):
    __tablename__ = "visitor_access_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    visitor_visit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("visitor_visits.id", ondelete="SET NULL")
    )
    applicant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_role: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[VisitorAccessRequestStatus] = mapped_column(
        Enum(VisitorAccessRequestStatus, name="visitor_access_request_status"),
        nullable=False,
        server_default=text("'pending'"),
    )
    requester_ip: Mapped[str | None] = mapped_column(INET)
    requester_ua: Mapped[str | None] = mapped_column(String(512))
    request_context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decision_note: Mapped[str | None] = mapped_column(Text)
    github_invitation_id: Mapped[int | None] = mapped_column(Integer)
    github_org: Mapped[str | None] = mapped_column(String(255))
    github_invite_status: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_visitor_access_requests_status_created", "status", "created_at"),
        Index("ix_visitor_access_requests_email_status", "email", "status"),
        Index("ix_visitor_access_requests_visitor_visit_id", "visitor_visit_id"),
    )


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


class GatewayCommandQueue(Base):
    __tablename__ = "gateway_command_queue"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gateway_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_gateways.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    status: Mapped[CommandStatus] = mapped_column(
        Enum(CommandStatus, name="command_status"), nullable=False, server_default=text("'pending'")
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(512))

    __table_args__ = (
        Index("ix_gateway_command_queue_gateway_status", "gateway_id", "status"),
    )


class GatewayDiscoveryRun(Base):
    __tablename__ = "gateway_discovery_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gateway_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_gateways.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    approved_ranges: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    ports: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'"))
    scanned_host_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    findings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'"))
    agent_version: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        Index("ix_gateway_discovery_runs_gateway_started", "gateway_id", "started_at"),
    )


class CameraPublishState(Base):
    __tablename__ = "camera_publish_states"

    camera_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True
    )
    gateway_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("edge_gateways.id"))
    room: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[CameraPublishStatus] = mapped_column(
        Enum(CameraPublishStatus, name="camera_publish_status"),
        nullable=False,
        server_default=text("'idle'"),
    )
    last_viewer_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        Index("ix_camera_publish_states_status_due", "status", "stop_due_at"),
    )


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
    event_severity: Mapped[EventSeverity | None] = mapped_column(
        Enum(EventSeverity, name="event_severity")
    )
    event_outcome: Mapped[EventOutcome | None] = mapped_column(
        Enum(EventOutcome, name="event_outcome")
    )
    event_category: Mapped[EventCategory | None] = mapped_column(
        Enum(EventCategory, name="event_category")
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (
        Index("ix_audit_log_ts", "ts"),
        Index("ix_audit_log_actor_id", "actor_id"),
        Index("ix_audit_log_action", "action"),
        Index("ix_audit_log_category_severity", "event_category", "event_severity"),
        Index("ix_audit_log_session_id", "session_id"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity"), nullable=False
    )
    category: Mapped[AlertCategory] = mapped_column(
        Enum(AlertCategory, name="alert_category"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status"), nullable=False, server_default=text("'open'")
    )
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    source_event_id: Mapped[int | None] = mapped_column(BigInteger)
    resource: Mapped[str | None] = mapped_column(String(256))
    actor_type: Mapped[ActorType | None] = mapped_column(Enum(ActorType, name="actor_type"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        UniqueConstraint("source", "source_event_id", name="uq_alerts_source_event"),
        Index("ix_alerts_status_created_at", "status", "created_at"),
        Index("ix_alerts_severity_created_at", "severity", "created_at"),
    )


class AlertNotification(Base):
    __tablename__ = "alert_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'email'"))
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[AlertNotificationStatus] = mapped_column(
        Enum(AlertNotificationStatus, name="alert_notification_status"),
        nullable=False,
        server_default=text("'pending'"),
    )
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(256))

    __table_args__ = (Index("ix_alert_notifications_alert_id", "alert_id"),)


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


class LoginBaseline(Base):
    __tablename__ = "login_baselines"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    known_ips: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"))
    known_countries: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"))
    known_user_agents: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"))
    usual_hours_start: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("6"))
    usual_hours_end: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("23"))
    last_login_ip: Mapped[str | None] = mapped_column(String(45))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_country: Mapped[str | None] = mapped_column(String(2))
    login_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
