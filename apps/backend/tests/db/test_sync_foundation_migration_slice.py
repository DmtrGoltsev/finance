from __future__ import annotations

import importlib.util
import py_compile
import sys
import unittest
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[4]
REVISION_PATH = (
    REPO_ROOT / "db" / "migrations" / "versions" / "20260614_0016_sync_foundation.py"
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


class SyncFoundationMigrationSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = REVISION_PATH.read_text(encoding="utf-8")
        self.module = self.load_revision("sync_foundation_revision", REVISION_PATH)

    def load_revision(self, name: str, path: Path) -> ModuleType:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_revision_compiles_and_chains_after_date_only_snapshots(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)

        self.assertEqual("20260614_0016", self.module.revision)
        self.assertEqual("20260612_0015", self.module.down_revision)

    def test_upgrade_creates_sync_tables_and_indexes(self) -> None:
        recorder = OperationRecorder()
        original_op = self.module.op
        self.module.op = recorder
        try:
            self.module.upgrade()
        finally:
            self.module.op = original_op

        self.assertEqual(
            ["sync_clients", "sync_changes", "sync_client_mutations"],
            [name for name, _columns in recorder.created_tables],
        )
        columns_by_table = {name: set(columns) for name, columns in recorder.created_tables}
        self.assertIn("server_cursor", columns_by_table["sync_clients"])
        self.assertIn("seq", columns_by_table["sync_changes"])
        self.assertIn("payload", columns_by_table["sync_changes"])
        self.assertIn("tombstone_payload", columns_by_table["sync_changes"])
        self.assertIn("request_hash", columns_by_table["sync_client_mutations"])
        self.assertIn("response_payload", columns_by_table["sync_client_mutations"])
        self.assertIn(
            ("ix_sync_changes_owner_visibility", "sync_changes", False),
            recorder.created_indexes,
        )
        self.assertIn(
            ("ix_sync_changes_household_visibility", "sync_changes", False),
            recorder.created_indexes,
        )
        self.assertIn(
            (
                "ix_sync_client_mutations_actor_status_created",
                "sync_client_mutations",
                False,
            ),
            recorder.created_indexes,
        )

    def test_idempotency_and_visibility_contracts_are_present(self) -> None:
        for required in (
            "uq_sync_client_mutations_actor_device_client_mutation",
            "actor_user_id",
            "device_id",
            "client_mutation_id",
            "request_hash",
            "scope_type IN ('personal', 'household', 'system')",
            "ck_sync_changes_sync_scope_shape",
        ):
            self.assertIn(required, self.source)

    def test_downgrade_drops_only_sync_tables(self) -> None:
        recorder = OperationRecorder()
        original_op = self.module.op
        self.module.op = recorder
        try:
            self.module.downgrade()
        finally:
            self.module.op = original_op

        self.assertEqual(
            ["sync_client_mutations", "sync_changes", "sync_clients"],
            recorder.dropped_tables,
        )


if __name__ == "__main__":
    unittest.main()
