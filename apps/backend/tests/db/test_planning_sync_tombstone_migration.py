from __future__ import annotations

import importlib.util
import py_compile
import sys
import unittest
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[4]
REVISION_PATH = (
    REPO_ROOT
    / "db"
    / "migrations"
    / "versions"
    / "20260618_0017_planning_sync_tombstones.py"
)


class BatchOperationRecorder:
    def __init__(self, recorder: OperationRecorder, table_name: str) -> None:
        self._recorder = recorder
        self._table_name = table_name

    def __enter__(self) -> BatchOperationRecorder:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def add_column(self, column) -> None:
        self._recorder.added_columns.append((self._table_name, column.name))

    def create_check_constraint(self, name: str, sqltext: str) -> None:
        self._recorder.created_checks.append((self._table_name, name, sqltext))

    def drop_constraint(self, name: str, *, type_: str) -> None:
        self._recorder.dropped_checks.append((self._table_name, name, type_))

    def drop_column(self, name: str) -> None:
        self._recorder.dropped_columns.append((self._table_name, name))


class OperationRecorder:
    def __init__(self) -> None:
        self.added_columns: list[tuple[str, str]] = []
        self.created_checks: list[tuple[str, str, str]] = []
        self.created_indexes: list[tuple[str, str, tuple[str, ...]]] = []
        self.dropped_checks: list[tuple[str, str, str]] = []
        self.dropped_columns: list[tuple[str, str]] = []
        self.dropped_indexes: list[tuple[str, str | None]] = []

    def f(self, name: str) -> str:
        return name

    def batch_alter_table(self, table_name: str, **_kwargs) -> BatchOperationRecorder:
        return BatchOperationRecorder(self, table_name)

    def create_index(self, name: str, table_name: str, columns) -> None:
        self.created_indexes.append((name, table_name, tuple(columns)))

    def drop_index(self, name: str, *, table_name: str | None = None) -> None:
        self.dropped_indexes.append((name, table_name))


class PlanningSyncTombstoneMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = REVISION_PATH.read_text(encoding="utf-8")
        self.module = self.load_revision("planning_sync_tombstones_revision", REVISION_PATH)

    def load_revision(self, name: str, path: Path) -> ModuleType:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_revision_compiles_and_chains_after_sync_foundation(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)

        self.assertEqual("20260618_0017", self.module.revision)
        self.assertEqual("20260614_0016", self.module.down_revision)

    def test_upgrade_adds_planning_child_tombstones_and_indexes(self) -> None:
        recorder = OperationRecorder()
        original_op = self.module.op
        self.module.op = recorder
        try:
            self.module.upgrade()
        finally:
            self.module.op = original_op

        for table_name in ("planning_income_sources", "planning_allocations"):
            self.assertIn((table_name, "record_status"), recorder.added_columns)
            self.assertIn((table_name, "deleted_at"), recorder.added_columns)
            self.assertIn(
                (
                    table_name,
                    f"ck_{table_name}_record_status_valid",
                    self.module.ACTIVE_DELETED_CHECK,
                ),
                recorder.created_checks,
            )
            self.assertIn(
                (
                    table_name,
                    f"ck_{table_name}_record_status_deleted_at_shape",
                    self.module.DELETED_AT_SHAPE_CHECK,
                ),
                recorder.created_checks,
            )

        self.assertIn(
            (
                "ix_planning_income_sources_plan_status",
                "planning_income_sources",
                ("plan_id", "record_status"),
            ),
            recorder.created_indexes,
        )
        self.assertIn(
            (
                "ix_planning_allocations_plan_status",
                "planning_allocations",
                ("plan_id", "record_status"),
            ),
            recorder.created_indexes,
        )

    def test_downgrade_drops_only_planning_tombstone_additions(self) -> None:
        recorder = OperationRecorder()
        original_op = self.module.op
        self.module.op = recorder
        try:
            self.module.downgrade()
        finally:
            self.module.op = original_op

        self.assertEqual(
            [
                ("ix_planning_allocations_plan_status", "planning_allocations"),
                ("ix_planning_income_sources_plan_status", "planning_income_sources"),
            ],
            recorder.dropped_indexes,
        )
        self.assertEqual(
            [
                ("planning_allocations", "deleted_at"),
                ("planning_allocations", "record_status"),
                ("planning_income_sources", "deleted_at"),
                ("planning_income_sources", "record_status"),
            ],
            recorder.dropped_columns,
        )


if __name__ == "__main__":
    unittest.main()
