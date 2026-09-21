from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
ADMIN_DSN_ENV = "FINANCE_TEST_POSTGRES_ADMIN_DSN"


def _admin_dsn() -> str:
    dsn = os.getenv(ADMIN_DSN_ENV)
    if not dsn:
        pytest.skip(f"{ADMIN_DSN_ENV} is required for disposable PostgreSQL migration tests")
    return dsn


def _database_dsn(admin_dsn: str, database: str) -> str:
    values = conninfo_to_dict(admin_dsn)
    values["dbname"] = database
    return " ".join(f"{key}={value}" for key, value in values.items())


def _async_database_url(admin_dsn: str, database: str) -> str:
    values = conninfo_to_dict(admin_dsn)
    user = quote(values.get("user", "postgres"), safe="")
    password = values.get("password")
    credentials = user if not password else f"{user}:{quote(password, safe='')}"
    host = values.get("host", "127.0.0.1")
    port = values.get("port", "5432")
    return f"postgresql+asyncpg://{credentials}@{host}:{port}/{quote(database, safe='')}"


@pytest.fixture
def disposable_database() -> Iterator[tuple[str, str]]:
    admin_dsn = _admin_dsn()
    database = f"finance_migration_{uuid4().hex}"
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        yield _database_dsn(admin_dsn, database), _async_database_url(admin_dsn, database)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid <> pg_backend_pid()",
                (database,),
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def _alembic(
    database_url: str, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["FINANCE_BACKEND_DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *arguments],
        cwd=BACKEND_ROOT,
        env=environment,
        check=check,
        capture_output=True,
        text=True,
    )


def _offline_sql(database_url: str, revision_range: str) -> str:
    result = _alembic(database_url, "upgrade", revision_range, "--sql")
    return result.stdout


def _create_compatible_preexisting_outbox(
    connection: psycopg.Connection[tuple[object, ...]],
) -> str:
    event_id = str(uuid4())
    connection.execute(
        """
        CREATE TABLE outbox_events (
            id uuid PRIMARY KEY,
            event_type text NOT NULL,
            aggregate_type text NOT NULL,
            aggregate_id uuid NOT NULL,
            scope_type text NULL,
            owner_user_id uuid NULL,
            household_id uuid NULL,
            membership_version bigint NULL,
            payload_safe jsonb NOT NULL DEFAULT '{}'::jsonb,
            status text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            available_at timestamptz NOT NULL,
            processed_at timestamptz NULL,
            attempt_count integer NOT NULL DEFAULT 0,
            deduplication_key text NULL
        );
        CREATE INDEX ix_outbox_events_status_available_created
            ON outbox_events(status, available_at, created_at);
        CREATE INDEX ix_outbox_events_event_type_created
            ON outbox_events(event_type, created_at);
        CREATE INDEX ix_outbox_events_owner_created
            ON outbox_events(owner_user_id, created_at);
        CREATE INDEX ix_outbox_events_household_created
            ON outbox_events(household_id, created_at);
        CREATE UNIQUE INDEX uq_outbox_events_deduplication_key
            ON outbox_events(deduplication_key) WHERE deduplication_key IS NOT NULL;
        """
    )
    connection.execute(
        """
        INSERT INTO outbox_events (
            id, event_type, aggregate_type, aggregate_id, status, available_at,
            deduplication_key
        ) VALUES (%s, 'preexisting', 'test', %s, 'pending', now(), 'preexisting-key')
        """,
        (event_id, str(uuid4())),
    )
    return event_id


def test_fresh_base_head_base_owns_and_removes_outbox(
    disposable_database: tuple[str, str],
) -> None:
    database_dsn, database_url = disposable_database
    _alembic(database_url, "upgrade", "head")
    with psycopg.connect(database_dsn) as connection:
        assert connection.execute("SELECT to_regclass('outbox_events')").fetchone()[0]
        ownership = connection.execute(
            "SELECT object_type, object_name FROM finance_alembic_object_ownership "
            "ORDER BY object_type, object_name"
        ).fetchall()
        assert ownership == [
            ("column", "outbox_events.deduplication_key"),
            ("index", "uq_outbox_events_deduplication_key"),
            ("table", "outbox_events"),
        ]

    _alembic(database_url, "downgrade", "base")
    with psycopg.connect(database_dsn) as connection:
        assert connection.execute("SELECT to_regclass('outbox_events')").fetchone()[0] is None
        assert (
            connection.execute(
                "SELECT to_regclass('finance_alembic_object_ownership')"
            ).fetchone()[0]
            is None
        )


def test_preexisting_outbox_and_dedup_survive_head_0020_and_base(
    disposable_database: tuple[str, str],
) -> None:
    database_dsn, database_url = disposable_database
    _alembic(database_url, "upgrade", "20260919_0020")
    with psycopg.connect(database_dsn, autocommit=True) as connection:
        event_id = _create_compatible_preexisting_outbox(connection)

    _alembic(database_url, "upgrade", "head")
    with psycopg.connect(database_dsn) as connection:
        assert connection.execute(
            "SELECT object_type, object_name FROM finance_alembic_object_ownership"
        ).fetchall() == []

    _alembic(database_url, "downgrade", "20260919_0020")
    with psycopg.connect(database_dsn) as connection:
        assert connection.execute(
            "SELECT deduplication_key FROM outbox_events WHERE id=%s", (event_id,)
        ).fetchone() == ("preexisting-key",)
        assert connection.execute(
            "SELECT to_regclass('uq_outbox_events_deduplication_key')"
        ).fetchone()[0]
        assert (
            connection.execute(
                "SELECT to_regclass('finance_alembic_object_ownership')"
            ).fetchone()[0]
            is None
        )

    _alembic(database_url, "downgrade", "base")
    with psycopg.connect(database_dsn) as connection:
        assert connection.execute(
            "SELECT deduplication_key FROM outbox_events WHERE id=%s", (event_id,)
        ).fetchone() == ("preexisting-key",)


def test_incompatible_preexisting_outbox_fails_fast(
    disposable_database: tuple[str, str],
) -> None:
    database_dsn, database_url = disposable_database
    _alembic(database_url, "upgrade", "20260919_0020")
    with psycopg.connect(database_dsn, autocommit=True) as connection:
        connection.execute("CREATE TABLE outbox_events (id text PRIMARY KEY)")

    result = _alembic(database_url, "upgrade", "20260919_0021", check=False)
    assert result.returncode != 0
    assert "incompatible preexisting outbox_events" in result.stderr
    assert "missing column event_type" in result.stderr
    with psycopg.connect(database_dsn) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "20260919_0020",
        )
        assert (
            connection.execute(
                "SELECT to_regclass('finance_alembic_object_ownership')"
            ).fetchone()[0]
            is None
        )


def test_legacy_applied_0021_without_ownership_registry_upgrades_to_head(
    disposable_database: tuple[str, str],
) -> None:
    database_dsn, database_url = disposable_database
    _alembic(database_url, "upgrade", "20260919_0021")
    with psycopg.connect(database_dsn, autocommit=True) as connection:
        connection.execute("DROP TABLE finance_alembic_object_ownership")

    _alembic(database_url, "upgrade", "head")
    with psycopg.connect(database_dsn) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "20260921_0025",
        )
        outbox_columns = {
            row[0]
            for row in connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND table_name='outbox_events'"
            ).fetchall()
        }
        assert {"deduplication_key", "lease_token", "lease_until", "delivery_attempts"} <= (
            outbox_columns
        )


def test_fresh_head_legacy_report_0024_0025_cycle(
    disposable_database: tuple[str, str],
) -> None:
    database_dsn, database_url = disposable_database
    _alembic(database_url, "upgrade", "head")
    _alembic(database_url, "downgrade", "20260920_0024")
    report_id = str(uuid4())
    with psycopg.connect(database_dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        connection.execute(
            """
            INSERT INTO recommendation_reports (
                id, owner_user_id, job_id, summary, assumptions, generated_at,
                valid_until, disclaimer
            ) VALUES (%s, %s, %s, 'legacy', '{}'::json, now(), now() + interval '1 day', 'test')
            """,
            (report_id, str(uuid4()), str(uuid4())),
        )
        connection.execute("SET session_replication_role = origin")

    _alembic(database_url, "upgrade", "20260921_0025")
    with psycopg.connect(database_dsn, autocommit=True) as connection:
        assert connection.execute(
            "SELECT summary, callback_hash FROM recommendation_reports WHERE id=%s",
            (report_id,),
        ).fetchone() == ("legacy", None)
        connection.execute(
            "UPDATE recommendation_reports SET callback_hash='canonical' WHERE id=%s",
            (report_id,),
        )

    _alembic(database_url, "downgrade", "20260920_0024")
    with psycopg.connect(database_dsn) as connection:
        assert connection.execute(
            "SELECT summary FROM recommendation_reports WHERE id=%s", (report_id,)
        ).fetchone() == ("legacy",)

    _alembic(database_url, "upgrade", "20260921_0025")
    with psycopg.connect(database_dsn) as connection:
        assert connection.execute(
            "SELECT summary, callback_hash FROM recommendation_reports WHERE id=%s",
            (report_id,),
        ).fetchone() == ("legacy", None)


def test_offline_sql_is_explicitly_fresh_only() -> None:
    sql_output = _offline_sql(
        "postgresql+asyncpg://offline@127.0.0.1:1/offline",
        "20260919_0020:20260919_0021",
    )
    guard_at = sql_output.index("offline SQL supports only a fresh outbox_events path")
    create_at = sql_output.index("CREATE TABLE outbox_events")
    assert guard_at < create_at
    assert "CREATE TABLE finance_alembic_object_ownership" in sql_output


def test_offline_sql_applies_to_fresh_0020_slice(
    disposable_database: tuple[str, str],
) -> None:
    database_dsn, database_url = disposable_database
    _alembic(database_url, "upgrade", "20260919_0020")
    sql_output = _offline_sql(database_url, "20260919_0020:20260919_0021")
    with psycopg.connect(database_dsn, autocommit=True) as connection:
        connection.execute(sql_output)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "20260919_0021",
        )
        assert connection.execute("SELECT to_regclass('outbox_events')").fetchone()[0]


def test_offline_sql_fails_before_touching_preexisting_outbox(
    disposable_database: tuple[str, str],
) -> None:
    database_dsn, database_url = disposable_database
    _alembic(database_url, "upgrade", "20260919_0020")
    with psycopg.connect(database_dsn, autocommit=True) as connection:
        event_id = _create_compatible_preexisting_outbox(connection)
    with psycopg.connect(database_dsn, autocommit=True) as connection:
        with pytest.raises(psycopg.errors.RaiseException, match="supports only a fresh"):
            connection.execute(_offline_sql(database_url, "20260919_0020:20260919_0021"))
    with psycopg.connect(database_dsn) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "20260919_0020",
        )
        assert connection.execute(
            "SELECT deduplication_key FROM outbox_events WHERE id=%s", (event_id,)
        ).fetchone() == ("preexisting-key",)
        assert (
            connection.execute(
                "SELECT to_regclass('finance_alembic_object_ownership')"
            ).fetchone()[0]
            is None
        )
        assert connection.execute("SELECT to_regclass('recommendation_jobs')").fetchone()[0] is None
