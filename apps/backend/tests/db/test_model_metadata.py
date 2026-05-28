from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT / "src"))


try:
    from sqlalchemy import CheckConstraint, Numeric

    import app.db.models  # noqa: F401
    from app.db.base import Base

    SQLALCHEMY_IMPORT_ERROR = None
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without deps
    SQLALCHEMY_IMPORT_ERROR = exc


EXPECTED_TABLES = {
    "users",
    "households",
    "memberships",
    "invites",
    "accounts",
    "categories",
    "transactions",
    "capture_drafts",
    "sessions",
    "password_reset_tokens",
    "export_jobs",
    "deletion_requests",
    "audit_events",
    "outbox_events",
}


@unittest.skipIf(SQLALCHEMY_IMPORT_ERROR is not None, "SQLAlchemy is unavailable")
class ModelMetadataTests(unittest.TestCase):
    def test_all_planned_tables_are_registered(self) -> None:
        self.assertEqual(EXPECTED_TABLES, set(Base.metadata.tables))

    def test_money_columns_use_numeric_20_4(self) -> None:
        for table_name, column_name in (
            ("accounts", "initial_balance_amount"),
            ("accounts", "current_balance_amount"),
            ("transactions", "amount"),
            ("capture_drafts", "amount"),
        ):
            column_type = Base.metadata.tables[table_name].c[column_name].type
            self.assertIsInstance(column_type, Numeric)
            self.assertEqual(20, column_type.precision)
            self.assertEqual(4, column_type.scale)

    def test_scope_and_source_constraints_are_present(self) -> None:
        self.assertIn("color", Base.metadata.tables["categories"].c)
        self.assertCheckContains(
            "accounts",
            "exactly_one_scope",
            ["ownership_type", "owner_user_id", "household_id"],
        )
        self.assertCheckContains(
            "categories",
            "exactly_one_scope",
            ["category_scope", "owner_user_id", "household_id"],
        )
        self.assertCheckContains(
            "transactions",
            "source_type_manual_only",
            ["source_type", "manual"],
        )
        self.assertCheckContains(
            "capture_drafts",
            "capture_source_valid",
            ["capture_source", "screenshot"],
        )

    def test_transaction_transfer_shape_constraint_is_present(self) -> None:
        self.assertCheckContains(
            "transactions",
            "transfer_shape",
            [
                "counterparty_account_id",
                "account_id",
                "category_id",
                "transfer_scope",
                "transfer_status",
            ],
        )

    def test_expected_partial_indexes_are_present(self) -> None:
        for table_name, index_name in (
            ("memberships", "ix_memberships_active_user_household"),
            ("accounts", "ix_accounts_owner_user_status"),
            ("accounts", "ix_accounts_household_status"),
            ("sessions", "ix_sessions_user_active_expires"),
            ("sessions", "ix_sessions_session_version"),
            ("transactions", "ix_transactions_account_occurred_status"),
            ("capture_drafts", "ix_capture_drafts_owner_status_created"),
            ("export_jobs", "ix_export_jobs_requested_status_created"),
            ("outbox_events", "ix_outbox_events_status_available_created"),
        ):
            self.assertIn(
                index_name,
                {index.name for index in Base.metadata.tables[table_name].indexes},
            )

    def assertCheckContains(self, table_name: str, suffix: str, fragments: list[str]) -> None:
        constraints = [
            constraint
            for constraint in Base.metadata.tables[table_name].constraints
            if isinstance(constraint, CheckConstraint) and constraint.name.endswith(suffix)
        ]
        self.assertTrue(constraints, f"{table_name} missing CHECK ending with {suffix!r}")
        constraint_text = str(constraints[0].sqltext)
        for fragment in fragments:
            self.assertIn(fragment, constraint_text)


if __name__ == "__main__":
    unittest.main()
