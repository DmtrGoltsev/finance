"""Add planning allocation recurrence, savings goals, and progress metadata.

Revision ID: 20260607_0013
Revises: 20260607_0012
Create Date: 2026-06-07

Rollback notes:
- Downgrade drops only additive planning allocation metadata.
- No transactions, balances, categories, accounts, or production data are mutated.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260607_0013"
down_revision: str | None = "20260607_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MONEY = sa.Numeric(20, 4)


def upgrade() -> None:
    with op.batch_alter_table("planning_allocations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "recurrence_type",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'regular'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "is_savings_goal",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch_op.add_column(sa.Column("goal_target_amount", MONEY, nullable=True))
        batch_op.add_column(sa.Column("goal_due_month", sa.Date(), nullable=True))
        batch_op.create_check_constraint(
            op.f("ck_planning_allocations_recurrence_type_valid"),
            "recurrence_type IN ('regular', 'one_off')",
        )
        batch_op.create_check_constraint(
            op.f("ck_planning_allocations_positive_goal_target_amount"),
            "goal_target_amount IS NULL OR goal_target_amount > 0",
        )
        batch_op.create_check_constraint(
            op.f("ck_planning_allocations_savings_goal_investment_target"),
            "is_savings_goal = false OR target_type = 'investment_asset_category'",
        )


def downgrade() -> None:
    with op.batch_alter_table("planning_allocations") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_planning_allocations_savings_goal_investment_target"),
            type_="check",
        )
        batch_op.drop_constraint(
            op.f("ck_planning_allocations_positive_goal_target_amount"),
            type_="check",
        )
        batch_op.drop_constraint(
            op.f("ck_planning_allocations_recurrence_type_valid"),
            type_="check",
        )
        batch_op.drop_column("goal_due_month")
        batch_op.drop_column("goal_target_amount")
        batch_op.drop_column("is_savings_goal")
        batch_op.drop_column("recurrence_type")
