from __future__ import annotations

import ast
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
    / "20260518_0003_accounts_categories_immutable_scope_triggers.py"
)


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        if isinstance(node.func, ast.Name):
            return node.func.id
    return None


class AccountsCategoriesImmutableScopeMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = REVISION_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.calls = [node for node in ast.walk(cls.tree) if isinstance(node, ast.Call)]

    def test_revision_compiles(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)

    def test_revision_imports_when_alembic_is_available(self) -> None:
        if importlib.util.find_spec("alembic") is None:
            self.skipTest("Alembic is unavailable")

        spec = importlib.util.spec_from_file_location(
            "accounts_categories_immutable_scope_revision",
            REVISION_PATH,
        )
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertEqual("20260518_0003", module.revision)
        self.assertEqual("20260518_0002", module.down_revision)

    def test_creates_expected_guard_triggers_only(self) -> None:
        source = self.source
        for required in (
            "prevent_accounts_scope_update",
            "trg_accounts_immutable_scope",
            "BEFORE UPDATE OF ownership_type, owner_user_id, household_id ON accounts",
            "account ownership scope is immutable",
            "prevent_categories_scope_update",
            "trg_categories_immutable_scope",
            "BEFORE UPDATE OF category_scope, owner_user_id, household_id ON categories",
            "category scope is immutable",
            "integrity_constraint_violation",
        ):
            self.assertIn(required, source)

        self.assertNotIn("transactions", source)
        self.assertNotIn("sessions", source)

    def test_downgrade_drops_triggers_before_functions(self) -> None:
        downgrade_source = self.source.split("def downgrade() -> None:", 1)[1]
        expected_order = [
            "DROP TRIGGER IF EXISTS trg_categories_immutable_scope ON categories",
            "DROP FUNCTION IF EXISTS prevent_categories_scope_update()",
            "DROP TRIGGER IF EXISTS trg_accounts_immutable_scope ON accounts",
            "DROP FUNCTION IF EXISTS prevent_accounts_scope_update()",
        ]
        positions = [downgrade_source.index(fragment) for fragment in expected_order]

        self.assertEqual(sorted(positions), positions)

    def test_revision_uses_execute_without_creating_tables(self) -> None:
        call_names = [_call_name(call) for call in self.calls]

        self.assertIn("execute", call_names)
        self.assertNotIn("create_table", call_names)
        self.assertNotIn("drop_table", call_names)


if __name__ == "__main__":
    unittest.main()
