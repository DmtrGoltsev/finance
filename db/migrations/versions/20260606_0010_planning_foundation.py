"""Create planning plans, income sources, and allocations.

Revision ID: 20260606_0010
Revises: 20260531_0009
Create Date: 2026-06-06

Rollback notes:
- Downgrade drops only planning allocation/source/plan tables and indexes.
- Planning confirmation stores planning state only and has no transaction FK.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260606_0010"
down_revision: str | None = "20260531_0009"
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
        "planning_plans",
        *_base_columns(),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("owner_user_id", UUID, nullable=True),
        sa.Column("household_id", UUID, nullable=True),
        sa.Column("plan_month", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("created_by_user_id", UUID, nullable=False),
        sa.CheckConstraint(
            "scope_type IN ('personal', 'household')",
            name=op.f("ck_planning_plans_scope_type_valid"),
        ),
        sa.CheckConstraint(
            "(scope_type = 'personal' AND owner_user_id IS NOT NULL AND household_id IS NULL) "
            "OR (scope_type = 'household' AND household_id IS NOT NULL AND owner_user_id IS NULL)",
            name=op.f("ck_planning_plans_exactly_one_scope"),
        ),
        sa.CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name=op.f("ck_planning_plans_currency_iso_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_planning_plans_owner_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_planning_plans_household_id_households"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_planning_plans_created_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_planning_plans")),
    )
    op.create_index(
        "uq_planning_plans_personal_month",
        "planning_plans",
        ["owner_user_id", "plan_month"],
        unique=True,
        postgresql_where=sa.text("scope_type = 'personal'"),
    )
    op.create_index(
        "uq_planning_plans_household_month",
        "planning_plans",
        ["household_id", "plan_month"],
        unique=True,
        postgresql_where=sa.text("scope_type = 'household'"),
    )
    op.create_index(
        "ix_planning_plans_owner_month",
        "planning_plans",
        ["owner_user_id", sa.text("plan_month DESC")],
    )
    op.create_index(
        "ix_planning_plans_household_month",
        "planning_plans",
        ["household_id", sa.text("plan_month DESC")],
    )

    op.create_table(
        "planning_income_sources",
        *_base_columns(),
        sa.Column("plan_id", UUID, nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=False),
        sa.Column(
            "confirmation_state",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'planned'"),
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", UUID, nullable=True),
        sa.Column("created_by_user_id", UUID, nullable=False),
        sa.CheckConstraint(
            "amount > 0",
            name=op.f("ck_planning_income_sources_positive_amount"),
        ),
        sa.CheckConstraint(
            "day_of_month >= 1 AND day_of_month <= 31",
            name=op.f("ck_planning_income_sources_day_of_month_range"),
        ),
        sa.CheckConstraint(
            "confirmation_state IN ('planned', 'confirmed')",
            name=op.f("ck_planning_income_sources_confirmation_state_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["planning_plans.id"],
            name=op.f("fk_planning_income_sources_plan_id_planning_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_planning_income_sources_confirmed_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_planning_income_sources_created_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_planning_income_sources")),
    )
    op.create_index(
        "ix_planning_income_sources_plan_id",
        "planning_income_sources",
        ["plan_id"],
    )
    op.create_index(
        "ix_planning_income_sources_plan_state",
        "planning_income_sources",
        ["plan_id", "confirmation_state"],
    )

    op.create_table(
        "planning_allocations",
        *_base_columns(),
        sa.Column("plan_id", UUID, nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", UUID, nullable=True),
        sa.Column("target_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "requires_attention",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("attention_reason", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("allocation_mode", sa.Text(), nullable=False),
        sa.Column("allocation_value", MONEY, nullable=False),
        sa.Column("created_by_user_id", UUID, nullable=False),
        sa.CheckConstraint(
            "target_type IN ('expense_category', 'account')",
            name=op.f("ck_planning_allocations_target_type_valid"),
        ),
        sa.CheckConstraint(
            "allocation_mode IN ('amount', 'percent')",
            name=op.f("ck_planning_allocations_allocation_mode_valid"),
        ),
        sa.CheckConstraint(
            "allocation_value >= 0",
            name=op.f("ck_planning_allocations_non_negative_allocation_value"),
        ),
        sa.CheckConstraint(
            "(target_id IS NOT NULL AND requires_attention = false) "
            "OR (target_id IS NULL AND requires_attention = true)",
            name=op.f("ck_planning_allocations_target_attention_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["planning_plans.id"],
            name=op.f("fk_planning_allocations_plan_id_planning_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_planning_allocations_created_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_planning_allocations")),
    )
    op.create_index(
        "ix_planning_allocations_plan_id",
        "planning_allocations",
        ["plan_id"],
    )
    op.create_index(
        "ix_planning_allocations_plan_attention",
        "planning_allocations",
        ["plan_id", "requires_attention"],
    )


def downgrade() -> None:
    op.drop_index("ix_planning_allocations_plan_attention", table_name="planning_allocations")
    op.drop_index("ix_planning_allocations_plan_id", table_name="planning_allocations")
    op.drop_table("planning_allocations")
    op.drop_index(
        "ix_planning_income_sources_plan_state",
        table_name="planning_income_sources",
    )
    op.drop_index("ix_planning_income_sources_plan_id", table_name="planning_income_sources")
    op.drop_table("planning_income_sources")
    op.drop_index("ix_planning_plans_household_month", table_name="planning_plans")
    op.drop_index("ix_planning_plans_owner_month", table_name="planning_plans")
    op.drop_index("uq_planning_plans_household_month", table_name="planning_plans")
    op.drop_index("uq_planning_plans_personal_month", table_name="planning_plans")
    op.drop_table("planning_plans")
