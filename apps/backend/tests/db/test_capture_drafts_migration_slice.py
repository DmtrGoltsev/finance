from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
REVISION_PATH = REPO_ROOT / "db" / "migrations" / "versions" / "20260523_0007_capture_drafts.py"


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


class CaptureDraftsMigrationSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = REVISION_PATH.read_text(encoding="utf-8")
        spec = importlib.util.spec_from_file_location("capture_drafts_revision", REVISION_PATH)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.module = module

    def test_revision_chains_after_api_vocabulary_alignment(self) -> None:
        self.assertEqual("20260523_0007", self.module.revision)
        self.assertEqual("20260519_0006", self.module.down_revision)

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
        self.assertIn("no raw sms, notification, or screenshot payload columns", lowered)
        for forbidden in ("raw_message", "raw_notification", "raw_screenshot", "raw_body"):
            self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
