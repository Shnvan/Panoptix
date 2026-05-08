"""Create least-privilege DB roles and grants (runtime vs migrator).

Revision ID: 0003_roles_and_grants
Revises: 0002_camera_display_name
Create Date: 2026-05-08
"""

from __future__ import annotations

from alembic import op


revision = "0003_roles_and_grants"
down_revision = "0002_camera_display_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Note: This migration assumes it runs with sufficient privileges (owner/admin role).
    # It creates roles but does not set passwords; credentials are managed outside migrations.

    op.execute("DO $$ BEGIN CREATE ROLE cctv_migrator; EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute(
        "DO $$ BEGIN CREATE ROLE cctv_app_runtime; EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )

    # Keep `public` schema as the application schema; restrict default privileges.
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC;")
    op.execute("GRANT USAGE ON SCHEMA public TO cctv_migrator;")
    op.execute("GRANT USAGE ON SCHEMA public TO cctv_app_runtime;")

    # Migrator can manage schema objects.
    op.execute("GRANT CREATE ON SCHEMA public TO cctv_migrator;")

    # Runtime: DML only. We grant per-table below.
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM cctv_app_runtime;")
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM cctv_app_runtime;")

    # Grant runtime permissions for application tables.
    # Most tables: read/write. Immutable tables get INSERT/SELECT only.
    rw_tables = [
        "users",
        "roles",
        "permissions",
        "role_permissions",
        "user_roles",
        "sessions",
        "sites",
        "edge_gateways",
        "cameras",
        "camera_acl",
        "gateway_camera_assignments",
        "camera_events",
        "stream_grants",
        "break_glass_usage",
        "privacy_notice_acceptances",
        "dpa_artifacts",
        "dsr_requests",
        "system_config",
        "backup_runs",
        "webhook_replay_cache",
    ]
    for t in rw_tables:
        op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{t}" TO cctv_app_runtime;')

    # Audit tables: append-only posture for runtime.
    op.execute('GRANT SELECT, INSERT ON TABLE "audit_log" TO cctv_app_runtime;')
    op.execute('REVOKE UPDATE, DELETE, TRUNCATE ON TABLE "audit_log" FROM cctv_app_runtime;')
    op.execute('GRANT SELECT, INSERT, UPDATE ON TABLE "audit_hmac_keys" TO cctv_app_runtime;')

    # Sequences (identity/serial): allow runtime to use sequences for inserts.
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cctv_app_runtime;")

    # Default privileges for future migrations (owned by the executing role):
    # ensure new tables/sequences get runtime DML permissions.
    op.execute(
        """
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cctv_app_runtime;
        """
    )
    op.execute(
        """
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO cctv_app_runtime;
        """
    )


def downgrade() -> None:
    # Best-effort rollback: keep schema secure, but remove role grants.
    op.execute("REVOKE USAGE ON SCHEMA public FROM cctv_app_runtime;")
    op.execute("REVOKE USAGE ON SCHEMA public FROM cctv_migrator;")
    op.execute("REVOKE CREATE ON SCHEMA public FROM cctv_migrator;")

    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM cctv_app_runtime;")
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM cctv_app_runtime;")

    op.execute("DO $$ BEGIN DROP ROLE cctv_app_runtime; EXCEPTION WHEN undefined_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN DROP ROLE cctv_migrator; EXCEPTION WHEN undefined_object THEN NULL; END $$;")

