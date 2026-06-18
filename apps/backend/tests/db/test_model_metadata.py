from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT / "src"))


try:
    from sqlalchemy import CheckConstraint, Numeric, UniqueConstraint

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
    "account_balance_snapshots",
    "asset_categories",
    "categories",
    "transactions",
    "capture_drafts",
    "capture_category_mappings",
    "planning_plans",
    "planning_income_sources",
    "planning_allocations",
    "sessions",
    "password_reset_tokens",
    "export_jobs",
    "deletion_requests",
    "audit_events",
    "outbox_events",
    "sync_clients",
    "sync_changes",
    "sync_client_mutations",
}


@unittest.skipIf(SQLALCHEMY_IMPORT_ERROR is not None, "SQLAlchemy is unavailable")
class ModelMetadataTests(unittest.TestCase):
    def test_all_planned_tables_are_registered(self) -> None:
        self.assertEqual(EXPECTED_TABLES, set(Base.metadata.tables))

    def test_money_columns_use_numeric_20_4(self) -> None:
        for table_name, column_name in (
            ("accounts", "initial_balance_amount"),
            ("accounts", "current_balance_amount"),
            ("account_balance_snapshots", "balance_amount"),
            ("asset_categories", "manual_amount"),
            ("transactions", "amount"),
            ("capture_drafts", "amount"),
            ("planning_income_sources", "amount"),
            ("planning_allocations", "allocation_value"),
            ("planning_allocations", "goal_target_amount"),
        ):
            column_type = Base.metadata.tables[table_name].c[column_name].type
            self.assertIsInstance(column_type, Numeric)
            self.assertEqual(20, column_type.precision)
            self.assertEqual(4, column_type.scale)

    def test_scope_and_source_constraints_are_present(self) -> None:
        self.assertIn("color", Base.metadata.tables["categories"].c)
        self.assertIn("icon_key", Base.metadata.tables["asset_categories"].c)
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
            "asset_categories",
            "exactly_one_scope",
            ["scope_type", "owner_user_id", "household_id"],
        )
        self.assertCheckContains(
            "asset_categories",
            "non_negative_manual_amount",
            ["manual_amount"],
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
        self.assertCheckContains(
            "planning_plans",
            "exactly_one_scope",
            ["scope_type", "owner_user_id", "household_id"],
        )
        self.assertCheckContains(
            "planning_allocations",
            "target_attention_shape",
            ["target_id", "requires_attention"],
        )
        self.assertCheckContains(
            "planning_allocations",
            "target_type_valid",
            ["expense_category", "account", "asset", "investment_asset_category"],
        )
        self.assertCheckContains(
            "planning_income_sources",
            "record_status_deleted_at_shape",
            ["record_status", "active", "deleted", "deleted_at"],
        )
        self.assertCheckContains(
            "planning_allocations",
            "record_status_deleted_at_shape",
            ["record_status", "active", "deleted", "deleted_at"],
        )
        self.assertCheckContains(
            "planning_allocations",
            "recurrence_type_valid",
            ["recurrence_type", "regular", "one_off"],
        )
        self.assertCheckContains(
            "planning_allocations",
            "savings_goal_investment_target",
            ["is_savings_goal", "investment_asset_category"],
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
            ("accounts", "ix_accounts_payment_status"),
            (
                "account_balance_snapshots",
                "ix_account_balance_snapshots_account_date_created",
            ),
            ("accounts", "ix_accounts_asset_category_id"),
            ("asset_categories", "ix_asset_categories_owner_status"),
            ("accounts", "ix_accounts_household_status"),
            ("sessions", "ix_sessions_user_active_expires"),
            ("sessions", "ix_sessions_session_version"),
            ("transactions", "ix_transactions_account_occurred_status"),
            ("capture_drafts", "ix_capture_drafts_owner_status_created"),
            (
                "capture_category_mappings",
                "uq_capture_category_mappings_owner_personal_hash",
            ),
            ("planning_plans", "uq_planning_plans_personal_month"),
            ("planning_income_sources", "ix_planning_income_sources_plan_id"),
            ("planning_income_sources", "ix_planning_income_sources_plan_status"),
            ("planning_allocations", "ix_planning_allocations_plan_attention"),
            ("planning_allocations", "ix_planning_allocations_plan_status"),
            ("export_jobs", "ix_export_jobs_requested_status_created"),
            ("outbox_events", "ix_outbox_events_status_available_created"),
            ("sync_clients", "ix_sync_clients_actor_last_seen"),
            ("sync_changes", "ix_sync_changes_seq"),
            ("sync_changes", "ix_sync_changes_entity"),
            ("sync_changes", "ix_sync_changes_owner_visibility"),
            ("sync_changes", "ix_sync_changes_household_visibility"),
            (
                "sync_client_mutations",
                "ix_sync_client_mutations_actor_status_created",
            ),
            ("sync_client_mutations", "ix_sync_client_mutations_entity"),
            ("sync_client_mutations", "ix_sync_client_mutations_change_seq"),
        ):
            self.assertIn(
                index_name,
                {index.name for index in Base.metadata.tables[table_name].indexes},
            )

    def test_sync_foundation_tables_are_registered(self) -> None:
        sync_clients = Base.metadata.tables["sync_clients"]
        self.assertEqual(
            {"actor_user_id", "device_id"},
            set(sync_clients.primary_key.columns.keys()),
        )
        self.assertIn("server_cursor", sync_clients.c)
        self.assertCheckContains(
            "sync_clients",
            "non_negative_server_cursor",
            ["server_cursor"],
        )

        sync_changes = Base.metadata.tables["sync_changes"]
        self.assertIn("seq", sync_changes.c)
        self.assertIn("payload", sync_changes.c)
        self.assertIn("tombstone_payload", sync_changes.c)
        self.assertCheckContains(
            "sync_changes",
            "sync_scope_shape",
            ["personal", "household", "system", "owner_user_id", "household_id"],
        )

        sync_mutations = Base.metadata.tables["sync_client_mutations"]
        self.assertIn("request_hash", sync_mutations.c)
        self.assertIn("response_payload", sync_mutations.c)
        self.assertIn("change_seq", sync_mutations.c)
        self.assertCheckContains(
            "sync_client_mutations",
            "status_valid",
            ["pending", "applied", "failed"],
        )
        unique_constraints = {
            constraint.name
            for constraint in sync_mutations.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        self.assertIn(
            "uq_sync_client_mutations_actor_device_client_mutation",
            unique_constraints,
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
