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
    / "20260519_0006_align_api_vocabulary_constraints.py"
)


class ApiVocabularyConstraintsMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = REVISION_PATH.read_text(encoding="utf-8")

    def test_revision_compiles_and_chains_after_transfer_safety(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)

        if importlib.util.find_spec("alembic") is None:
            self.skipTest("Alembic is unavailable")

        spec = importlib.util.spec_from_file_location("api_vocabulary_constraints", REVISION_PATH)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertEqual("20260519_0006", module.revision)
        self.assertEqual("20260518_0005", module.down_revision)

    def test_upgrade_expands_account_and_transaction_constraints(self) -> None:
        for required in (
            'ACCOUNT_TYPE_CONSTRAINT = "ck_accounts_account_type_valid"',
            'TRANSACTION_TYPE_CONSTRAINT = "ck_transactions_transaction_type_valid"',
            '"card"',
            '"metal"',
            '"other"',
            '"asset_buy"',
            '"asset_sell"',
            '"interest"',
            '"dividend"',
            '"adjustment"',
            "ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}",
            "ADD CONSTRAINT {constraint_name} CHECK ({condition}) NOT VALID",
            "VALIDATE CONSTRAINT {constraint_name}",
            'op.batch_alter_table(table_name, recreate="always")',
        ):
            self.assertIn(required, self.source)

    def test_downgrade_documents_previous_narrow_constraints(self) -> None:
        for required in (
            'PREVIOUS_ACCOUNT_TYPES = ("cash", "bank", "deposit", "brokerage")',
            'PREVIOUS_TRANSACTION_TYPES = ("income", "expense", "transfer", "brokerage")',
        ):
            self.assertIn(required, self.source)


if __name__ == "__main__":
    unittest.main()
