from __future__ import annotations

import importlib.util
import py_compile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
REVISION_PATH = (
    REPO_ROOT
    / "db"
    / "migrations"
    / "versions"
    / "20260518_0005_transaction_transfer_safety.py"
)


class TransactionTransferSafetyMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = REVISION_PATH.read_text(encoding="utf-8")

    def test_revision_compiles_and_chains_after_transactions(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)

        if importlib.util.find_spec("alembic") is None:
            self.skipTest("Alembic is unavailable")

        spec = importlib.util.spec_from_file_location("transfer_safety_revision", REVISION_PATH)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertEqual("20260518_0005", module.revision)
        self.assertEqual("20260518_0004", module.down_revision)

    def test_postgresql_trigger_guards_same_scope_and_currency(self) -> None:
        for required in (
            'FUNCTION_NAME = "finance_validate_transaction_transfer_safety"',
            'TRIGGER_NAME = "trg_transactions_transfer_safety"',
            "CREATE OR REPLACE FUNCTION {FUNCTION_NAME}",
            "CREATE TRIGGER {TRIGGER_NAME}",
            "BEFORE INSERT OR UPDATE OF",
            "source_account.currency <> NEW.currency",
            "counterparty_account.currency <> NEW.currency",
            "NEW.transfer_scope = 'personal_same_owner'",
            "source_account.ownership_type = 'personal'",
            "source_account.owner_user_id = counterparty_account.owner_user_id",
            "NEW.transfer_scope = 'household_same_household'",
            "source_account.ownership_type = 'shared'",
            "source_account.household_id = counterparty_account.household_id",
            "transactions_transfer_same_scope_guard",
            "transactions_transfer_same_currency_guard",
        ):
            self.assertIn(required, self.source)

    def test_downgrade_removes_trigger_and_function_only(self) -> None:
        self.assertIn(
            "DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON transactions",
            self.source,
        )
        self.assertIn(
            "DROP FUNCTION IF EXISTS {FUNCTION_NAME}()",
            self.source,
        )
        self.assertNotIn("drop_table", self.source.casefold())


if __name__ == "__main__":
    unittest.main()
