from __future__ import annotations

import ast
import importlib.util
import py_compile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
REVISION_PATH = (
    REPO_ROOT / "db" / "migrations" / "versions" / "20260518_0004_transactions.py"
)


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        if isinstance(node.func, ast.Name):
            return node.func.id
    return None


def _literal_arg(node: ast.Call, index: int) -> str | None:
    if len(node.args) <= index:
        return None
    value = node.args[index]
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


class TransactionsMigrationSliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = REVISION_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.calls = [node for node in ast.walk(cls.tree) if isinstance(node, ast.Call)]

    def test_revision_compiles_and_chains_after_immutable_scope_guards(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)

        if (
            importlib.util.find_spec("alembic") is None
            or importlib.util.find_spec("sqlalchemy") is None
        ):
            self.skipTest("Alembic/SQLAlchemy are unavailable")

        spec = importlib.util.spec_from_file_location("transactions_revision", REVISION_PATH)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertEqual("20260518_0004", module.revision)
        self.assertEqual("20260518_0003", module.down_revision)

    def test_creates_only_transactions_table(self) -> None:
        created_tables = [
            _literal_arg(call, 0)
            for call in self.calls
            if _call_name(call) == "create_table" and _literal_arg(call, 0)
        ]
        self.assertEqual(["transactions"], created_tables)

    def test_required_constraints_and_indexes_are_present(self) -> None:
        for required in (
            "postgresql.UUID(as_uuid=True)",
            "sa.Numeric(20, 4)",
            "source_type = 'manual'",
            "amount > 0",
            "currency = upper(currency) AND length(currency) = 3",
            "counterparty_account_id <> account_id",
            "transaction_type NOT IN ('income', 'expense') OR category_id IS NOT NULL",
            "record_status IN ('active', 'deleted')",
            "ix_transactions_account_occurred_status",
            "ix_transactions_category_occurred",
            "ix_transactions_counterparty_account",
            "ix_transactions_created_by_occurred",
            "ix_transactions_source_type",
        ):
            self.assertIn(required, self.source)

    def test_downgrade_drops_indexes_and_table(self) -> None:
        dropped_indexes = [
            _literal_arg(call, 0)
            for call in self.calls
            if _call_name(call) == "drop_index" and _literal_arg(call, 0)
        ]
        self.assertEqual(
            [
                "ix_transactions_source_type",
                "ix_transactions_created_by_occurred",
                "ix_transactions_counterparty_account",
                "ix_transactions_category_occurred",
                "ix_transactions_account_occurred_status",
            ],
            dropped_indexes,
        )
        self.assertIn('op.drop_table("transactions")', self.source)


if __name__ == "__main__":
    unittest.main()

