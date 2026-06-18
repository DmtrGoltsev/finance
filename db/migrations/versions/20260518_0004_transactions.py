"""Create manual transactions table.

Revision ID: 20260518_0004
Revises: 20260518_0003
Create Date: 2026-05-18

Rollback notes:
- Downgrade drops only the transactions table and its indexes.
- Account/category/user prerequisite data is preserved.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260518_0004"
down_revision: str | None = "20260518_0003"
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
        "transactions",
        *_base_columns(),
        sa.Column("transaction_type", sa.Text(), nullable=False),
        sa.Column("account_id", UUID, nullable=False),
        sa.Column("counterparty_account_id", UUID, nullable=True),
        sa.Column("category_id", UUID, nullable=True),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("transfer_scope", sa.Text(), nullable=True),
        sa.Column("transfer_status", sa.Text(), nullable=True),
        sa.Column("record_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_by_user_id", UUID, nullable=False),
        sa.Column("last_edited_by_user_id", UUID, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "transaction_type IN ('income', 'expense', 'transfer', 'brokerage')",
            name=op.f("ck_transactions_transaction_type_valid"),
        ),
        sa.CheckConstraint(
            "source_type IN ('manual')",
            name=op.f("ck_transactions_source_type_valid"),
        ),
        sa.CheckConstraint(
            "source_type = 'manual'",
            name=op.f("ck_transactions_source_type_manual_only"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_transactions_positive_amount")),
        sa.CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name=op.f("ck_transactions_currency_iso_shape"),
        ),
        sa.CheckConstraint(
            "(transaction_type = 'transfer' "
            "AND counterparty_account_id IS NOT NULL "
            "AND counterparty_account_id <> account_id "
            "AND category_id IS NULL "
            "AND transfer_scope IN ('personal_same_owner', 'household_same_household') "
            "AND transfer_status IN ('posted', 'voided')) "
            "OR (transaction_type <> 'transfer' "
            "AND counterparty_account_id IS NULL "
            "AND transfer_scope IS NULL "
            "AND transfer_status IS NULL)",
            name=op.f("ck_transactions_transfer_shape"),
        ),
        sa.CheckConstraint(
            "transaction_type NOT IN ('income', 'expense') OR category_id IS NOT NULL",
            name=op.f("ck_transactions_income_expense_category_required"),
        ),
        sa.CheckConstraint(
            "record_status IN ('active', 'deleted')",
            name=op.f("ck_transactions_record_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_transactions_account_id_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["counterparty_account_id"],
            ["accounts.id"],
            name=op.f("fk_transactions_counterparty_account_id_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_transactions_category_id_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_transactions_created_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["last_edited_by_user_id"],
            ["users.id"],
            name=op.f("fk_transactions_last_edited_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
    )
    op.create_index(
        "ix_transactions_account_occurred_status",
        "transactions",
        ["account_id", sa.text("occurred_at DESC"), "record_status"],
    )
    op.create_index(
        "ix_transactions_category_occurred",
        "transactions",
        ["category_id", sa.text("occurred_at DESC")],
        postgresql_where=sa.text("category_id IS NOT NULL"),
    )
    op.create_index(
        "ix_transactions_counterparty_account",
        "transactions",
        ["counterparty_account_id"],
        postgresql_where=sa.text("counterparty_account_id IS NOT NULL"),
    )
    op.create_index(
        "ix_transactions_created_by_occurred",
        "transactions",
        ["created_by_user_id", sa.text("occurred_at DESC")],
    )
    op.create_index("ix_transactions_source_type", "transactions", ["source_type"])


def downgrade() -> None:
    op.drop_index("ix_transactions_source_type", table_name="transactions")
    op.drop_index("ix_transactions_created_by_occurred", table_name="transactions")
    op.drop_index("ix_transactions_counterparty_account", table_name="transactions")
    op.drop_index("ix_transactions_category_occurred", table_name="transactions")
    op.drop_index("ix_transactions_account_occurred_status", table_name="transactions")
    op.drop_table("transactions")
