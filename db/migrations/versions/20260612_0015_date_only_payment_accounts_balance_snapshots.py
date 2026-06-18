"""Add date-only finance contract fields and balance snapshots.

Revision ID: 20260612_0015
Revises: 20260608_0014
Create Date: 2026-06-12

Rollback notes:
- Downgrade drops additive date-only columns, payment-account flag, and balance
  snapshots only.
- Existing legacy occurred_at datetimes and account balances are preserved.
- Snapshot backfill anchors on the persisted current balance and reverses
  dated active transactions to create deterministic month-end and transaction
  date balances. This is exact only when current_balance already reflects the
  active ledger under the balance-effect mapping below; otherwise it is the
  best deterministic historical approximation and keeps the limitation visible
  through snapshot dates.
"""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260612_0015"
down_revision: str | None = "20260608_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UUID = postgresql.UUID(as_uuid=True)
MONEY = sa.Numeric(20, 4)
ZERO = Decimal("0.0000")

BALANCE_POSITIVE_TRANSACTION_TYPES = frozenset(
    {"income", "brokerage", "asset_buy", "interest", "dividend", "adjustment"}
)
BALANCE_NEGATIVE_TRANSACTION_TYPES = frozenset({"expense", "asset_sell"})


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
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_payment_account",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            )
        )
        batch_op.create_index(
            "ix_accounts_payment_status",
            ["is_payment_account", "record_status"],
        )

    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(sa.Column("transaction_date", sa.Date(), nullable=True))

    _backfill_transaction_dates()
    _set_column_not_null("transactions", "transaction_date", sa.Date())

    op.create_index(
        "ix_transactions_account_transaction_date_status",
        "transactions",
        ["account_id", sa.text("transaction_date DESC"), "record_status"],
    )
    op.create_index(
        "ix_transactions_category_transaction_date",
        "transactions",
        ["category_id", sa.text("transaction_date DESC")],
        postgresql_where=sa.text("category_id IS NOT NULL"),
    )

    with op.batch_alter_table("capture_drafts") as batch_op:
        batch_op.add_column(sa.Column("occurred_date", sa.Date(), nullable=True))

    _backfill_capture_draft_dates()

    op.create_table(
        "account_balance_snapshots",
        *_base_columns(),
        sa.Column("account_id", UUID, nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("balance_amount", MONEY, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name=op.f("ck_account_balance_snapshots_currency_iso_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_account_balance_snapshots_account_id_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_balance_snapshots")),
    )
    op.create_index(
        "ix_account_balance_snapshots_account_date_created",
        "account_balance_snapshots",
        ["account_id", sa.text("snapshot_date DESC"), sa.text("created_at DESC")],
    )
    _backfill_account_balance_snapshots()


def downgrade() -> None:
    op.drop_index(
        "ix_account_balance_snapshots_account_date_created",
        table_name="account_balance_snapshots",
    )
    op.drop_table("account_balance_snapshots")

    with op.batch_alter_table("capture_drafts") as batch_op:
        batch_op.drop_column("occurred_date")

    op.drop_index("ix_transactions_category_transaction_date", table_name="transactions")
    op.drop_index(
        "ix_transactions_account_transaction_date_status",
        table_name="transactions",
    )
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_column("transaction_date")

    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_index("ix_accounts_payment_status")
        batch_op.drop_column("is_payment_account")


def _backfill_transaction_dates() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "UPDATE transactions "
            "SET transaction_date = (occurred_at AT TIME ZONE 'UTC')::date "
            "WHERE transaction_date IS NULL"
        )
        return
    op.execute(
        "UPDATE transactions "
        "SET transaction_date = date(occurred_at) "
        "WHERE transaction_date IS NULL"
    )


def _backfill_capture_draft_dates() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "UPDATE capture_drafts "
            "SET occurred_date = (occurred_at AT TIME ZONE 'UTC')::date "
            "WHERE occurred_at IS NOT NULL AND occurred_date IS NULL"
        )
        return
    op.execute(
        "UPDATE capture_drafts "
        "SET occurred_date = date(occurred_at) "
        "WHERE occurred_at IS NOT NULL AND occurred_date IS NULL"
    )


def _backfill_account_balance_snapshots() -> None:
    bind = op.get_bind()
    accounts = sa.table(
        "accounts",
        sa.column("id", UUID),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("initial_balance_amount", MONEY),
        sa.column("current_balance_amount", MONEY),
        sa.column("currency", sa.String(length=3)),
    )
    transactions = sa.table(
        "transactions",
        sa.column("transaction_type", sa.String()),
        sa.column("account_id", UUID),
        sa.column("counterparty_account_id", UUID),
        sa.column("amount", MONEY),
        sa.column("transaction_date", sa.Date()),
        sa.column("transfer_status", sa.String()),
        sa.column("record_status", sa.String()),
    )
    snapshots = sa.table(
        "account_balance_snapshots",
        sa.column("id", UUID),
        sa.column("account_id", UUID),
        sa.column("snapshot_date", sa.Date()),
        sa.column("balance_amount", MONEY),
        sa.column("currency", sa.String(length=3)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("version", sa.BigInteger()),
    )
    rows = bind.execute(
        sa.select(
            accounts.c.id,
            accounts.c.created_at,
            accounts.c.updated_at,
            accounts.c.initial_balance_amount,
            accounts.c.current_balance_amount,
            accounts.c.currency,
        )
    ).mappings()
    transaction_rows = bind.execute(
        sa.select(
            transactions.c.transaction_type,
            transactions.c.account_id,
            transactions.c.counterparty_account_id,
            transactions.c.amount,
            transactions.c.transaction_date,
            transactions.c.transfer_status,
        ).where(transactions.c.record_status == "active")
    ).mappings()

    deltas_by_account_date: dict[object, dict[date, Decimal]] = defaultdict(
        lambda: defaultdict(lambda: ZERO)
    )
    latest_transaction_date_by_account: dict[object, date] = {}
    transaction_dates_by_account: dict[object, set[date]] = defaultdict(set)
    for row in transaction_rows:
        transaction_date = _date_from_value(row["transaction_date"])
        for account_id, delta in _transaction_balance_deltas(row):
            deltas_by_account_date[account_id][transaction_date] += delta
            transaction_dates_by_account[account_id].add(transaction_date)
            latest_transaction_date_by_account[account_id] = max(
                transaction_date,
                latest_transaction_date_by_account.get(account_id, transaction_date),
            )

    payload = []
    for row in rows:
        account_id = row["id"]
        created_at = _datetime_from_value(row["created_at"])
        updated_at = _datetime_from_value(row["updated_at"])
        known_transaction_dates = transaction_dates_by_account.get(account_id, set())
        start_date = min(created_at.date(), *(known_transaction_dates or {created_at.date()}))
        anchor_date = max(
            updated_at.date(),
            latest_transaction_date_by_account.get(account_id, updated_at.date()),
        )
        current_balance = (
            Decimal(row["current_balance_amount"])
            if row["current_balance_amount"] is not None
            else Decimal(row["initial_balance_amount"])
        )
        future_delta = ZERO
        for snapshot_date in sorted(
            _snapshot_dates(
                start_date=start_date,
                anchor_date=anchor_date,
                transaction_dates=known_transaction_dates,
            ),
            reverse=True,
        ):
            payload.append(
                {
                    "id": uuid4(),
                    "account_id": account_id,
                    "snapshot_date": snapshot_date,
                    "balance_amount": current_balance - future_delta,
                    "currency": row["currency"],
                    "created_at": updated_at,
                    "updated_at": updated_at,
                    "version": 1,
                }
            )
            future_delta += deltas_by_account_date[account_id].get(snapshot_date, ZERO)
    if payload:
        op.bulk_insert(snapshots, payload)


def _transaction_balance_deltas(row):
    transaction_type = row["transaction_type"]
    amount = Decimal(row["amount"])
    if transaction_type == "transfer":
        if row["transfer_status"] != "posted" or row["counterparty_account_id"] is None:
            return ()
        return (
            (row["account_id"], -amount),
            (row["counterparty_account_id"], amount),
        )
    if transaction_type in BALANCE_POSITIVE_TRANSACTION_TYPES:
        return ((row["account_id"], amount),)
    if transaction_type in BALANCE_NEGATIVE_TRANSACTION_TYPES:
        return ((row["account_id"], -amount),)
    return ()


def _snapshot_dates(
    *,
    start_date: date,
    anchor_date: date,
    transaction_dates: set[date],
) -> set[date]:
    dates = {start_date, anchor_date}
    dates.update(value for value in transaction_dates if start_date <= value <= anchor_date)
    dates.update(_month_end_dates(start_date, anchor_date))
    return dates


def _month_end_dates(start_date: date, anchor_date: date):
    current = date(start_date.year, start_date.month, 1)
    while current <= anchor_date:
        month_end = date(current.year, current.month, monthrange(current.year, current.month)[1])
        if start_date <= month_end <= anchor_date:
            yield month_end
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)


def _date_from_value(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return _datetime_from_value(value).date()


def _datetime_from_value(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _set_column_not_null(
    table_name: str,
    column_name: str,
    column_type: sa.types.TypeEngine,
) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table_name, recreate="always") as batch_op:
            batch_op.alter_column(
                column_name,
                existing_type=column_type,
                nullable=False,
            )
        return
    op.alter_column(table_name, column_name, existing_type=column_type, nullable=False)
