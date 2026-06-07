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
    / "20260607_0011_planning_allocation_asset_target.py"
)


class PlanningAssetTargetMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = REVISION_PATH.read_text(encoding="utf-8")

    def test_revision_compiles_and_chains_after_planning_foundation(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)

        if importlib.util.find_spec("alembic") is None:
            self.skipTest("Alembic is unavailable")

        spec = importlib.util.spec_from_file_location("planning_asset_target", REVISION_PATH)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertEqual("20260607_0011", module.revision)
        self.assertEqual("20260606_0010", module.down_revision)

    def test_upgrade_expands_planning_allocation_target_constraint(self) -> None:
        for required in (
            'PLANNING_ALLOCATION_TARGET_TYPE_CONSTRAINT = (',
            '"ck_planning_allocations_target_type_valid"',
            'TARGET_TYPES = ("expense_category", "account", "asset")',
            "ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}",
            "ADD CONSTRAINT {constraint_name} CHECK ({condition}) NOT VALID",
            "VALIDATE CONSTRAINT {constraint_name}",
            'op.batch_alter_table(table_name, recreate="always")',
        ):
            self.assertIn(required, self.source)

    def test_downgrade_documents_previous_target_types(self) -> None:
        self.assertIn(
            'PREVIOUS_TARGET_TYPES = ("expense_category", "account")',
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
