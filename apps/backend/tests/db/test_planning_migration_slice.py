from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[4]
REVISION_PATH = (
    REPO_ROOT / "db" / "migrations" / "versions" / "20260606_0010_planning_foundation.py"
)


class OperationRecorder:
    def __init__(self) -> None:
        self.created_tables: list[tuple[str, list[str]]] = []
        self.created_indexes: list[tuple[str, str, bool]] = []
        self.dropped_indexes: list[tuple[str, str | None]] = []
        self.dropped_tables: list[str] = []

    def f(self, name: str) -> str:
        return name

    def create_table(self, name: str, *elements, **_kwargs) -> None:
        self.created_tables.append((name, [getattr(element, "name", "") for element in elements]))

    def create_index(self, name: str, table_name: str, _columns, **kwargs) -> None:
        self.created_indexes.append((name, table_name, bool(kwargs.get("unique", False))))

    def drop_index(self, name: str, *, table_name: str | None = None, **_kwargs) -> None:
        self.dropped_indexes.append((name, table_name))

    def drop_table(self, name: str) -> None:
        self.dropped_tables.append(name)


class PlanningMigrationSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = REVISION_PATH.read_text(encoding="utf-8")
        self.module = self.load_revision("planning_foundation_revision", REVISION_PATH)

    def load_revision(self, name: str, path: Path) -> ModuleType:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_revision_chains_after_capture_category_mappings(self) -> None:
        self.assertEqual("20260606_0010", self.module.revision)
        self.assertEqual("20260531_0009", self.module.down_revision)

    def test_upgrade_creates_planning_tables_and_indexes(self) -> None:
        recorder = OperationRecorder()
        original_op = self.module.op
        self.module.op = recorder
        try:
            self.module.upgrade()
        finally:
            self.module.op = original_op

        self.assertEqual(
            ["planning_plans", "planning_income_sources", "planning_allocations"],
            [name for name, _columns in recorder.created_tables],
        )
        columns_by_table = {name: set(columns) for name, columns in recorder.created_tables}
        self.assertIn("plan_month", columns_by_table["planning_plans"])
        self.assertIn("confirmation_state", columns_by_table["planning_income_sources"])
        self.assertIn("target_snapshot", columns_by_table["planning_allocations"])
        self.assertIn("requires_attention", columns_by_table["planning_allocations"])
        self.assertIn(
            ("uq_planning_plans_personal_month", "planning_plans", True),
            recorder.created_indexes,
        )
        self.assertIn(
            ("ix_planning_allocations_plan_attention", "planning_allocations", False),
            recorder.created_indexes,
        )

    def test_planning_confirmation_has_no_transaction_fk_or_creation_language(self) -> None:
        lowered = self.source.lower()
        self.assertIn("has no transaction fk", lowered)
        self.assertNotIn("transaction_id", lowered)
        self.assertNotIn("transactions.id", lowered)
        self.assertNotIn("create transaction", lowered)

    def test_downgrade_drops_only_planning_tables(self) -> None:
        recorder = OperationRecorder()
        original_op = self.module.op
        self.module.op = recorder
        try:
            self.module.downgrade()
        finally:
            self.module.op = original_op

        self.assertEqual(
            ["planning_allocations", "planning_income_sources", "planning_plans"],
            recorder.dropped_tables,
        )


if __name__ == "__main__":
    unittest.main()
