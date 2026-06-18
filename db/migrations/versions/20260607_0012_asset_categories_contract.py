"""Add asset categories and investment planning target.

Revision ID: 20260607_0012
Revises: 20260607_0011
Create Date: 2026-06-07

Rollback notes:
- Downgrade drops only the additive nullable account link and asset category table.
- Downgrade restores the previous planning target vocabulary and will fail safely
  if investment_asset_category allocations still exist.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260607_0012"
down_revision: str | None = "20260607_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UUID = postgresql.UUID(as_uuid=True)
MONEY = sa.Numeric(20, 4)
ASSET_TYPES = ("cash", "bank", "card", "deposit", "brokerage", "metal", "other")
RECORD_STATUSES = ("active", "archived", "deleted")
TARGET_TYPES = ("expense_category", "account", "asset", "investment_asset_category")
PREVIOUS_TARGET_TYPES = ("expense_category", "account", "asset")
PLANNING_ALLOCATION_TARGET_TYPE_CONSTRAINT = (
    "ck_planning_allocations_target_type_valid"
)


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
        "asset_categories",
        *_base_columns(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("owner_user_id", UUID, nullable=True),
        sa.Column("household_id", UUID, nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("asset_type", sa.Text(), nullable=False),
        sa.Column("manual_amount", MONEY, nullable=False, server_default=sa.text("0")),
        sa.Column("is_investment", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("record_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_by_user_id", UUID, nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "scope_type IN ('personal', 'household')",
            name=op.f("ck_asset_categories_scope_type_valid"),
        ),
        sa.CheckConstraint(
            _in_values("asset_type", ASSET_TYPES),
            name=op.f("ck_asset_categories_asset_type_valid"),
        ),
        sa.CheckConstraint(
            "(scope_type = 'personal' AND owner_user_id IS NOT NULL AND household_id IS NULL) "
            "OR (scope_type = 'household' AND household_id IS NOT NULL AND owner_user_id IS NULL)",
            name=op.f("ck_asset_categories_exactly_one_scope"),
        ),
        sa.CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name=op.f("ck_asset_categories_currency_iso_shape"),
        ),
        sa.CheckConstraint(
            "manual_amount >= 0",
            name=op.f("ck_asset_categories_non_negative_manual_amount"),
        ),
        sa.CheckConstraint(
            _in_values("record_status", RECORD_STATUSES),
            name=op.f("ck_asset_categories_record_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_asset_categories_owner_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_asset_categories_household_id_households"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_asset_categories_created_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_categories")),
    )
    op.create_index(
        "ix_asset_categories_owner_status",
        "asset_categories",
        ["owner_user_id", "record_status"],
    )
    op.create_index(
        "ix_asset_categories_household_status",
        "asset_categories",
        ["household_id", "record_status"],
    )
    op.create_index(
        "ix_asset_categories_investment_status",
        "asset_categories",
        ["is_investment", "record_status"],
    )

    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(sa.Column("asset_category_id", UUID, nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_accounts_asset_category_id_asset_categories"),
            "asset_categories",
            ["asset_category_id"],
            ["id"],
        )
        batch_op.create_index("ix_accounts_asset_category_id", ["asset_category_id"])

    _replace_check_constraint(
        table_name="planning_allocations",
        constraint_name=PLANNING_ALLOCATION_TARGET_TYPE_CONSTRAINT,
        condition=_in_values("target_type", TARGET_TYPES),
    )


def downgrade() -> None:
    _replace_check_constraint(
        table_name="planning_allocations",
        constraint_name=PLANNING_ALLOCATION_TARGET_TYPE_CONSTRAINT,
        condition=_in_values("target_type", PREVIOUS_TARGET_TYPES),
    )

    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_index("ix_accounts_asset_category_id")
        batch_op.drop_constraint(
            op.f("fk_accounts_asset_category_id_asset_categories"),
            type_="foreignkey",
        )
        batch_op.drop_column("asset_category_id")

    op.drop_index("ix_asset_categories_investment_status", table_name="asset_categories")
    op.drop_index("ix_asset_categories_household_status", table_name="asset_categories")
    op.drop_index("ix_asset_categories_owner_status", table_name="asset_categories")
    op.drop_table("asset_categories")


def _in_values(column_name: str, values: tuple[str, ...]) -> str:
    quoted_values = ", ".join(f"'{value}'" for value in values)
    return f"{column_name} IN ({quoted_values})"


def _replace_check_constraint(
    *,
    table_name: str,
    constraint_name: str,
    condition: str,
) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name};")
        op.execute(
            f"ALTER TABLE {table_name} "
            f"ADD CONSTRAINT {constraint_name} CHECK ({condition}) NOT VALID;"
        )
        op.execute(f"ALTER TABLE {table_name} VALIDATE CONSTRAINT {constraint_name};")
        return

    with op.batch_alter_table(table_name, recreate="always") as batch_op:
        batch_op.drop_constraint(constraint_name, type_="check")
        batch_op.create_check_constraint(constraint_name, condition)
