from __future__ import annotations

import argparse
import uuid

from sqlalchemy import create_engine, text

from cctv_api.core.config import Settings
from cctv_api.db import normalize_database_url


WANTED_ENUMS = {
    "camera_source_type",
    "gateway_status",
    "camera_event_kind",
    "event_source",
    "stream_kind",
    "actor_type",
    "dpa_kind",
    "subject_type",
    "request_type",
    "backup_upload_status",
}

WANTED_TABLES = {
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
    "audit_hmac_keys",
    "audit_log",
    "break_glass_usage",
    "privacy_notice_acceptances",
    "dpa_artifacts",
    "dsr_requests",
    "system_config",
    "backup_runs",
    "webhook_replay_cache",
    "alembic_version",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Run write-path constraint tests inside a rollback-only transaction.",
    )
    args = parser.parse_args()

    raw = Settings().DATABASE_URL
    if not raw:
        raise SystemExit("DATABASE_URL is not set")

    url = normalize_database_url(raw)
    engine = create_engine(url, pool_pre_ping=True)

    with engine.connect() as conn:
        db = conn.execute(text("select current_database()")).scalar_one()
        user = conn.execute(text("select current_user")).scalar_one()
        version = conn.execute(text("select version()")).scalar_one()

        tables = conn.execute(
            text("select tablename from pg_tables where schemaname='public' order by tablename")
        ).scalars().all()

        enums = conn.execute(
            text("select typname from pg_type where typtype='e' order by typname")
        ).scalars().all()

        idx = conn.execute(
            text(
                """
                select indexname, indexdef
                from pg_indexes
                where schemaname='public'
                order by indexname
                """
            )
        ).all()

        triggers = conn.execute(
            text(
                """
                select tgname, rel.relname as table_name, pg_get_triggerdef(t.oid) as def
                from pg_trigger t
                join pg_class rel on rel.oid = t.tgrelid
                join pg_namespace n on n.oid = rel.relnamespace
                where n.nspname='public' and not t.tgisinternal
                order by rel.relname, tgname
                """
            )
        ).all()

        foreign_keys = conn.execute(
            text(
                """
                select
                  tc.table_name,
                  kcu.column_name,
                  ccu.table_name as foreign_table_name,
                  ccu.column_name as foreign_column_name
                from information_schema.table_constraints tc
                join information_schema.key_column_usage kcu
                  on tc.constraint_name = kcu.constraint_name
                 and tc.table_schema = kcu.table_schema
                join information_schema.constraint_column_usage ccu
                  on ccu.constraint_name = tc.constraint_name
                 and ccu.table_schema = tc.table_schema
                where tc.table_schema = 'public'
                  and tc.constraint_type = 'FOREIGN KEY'
                order by tc.table_name, kcu.column_name
                """
            )
        ).all()

    print("connected=ok")
    print(f"db={db}")
    print(f"user={user}")
    print(f"pg_version_prefix={str(version).split(' ', 1)[0]}")

    tables_set = set(tables)
    print(f"tables_present={len(tables)}")
    print(f"tables_missing={sorted(WANTED_TABLES - tables_set)}")
    print(f"tables_extra={sorted(tables_set - WANTED_TABLES)}")

    enums_set = set(enums)
    print(f"wanted_enums_present={sorted(WANTED_ENUMS & enums_set)}")
    print(f"wanted_enums_missing={sorted(WANTED_ENUMS - enums_set)}")

    print("partial_unique_indexes=")
    for name, definition in idx:
        if " WHERE " in definition and ("uq_camera_acl_active_user_camera" in name or "uq_gateway_camera_assignments_active" in name):
            print(f"  {name}: {definition}")

    wanted_indexes = {
        "ix_sessions_user_id",
        "ix_sessions_user_active",
        "ix_cameras_site_id",
        "ix_cameras_gateway_id",
        "ix_edge_gateways_status",
        "ix_edge_gateways_last_seen_at",
    }
    idx_names = {name for name, _ in idx}
    print("wanted_indexes_missing=" + str(sorted(wanted_indexes - idx_names)))

    print("audit_triggers=")
    for tgname, table_name, definition in triggers:
        if table_name == "audit_log":
            print(f"  {tgname}: {definition}")

    print("foreign_keys_count=" + str(len(foreign_keys)))
    # Print a focused subset for the core authz relationships.
    core_fk_tables = {
        "sessions",
        "camera_acl",
        "gateway_camera_assignments",
        "cameras",
        "stream_grants",
        "audit_log",
        "dsr_requests",
    }
    print("foreign_keys_core=")
    for table_name, column_name, foreign_table_name, foreign_column_name in foreign_keys:
        if table_name in core_fk_tables:
            print(
                f"  {table_name}.{column_name} -> {foreign_table_name}.{foreign_column_name}"
            )

    if args.selftest:
        print("selftest=")
        conn = engine.connect()
        trans = conn.begin()
        try:
            conn.execute(text("set local timezone to 'UTC'"))

            # Minimal fixtures.
            user_id = uuid.uuid4()
            camera_id = uuid.uuid4()
            room_uuid = uuid.uuid4()

            conn.execute(
                text("insert into users (id, email, role_default) values (:id, :email, 'none')"),
                {"id": user_id, "email": f"test-user-{user_id}@example.test"},
            )
            conn.execute(
                text("insert into sites (id, name) values (:id, 'Test Site')"),
                {"id": uuid.uuid4()},
            )

            conn.execute(
                text(
                    """
                    insert into edge_gateways (id, name, status)
                    values (:id, 'Test GW', 'enabled')
                    """
                ),
                {"id": uuid.uuid4()},
            )

            # Create a camera without assigning gateway/site (nullable per ERD).
            conn.execute(
                text(
                    """
                    insert into cameras (id, display_name, source_type, room_uuid, livekit_room_name)
                    values (:id, 'Test Cam', 'synthetic_rtsp_test_source', :room_uuid, :room)
                    """
                ),
                {
                    "id": camera_id,
                    "room_uuid": room_uuid,
                    "room": f"camera_{str(camera_id).replace('-', '')[:8]}",
                },
            )

            # Partial unique index should reject duplicate active ACL rows.
            conn.execute(
                text(
                    """
                    insert into camera_acl (user_id, camera_id, granted_at)
                    values (:u, :c, now())
                    """
                ),
                {"u": user_id, "c": camera_id},
            )
            try:
                sp = conn.begin_nested()
                try:
                    conn.execute(
                        text(
                            """
                            insert into camera_acl (user_id, camera_id, granted_at)
                            values (:u, :c, now())
                            """
                        ),
                        {"u": user_id, "c": camera_id},
                    )
                    print("  camera_acl_partial_unique=UNEXPECTED_OK")
                    sp.rollback()
                except Exception:
                    sp.rollback()
                    raise
            except Exception as e:  # noqa: BLE001
                print(f"  camera_acl_partial_unique=ok ({e.__class__.__name__})")

            # Stream-grants check constraint should enforce kind/field consistency.
            sp = conn.begin_nested()
            try:
                conn.execute(
                    text(
                        """
                        insert into stream_grants
                          (id, camera_id, jti, kind, issued_at, expires_at, user_id)
                        values
                          (:id, :camera_id, 'jti', 'gateway_publish', now(), now() + interval '30 seconds', :user_id)
                        """
                    ),
                    {"id": uuid.uuid4(), "camera_id": camera_id, "user_id": user_id},
                )
                print("  stream_grants_kind_check=UNEXPECTED_OK")
                sp.rollback()
            except Exception as e:  # noqa: BLE001
                sp.rollback()
                print(f"  stream_grants_kind_check=ok ({e.__class__.__name__})")

            # Audit immutability trigger should block UPDATE/DELETE.
            conn.execute(
                text("insert into audit_hmac_keys (version, key_enc) values (1, '\\\\x00'::bytea)")
            )
            audit_id = conn.execute(
                text(
                    """
                    insert into audit_log (ts, actor_type, action, resource, hash, hmac_key_version)
                    values (now(), 'system', 'test.insert', 'test', 'deadbeef', 1)
                    returning id
                    """
                )
            ).scalar_one()

            try:
                sp = conn.begin_nested()
                try:
                    conn.execute(
                        text("update audit_log set action='test.update' where id=:id"),
                        {"id": audit_id},
                    )
                    print("  audit_update_block=UNEXPECTED_OK")
                    sp.rollback()
                except Exception:
                    sp.rollback()
                    raise
            except Exception as e:  # noqa: BLE001
                print(f"  audit_update_block=ok ({e.__class__.__name__})")

            try:
                sp = conn.begin_nested()
                try:
                    conn.execute(text("delete from audit_log where id=:id"), {"id": audit_id})
                    print("  audit_delete_block=UNEXPECTED_OK")
                    sp.rollback()
                except Exception:
                    sp.rollback()
                    raise
            except Exception as e:  # noqa: BLE001
                print(f"  audit_delete_block=ok ({e.__class__.__name__})")

            # Roll back selftest changes.
            trans.rollback()
            print("  rolled_back=yes")
        finally:
            conn.close()


if __name__ == "__main__":
    main()
