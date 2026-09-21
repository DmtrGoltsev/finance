"""Add asynchronous investment recommendation jobs and reports.

Revision ID: 20260919_0021
Revises: 20260919_0020
Create Date: 2026-09-19
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "20260919_0021"
down_revision: str | None = "20260919_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
MONEY = sa.Numeric(20, 4)
PERCENT = sa.Numeric(7, 4)
OWNERSHIP_TABLE = "finance_alembic_object_ownership"
OWNERSHIP_REVISION = revision
BASE_OUTBOX_INDEX_COLUMNS = {
    ("status", "available_at", "created_at"),
    ("event_type", "created_at"),
    ("owner_user_id", "created_at"),
    ("household_id", "created_at"),
}
OUTBOX_STATUSES = {"pending", "processing", "processed", "failed", "dead"}
EXPECTED_FOREIGN_KEYS = {
    ("owner_user_id",): ("users", ("id",)),
    ("household_id",): ("households", ("id",)),
}


def _create_ownership_table() -> None:
    op.create_table(
        OWNERSHIP_TABLE,
        sa.Column("revision_id", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("object_name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("revision_id", "object_type", "object_name"),
    )


def _record_owned(object_type: str, object_name: str) -> None:
    op.execute(
        sa.text(
            f"INSERT INTO {OWNERSHIP_TABLE} (revision_id, object_type, object_name) "
            f"VALUES ('{OWNERSHIP_REVISION}', '{object_type}', '{object_name}')"
        )
    )


def _type_matches(actual: sa.types.TypeEngine, expected: str) -> bool:
    if expected == "uuid":
        return isinstance(actual, sa.Uuid)
    if expected == "text":
        return isinstance(actual, sa.Text)
    if expected == "bigint":
        return isinstance(actual, sa.BigInteger)
    if expected == "integer":
        return isinstance(actual, sa.Integer) and not isinstance(actual, sa.BigInteger)
    if expected == "json":
        return isinstance(actual, sa.JSON)
    if expected == "datetime":
        return isinstance(actual, sa.DateTime) and bool(actual.timezone)
    return False


def _normalized_sql(value: object | None) -> str:
    if value is None:
        return ""
    normalized = str(value).lower().replace('"', "")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def _default_matches(value: object | None, expected: str) -> bool:
    normalized = _normalized_sql(value)
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1]
    if expected == "empty_json":
        return normalized in {"'{}'::json", "'{}'::jsonb"}
    if expected == "now":
        return normalized in {"now()", "current_timestamp"}
    if expected == "zero":
        return normalized in {"0", "0::integer"}
    return False


def _status_check_matches(sqltext: object | None) -> bool:
    normalized = _normalized_sql(sqltext)
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1]
    literals = set(re.findall(r"'([^']+)'(?:::[a-z ]+)?", normalized))
    if literals != OUTBOX_STATUSES:
        return False
    without_literals = re.sub(r"'[^']+'(?:::[a-z ]+)?", "?", normalized)
    return bool(
        re.fullmatch(r"statusin\(\?(?:,\?){4}\)", without_literals)
        or re.fullmatch(r"status=any\(array\[\?(?:,\?){4}\]\)", without_literals)
    )


def _index_predicate(index: dict[str, object]) -> object | None:
    dialect_options = index.get("dialect_options") or {}
    if isinstance(dialect_options, dict):
        return dialect_options.get("postgresql_where")
    return None


def _dedup_predicate_matches(index: dict[str, object]) -> bool:
    normalized = _normalized_sql(_index_predicate(index))
    normalized = normalized.replace("outbox_events.", "")
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1]
    return normalized == "deduplication_keyisnotnull"


def _validate_existing_outbox(inspector: sa.Inspector) -> tuple[set[str], bool]:
    expected_columns = {
        "id": ("uuid", False),
        "event_type": ("text", False),
        "aggregate_type": ("text", False),
        "aggregate_id": ("uuid", False),
        "scope_type": ("text", True),
        "owner_user_id": ("uuid", True),
        "household_id": ("uuid", True),
        "membership_version": ("bigint", True),
        "payload_safe": ("json", False),
        "status": ("text", False),
        "created_at": ("datetime", False),
        "available_at": ("datetime", False),
        "processed_at": ("datetime", True),
        "attempt_count": ("integer", False),
    }
    columns = {column["name"]: column for column in inspector.get_columns("outbox_events")}
    problems: list[str] = []
    for name, (expected_type, nullable) in expected_columns.items():
        column = columns.get(name)
        if column is None:
            problems.append(f"missing column {name}")
            continue
        if not _type_matches(column["type"], expected_type):
            problems.append(f"column {name} has incompatible type {column['type']}")
        if bool(column["nullable"]) != nullable:
            problems.append(f"column {name} has incompatible nullability")

    for name, expected_default in {
        "payload_safe": "empty_json",
        "created_at": "now",
        "attempt_count": "zero",
    }.items():
        column = columns.get(name)
        if column is not None and not _default_matches(column.get("default"), expected_default):
            problems.append(f"column {name} has incompatible server default")

    primary_key = inspector.get_pk_constraint("outbox_events").get("constrained_columns") or []
    if primary_key != ["id"]:
        problems.append(f"primary key must be (id), got {primary_key}")

    foreign_keys = inspector.get_foreign_keys("outbox_events")
    for constrained_columns, (target_table, target_columns) in EXPECTED_FOREIGN_KEYS.items():
        matching = [
            foreign_key
            for foreign_key in foreign_keys
            if tuple(foreign_key.get("constrained_columns") or ()) == constrained_columns
            and foreign_key.get("referred_table") == target_table
            and tuple(foreign_key.get("referred_columns") or ()) == target_columns
            and (foreign_key.get("options") or {}).get("ondelete") in {None, "NO ACTION"}
        ]
        if not matching:
            problems.append(
                f"missing foreign key {constrained_columns[0]} -> {target_table}.id "
                "ON DELETE NO ACTION"
            )

    checks = inspector.get_check_constraints("outbox_events")
    if not any(_status_check_matches(check.get("sqltext")) for check in checks):
        problems.append("missing exact status CHECK for the outbox status model")

    indexes = inspector.get_indexes("outbox_events")
    for expected_columns_for_index in BASE_OUTBOX_INDEX_COLUMNS:
        matching = [
            index
            for index in indexes
            if tuple(index.get("column_names") or ()) == expected_columns_for_index
            and not index.get("unique")
            and _index_predicate(index) is None
        ]
        if not matching:
            problems.append(
                f"missing non-partial runtime index on {expected_columns_for_index}"
            )

    dedup_column = columns.get("deduplication_key")
    if dedup_column is not None and (
        not _type_matches(dedup_column["type"], "text") or not dedup_column["nullable"]
    ):
        problems.append("column deduplication_key must be nullable text")
    dedup_indexes = [
        index
        for index in indexes
        if tuple(index.get("column_names") or ()) == ("deduplication_key",)
    ]
    exact_dedup_indexes = [
        index
        for index in dedup_indexes
        if index.get("unique") and _dedup_predicate_matches(index)
    ]
    if dedup_indexes and not exact_dedup_indexes:
        problems.append(
            "deduplication index must be unique on deduplication_key with predicate "
            "deduplication_key IS NOT NULL"
        )
    if exact_dedup_indexes and dedup_column is None:
        problems.append("deduplication index exists without deduplication_key column")

    if problems:
        details = "; ".join(problems)
        raise RuntimeError(
            f"Migration {revision}: incompatible preexisting outbox_events: {details}"
        )
    return set(columns), bool(exact_dedup_indexes)


def _create_outbox_events() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", UUID, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", UUID, nullable=False),
        sa.Column("scope_type", sa.Text(), nullable=True),
        sa.Column("owner_user_id", UUID, nullable=True),
        sa.Column("household_id", UUID, nullable=True),
        sa.Column("membership_version", sa.BigInteger(), nullable=True),
        sa.Column(
            "payload_safe",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'failed', 'dead')",
            name=op.f("ck_outbox_events_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name=op.f("fk_outbox_events_owner_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_outbox_events_household_id_households"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_events")),
    )
    op.create_index(
        "ix_outbox_events_status_available_created",
        "outbox_events",
        ["status", "available_at", "created_at"],
    )
    op.create_index(
        "ix_outbox_events_event_type_created",
        "outbox_events",
        ["event_type", "created_at"],
    )
    op.create_index(
        "ix_outbox_events_owner_created",
        "outbox_events",
        ["owner_user_id", "created_at"],
    )
    op.create_index(
        "ix_outbox_events_household_created",
        "outbox_events",
        ["household_id", "created_at"],
    )


def upgrade() -> None:
    if context.is_offline_mode():
        if op.get_context().dialect.name != "postgresql":
            raise RuntimeError(
                f"Migration {revision}: offline SQL is supported only for PostgreSQL"
            )
        op.execute(
            sa.text(
                "DO $finance_0021$ BEGIN "
                "IF to_regclass(current_schema() || '.outbox_events') IS NOT NULL THEN "
                "RAISE EXCEPTION 'Migration 20260919_0021 offline SQL supports only a fresh "
                "outbox_events path; use online Alembic for a preexisting table'; "
                "END IF; "
                "IF to_regclass(current_schema() || '.finance_alembic_object_ownership') "
                "IS NOT NULL THEN "
                "RAISE EXCEPTION 'Migration 20260919_0021 ownership table already exists'; "
                "END IF; END $finance_0021$;"
            )
        )
        _create_ownership_table()
        _create_outbox_events()
        _record_owned("table", "outbox_events")
        op.add_column("outbox_events", sa.Column("deduplication_key", sa.Text(), nullable=True))
        _record_owned("column", "outbox_events.deduplication_key")
        op.create_index(
            "uq_outbox_events_deduplication_key",
            "outbox_events",
            ["deduplication_key"],
            unique=True,
            postgresql_where=sa.text("deduplication_key IS NOT NULL"),
            sqlite_where=sa.text("deduplication_key IS NOT NULL"),
        )
        _record_owned("index", "uq_outbox_events_deduplication_key")
        _create_recommendation_tables()
        return

    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(OWNERSHIP_TABLE):
        raise RuntimeError(f"Migration {revision}: ownership table already exists")
    outbox_exists = inspector.has_table("outbox_events")
    if outbox_exists:
        columns, has_dedup_index = _validate_existing_outbox(inspector)
    else:
        columns, has_dedup_index = set(), False

    _create_ownership_table()
    if not outbox_exists:
        _create_outbox_events()
        _record_owned("table", "outbox_events")
    if "deduplication_key" not in columns:
        op.add_column("outbox_events", sa.Column("deduplication_key", sa.Text(), nullable=True))
        _record_owned("column", "outbox_events.deduplication_key")
    if not has_dedup_index:
        op.create_index(
            "uq_outbox_events_deduplication_key",
            "outbox_events",
            ["deduplication_key"],
            unique=True,
            postgresql_where=sa.text("deduplication_key IS NOT NULL"),
            sqlite_where=sa.text("deduplication_key IS NOT NULL"),
        )
        _record_owned("index", "uq_outbox_events_deduplication_key")
    _create_recommendation_tables()


def _create_recommendation_tables() -> None:
    op.create_table(
        "recommendation_jobs",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_user_id", UUID, nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("market_data_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint(
            "status IN ('queued', 'collecting', 'analyzing', 'ready', 'failed')",
            name=op.f("ck_recommendation_jobs_status_valid"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 1 AND attempt_count <= 3",
            name=op.f("ck_recommendation_jobs_attempt_count_range"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name=op.f("fk_recommendation_jobs_owner_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendation_jobs")),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name=op.f("uq_recommendation_jobs_owner_idempotency_key"),
        ),
    )
    op.create_index(
        "ix_recommendation_jobs_owner_created",
        "recommendation_jobs",
        ["owner_user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_recommendation_jobs_status_created", "recommendation_jobs", ["status", "created_at"]
    )

    op.create_table(
        "recommendation_job_snapshots",
        sa.Column("id", UUID, nullable=False),
        sa.Column("job_id", UUID, nullable=False),
        sa.Column("snapshot_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["recommendation_jobs.id"],
            name=op.f("fk_recommendation_job_snapshots_job_id_recommendation_jobs"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["portfolio_snapshots.id"],
            name=op.f("fk_recommendation_job_snapshots_snapshot_id_portfolio_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendation_job_snapshots")),
        sa.UniqueConstraint(
            "job_id", "snapshot_id", name=op.f("uq_recommendation_job_snapshots_pair")
        ),
    )

    op.create_table(
        "recommendation_reports",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_user_id", UUID, nullable=False),
        sa.Column("job_id", UUID, nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_recommendation_reports_owner_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["recommendation_jobs.id"],
            name=op.f("fk_recommendation_reports_job_id_recommendation_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendation_reports")),
        sa.UniqueConstraint("job_id", name=op.f("uq_recommendation_reports_job_id")),
    )
    op.create_index(
        "ix_recommendation_reports_owner_generated",
        "recommendation_reports",
        ["owner_user_id", sa.text("generated_at DESC")],
    )

    op.create_table(
        "recommendation_actions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("report_id", UUID, nullable=False),
        sa.Column("instrument_name", sa.Text(), nullable=False),
        sa.Column("ticker", sa.Text(), nullable=True),
        sa.Column("isin", sa.Text(), nullable=True),
        sa.Column("risk_bucket", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("current_percent", PERCENT, nullable=False),
        sa.Column("target_percent", PERCENT, nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("risks", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "action IN ('keep', 'reduce', 'increase', 'add')",
            name=op.f("ck_recommendation_actions_action_valid"),
        ),
        sa.CheckConstraint(
            "priority >= 1 AND priority <= 100",
            name=op.f("ck_recommendation_actions_priority_range"),
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["recommendation_reports.id"],
            name=op.f("fk_recommendation_actions_report_id_recommendation_reports"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendation_actions")),
    )
    op.create_index(
        "ix_recommendation_actions_report_priority",
        "recommendation_actions",
        ["report_id", "priority"],
    )

    op.create_table(
        "recommendation_sources",
        sa.Column("id", UUID, nullable=False),
        sa.Column("report_id", UUID, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("publisher", sa.Text(), nullable=False),
        sa.Column("trust_tier", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["recommendation_reports.id"],
            name=op.f("fk_recommendation_sources_report_id_recommendation_reports"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendation_sources")),
    )
    op.create_index("ix_recommendation_sources_report", "recommendation_sources", ["report_id"])

    op.create_table(
        "recommendation_callback_nonces",
        sa.Column("id", UUID, nullable=False),
        sa.Column("job_id", UUID, nullable=False),
        sa.Column("nonce", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["recommendation_jobs.id"],
            name=op.f("fk_recommendation_callback_nonces_job_id_recommendation_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendation_callback_nonces")),
        sa.UniqueConstraint("nonce", name=op.f("uq_recommendation_callback_nonces_nonce")),
    )
    op.create_index(
        "ix_recommendation_callback_nonces_expires",
        "recommendation_callback_nonces",
        ["expires_at"],
    )


def _downgrade_targets_0020_only() -> bool:
    target = context.get_revision_argument()
    if isinstance(target, (tuple, list)):
        return tuple(target) == (down_revision,)
    return target == down_revision


def _guard_outbox_downgrade() -> None:
    targets_0020_only = _downgrade_targets_0020_only()
    if context.is_offline_mode():
        below_0020_guard = ""
        if not targets_0020_only:
            below_0020_guard = (
                "IF NOT EXISTS (SELECT 1 FROM finance_alembic_object_ownership "
                "WHERE revision_id='20260919_0021' AND object_type='table' "
                "AND object_name='outbox_events') THEN "
                "RAISE EXCEPTION 'Migration 20260919_0021 cannot downgrade below 0020: "
                "preexisting outbox_events is not owned by this revision'; END IF; "
            )
        op.execute(
            sa.text(
                "DO $finance_0021_guard$ BEGIN "
                "IF to_regclass(current_schema() || '.finance_alembic_object_ownership') "
                "IS NULL THEN "
                "RAISE EXCEPTION 'Migration 20260919_0021 cannot safely downgrade: "
                "ownership metadata is unavailable for a legacy-applied revision'; "
                "END IF; "
                f"{below_0020_guard}"
                "END $finance_0021_guard$;"
            )
        )
        return

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(OWNERSHIP_TABLE):
        raise RuntimeError(
            f"Migration {revision} cannot safely downgrade: ownership metadata is "
            "unavailable for a legacy-applied revision"
        )
    if targets_0020_only:
        return
    owns_table = op.get_bind().scalar(
        sa.text(
            f"SELECT EXISTS (SELECT 1 FROM {OWNERSHIP_TABLE} "
            "WHERE revision_id=:revision_id AND object_type='table' "
            "AND object_name='outbox_events')"
        ),
        {"revision_id": OWNERSHIP_REVISION},
    )
    if not owns_table:
        raise RuntimeError(
            f"Migration {revision} cannot downgrade below {down_revision}: preexisting "
            "outbox_events is not owned by this revision"
        )


def downgrade() -> None:
    _guard_outbox_downgrade()
    op.drop_index(
        "ix_recommendation_callback_nonces_expires", table_name="recommendation_callback_nonces"
    )
    op.drop_table("recommendation_callback_nonces")
    op.drop_index("ix_recommendation_sources_report", table_name="recommendation_sources")
    op.drop_table("recommendation_sources")
    op.drop_index("ix_recommendation_actions_report_priority", table_name="recommendation_actions")
    op.drop_table("recommendation_actions")
    op.drop_index("ix_recommendation_reports_owner_generated", table_name="recommendation_reports")
    op.drop_table("recommendation_reports")
    op.drop_table("recommendation_job_snapshots")
    op.drop_index("ix_recommendation_jobs_status_created", table_name="recommendation_jobs")
    op.drop_index("ix_recommendation_jobs_owner_created", table_name="recommendation_jobs")
    op.drop_table("recommendation_jobs")
    if context.is_offline_mode():
        if op.get_context().dialect.name != "postgresql":
            raise RuntimeError(
                f"Migration {revision}: offline SQL is supported only for PostgreSQL"
            )
        op.execute(
            sa.text(
                "DO $finance_0021$ DECLARE owns_table boolean; owns_column boolean; "
                "owns_index boolean; BEGIN "
                "IF to_regclass(current_schema() || '.finance_alembic_object_ownership') "
                "IS NULL THEN "
                "RAISE EXCEPTION 'Migration 20260919_0021 ownership metadata disappeared "
                "during downgrade'; END IF; "
                "SELECT EXISTS (SELECT 1 FROM finance_alembic_object_ownership "
                "WHERE revision_id='20260919_0021' AND object_type='table' "
                "AND object_name='outbox_events') INTO owns_table; "
                "SELECT EXISTS (SELECT 1 FROM finance_alembic_object_ownership "
                "WHERE revision_id='20260919_0021' AND object_type='column' "
                "AND object_name='outbox_events.deduplication_key') INTO owns_column; "
                "SELECT EXISTS (SELECT 1 FROM finance_alembic_object_ownership "
                "WHERE revision_id='20260919_0021' AND object_type='index' "
                "AND object_name='uq_outbox_events_deduplication_key') INTO owns_index; "
                "IF owns_table THEN DROP TABLE outbox_events; ELSE "
                "IF owns_index THEN DROP INDEX IF EXISTS uq_outbox_events_deduplication_key; "
                "END IF; "
                "IF owns_column THEN ALTER TABLE outbox_events DROP COLUMN deduplication_key; "
                "END IF; END IF; "
                "DROP TABLE finance_alembic_object_ownership; END $finance_0021$;"
            )
        )
        return

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(OWNERSHIP_TABLE):
        raise RuntimeError(f"Migration {revision}: ownership metadata disappeared during downgrade")
    owned = {
        (row.object_type, row.object_name)
        for row in op.get_bind()
        .execute(
            sa.text(
                f"SELECT object_type, object_name FROM {OWNERSHIP_TABLE} "
                "WHERE revision_id=:revision_id"
            ),
            {"revision_id": OWNERSHIP_REVISION},
        )
        .fetchall()
    }
    if ("table", "outbox_events") in owned:
        op.drop_table("outbox_events")
    else:
        indexes = {
            index["name"] for index in sa.inspect(op.get_bind()).get_indexes("outbox_events")
        }
        if (
            ("index", "uq_outbox_events_deduplication_key") in owned
            and "uq_outbox_events_deduplication_key" in indexes
        ):
            op.drop_index("uq_outbox_events_deduplication_key", table_name="outbox_events")
        columns = {
            column["name"] for column in sa.inspect(op.get_bind()).get_columns("outbox_events")
        }
        if (
            ("column", "outbox_events.deduplication_key") in owned
            and "deduplication_key" in columns
        ):
            op.drop_column("outbox_events", "deduplication_key")
    op.drop_table(OWNERSHIP_TABLE)
