"""Add asynchronous investment recommendation jobs and reports.

Revision ID: 20260919_0021
Revises: 20260919_0020
Create Date: 2026-09-19
"""

from __future__ import annotations

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


def _ensure_outbox_events() -> None:
    if context.is_offline_mode():
        _create_outbox_events()
        return
    if not sa.inspect(op.get_bind()).has_table("outbox_events"):
        _create_outbox_events()


def upgrade() -> None:
    _ensure_outbox_events()
    if context.is_offline_mode():
        op.add_column("outbox_events", sa.Column("deduplication_key", sa.Text(), nullable=True))
        op.create_index(
            "uq_outbox_events_deduplication_key",
            "outbox_events",
            ["deduplication_key"],
            unique=True,
            postgresql_where=sa.text("deduplication_key IS NOT NULL"),
            sqlite_where=sa.text("deduplication_key IS NOT NULL"),
        )
        _create_recommendation_tables()
        return
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("outbox_events")}
    if "deduplication_key" not in columns:
        op.add_column("outbox_events", sa.Column("deduplication_key", sa.Text(), nullable=True))
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("outbox_events")}
    if "uq_outbox_events_deduplication_key" not in indexes:
        op.create_index(
            "uq_outbox_events_deduplication_key",
            "outbox_events",
            ["deduplication_key"],
            unique=True,
            postgresql_where=sa.text("deduplication_key IS NOT NULL"),
            sqlite_where=sa.text("deduplication_key IS NOT NULL"),
        )
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


def downgrade() -> None:
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
    op.drop_index("uq_outbox_events_deduplication_key", table_name="outbox_events")
    op.drop_column("outbox_events", "deduplication_key")
    # The core outbox table is retained because it is not owned by the investment slice.
