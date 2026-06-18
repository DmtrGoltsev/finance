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
    / "20260607_0013_planning_iteration_mvp.py"
)


class PlanningIterationMvpMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = REVISION_PATH.read_text(encoding="utf-8")

    def test_revision_compiles_and_chains_after_asset_categories_contract(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)

        spec = importlib.util.spec_from_file_location("planning_iteration_mvp", REVISION_PATH)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertEqual("20260607_0013", module.revision)
        self.assertEqual("20260607_0012", module.down_revision)

    def test_upgrade_adds_only_allocation_iteration_metadata(self) -> None:
        for required in (
            '"planning_allocations"',
            '"recurrence_type"',
            "server_default=sa.text(\"'regular'\")",
            '"is_savings_goal"',
            'server_default=sa.text("false")',
            '"goal_target_amount"',
            '"goal_due_month"',
            "recurrence_type IN ('regular', 'one_off')",
            "goal_target_amount IS NULL OR goal_target_amount > 0",
            "is_savings_goal = false OR target_type = 'investment_asset_category'",
        ):
            self.assertIn(required, self.source)

        self.assertNotIn('op.create_table("transactions"', self.source)
        self.assertNotIn("transactions.id", self.source)

    def test_downgrade_drops_only_added_columns(self) -> None:
        for required in (
            'batch_op.drop_column("goal_due_month")',
            'batch_op.drop_column("goal_target_amount")',
            'batch_op.drop_column("is_savings_goal")',
            'batch_op.drop_column("recurrence_type")',
        ):
            self.assertIn(required, self.source)


if __name__ == "__main__":
    unittest.main()
