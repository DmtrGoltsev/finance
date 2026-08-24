"""SQLAlchemy 2.x model skeleton for the closed Finance MVP.

The models intentionally define table shape, foreign keys, CHECK constraints,
indexes, timestamps, and optimistic versions only. Routes, authz predicates,
services, triggers, and migration revisions are separate implementation work.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.model_enums import (
    ACCOUNT_TYPES,
    ACTIVE_DELETED_STATUSES,
    ASSET_CATEGORY_TYPES,
    AUDIT_RESULTS,
    AUDIT_SCOPE_TYPES,
    AUTH_STATUSES,
    CAPTURE_DRAFT_STATUSES,
    CAPTURE_SOURCES,
    CATEGORY_SCOPES,
    CATEGORY_TYPES,
    DELETION_REQUEST_STATUSES,
    EXPORT_SCOPE_TYPES,
    EXPORT_STATUSES,
    HOUSEHOLD_STATUSES,
    INVITE_STATUSES,
    MEMBERSHIP_STATUSES,
    OUTBOX_STATUSES,
    OWNERSHIP_TYPES,
    PLANNING_ALLOCATION_MODES,
    PLANNING_ALLOCATION_RECURRENCE_TYPES,
    PLANNING_ALLOCATION_TARGET_TYPES,
    PLANNING_INCOME_CONFIRMATION_STATES,
    PLANNING_SCOPE_TYPES,
    RECORD_STATUSES,
    RESET_TOKEN_STATUSES,
    SESSION_STATUSES,
    SESSION_TRANSPORTS,
    SOURCE_TYPES,
    TRANSACTION_TYPES,
    TRANSFER_SCOPES,
    TRANSFER_STATUSES,
)
from app.db.model_types import MONEY_NUMERIC, created_timestamp, updated_timestamp, uuid_fk, uuid_pk


def enum_check(column_name: str, values: tuple[str, ...]) -> str:
    quoted_values = ", ".join(f"'{value}'" for value in values)
    return f"{column_name} IN ({quoted_values})"


class VersionedMixin:
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))


class TimestampMixin:
    created_at: Mapped[datetime] = created_timestamp()
    updated_at: Mapped[datetime] = updated_timestamp()


class User(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(enum_check("auth_status", AUTH_STATUSES), name="auth_status_valid"),
        CheckConstraint(
            enum_check("record_status", ACTIVE_DELETED_STATUSES),
            name="record_status_valid",
        ),
        Index(
            "uq_users_email_normalized_not_deleted",
            "email_normalized",
            unique=True,
            postgresql_where=text("record_status <> 'deleted'"),
        ),
        Index("ix_users_auth_status_record_status", "auth_status", "record_status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    email_normalized: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    auth_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )
    record_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )
    session_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("1"),
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Household(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "households"
    __table_args__ = (
        CheckConstraint(enum_check("status", HOUSEHOLD_STATUSES), name="status_valid"),
        CheckConstraint(
            enum_check("record_status", ACTIVE_DELETED_STATUSES),
            name="record_status_valid",
        ),
        Index("ix_households_created_by_user_id", "created_by_user_id"),
        Index("ix_households_status_record_status", "status", "record_status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )
    record_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )
    membership_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("1"),
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Membership(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint(
            enum_check("membership_status", MEMBERSHIP_STATUSES),
            name="membership_status_valid",
        ),
        Index(
            "uq_memberships_active_household_user",
            "household_id",
            "user_id",
            unique=True,
            postgresql_where=text("membership_status = 'active'"),
        ),
        Index(
            "ix_memberships_active_user_household",
            "user_id",
            "household_id",
            postgresql_where=text("membership_status = 'active'"),
        ),
        Index(
            "ix_memberships_active_household_user",
            "household_id",
            "user_id",
            postgresql_where=text("membership_status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    household_id: Mapped[uuid.UUID] = uuid_fk("households.id")
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    membership_status: Mapped[str] = mapped_column(Text, nullable=False)
    invited_by_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invite(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "invites"
    __table_args__ = (
        CheckConstraint(enum_check("invite_status", INVITE_STATUSES), name="invite_status_valid"),
        Index(
            "uq_invites_pending_token_hash",
            "token_hash",
            unique=True,
            postgresql_where=text("invite_status = 'pending'"),
        ),
        Index(
            "ix_invites_household_status_pending",
            "household_id",
            "invite_status",
            postgresql_where=text("invite_status = 'pending'"),
        ),
        Index(
            "ix_invites_invited_user_status",
            "invited_user_id",
            "invite_status",
            postgresql_where=text("invited_user_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    household_id: Mapped[uuid.UUID] = uuid_fk("households.id")
    invited_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    invited_email_hash: Mapped[str | None] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    invite_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    accepted_by_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Account(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(enum_check("account_type", ACCOUNT_TYPES), name="account_type_valid"),
        CheckConstraint(enum_check("ownership_type", OWNERSHIP_TYPES), name="ownership_type_valid"),
        CheckConstraint(
            "(ownership_type = 'personal' AND owner_user_id IS NOT NULL AND household_id IS NULL) "
            "OR (ownership_type = 'shared' AND household_id IS NOT NULL AND owner_user_id IS NULL)",
            name="exactly_one_scope",
        ),
        CheckConstraint(enum_check("record_status", RECORD_STATUSES), name="record_status_valid"),
        CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name="currency_iso_shape",
        ),
        Index("ix_accounts_owner_user_status", "owner_user_id", "record_status"),
        Index("ix_accounts_household_status", "household_id", "record_status"),
        Index("ix_accounts_asset_category_id", "asset_category_id"),
        Index("ix_accounts_payment_status", "is_payment_account", "record_status"),
        Index(
            "ix_accounts_ownership_owner_status",
            "ownership_type",
            "owner_user_id",
            "record_status",
        ),
        Index(
            "ix_accounts_ownership_household_status",
            "ownership_type",
            "household_id",
            "record_status",
        ),
    )
    # TODO(db-trigger): forbid updates to ownership_type/owner_user_id/household_id before release.

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    ownership_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    household_id: Mapped[uuid.UUID | None] = uuid_fk("households.id", nullable=True)
    asset_category_id: Mapped[uuid.UUID | None] = uuid_fk("asset_categories.id", nullable=True)
    is_payment_account: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    initial_balance_amount: Mapped[Decimal] = mapped_column(
        MONEY_NUMERIC,
        nullable=False,
        server_default=text("0"),
    )
    current_balance_amount: Mapped[Decimal | None] = mapped_column(MONEY_NUMERIC)
    record_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )
    created_by_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountBalanceSnapshot(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "account_balance_snapshots"
    __table_args__ = (
        CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name="currency_iso_shape",
        ),
        Index(
            "ix_account_balance_snapshots_account_date_created",
            "account_id",
            text("snapshot_date DESC"),
            text("created_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    account_id: Mapped[uuid.UUID] = uuid_fk("accounts.id")
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    balance_amount: Mapped[Decimal] = mapped_column(MONEY_NUMERIC, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)


class AssetCategory(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "asset_categories"
    __table_args__ = (
        CheckConstraint(enum_check("scope_type", CATEGORY_SCOPES), name="scope_type_valid"),
        CheckConstraint(enum_check("asset_type", ASSET_CATEGORY_TYPES), name="asset_type_valid"),
        CheckConstraint(
            "(scope_type = 'personal' AND owner_user_id IS NOT NULL AND household_id IS NULL) "
            "OR (scope_type = 'household' AND household_id IS NOT NULL AND owner_user_id IS NULL)",
            name="exactly_one_scope",
        ),
        CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name="currency_iso_shape",
        ),
        CheckConstraint("manual_amount >= 0", name="non_negative_manual_amount"),
        CheckConstraint(enum_check("record_status", RECORD_STATUSES), name="record_status_valid"),
        Index("ix_asset_categories_owner_status", "owner_user_id", "record_status"),
        Index("ix_asset_categories_household_status", "household_id", "record_status"),
        Index("ix_asset_categories_investment_status", "is_investment", "record_status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    scope_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    household_id: Mapped[uuid.UUID | None] = uuid_fk("households.id", nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    asset_type: Mapped[str] = mapped_column(Text, nullable=False)
    icon_key: Mapped[str | None] = mapped_column(Text)
    manual_amount: Mapped[Decimal] = mapped_column(
        MONEY_NUMERIC,
        nullable=False,
        server_default=text("0"),
    )
    is_investment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    record_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )
    created_by_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Category(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint(enum_check("category_scope", CATEGORY_SCOPES), name="category_scope_valid"),
        CheckConstraint(enum_check("category_type", CATEGORY_TYPES), name="category_type_valid"),
        CheckConstraint(
            "(category_scope = 'personal' AND owner_user_id IS NOT NULL AND household_id IS NULL) "
            "OR (category_scope = 'household' "
            "AND household_id IS NOT NULL AND owner_user_id IS NULL)",
            name="exactly_one_scope",
        ),
        CheckConstraint(enum_check("record_status", RECORD_STATUSES), name="record_status_valid"),
        Index("ix_categories_owner_type_status", "owner_user_id", "category_type", "record_status"),
        Index(
            "ix_categories_household_type_status",
            "household_id",
            "category_type",
            "record_status",
        ),
    )
    # TODO(db-trigger): forbid updates to category_scope/owner_user_id/household_id before release.

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category_type: Mapped[str] = mapped_column(Text, nullable=False)
    category_scope: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    household_id: Mapped[uuid.UUID | None] = uuid_fk("households.id", nullable=True)
    icon_key: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(Text)
    record_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )
    created_by_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Transaction(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            enum_check("transaction_type", TRANSACTION_TYPES),
            name="transaction_type_valid",
        ),
        CheckConstraint(enum_check("source_type", SOURCE_TYPES), name="source_type_valid"),
        CheckConstraint("source_type = 'manual'", name="source_type_manual_only"),
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name="currency_iso_shape",
        ),
        CheckConstraint(
            "(transaction_type = 'transfer' "
            "AND counterparty_account_id IS NOT NULL "
            "AND counterparty_account_id <> account_id "
            "AND category_id IS NULL "
            f"AND transfer_scope IN ({', '.join(repr(value) for value in TRANSFER_SCOPES)}) "
            f"AND transfer_status IN ({', '.join(repr(value) for value in TRANSFER_STATUSES)})) "
            "OR (transaction_type <> 'transfer' "
            "AND counterparty_account_id IS NULL "
            "AND transfer_scope IS NULL "
            "AND transfer_status IS NULL)",
            name="transfer_shape",
        ),
        CheckConstraint(
            "transaction_type NOT IN ('income', 'expense') OR category_id IS NOT NULL",
            name="income_expense_category_required",
        ),
        CheckConstraint(
            enum_check("record_status", ACTIVE_DELETED_STATUSES),
            name="record_status_valid",
        ),
        Index(
            "ix_transactions_account_occurred_status",
            "account_id",
            text("occurred_at DESC"),
            "record_status",
        ),
        Index(
            "ix_transactions_account_transaction_date_status",
            "account_id",
            text("transaction_date DESC"),
            "record_status",
        ),
        Index(
            "ix_transactions_category_occurred",
            "category_id",
            text("occurred_at DESC"),
            postgresql_where=text("category_id IS NOT NULL"),
        ),
        Index(
            "ix_transactions_category_transaction_date",
            "category_id",
            text("transaction_date DESC"),
            postgresql_where=text("category_id IS NOT NULL"),
        ),
        Index(
            "ix_transactions_counterparty_account",
            "counterparty_account_id",
            postgresql_where=text("counterparty_account_id IS NOT NULL"),
        ),
        Index(
            "ix_transactions_created_by_occurred",
            "created_by_user_id",
            text("occurred_at DESC"),
        ),
        Index("ix_transactions_source_type", "source_type"),
    )
    # TODO(db-trigger): validate transfer same-scope and same-currency by comparing both
    # account rows.

    id: Mapped[uuid.UUID] = uuid_pk()
    transaction_type: Mapped[str] = mapped_column(Text, nullable=False)
    account_id: Mapped[uuid.UUID] = uuid_fk("accounts.id")
    counterparty_account_id: Mapped[uuid.UUID | None] = uuid_fk("accounts.id", nullable=True)
    category_id: Mapped[uuid.UUID | None] = uuid_fk("categories.id", nullable=True)
    amount: Mapped[Decimal] = mapped_column(MONEY_NUMERIC, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'manual'"))
    transfer_scope: Mapped[str | None] = mapped_column(Text)
    transfer_status: Mapped[str | None] = mapped_column(Text)
    record_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )
    created_by_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    last_edited_by_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaptureDraft(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "capture_drafts"
    __table_args__ = (
        CheckConstraint(enum_check("status", CAPTURE_DRAFT_STATUSES), name="status_valid"),
        CheckConstraint(enum_check("capture_source", CAPTURE_SOURCES), name="capture_source_valid"),
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name="currency_iso_shape",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_range",
        ),
        CheckConstraint(
            "(status = 'confirmed' AND transaction_id IS NOT NULL) OR "
            "(status <> 'confirmed' AND transaction_id IS NULL)",
            name="confirmed_transaction_shape",
        ),
        Index(
            "uq_capture_drafts_owner_idempotency_key",
            "owner_user_id",
            "idempotency_key",
            unique=True,
        ),
        Index(
            "ix_capture_drafts_owner_status_created",
            "owner_user_id",
            "status",
            text("created_at DESC"),
        ),
        Index("ix_capture_drafts_transaction_id", "transaction_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    capture_source: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    occurred_date: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(MONEY_NUMERIC, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    merchant_name: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[uuid.UUID | None] = uuid_fk("accounts.id", nullable=True)
    category_id: Mapped[uuid.UUID | None] = uuid_fk("categories.id", nullable=True)
    transaction_id: Mapped[uuid.UUID | None] = uuid_fk("transactions.id", nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(MONEY_NUMERIC)
    source_app_package: Mapped[str | None] = mapped_column(Text)
    source_app_label: Mapped[str | None] = mapped_column(Text)
    evidence_hash: Mapped[str | None] = mapped_column(Text)


class CaptureCategoryMapping(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "capture_category_mappings"
    __table_args__ = (
        CheckConstraint(
            "length(external_label_hash) = 64",
            name="external_label_hash_sha256",
        ),
        Index(
            "uq_capture_category_mappings_owner_personal_hash",
            "owner_user_id",
            "external_label_hash",
            unique=True,
            postgresql_where=text("household_id IS NULL"),
            sqlite_where=text("household_id IS NULL"),
        ),
        Index(
            "uq_capture_category_mappings_owner_household_hash",
            "owner_user_id",
            "household_id",
            "external_label_hash",
            unique=True,
            postgresql_where=text("household_id IS NOT NULL"),
            sqlite_where=text("household_id IS NOT NULL"),
        ),
        Index("ix_capture_category_mappings_category_id", "category_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    household_id: Mapped[uuid.UUID | None] = uuid_fk("households.id", nullable=True)
    category_id: Mapped[uuid.UUID] = uuid_fk("categories.id")
    external_label_hash: Mapped[str] = mapped_column(Text, nullable=False)


class PlanningPlan(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "planning_plans"
    __table_args__ = (
        CheckConstraint(enum_check("scope_type", PLANNING_SCOPE_TYPES), name="scope_type_valid"),
        CheckConstraint(
            "(scope_type = 'personal' AND owner_user_id IS NOT NULL AND household_id IS NULL) "
            "OR (scope_type = 'household' AND household_id IS NOT NULL AND owner_user_id IS NULL)",
            name="exactly_one_scope",
        ),
        CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name="currency_iso_shape",
        ),
        Index(
            "uq_planning_plans_personal_month",
            "owner_user_id",
            "plan_month",
            unique=True,
            postgresql_where=text("scope_type = 'personal'"),
            sqlite_where=text("scope_type = 'personal'"),
        ),
        Index(
            "uq_planning_plans_household_month",
            "household_id",
            "plan_month",
            unique=True,
            postgresql_where=text("scope_type = 'household'"),
            sqlite_where=text("scope_type = 'household'"),
        ),
        Index("ix_planning_plans_owner_month", "owner_user_id", text("plan_month DESC")),
        Index("ix_planning_plans_household_month", "household_id", text("plan_month DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    scope_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    household_id: Mapped[uuid.UUID | None] = uuid_fk("households.id", nullable=True)
    plan_month: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")


class PlanningIncomeSource(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "planning_income_sources"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("day_of_month >= 1 AND day_of_month <= 31", name="day_of_month_range"),
        CheckConstraint(
            enum_check("confirmation_state", PLANNING_INCOME_CONFIRMATION_STATES),
            name="confirmation_state_valid",
        ),
        CheckConstraint(
            enum_check("record_status", ACTIVE_DELETED_STATUSES),
            name="record_status_valid",
        ),
        CheckConstraint(
            "(record_status = 'active' AND deleted_at IS NULL) "
            "OR (record_status = 'deleted' AND deleted_at IS NOT NULL)",
            name="record_status_deleted_at_shape",
        ),
        Index("ix_planning_income_sources_plan_id", "plan_id"),
        Index("ix_planning_income_sources_plan_status", "plan_id", "record_status"),
        Index(
            "ix_planning_income_sources_plan_state",
            "plan_id",
            "confirmation_state",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    plan_id: Mapped[uuid.UUID] = uuid_fk("planning_plans.id")
    amount: Mapped[Decimal] = mapped_column(MONEY_NUMERIC, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmation_state: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'planned'"),
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    record_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlanningAllocation(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "planning_allocations"
    __table_args__ = (
        CheckConstraint(
            enum_check("target_type", PLANNING_ALLOCATION_TARGET_TYPES),
            name="target_type_valid",
        ),
        CheckConstraint(
            enum_check("allocation_mode", PLANNING_ALLOCATION_MODES),
            name="allocation_mode_valid",
        ),
        CheckConstraint(
            enum_check("recurrence_type", PLANNING_ALLOCATION_RECURRENCE_TYPES),
            name="recurrence_type_valid",
        ),
        CheckConstraint("allocation_value >= 0", name="non_negative_allocation_value"),
        CheckConstraint(
            "goal_target_amount IS NULL OR goal_target_amount > 0",
            name="positive_goal_target_amount",
        ),
        CheckConstraint(
            "is_savings_goal = false OR target_type = 'investment_asset_category'",
            name="savings_goal_investment_target",
        ),
        CheckConstraint(
            "(target_id IS NOT NULL AND requires_attention = false) "
            "OR (target_id IS NULL AND requires_attention = true)",
            name="target_attention_shape",
        ),
        CheckConstraint(
            enum_check("record_status", ACTIVE_DELETED_STATUSES),
            name="record_status_valid",
        ),
        CheckConstraint(
            "(record_status = 'active' AND deleted_at IS NULL) "
            "OR (record_status = 'deleted' AND deleted_at IS NOT NULL)",
            name="record_status_deleted_at_shape",
        ),
        Index("ix_planning_allocations_plan_id", "plan_id"),
        Index("ix_planning_allocations_plan_status", "plan_id", "record_status"),
        Index(
            "ix_planning_allocations_plan_attention",
            "plan_id",
            "requires_attention",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    plan_id: Mapped[uuid.UUID] = uuid_fk("planning_plans.id")
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    target_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    requires_attention: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    attention_reason: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    allocation_mode: Mapped[str] = mapped_column(Text, nullable=False)
    allocation_value: Mapped[Decimal] = mapped_column(MONEY_NUMERIC, nullable=False)
    recurrence_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'regular'"),
    )
    is_savings_goal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    goal_target_amount: Mapped[Decimal | None] = mapped_column(MONEY_NUMERIC)
    goal_due_month: Mapped[date | None] = mapped_column(Date)
    created_by_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    record_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Session(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(enum_check("transport", SESSION_TRANSPORTS), name="transport_valid"),
        CheckConstraint(enum_check("status", SESSION_STATUSES), name="status_valid"),
        CheckConstraint(
            "session_token_hash IS NOT NULL OR refresh_token_hash IS NOT NULL",
            name="at_least_one_token_hash",
        ),
        Index(
            "ix_sessions_user_active_expires",
            "user_id",
            "status",
            "expires_at",
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_sessions_session_version", "session_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    session_token_hash: Mapped[str | None] = mapped_column(Text, unique=True)
    refresh_token_hash: Mapped[str | None] = mapped_column(Text, unique=True)
    transport: Mapped[str] = mapped_column(Text, nullable=False)
    session_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    csrf_token_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(Text)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        CheckConstraint(enum_check("status", RESET_TOKEN_STATUSES), name="status_valid"),
        Index(
            "uq_password_reset_tokens_pending_token_hash",
            "token_hash",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "ix_password_reset_tokens_email_status_created",
            "email_hash",
            "status",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    email_hash: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_timestamp()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_ip_hash: Mapped[str | None] = mapped_column(Text)


class ExportJob(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "export_jobs"
    __table_args__ = (
        CheckConstraint(enum_check("scope_type", EXPORT_SCOPE_TYPES), name="scope_type_valid"),
        CheckConstraint(enum_check("status", EXPORT_STATUSES), name="status_valid"),
        CheckConstraint(
            "(scope_type = 'personal' "
            "AND owner_user_id = requested_by_user_id AND household_id IS NULL) "
            "OR (scope_type = 'household' AND household_id IS NOT NULL AND owner_user_id IS NULL) "
            "OR (scope_type = 'combined' AND owner_user_id = requested_by_user_id "
            "AND household_id IS NOT NULL)",
            name="export_scope_shape",
        ),
        Index(
            "ix_export_jobs_requested_status_created",
            "requested_by_user_id",
            "status",
            text("created_at DESC"),
        ),
        Index(
            "ix_export_jobs_household_status",
            "household_id",
            "status",
            postgresql_where=text("household_id IS NOT NULL"),
        ),
        Index(
            "ix_export_jobs_ready_expires",
            "expires_at",
            postgresql_where=text("status = 'ready'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    requested_by_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    export_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    household_id: Mapped[uuid.UUID | None] = uuid_fk("households.id", nullable=True)
    membership_version_at_request: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(Text)
    file_hash: Mapped[str | None] = mapped_column(Text)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeletionRequest(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "deletion_requests"
    __table_args__ = (
        CheckConstraint(
            enum_check("request_status", DELETION_REQUEST_STATUSES),
            name="request_status_valid",
        ),
        CheckConstraint("requested_by_user_id = target_user_id", name="self_only_request"),
        Index(
            "ix_deletion_requests_target_status_created",
            "target_user_id",
            "request_status",
            text("created_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    requested_by_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    target_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    request_status: Mapped[str] = mapped_column(Text, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fresh_auth_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason_code: Mapped[str | None] = mapped_column(Text)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(enum_check("scope_type", AUDIT_SCOPE_TYPES), name="scope_type_valid"),
        CheckConstraint(enum_check("result", AUDIT_RESULTS), name="result_valid"),
        CheckConstraint(
            "scope_type IS NULL "
            "OR (scope_type = 'personal' AND owner_user_id IS NOT NULL AND household_id IS NULL) "
            "OR (scope_type = 'household' AND household_id IS NOT NULL AND owner_user_id IS NULL) "
            "OR (scope_type = 'system' AND owner_user_id IS NULL AND household_id IS NULL)",
            name="audit_scope_shape",
        ),
        Index("ix_audit_events_actor_occurred", "actor_user_id", text("occurred_at DESC")),
        Index(
            "ix_audit_events_scope_owner_occurred",
            "scope_type",
            "owner_user_id",
            text("occurred_at DESC"),
        ),
        Index(
            "ix_audit_events_scope_household_occurred",
            "scope_type",
            "household_id",
            text("occurred_at DESC"),
        ),
        Index("ix_audit_events_request_id", "request_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    system_actor: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    scope_type: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    household_id: Mapped[uuid.UUID | None] = uuid_fk("households.id", nullable=True)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str | None] = mapped_column(Text)
    reason_code: Mapped[str | None] = mapped_column(Text)
    metadata_safe: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint(enum_check("status", OUTBOX_STATUSES), name="status_valid"),
        Index("ix_outbox_events_status_available_created", "status", "available_at", "created_at"),
        Index("ix_outbox_events_event_type_created", "event_type", "created_at"),
        Index("ix_outbox_events_owner_created", "owner_user_id", "created_at"),
        Index("ix_outbox_events_household_created", "household_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(Text, nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    scope_type: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    household_id: Mapped[uuid.UUID | None] = uuid_fk("households.id", nullable=True)
    membership_version: Mapped[int | None] = mapped_column(BigInteger)
    payload_safe: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_timestamp()
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class SyncClient(Base):
    __tablename__ = "sync_clients"
    __table_args__ = (
        PrimaryKeyConstraint("actor_user_id", "device_id", name="pk_sync_clients"),
        CheckConstraint("length(device_id) > 0", name="device_id_not_empty"),
        CheckConstraint("client_schema_version > 0", name="positive_client_schema_version"),
        CheckConstraint("server_cursor >= 0", name="non_negative_server_cursor"),
        Index("ix_sync_clients_actor_last_seen", "actor_user_id", text("last_seen_at DESC")),
    )

    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    device_id: Mapped[str] = mapped_column(Text, nullable=False)
    client_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    server_cursor: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("0"),
    )


class SyncChange(Base):
    __tablename__ = "sync_changes"
    __table_args__ = (
        CheckConstraint("seq > 0", name="positive_seq"),
        CheckConstraint("length(entity_type) > 0", name="entity_type_not_empty"),
        CheckConstraint("length(change_type) > 0", name="change_type_not_empty"),
        CheckConstraint(
            "scope_type IN ('personal', 'household', 'system')",
            name="scope_type_valid",
        ),
        CheckConstraint(
            "(scope_type = 'personal' AND owner_user_id IS NOT NULL AND household_id IS NULL) "
            "OR (scope_type = 'household' AND household_id IS NOT NULL AND owner_user_id IS NULL) "
            "OR (scope_type = 'system' AND owner_user_id IS NULL AND household_id IS NULL)",
            name="sync_scope_shape",
        ),
        Index("ix_sync_changes_seq", "seq"),
        Index("ix_sync_changes_entity", "entity_type", "entity_id", "seq"),
        Index(
            "ix_sync_changes_owner_visibility",
            "owner_user_id",
            "scope_type",
            "seq",
            postgresql_where=text("owner_user_id IS NOT NULL"),
            sqlite_where=text("owner_user_id IS NOT NULL"),
        ),
        Index(
            "ix_sync_changes_household_visibility",
            "household_id",
            "scope_type",
            "seq",
            postgresql_where=text("household_id IS NOT NULL"),
            sqlite_where=text("household_id IS NOT NULL"),
        ),
    )

    seq: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    household_id: Mapped[uuid.UUID | None] = uuid_fk("households.id", nullable=True)
    entity_version: Mapped[int | None] = mapped_column(BigInteger)
    entity_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    changed_by_user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    client_mutation_id: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    tombstone_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = created_timestamp()


class SyncClientMutation(TimestampMixin, Base):
    __tablename__ = "sync_client_mutations"
    __table_args__ = (
        UniqueConstraint(
            "actor_user_id",
            "device_id",
            "client_mutation_id",
            name="uq_sync_client_mutations_actor_device_client_mutation",
        ),
        CheckConstraint("length(device_id) > 0", name="device_id_not_empty"),
        CheckConstraint("length(client_mutation_id) > 0", name="client_mutation_id_not_empty"),
        CheckConstraint("length(request_hash) > 0", name="request_hash_not_empty"),
        CheckConstraint("length(entity_type) > 0", name="entity_type_not_empty"),
        CheckConstraint("length(operation) > 0", name="operation_not_empty"),
        CheckConstraint("status IN ('pending', 'applied', 'failed')", name="status_valid"),
        CheckConstraint("change_seq IS NULL OR change_seq > 0", name="positive_change_seq"),
        ForeignKeyConstraint(
            ["actor_user_id", "device_id"],
            ["sync_clients.actor_user_id", "sync_clients.device_id"],
            name="fk_sync_client_mutations_actor_device_sync_clients",
        ),
        Index(
            "ix_sync_client_mutations_actor_status_created",
            "actor_user_id",
            "status",
            text("created_at DESC"),
        ),
        Index("ix_sync_client_mutations_entity", "entity_type", "entity_id"),
        Index(
            "ix_sync_client_mutations_change_seq",
            "change_seq",
            postgresql_where=text("change_seq IS NOT NULL"),
            sqlite_where=text("change_seq IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    actor_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    device_id: Mapped[str] = mapped_column(Text, nullable=False)
    client_mutation_id: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'pending'"),
    )
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(Text)
    change_seq: Mapped[int | None] = mapped_column(BigInteger)
