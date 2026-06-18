"""Add planning child tombstones for offline sync.

Revision ID: 20260618_0017
Revises: 20260614_0016
Create Date: 2026-06-18

Rollback notes:
- Downgrade removes only planning income/allocation tombstone fields and indexes.
- Planning plans and existing child business fields are not modified.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260618_0017"
down_revision: str | None = "20260614_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ACTIVE_DELETED_CHECK = "record_status IN ('active', 'deleted')"
DELETED_AT_SHAPE_CHECK = (
    "(record_status = 'active' AND deleted_at IS NULL) "
    "OR (record_status = 'deleted' AND deleted_at IS NOT NULL)"
)


def upgrade() -> None:
    _add_tombstone_columns("planning_income_sources")
    op.create_index(
        "ix_planning_income_sources_plan_status",
        "planning_income_sources",
        ["plan_id", "record_status"],
    )

    _add_tombstone_columns("planning_allocations")
    op.create_index(
        "ix_planning_allocations_plan_status",
        "planning_allocations",
        ["plan_id", "record_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_planning_allocations_plan_status",
        table_name="planning_allocations",
    )
    _drop_tombstone_columns("planning_allocations")

    op.drop_index(
        "ix_planning_income_sources_plan_status",
        table_name="planning_income_sources",
    )
    _drop_tombstone_columns("planning_income_sources")


def _add_tombstone_columns(table_name: str) -> None:
    with op.batch_alter_table(table_name, recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "record_status",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'active'"),
            )
        )
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_check_constraint(
            op.f(f"ck_{table_name}_record_status_valid"),
            ACTIVE_DELETED_CHECK,
        )
        batch_op.create_check_constraint(
            op.f(f"ck_{table_name}_record_status_deleted_at_shape"),
            DELETED_AT_SHAPE_CHECK,
        )


def _drop_tombstone_columns(table_name: str) -> None:
    with op.batch_alter_table(table_name, recreate="always") as batch_op:
        batch_op.drop_constraint(
            op.f(f"ck_{table_name}_record_status_deleted_at_shape"),
            type_="check",
        )
        batch_op.drop_constraint(op.f(f"ck_{table_name}_record_status_valid"), type_="check")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("record_status")
