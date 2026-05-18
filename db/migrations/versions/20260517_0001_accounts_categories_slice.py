"""Create account/category slice prerequisite tables.

Revision ID: 20260517_0001
Revises:
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260517_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UUID = postgresql.UUID(as_uuid=True)
MONEY = sa.Numeric(20, 4)


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", UUID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        *_base_columns(),
        sa.Column("email_normalized", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("auth_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("record_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("session_version", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("auth_status IN ('active', 'deactivated')", name=op.f("ck_users_auth_status_valid")),
        sa.CheckConstraint("record_status IN ('active', 'deleted')", name=op.f("ck_users_record_status_valid")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        "uq_users_email_normalized_not_deleted",
        "users",
        ["email_normalized"],
        unique=True,
        postgresql_where=sa.text("record_status <> 'deleted'"),
    )
    op.create_index("ix_users_auth_status_record_status", "users", ["auth_status", "record_status"])

    op.create_table(
        "households",
        *_base_columns(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", UUID, nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("record_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("membership_version", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'archived')", name=op.f("ck_households_status_valid")),
        sa.CheckConstraint("record_status IN ('active', 'deleted')", name=op.f("ck_households_record_status_valid")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name=op.f("fk_households_created_by_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_households")),
    )
    op.create_index("ix_households_created_by_user_id", "households", ["created_by_user_id"])
    op.create_index("ix_households_status_record_status", "households", ["status", "record_status"])

    op.create_table(
        "memberships",
        *_base_columns(),
        sa.Column("household_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("membership_status", sa.Text(), nullable=False),
        sa.Column("invited_by_user_id", UUID, nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "membership_status IN ('invited', 'active', 'left', 'revoked')",
            name=op.f("ck_memberships_membership_status_valid"),
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], name=op.f("fk_memberships_household_id_households")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_memberships_user_id_users")),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], name=op.f("fk_memberships_invited_by_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
    )
    op.create_index(
        "uq_memberships_active_household_user",
        "memberships",
        ["household_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("membership_status = 'active'"),
    )
    op.create_index(
        "ix_memberships_active_user_household",
        "memberships",
        ["user_id", "household_id"],
        postgresql_where=sa.text("membership_status = 'active'"),
    )
    op.create_index(
        "ix_memberships_active_household_user",
        "memberships",
        ["household_id", "user_id"],
        postgresql_where=sa.text("membership_status = 'active'"),
    )

    op.create_table(
        "accounts",
        *_base_columns(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("account_type", sa.Text(), nullable=False),
        sa.Column("ownership_type", sa.Text(), nullable=False),
        sa.Column("owner_user_id", UUID, nullable=True),
        sa.Column("household_id", UUID, nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("initial_balance_amount", MONEY, nullable=False, server_default=sa.text("0")),
        sa.Column("current_balance_amount", MONEY, nullable=True),
        sa.Column("record_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_by_user_id", UUID, nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "account_type IN ('cash', 'bank', 'deposit', 'brokerage')",
            name=op.f("ck_accounts_account_type_valid"),
        ),
        sa.CheckConstraint("ownership_type IN ('personal', 'shared')", name=op.f("ck_accounts_ownership_type_valid")),
        sa.CheckConstraint(
            "(ownership_type = 'personal' AND owner_user_id IS NOT NULL AND household_id IS NULL) "
            "OR (ownership_type = 'shared' AND household_id IS NOT NULL AND owner_user_id IS NULL)",
            name=op.f("ck_accounts_exactly_one_scope"),
        ),
        sa.CheckConstraint(
            "record_status IN ('active', 'archived', 'deleted')",
            name=op.f("ck_accounts_record_status_valid"),
        ),
        sa.CheckConstraint("currency = upper(currency) AND length(currency) = 3", name=op.f("ck_accounts_currency_iso_shape")),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_accounts_owner_user_id_users")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], name=op.f("fk_accounts_household_id_households")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name=op.f("fk_accounts_created_by_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
    )
    op.create_index(
        "ix_accounts_owner_user_status",
        "accounts",
        ["owner_user_id", "record_status"],
        postgresql_where=sa.text("owner_user_id IS NOT NULL"),
    )
    op.create_index(
        "ix_accounts_household_status",
        "accounts",
        ["household_id", "record_status"],
        postgresql_where=sa.text("household_id IS NOT NULL"),
    )
    op.create_index(
        "ix_accounts_ownership_owner_status",
        "accounts",
        ["ownership_type", "owner_user_id", "record_status"],
        postgresql_where=sa.text("owner_user_id IS NOT NULL"),
    )
    op.create_index(
        "ix_accounts_ownership_household_status",
        "accounts",
        ["ownership_type", "household_id", "record_status"],
        postgresql_where=sa.text("household_id IS NOT NULL"),
    )

    op.create_table(
        "categories",
        *_base_columns(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category_type", sa.Text(), nullable=False),
        sa.Column("category_scope", sa.Text(), nullable=False),
        sa.Column("owner_user_id", UUID, nullable=True),
        sa.Column("household_id", UUID, nullable=True),
        sa.Column("icon_key", sa.Text(), nullable=True),
        sa.Column("color", sa.Text(), nullable=True),
        sa.Column("record_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_by_user_id", UUID, nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("category_scope IN ('personal', 'household')", name=op.f("ck_categories_category_scope_valid")),
        sa.CheckConstraint("category_type IN ('income', 'expense')", name=op.f("ck_categories_category_type_valid")),
        sa.CheckConstraint(
            "(category_scope = 'personal' AND owner_user_id IS NOT NULL AND household_id IS NULL) "
            "OR (category_scope = 'household' AND household_id IS NOT NULL AND owner_user_id IS NULL)",
            name=op.f("ck_categories_exactly_one_scope"),
        ),
        sa.CheckConstraint(
            "record_status IN ('active', 'archived', 'deleted')",
            name=op.f("ck_categories_record_status_valid"),
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_categories_owner_user_id_users")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], name=op.f("fk_categories_household_id_households")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name=op.f("fk_categories_created_by_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
    )
    op.create_index(
        "ix_categories_owner_type_status",
        "categories",
        ["owner_user_id", "category_type", "record_status"],
        postgresql_where=sa.text("owner_user_id IS NOT NULL"),
    )
    op.create_index(
        "ix_categories_household_type_status",
        "categories",
        ["household_id", "category_type", "record_status"],
        postgresql_where=sa.text("household_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_categories_household_type_status", table_name="categories")
    op.drop_index("ix_categories_owner_type_status", table_name="categories")
    op.drop_table("categories")

    op.drop_index("ix_accounts_ownership_household_status", table_name="accounts")
    op.drop_index("ix_accounts_ownership_owner_status", table_name="accounts")
    op.drop_index("ix_accounts_household_status", table_name="accounts")
    op.drop_index("ix_accounts_owner_user_status", table_name="accounts")
    op.drop_table("accounts")

    op.drop_index("ix_memberships_active_household_user", table_name="memberships")
    op.drop_index("ix_memberships_active_user_household", table_name="memberships")
    op.drop_index("uq_memberships_active_household_user", table_name="memberships")
    op.drop_table("memberships")

    op.drop_index("ix_households_status_record_status", table_name="households")
    op.drop_index("ix_households_created_by_user_id", table_name="households")
    op.drop_table("households")

    op.drop_index("ix_users_auth_status_record_status", table_name="users")
    op.drop_index("uq_users_email_normalized_not_deleted", table_name="users")
    op.drop_table("users")
