from __future__ import annotations

import importlib.util
import py_compile
import sys
import unittest
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[4]
REVISION_PATH = (
    REPO_ROOT / "db" / "migrations" / "versions" / "20260822_0019_bearer_access_expiry.py"
)


class OperationRecorder:
    def __init__(self) -> None:
        self.added_columns: list[tuple[str, str, bool]] = []
        self.dropped_columns: list[tuple[str, str]] = []
        self.executed_sql: list[str] = []

    def add_column(self, table_name: str, column) -> None:
        self.added_columns.append((table_name, column.name, column.nullable))

    def drop_column(self, table_name: str, column_name: str) -> None:
        self.dropped_columns.append((table_name, column_name))

    def execute(self, statement) -> None:
        self.executed_sql.append(str(statement))


class BearerAccessExpiryMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = self.load_revision("bearer_access_expiry_revision", REVISION_PATH)

    @staticmethod
    def load_revision(name: str, path: Path) -> ModuleType:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_revision_compiles_and_chains_from_ios_bearer_revision(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)
        self.assertEqual("20260822_0019", self.module.revision)
        self.assertEqual("20260822_0018", self.module.down_revision)

    def test_upgrade_adds_nullable_column_and_backfills_only_mobile_sessions(self) -> None:
        recorder = OperationRecorder()
        original_op = self.module.op
        self.module.op = recorder
        try:
            self.module.upgrade()
        finally:
            self.module.op = original_op

        self.assertEqual([("sessions", "access_expires_at", True)], recorder.added_columns)
        self.assertEqual(
            [
                "UPDATE sessions SET access_expires_at = expires_at "
                "WHERE transport IN ('android_bearer', 'ios_bearer')"
            ],
            recorder.executed_sql,
        )

    def test_downgrade_drops_only_access_expiry_column(self) -> None:
        recorder = OperationRecorder()
        original_op = self.module.op
        self.module.op = recorder
        try:
            self.module.downgrade()
        finally:
            self.module.op = original_op

        self.assertEqual([("sessions", "access_expires_at")], recorder.dropped_columns)
        self.assertEqual([], recorder.executed_sql)


if __name__ == "__main__":
    unittest.main()
