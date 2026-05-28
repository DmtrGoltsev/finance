from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[4]
REVISION_PATH = REPO_ROOT / "db" / "migrations" / "versions" / "20260523_0007_capture_drafts.py"
RESTRICT_REVISION_PATH = (
    REPO_ROOT
    / "db"
    / "migrations"
    / "versions"
    / "20260528_0008_restrict_capture_drafts_screenshot_source.py"
)


class ScalarResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class BindRecorder:
    def __init__(self, legacy_source_count: int) -> None:
        self.legacy_source_count = legacy_source_count
        self.executed: list[object] = []

    def execute(self, statement: object) -> ScalarResult:
        self.executed.append(statement)
        return ScalarResult(self.legacy_source_count)


class OperationRecorder:
    def __init__(self, *, legacy_source_count: int = 0) -> None:
        self.created_tables: list[tuple[str, list[str]]] = []
        self.created_indexes: list[tuple[str, str, bool]] = []
        self.created_check_constraints: list[tuple[str, str, str]] = []
        self.dropped_constraints: list[tuple[str, str, str | None]] = []
        self.dropped_indexes: list[tuple[str, str | None]] = []
        self.dropped_tables: list[str] = []
        self.bind = BindRecorder(legacy_source_count)

    def f(self, name: str) -> str:
        return name

    def get_bind(self) -> BindRecorder:
        return self.bind

    def create_table(self, name: str, *elements, **_kwargs) -> None:
        self.created_tables.append((name, [getattr(element, "name", "") for element in elements]))

    def create_index(self, name: str, table_name: str, _columns, **kwargs) -> None:
        self.created_indexes.append((name, table_name, bool(kwargs.get("unique", False))))

    def create_check_constraint(self, name: str, table_name: str, condition: str) -> None:
        self.created_check_constraints.append((name, table_name, condition))

    def drop_constraint(self, name: str, table_name: str, *, type_: str | None = None) -> None:
        self.dropped_constraints.append((name, table_name, type_))

    def drop_index(self, name: str, *, table_name: str | None = None, **_kwargs) -> None:
        self.dropped_indexes.append((name, table_name))

    def drop_table(self, name: str) -> None:
        self.dropped_tables.append(name)


class CaptureDraftsMigrationSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = REVISION_PATH.read_text(encoding="utf-8")
        self.module = self.load_revision("capture_drafts_revision", REVISION_PATH)
        self.restrict_source = RESTRICT_REVISION_PATH.read_text(encoding="utf-8")
        self.restrict_module = self.load_revision(
            "restrict_capture_drafts_revision",
            RESTRICT_REVISION_PATH,
        )

    def load_revision(self, name: str, path: Path) -> ModuleType:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_revision_chains_after_api_vocabulary_alignment(self) -> None:
        self.assertEqual("20260523_0007", self.module.revision)
        self.assertEqual("20260519_0006", self.module.down_revision)

    def test_restrict_source_revision_chains_after_capture_drafts(self) -> None:
        self.assertEqual("20260528_0008", self.restrict_module.revision)
        self.assertEqual("20260523_0007", self.restrict_module.down_revision)

    def test_creates_safe_capture_drafts_table_without_raw_body_columns(self) -> None:
        recorder = OperationRecorder()
        original_op = self.module.op
        self.module.op = recorder
        try:
            self.module.upgrade()
        finally:
            self.module.op = original_op

        self.assertEqual(["capture_drafts"], [name for name, _ in recorder.created_tables])
        columns = set(recorder.created_tables[0][1])
        self.assertIn("owner_user_id", columns)
        self.assertIn("idempotency_key", columns)
        self.assertIn("capture_source", columns)
        self.assertIn("evidence_hash", columns)
        self.assertIn("transaction_id", columns)
        self.assertTrue(
            {"raw_message", "raw_notification", "raw_body", "body", "text"}.isdisjoint(columns)
        )
        self.assertIn(
            ("uq_capture_drafts_owner_idempotency_key", "capture_drafts", True),
            recorder.created_indexes,
        )

    def test_downgrade_drops_only_capture_drafts(self) -> None:
        recorder = OperationRecorder()
        original_op = self.module.op
        self.module.op = recorder
        try:
            self.module.downgrade()
        finally:
            self.module.op = original_op

        self.assertEqual(["capture_drafts"], recorder.dropped_tables)
        self.assertTrue(
            all(table_name == "capture_drafts" for _name, table_name in recorder.dropped_indexes)
        )

    def test_revision_source_documents_no_raw_payload_columns(self) -> None:
        lowered = self.source.lower()
        self.assertIn("no raw screenshot image or ocr payload columns", lowered)
        for forbidden in ("raw_message", "raw_notification", "raw_screenshot", "raw_body"):
            self.assertNotIn(forbidden, lowered)

    def test_restrict_source_upgrade_tightens_check_without_data_cleanup(self) -> None:
        recorder = OperationRecorder()
        original_op = self.restrict_module.op
        self.restrict_module.op = recorder
        try:
            self.restrict_module.upgrade()
        finally:
            self.restrict_module.op = original_op

        self.assertTrue(recorder.bind.executed)
        self.assertEqual(
            [("ck_capture_drafts_capture_source_valid", "capture_drafts", "check")],
            recorder.dropped_constraints,
        )
        self.assertEqual(
            [
                (
                    "ck_capture_drafts_capture_source_valid",
                    "capture_drafts",
                    "capture_source IN ('screenshot')",
                )
            ],
            recorder.created_check_constraints,
        )

    def test_restrict_source_upgrade_blocks_legacy_rows_without_cleanup(self) -> None:
        recorder = OperationRecorder(legacy_source_count=1)
        original_op = self.restrict_module.op
        self.restrict_module.op = recorder
        try:
            with self.assertRaisesRegex(RuntimeError, "manual data decision required"):
                self.restrict_module.upgrade()
        finally:
            self.restrict_module.op = original_op

        self.assertTrue(recorder.bind.executed)
        self.assertEqual([], recorder.dropped_constraints)
        self.assertEqual([], recorder.created_check_constraints)


if __name__ == "__main__":
    unittest.main()
