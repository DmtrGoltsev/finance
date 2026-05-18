from __future__ import annotations

import ast
import importlib.util
import py_compile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
REVISION_PATH = (
    REPO_ROOT / "db" / "migrations" / "versions" / "20260517_0001_accounts_categories_slice.py"
)

EXPECTED_TABLES = ["users", "households", "memberships", "accounts", "categories"]
EXCLUDED_TABLES = {
    "invites",
    "transactions",
    "sessions",
    "password_reset_tokens",
    "export_jobs",
    "deletion_requests",
    "audit_events",
    "outbox_events",
    "reports",
    "transfers",
}


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


class AccountsCategoriesMigrationSliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = REVISION_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.calls = [node for node in ast.walk(cls.tree) if isinstance(node, ast.Call)]

    def test_revision_compiles(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)

    def test_revision_imports_when_alembic_is_available(self) -> None:
        if (
            importlib.util.find_spec("alembic") is None
            or importlib.util.find_spec("sqlalchemy") is None
        ):
            self.skipTest("Alembic/SQLAlchemy are unavailable")

        spec = importlib.util.spec_from_file_location(
            "accounts_categories_slice_revision",
            REVISION_PATH,
        )
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertEqual("20260517_0001", module.revision)
        self.assertIsNone(module.down_revision)

    def test_creates_only_first_slice_tables(self) -> None:
        created_tables = [
            _literal_arg(call, 0)
            for call in self.calls
            if _call_name(call) == "create_table" and _literal_arg(call, 0)
        ]

        self.assertEqual(EXPECTED_TABLES, created_tables)
        self.assertTrue(EXCLUDED_TABLES.isdisjoint(created_tables))

    def test_downgrade_drops_tables_in_reverse_order(self) -> None:
        dropped_tables = [
            _literal_arg(call, 0)
            for call in self.calls
            if _call_name(call) == "drop_table" and _literal_arg(call, 0)
        ]

        self.assertEqual(list(reversed(EXPECTED_TABLES)), dropped_tables)

    def test_required_columns_and_constraints_are_present(self) -> None:
        for table_name in EXPECTED_TABLES:
            for column_name in ("id", "created_at", "updated_at", "version"):
                self.assertIn(
                    f'"{column_name}"',
                    self.source,
                    f"{table_name} missing {column_name}",
                )

        for required in (
            "postgresql.UUID(as_uuid=True)",
            "sa.Numeric(20, 4)",
            "initial_balance_amount",
            "current_balance_amount",
            "color",
            "ck_accounts_exactly_one_scope",
            "ck_categories_exactly_one_scope",
            "ck_accounts_currency_iso_shape",
            "record_status IN ('active', 'archived', 'deleted')",
            "membership_status IN ('invited', 'active', 'left', 'revoked')",
        ):
            self.assertIn(required, self.source)

    def test_required_indexes_are_present(self) -> None:
        for index_name in (
            "uq_memberships_active_household_user",
            "ix_memberships_active_user_household",
            "ix_memberships_active_household_user",
            "ix_accounts_owner_user_status",
            "ix_accounts_household_status",
            "ix_accounts_ownership_owner_status",
            "ix_accounts_ownership_household_status",
            "ix_categories_owner_type_status",
            "ix_categories_household_type_status",
        ):
            self.assertIn(index_name, self.source)

        self.assertIn("membership_status = 'active'", self.source)
        self.assertIn("owner_user_id IS NOT NULL", self.source)
        self.assertIn("household_id IS NOT NULL", self.source)


if __name__ == "__main__":
    unittest.main()
