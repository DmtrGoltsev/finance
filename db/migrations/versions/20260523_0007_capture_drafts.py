"""Create safe auto-capture drafts table.

Revision ID: 20260523_0007
Revises: 20260519_0006
Create Date: 2026-05-23

Rollback notes:
- Downgrade drops only capture_drafts and its indexes.
- No raw screenshot image or OCR payload columns are created by this revision.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260523_0007"
down_revision: str | None = "20260519_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UUID = postgresql.UUID(as_uuid=True)
MONEY = sa.Numeric(20, 4)


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", UUID, nullable=False),
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
        sa.Column("version", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
    ]


def upgrade() -> None:
    op.create_table(
        "capture_drafts",
        *_base_columns(),
        sa.Column("owner_user_id", UUID, nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("capture_source", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("merchant_name", sa.Text(), nullable=True),
        sa.Column("account_id", UUID, nullable=True),
        sa.Column("category_id", UUID, nullable=True),
        sa.Column("transaction_id", UUID, nullable=True),
        sa.Column("confidence", MONEY, nullable=True),
        sa.Column("source_app_package", sa.Text(), nullable=True),
        sa.Column("source_app_label", sa.Text(), nullable=True),
        sa.Column("evidence_hash", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'discarded')",
            name=op.f("ck_capture_drafts_status_valid"),
        ),
        sa.CheckConstraint(
            "capture_source IN ('sms', 'notification', 'screenshot')",
            name=op.f("ck_capture_drafts_capture_source_valid"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_capture_drafts_positive_amount")),
        sa.CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name=op.f("ck_capture_drafts_currency_iso_shape"),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_capture_drafts_confidence_range"),
        ),
        sa.CheckConstraint(
            "(status = 'confirmed' AND transaction_id IS NOT NULL) OR "
            "(status <> 'confirmed' AND transaction_id IS NULL)",
            name=op.f("ck_capture_drafts_confirmed_transaction_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_capture_drafts_owner_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_capture_drafts_account_id_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_capture_drafts_category_id_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=op.f("fk_capture_drafts_transaction_id_transactions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_capture_drafts")),
    )
    op.create_index(
        "uq_capture_drafts_owner_idempotency_key",
        "capture_drafts",
        ["owner_user_id", "idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_capture_drafts_owner_status_created",
        "capture_drafts",
        ["owner_user_id", "status", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_capture_drafts_transaction_id",
        "capture_drafts",
        ["transaction_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_capture_drafts_transaction_id", table_name="capture_drafts")
    op.drop_index("ix_capture_drafts_owner_status_created", table_name="capture_drafts")
    op.drop_index("uq_capture_drafts_owner_idempotency_key", table_name="capture_drafts")
    op.drop_table("capture_drafts")
