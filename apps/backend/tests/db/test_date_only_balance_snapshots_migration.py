from __future__ import annotations

import importlib.util
import py_compile
import unittest
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa

REPO_ROOT = Path(__file__).resolve().parents[4]
REVISION_PATH = (
    REPO_ROOT
    / "db"
    / "migrations"
    / "versions"
    / "20260612_0015_date_only_payment_accounts_balance_snapshots.py"
)


def _load_revision_module():
    spec = importlib.util.spec_from_file_location("date_only_balance_snapshots", REVISION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DateOnlyBalanceSnapshotsMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = REVISION_PATH.read_text(encoding="utf-8")

    def test_revision_compiles_and_chains_after_asset_category_icon_key(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)

        module = _load_revision_module()

        self.assertEqual("20260612_0015", module.revision)
        self.assertEqual("20260608_0014", module.down_revision)

    def test_backfill_documents_deterministic_historical_limitations(self) -> None:
        for required in (
            "best deterministic historical approximation",
            "BALANCE_POSITIVE_TRANSACTION_TYPES",
            "_month_end_dates",
            "_transaction_balance_deltas",
        ):
            self.assertIn(required, self.source)

    def test_backfill_creates_month_end_snapshots_from_current_balance_and_ledger(
        self,
    ) -> None:
        module = _load_revision_module()
        metadata = sa.MetaData()
        accounts = sa.Table(
            "accounts",
            metadata,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("initial_balance_amount", sa.Numeric(20, 4), nullable=False),
            sa.Column("current_balance_amount", sa.Numeric(20, 4), nullable=True),
            sa.Column("currency", sa.String(3), nullable=False),
        )
        transactions = sa.Table(
            "transactions",
            metadata,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("transaction_type", sa.String(), nullable=False),
            sa.Column("account_id", sa.String(36), nullable=False),
            sa.Column("counterparty_account_id", sa.String(36), nullable=True),
            sa.Column("amount", sa.Numeric(20, 4), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("transaction_date", sa.Date(), nullable=False),
            sa.Column("transfer_status", sa.String(), nullable=True),
            sa.Column("record_status", sa.String(), nullable=False),
        )
        snapshots = sa.Table(
            "account_balance_snapshots",
            metadata,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("account_id", sa.String(36), nullable=False),
            sa.Column("snapshot_date", sa.Date(), nullable=False),
            sa.Column("balance_amount", sa.Numeric(20, 4), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("version", sa.BigInteger(), nullable=False),
        )
        engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)
        metadata.create_all(engine)
        observed_at = datetime(2026, 3, 31, 12, tzinfo=UTC)

        class FakeOp:
            def __init__(self, connection) -> None:  # type: ignore[no-untyped-def]
                self.connection = connection

            def get_bind(self):  # type: ignore[no-untyped-def]
                return self.connection

            def bulk_insert(self, _table, rows) -> None:  # type: ignore[no-untyped-def]
                normalized_rows = [{**row, "id": str(row["id"])} for row in rows]
                self.connection.execute(snapshots.insert(), normalized_rows)

        with engine.begin() as connection:
            connection.execute(
                accounts.insert(),
                [
                    {
                        "id": "acct-1",
                        "created_at": datetime(2026, 1, 1, 12, tzinfo=UTC),
                        "updated_at": observed_at,
                        "initial_balance_amount": Decimal("900.0000"),
                        "current_balance_amount": Decimal("1000.0000"),
                        "currency": "RUB",
                    },
                    {
                        "id": "acct-2",
                        "created_at": datetime(2026, 1, 1, 12, tzinfo=UTC),
                        "updated_at": observed_at,
                        "initial_balance_amount": Decimal("200.0000"),
                        "current_balance_amount": Decimal("200.0000"),
                        "currency": "RUB",
                    },
                ],
            )
            connection.execute(
                transactions.insert(),
                [
                    {
                        "id": "txn-income",
                        "transaction_type": "income",
                        "account_id": "acct-1",
                        "counterparty_account_id": None,
                        "amount": Decimal("100.0000"),
                        "currency": "RUB",
                        "transaction_date": date(2026, 1, 15),
                        "transfer_status": None,
                        "record_status": "active",
                    },
                    {
                        "id": "txn-expense",
                        "transaction_type": "expense",
                        "account_id": "acct-1",
                        "counterparty_account_id": None,
                        "amount": Decimal("40.0000"),
                        "currency": "RUB",
                        "transaction_date": date(2026, 1, 20),
                        "transfer_status": None,
                        "record_status": "active",
                    },
                    {
                        "id": "txn-transfer",
                        "transaction_type": "transfer",
                        "account_id": "acct-1",
                        "counterparty_account_id": "acct-2",
                        "amount": Decimal("25.0000"),
                        "currency": "RUB",
                        "transaction_date": date(2026, 2, 10),
                        "transfer_status": "posted",
                        "record_status": "active",
                    },
                    {
                        "id": "txn-dividend",
                        "transaction_type": "dividend",
                        "account_id": "acct-1",
                        "counterparty_account_id": None,
                        "amount": Decimal("10.0000"),
                        "currency": "RUB",
                        "transaction_date": date(2026, 2, 28),
                        "transfer_status": None,
                        "record_status": "active",
                    },
                    {
                        "id": "txn-deleted",
                        "transaction_type": "expense",
                        "account_id": "acct-1",
                        "counterparty_account_id": None,
                        "amount": Decimal("500.0000"),
                        "currency": "RUB",
                        "transaction_date": date(2026, 3, 1),
                        "transfer_status": None,
                        "record_status": "deleted",
                    },
                ],
            )

            original_op = module.op
            original_uuid = module.UUID
            module.op = FakeOp(connection)
            module.UUID = sa.String(36)
            try:
                module._backfill_account_balance_snapshots()
            finally:
                module.op = original_op
                module.UUID = original_uuid

            rows = connection.execute(
                sa.select(
                    snapshots.c.account_id,
                    snapshots.c.snapshot_date,
                    snapshots.c.balance_amount,
                )
            ).all()

        balance_by_account_date = {
            (row.account_id, row.snapshot_date): row.balance_amount for row in rows
        }
        self.assertEqual(
            Decimal("1015.0000"),
            balance_by_account_date[("acct-1", date(2026, 1, 31))],
        )
        self.assertEqual(
            Decimal("1000.0000"),
            balance_by_account_date[("acct-1", date(2026, 2, 28))],
        )
        self.assertEqual(
            Decimal("1000.0000"),
            balance_by_account_date[("acct-1", date(2026, 3, 31))],
        )
        self.assertEqual(
            Decimal("175.0000"),
            balance_by_account_date[("acct-2", date(2026, 1, 31))],
        )
        self.assertEqual(
            Decimal("200.0000"),
            balance_by_account_date[("acct-2", date(2026, 2, 28))],
        )
        self.assertIn(("acct-1", date(2026, 1, 15)), balance_by_account_date)
        self.assertIn(("acct-1", date(2026, 2, 10)), balance_by_account_date)


if __name__ == "__main__":
    unittest.main()
