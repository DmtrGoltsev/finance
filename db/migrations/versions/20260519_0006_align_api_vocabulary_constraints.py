"""Align account and transaction CHECK constraints with API vocabulary.

Revision ID: 20260519_0006
Revises: 20260518_0005
Create Date: 2026-05-19

Rollback notes:
- Downgrade restores the previous narrower CHECK constraints.
- Downgrade will fail safely if rows using the expanded vocabulary exist.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260519_0006"
down_revision: str | None = "20260518_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ACCOUNT_TYPE_CONSTRAINT = "ck_accounts_account_type_valid"
TRANSACTION_TYPE_CONSTRAINT = "ck_transactions_transaction_type_valid"

ACCOUNT_TYPES = ("cash", "bank", "deposit", "brokerage", "card", "metal", "other")
PREVIOUS_ACCOUNT_TYPES = ("cash", "bank", "deposit", "brokerage")

TRANSACTION_TYPES = (
    "income",
    "expense",
    "transfer",
    "brokerage",
    "asset_buy",
    "asset_sell",
    "interest",
    "dividend",
    "adjustment",
)
PREVIOUS_TRANSACTION_TYPES = ("income", "expense", "transfer", "brokerage")


def upgrade() -> None:
    _replace_check_constraint(
        table_name="accounts",
        constraint_name=ACCOUNT_TYPE_CONSTRAINT,
        condition=_in_values("account_type", ACCOUNT_TYPES),
    )
    _replace_check_constraint(
        table_name="transactions",
        constraint_name=TRANSACTION_TYPE_CONSTRAINT,
        condition=_in_values("transaction_type", TRANSACTION_TYPES),
    )


def downgrade() -> None:
    _replace_check_constraint(
        table_name="transactions",
        constraint_name=TRANSACTION_TYPE_CONSTRAINT,
        condition=_in_values("transaction_type", PREVIOUS_TRANSACTION_TYPES),
    )
    _replace_check_constraint(
        table_name="accounts",
        constraint_name=ACCOUNT_TYPE_CONSTRAINT,
        condition=_in_values("account_type", PREVIOUS_ACCOUNT_TYPES),
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
