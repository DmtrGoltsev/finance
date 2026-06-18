"""Allow planning allocations to target account-backed assets.

Revision ID: 20260607_0011
Revises: 20260606_0010
Create Date: 2026-06-07

Rollback notes:
- Downgrade restores the previous target type vocabulary.
- Downgrade will fail safely if planning allocations with target_type='asset' exist.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260607_0011"
down_revision: str | None = "20260606_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PLANNING_ALLOCATION_TARGET_TYPE_CONSTRAINT = (
    "ck_planning_allocations_target_type_valid"
)
TARGET_TYPES = ("expense_category", "account", "asset")
PREVIOUS_TARGET_TYPES = ("expense_category", "account")


def upgrade() -> None:
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
