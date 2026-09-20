from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.model_types import MONEY_NUMERIC, created_timestamp, updated_timestamp, uuid_fk, uuid_pk

PERCENT_NUMERIC = Numeric(7, 4)


class MoexInstrumentModel(Base):
    __tablename__ = "moex_instruments"
    __table_args__ = (Index("ix_moex_instruments_isin", "isin"),)

    secid: Mapped[str] = mapped_column(Text, primary_key=True)
    isin: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InvestmentPolicyModel(Base):
    __tablename__ = "investment_policies"
    __table_args__ = (
        UniqueConstraint("owner_user_id", name="uq_investment_policies_owner_user_id"),
        CheckConstraint(
            "conservative_percent + moderate_percent + aggressive_percent = 100",
            name="allocation_total_100",
        ),
        CheckConstraint(
            "conservative_percent >= 0 AND moderate_percent >= 0 AND aggressive_percent >= 0",
            name="allocation_non_negative",
        ),
        CheckConstraint(
            "tolerance_percent >= 0 AND tolerance_percent <= 25",
            name="tolerance_range",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    conservative_percent: Mapped[Decimal] = mapped_column(PERCENT_NUMERIC, nullable=False)
    moderate_percent: Mapped[Decimal] = mapped_column(PERCENT_NUMERIC, nullable=False)
    aggressive_percent: Mapped[Decimal] = mapped_column(PERCENT_NUMERIC, nullable=False)
    tolerance_percent: Mapped[Decimal] = mapped_column(PERCENT_NUMERIC, nullable=False)
    created_at: Mapped[datetime] = created_timestamp()
    updated_at: Mapped[datetime] = updated_timestamp()
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))


class BrokerageAccountProfileModel(Base):
    __tablename__ = "brokerage_account_profiles"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "brokerage",
            "label_key",
            name="uq_brokerage_account_profiles_owner_brokerage_label",
        ),
        CheckConstraint(
            "brokerage IN ('sinara', 'sber_investments', 'finam')",
            name="brokerage_valid",
        ),
        CheckConstraint(
            "account_type IN ('brokerage', 'iis_a', 'iis_b', 'iis_iii')",
            name="account_type_valid",
        ),
        Index(
            "ix_brokerage_account_profiles_owner_brokerage",
            "owner_user_id",
            "brokerage",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    brokerage: Mapped[str] = mapped_column(Text, nullable=False)
    user_label: Mapped[str] = mapped_column(Text, nullable=False)
    label_key: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_timestamp()
    updated_at: Mapped[datetime] = updated_timestamp()


class PortfolioImportModel(Base):
    __tablename__ = "portfolio_imports"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_portfolio_imports_owner_idempotency_key",
        ),
        CheckConstraint(
            "brokerage IN ('sinara', 'sber_investments', 'finam')",
            name="brokerage_valid",
        ),
        CheckConstraint("status IN ('pending', 'confirmed')", name="status_valid"),
        CheckConstraint("screenshot_count > 0", name="screenshot_count_positive"),
        Index("ix_portfolio_imports_owner_created", "owner_user_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    account_profile_id: Mapped[uuid.UUID | None] = uuid_fk(
        "brokerage_account_profiles.id", nullable=True
    )
    brokerage: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    screenshot_count: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_timestamp()
    updated_at: Mapped[datetime] = updated_timestamp()


class PortfolioSnapshotModel(Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        UniqueConstraint("import_id", name="uq_portfolio_snapshots_import_id"),
        CheckConstraint("currency = 'RUB'", name="currency_rub_only"),
        CheckConstraint("free_cash >= 0", name="free_cash_non_negative"),
        CheckConstraint("monthly_contribution >= 0", name="monthly_contribution_non_negative"),
        CheckConstraint("total_value >= 0", name="total_value_non_negative"),
        Index(
            "ix_portfolio_snapshots_owner_observed",
            "owner_user_id",
            text("observed_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    import_id: Mapped[uuid.UUID] = uuid_fk("portfolio_imports.id")
    account_profile_id: Mapped[uuid.UUID | None] = uuid_fk(
        "brokerage_account_profiles.id", nullable=True
    )
    brokerage: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'RUB'"))
    free_cash: Mapped[Decimal] = mapped_column(MONEY_NUMERIC, nullable=False)
    monthly_contribution: Mapped[Decimal] = mapped_column(MONEY_NUMERIC, nullable=False)
    total_value: Mapped[Decimal] = mapped_column(MONEY_NUMERIC, nullable=False)
    created_at: Mapped[datetime] = created_timestamp()


class PortfolioPositionModel(Base):
    __tablename__ = "portfolio_positions"
    __table_args__ = (
        CheckConstraint(
            "instrument_type IN ('stock', 'bond', 'fund')", name="instrument_type_valid"
        ),
        CheckConstraint(
            "risk_bucket IN ('conservative', 'moderate', 'aggressive')",
            name="risk_bucket_valid",
        ),
        CheckConstraint("currency = 'RUB'", name="currency_rub_only"),
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint("market_value >= 0", name="market_value_non_negative"),
        Index("ix_portfolio_positions_snapshot", "snapshot_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    snapshot_id: Mapped[uuid.UUID] = uuid_fk("portfolio_snapshots.id")
    instrument_name: Mapped[str] = mapped_column(Text, nullable=False)
    ticker: Mapped[str | None] = mapped_column(Text)
    isin: Mapped[str | None] = mapped_column(Text)
    instrument_type: Mapped[str] = mapped_column(Text, nullable=False)
    risk_bucket: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'RUB'"))
    quantity: Mapped[Decimal] = mapped_column(MONEY_NUMERIC, nullable=False)
    market_price: Mapped[Decimal | None] = mapped_column(MONEY_NUMERIC)
    market_value: Mapped[Decimal] = mapped_column(MONEY_NUMERIC, nullable=False)
    average_price: Mapped[Decimal | None] = mapped_column(MONEY_NUMERIC)
    nominal: Mapped[Decimal | None] = mapped_column(MONEY_NUMERIC)
    accrued_interest: Mapped[Decimal | None] = mapped_column(MONEY_NUMERIC)
    coupon_rate: Mapped[Decimal | None] = mapped_column(PERCENT_NUMERIC)
    maturity_date: Mapped[date | None] = mapped_column(Date)
    tax_account_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'brokerage'")
    )
    holding_started_at: Mapped[date | None] = mapped_column(Date)
    estimated_fee_rate: Mapped[Decimal | None] = mapped_column(PERCENT_NUMERIC)


class RecommendationJobModel(Base):
    __tablename__ = "recommendation_jobs"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_recommendation_jobs_owner_idempotency_key",
        ),
        CheckConstraint(
            "status IN ('queued', 'collecting', 'analyzing', 'ready', 'failed')",
            name="status_valid",
        ),
        CheckConstraint("attempt_count >= 1 AND attempt_count <= 3", name="attempt_count_range"),
        Index("ix_recommendation_jobs_owner_created", "owner_user_id", text("created_at DESC")),
        Index("ix_recommendation_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    market_data_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_timestamp()
    updated_at: Mapped[datetime] = updated_timestamp()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))


class RecommendationJobSnapshotModel(Base):
    __tablename__ = "recommendation_job_snapshots"
    __table_args__ = (
        UniqueConstraint("job_id", "snapshot_id", name="uq_recommendation_job_snapshots_pair"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = uuid_fk("recommendation_jobs.id")
    snapshot_id: Mapped[uuid.UUID] = uuid_fk("portfolio_snapshots.id")


class RecommendationReportModel(Base):
    __tablename__ = "recommendation_reports"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_recommendation_reports_job_id"),
        Index(
            "ix_recommendation_reports_owner_generated", "owner_user_id", text("generated_at DESC")
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    job_id: Mapped[uuid.UUID] = uuid_fk("recommendation_jobs.id")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)


class RecommendationActionModel(Base):
    __tablename__ = "recommendation_actions"
    __table_args__ = (
        CheckConstraint("action IN ('keep', 'reduce', 'increase', 'add')", name="action_valid"),
        CheckConstraint("priority >= 1 AND priority <= 100", name="priority_range"),
        Index("ix_recommendation_actions_report_priority", "report_id", "priority"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    report_id: Mapped[uuid.UUID] = uuid_fk("recommendation_reports.id")
    instrument_name: Mapped[str] = mapped_column(Text, nullable=False)
    ticker: Mapped[str | None] = mapped_column(Text)
    isin: Mapped[str | None] = mapped_column(Text)
    risk_bucket: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    current_percent: Mapped[Decimal] = mapped_column(PERCENT_NUMERIC, nullable=False)
    target_percent: Mapped[Decimal] = mapped_column(PERCENT_NUMERIC, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY_NUMERIC, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    risks: Mapped[str] = mapped_column(Text, nullable=False)


class RecommendationSourceModel(Base):
    __tablename__ = "recommendation_sources"
    __table_args__ = (Index("ix_recommendation_sources_report", "report_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    report_id: Mapped[uuid.UUID] = uuid_fk("recommendation_reports.id")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str] = mapped_column(Text, nullable=False)
    trust_tier: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RecommendationCallbackNonceModel(Base):
    __tablename__ = "recommendation_callback_nonces"
    __table_args__ = (
        UniqueConstraint("nonce", name="uq_recommendation_callback_nonces_nonce"),
        Index("ix_recommendation_callback_nonces_expires", "expires_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = uuid_fk("recommendation_jobs.id")
    nonce: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
