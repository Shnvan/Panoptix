"""Initial Panoptix control-plane schema (core MVP).

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-05-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums (Postgres)
    camera_source_type = postgresql.ENUM(
        "rtsp",
        "nvr_rtsp",
        "onvif_profile_s",
        "onvif_profile_t",
        "synthetic_rtsp_test_source",
        name="camera_source_type",
        create_type=False,
    )
    gateway_status = postgresql.ENUM(
        "enabled", "disabled", "retired", name="gateway_status", create_type=False
    )
    camera_event_kind = postgresql.ENUM(
        "online", "offline", "degraded", "reconnecting", "retired", name="camera_event_kind"
        ,
        create_type=False,
    )
    event_source = postgresql.ENUM(
        "heartbeat", "livekit_webhook", "mediamtx_callback", "admin_action", name="event_source"
        ,
        create_type=False,
    )
    stream_kind = postgresql.ENUM(
        "viewer_subscribe", "gateway_publish", name="stream_kind", create_type=False
    )
    actor_type = postgresql.ENUM(
        "user", "gateway", "system", "break_glass", "service_token_monitor", name="actor_type"
        ,
        create_type=False,
    )
    dpa_kind = postgresql.ENUM(
        "ropa",
        "processor_dpa",
        "pia",
        "breach_log",
        "retention_policy",
        "bystander_signage_attestation",
        "cross_border_transfer_basis",
        name="dpa_kind",
        create_type=False,
    )
    subject_type = postgresql.ENUM("user", "bystander", "site_contact", name="subject_type", create_type=False)
    request_type = postgresql.ENUM(
        "access", "correction", "deletion", "objection", "restriction", "other", name="request_type"
        ,
        create_type=False,
    )
    backup_upload_status = postgresql.ENUM(
        "pending", "uploaded", "failed", name="backup_upload_status", create_type=False
    )

    bind = op.get_bind()
    for enum_t in (
        camera_source_type,
        gateway_status,
        camera_event_kind,
        event_source,
        stream_kind,
        actor_type,
        dpa_kind,
        subject_type,
        request_type,
        backup_upload_status,
    ):
        enum_t.create(bind, checkfirst=True)

    # Identity & access
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column("idp_subject", sa.String(length=255)),
        sa.Column("role_default", sa.String(length=64), nullable=False, server_default=sa.text("'none'")),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False, unique=True),
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource", sa.String(length=128), nullable=False),
        sa.UniqueConstraint("action", "resource", name="uq_permissions_action_resource"),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "permission_id",
            sa.Integer(),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cf_jti", sa.String(length=255)),
        sa.Column("ua_fp", sa.String(length=255)),
        sa.Column("ip", postgresql.INET()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )

    # Camera & gateway
    op.create_table(
        "sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=512)),
        sa.Column("bystander_signage_attested_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "edge_gateways",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", gateway_status, nullable=False, server_default=sa.text("'enabled'")),
        sa.Column("service_token_hash", sa.String(length=255)),
        sa.Column("mtls_fingerprint", sa.String(length=255)),
        sa.Column("cert_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "cameras",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", camera_source_type, nullable=False),
        sa.Column("room_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("livekit_room_name", sa.String(length=64), nullable=False, unique=True),
        sa.Column("gateway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edge_gateways.id")),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "camera_acl",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), primary_key=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_camera_acl_active_user_camera",
        "camera_acl",
        ["user_id", "camera_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "gateway_camera_assignments",
        sa.Column("gateway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edge_gateways.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), primary_key=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_gateway_camera_assignments_active",
        "gateway_camera_assignments",
        ["gateway_id", "camera_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "camera_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gateway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edge_gateways.id")),
        sa.Column("kind", camera_event_kind, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", event_source, nullable=False),
    )
    op.create_index("ix_camera_events_camera_at", "camera_events", ["camera_id", "at"])

    # Streaming
    op.create_table(
        "stream_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("gateway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edge_gateways.id", ondelete="SET NULL")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="SET NULL")),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("kind", stream_kind, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("denied_reason", sa.String(length=128)),
    )
    op.create_index("ix_stream_grants_camera_issued_at", "stream_grants", ["camera_id", "issued_at"])

    # Audit & security
    op.create_table(
        "audit_hmac_keys",
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("key_enc", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_type", actor_type, nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource", sa.String(length=256), nullable=False),
        sa.Column("ip", postgresql.INET()),
        sa.Column("ua", sa.String(length=512)),
        sa.Column("prev_hash", sa.String(length=128)),
        sa.Column("hash", sa.String(length=128), nullable=False),
        sa.Column("hmac_key_version", sa.Integer(), sa.ForeignKey("audit_hmac_keys.version"), nullable=False),
        sa.Column("payload", postgresql.JSONB()),
    )
    op.create_index("ix_audit_log_ts", "audit_log", ["ts"])

    # Append-only guardrails for audit_log (immutability)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION panoptix_audit_log_immutable()
        RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'audit_log is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_no_update
        BEFORE UPDATE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION panoptix_audit_log_immutable();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_no_delete
        BEFORE DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION panoptix_audit_log_immutable();
        """
    )

    op.create_table(
        "break_glass_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_by_reason", sa.String(length=512)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("closed_reason", sa.String(length=512)),
        sa.Column("auto_disable_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotation_completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_break_glass_usage_opened_at", "break_glass_usage", ["opened_at"])

    # Privacy & compliance (retained even if not prototype-blocking)
    op.create_table(
        "privacy_notice_acceptances",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("notice_version", sa.String(length=64), primary_key=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "dpa_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", dpa_kind, nullable=False),
        sa.Column("path_to_r2", sa.String(length=512)),
        sa.Column("signed_hash", sa.String(length=128)),
        sa.Column("effective_at", sa.DateTime(timezone=True)),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "dsr_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("requester_contact", sa.String(length=320), nullable=False),
        sa.Column("subject_type", subject_type, nullable=False),
        sa.Column("request_type", request_type, nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="SET NULL")),
        sa.Column("camera_scope_note", sa.Text()),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.Text()),
        sa.Column("artefact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dpa_artifacts.id", ondelete="SET NULL")),
    )
    op.create_index("ix_dsr_requests_due_at", "dsr_requests", ["due_at"])

    # System & ops
    op.create_table(
        "system_config",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("value", sa.String(length=512), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "backup_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("sha256", sa.String(length=64)),
        sa.Column("restore_format_ok", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("restore_schema_ok", sa.Boolean()),
        sa.Column("row_count_estimate", sa.BigInteger()),
        sa.Column("upload_status", backup_upload_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("notes", sa.Text()),
    )

    op.create_table(
        "webhook_replay_cache",
        sa.Column("provider", sa.String(length=64), primary_key=True),
        sa.Column("signature", sa.String(length=256), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    # Drop tables in reverse-ish dependency order.
    op.drop_table("webhook_replay_cache")
    op.drop_table("backup_runs")
    op.drop_table("system_config")
    op.drop_index("ix_dsr_requests_due_at", table_name="dsr_requests")
    op.drop_table("dsr_requests")
    op.drop_table("dpa_artifacts")
    op.drop_table("privacy_notice_acceptances")
    op.drop_index("ix_break_glass_usage_opened_at", table_name="break_glass_usage")
    op.drop_table("break_glass_usage")

    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_no_delete ON audit_log;")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_no_update ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS panoptix_audit_log_immutable();")
    op.drop_index("ix_audit_log_ts", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("audit_hmac_keys")

    op.drop_index("ix_stream_grants_camera_issued_at", table_name="stream_grants")
    op.drop_table("stream_grants")

    op.drop_index("ix_camera_events_camera_at", table_name="camera_events")
    op.drop_table("camera_events")

    op.drop_index("uq_gateway_camera_assignments_active", table_name="gateway_camera_assignments")
    op.drop_table("gateway_camera_assignments")
    op.drop_index("uq_camera_acl_active_user_camera", table_name="camera_acl")
    op.drop_table("camera_acl")
    op.drop_table("cameras")
    op.drop_table("edge_gateways")
    op.drop_table("sites")

    op.drop_table("sessions")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")

    # Drop enums last.
    bind = op.get_bind()
    for enum_name in (
        "backup_upload_status",
        "request_type",
        "subject_type",
        "dpa_kind",
        "actor_type",
        "stream_kind",
        "event_source",
        "camera_event_kind",
        "gateway_status",
        "camera_source_type",
    ):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
