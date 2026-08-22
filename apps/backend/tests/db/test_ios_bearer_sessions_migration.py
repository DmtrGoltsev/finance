from __future__ import annotations

import importlib.util
import py_compile
import sys
import unittest
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[4]
REVISION_PATH = (
    REPO_ROOT / "db" / "migrations" / "versions" / "20260822_0018_ios_bearer_sessions.py"
)


class BatchOperationRecorder:
    def __init__(self, recorder: OperationRecorder, table_name: str) -> None:
        self._recorder = recorder
        self._table_name = table_name

    def __enter__(self) -> BatchOperationRecorder:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def drop_constraint(self, name: str, *, type_: str) -> None:
        self._recorder.dropped_checks.append((self._table_name, name, type_))

    def create_check_constraint(self, name: str, sqltext: str) -> None:
        self._recorder.created_checks.append((self._table_name, name, sqltext))


class OperationRecorder:
    def __init__(self) -> None:
        self.dropped_checks: list[tuple[str, str, str]] = []
        self.created_checks: list[tuple[str, str, str]] = []
        self.executed_sql: list[str] = []

    def f(self, name: str) -> str:
        return name

    def batch_alter_table(self, table_name: str, **_kwargs) -> BatchOperationRecorder:
        return BatchOperationRecorder(self, table_name)

    def execute(self, statement) -> None:
        self.executed_sql.append(str(statement))


class IosBearerSessionsMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = self.load_revision("ios_bearer_sessions_revision", REVISION_PATH)

    @staticmethod
    def load_revision(name: str, path: Path) -> ModuleType:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_revision_compiles_and_chains_from_current_head(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)
        self.assertEqual("20260822_0018", self.module.revision)
        self.assertEqual("20260618_0017", self.module.down_revision)

    def test_upgrade_replaces_constraint_with_ios_transport(self) -> None:
        recorder = OperationRecorder()
        original_op = self.module.op
        self.module.op = recorder
        try:
            self.module.upgrade()
        finally:
            self.module.op = original_op

        self.assertEqual(
            [("sessions", "ck_sessions_transport_valid", "check")],
            recorder.dropped_checks,
        )
        self.assertEqual(
            [
                (
                    "sessions",
                    "ck_sessions_transport_valid",
                    "transport IN ('cookie', 'android_bearer', 'ios_bearer')",
                )
            ],
            recorder.created_checks,
        )
        self.assertEqual([], recorder.executed_sql)

    def test_downgrade_deletes_ios_sessions_before_restoring_constraint(self) -> None:
        recorder = OperationRecorder()
        original_op = self.module.op
        self.module.op = recorder
        try:
            self.module.downgrade()
        finally:
            self.module.op = original_op

        self.assertEqual(
            ["DELETE FROM sessions WHERE transport = 'ios_bearer'"],
            recorder.executed_sql,
        )
        self.assertEqual(
            [
                (
                    "sessions",
                    "ck_sessions_transport_valid",
                    "transport IN ('cookie', 'android_bearer')",
                )
            ],
            recorder.created_checks,
        )


if __name__ == "__main__":
    unittest.main()
