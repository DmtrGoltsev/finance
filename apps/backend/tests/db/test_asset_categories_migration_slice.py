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
    / "20260607_0012_asset_categories_contract.py"
)
ICON_KEY_REVISION_PATH = (
    REPO_ROOT
    / "db"
    / "migrations"
    / "versions"
    / "20260608_0014_asset_category_icon_key.py"
)


class AssetCategoriesMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = REVISION_PATH.read_text(encoding="utf-8")

    def test_revision_compiles_and_chains_after_asset_target(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)

        spec = importlib.util.spec_from_file_location("asset_categories_contract", REVISION_PATH)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertEqual("20260607_0012", module.revision)
        self.assertEqual("20260607_0011", module.down_revision)

    def test_upgrade_adds_asset_categories_and_account_link(self) -> None:
        for required in (
            'op.create_table(\n        "asset_categories"',
            '"ix_asset_categories_owner_status"',
            '"ix_asset_categories_household_status"',
            '"ix_asset_categories_investment_status"',
            'batch_op.add_column(sa.Column("asset_category_id"',
            '"ix_accounts_asset_category_id"',
            '"investment_asset_category"',
        ):
            self.assertIn(required, self.source)

    def test_downgrade_documents_previous_target_types(self) -> None:
        self.assertIn(
            'PREVIOUS_TARGET_TYPES = ("expense_category", "account", "asset")',
            self.source,
        )

    def test_icon_key_revision_is_additive_and_chains_after_planning_iteration(self) -> None:
        py_compile.compile(str(ICON_KEY_REVISION_PATH), doraise=True)

        spec = importlib.util.spec_from_file_location(
            "asset_category_icon_key",
            ICON_KEY_REVISION_PATH,
        )
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = ICON_KEY_REVISION_PATH.read_text(encoding="utf-8")

        self.assertEqual("20260608_0014", module.revision)
        self.assertEqual("20260607_0013", module.down_revision)
        self.assertIn('batch_op.add_column(sa.Column("icon_key"', source)
        self.assertIn('batch_op.drop_column("icon_key")', source)


if __name__ == "__main__":
    unittest.main()
