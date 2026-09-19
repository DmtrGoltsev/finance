"""Add personal investment policies and confirmed portfolio snapshots.

Revision ID: 20260919_0020
Revises: 20260822_0019
Create Date: 2026-09-19

Only sanitized structured positions are persisted. This schema intentionally
has no image, OCR text, person-name, broker credential, or account-number field.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260919_0020"
down_revision: str | None = "20260822_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
MONEY = sa.Numeric(20, 4)
PERCENT = sa.Numeric(7, 4)


def upgrade() -> None:
    op.create_table(
        "investment_policies",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_user_id", UUID, nullable=False),
        sa.Column("conservative_percent", PERCENT, nullable=False),
        sa.Column("moderate_percent", PERCENT, nullable=False),
        sa.Column("aggressive_percent", PERCENT, nullable=False),
        sa.Column("tolerance_percent", PERCENT, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint(
            "conservative_percent + moderate_percent + aggressive_percent = 100",
            name=op.f("ck_investment_policies_allocation_total_100"),
        ),
        sa.CheckConstraint(
            "conservative_percent >= 0 AND moderate_percent >= 0 AND aggressive_percent >= 0",
            name=op.f("ck_investment_policies_allocation_non_negative"),
        ),
        sa.CheckConstraint(
            "tolerance_percent >= 0 AND tolerance_percent <= 25",
            name=op.f("ck_investment_policies_tolerance_range"),
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_investment_policies_owner_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_investment_policies")),
        sa.UniqueConstraint("owner_user_id", name=op.f("uq_investment_policies_owner_user_id")),
    )

    op.create_table(
        "portfolio_imports",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_user_id", UUID, nullable=False),
        sa.Column("brokerage", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("screenshot_count", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("brokerage IN ('sinara', 'sber_investments', 'finam')", name=op.f("ck_portfolio_imports_brokerage_valid")),
        sa.CheckConstraint("status IN ('pending', 'confirmed')", name=op.f("ck_portfolio_imports_status_valid")),
        sa.CheckConstraint("screenshot_count > 0", name=op.f("ck_portfolio_imports_screenshot_count_positive")),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_portfolio_imports_owner_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portfolio_imports")),
        sa.UniqueConstraint("owner_user_id", "idempotency_key", name=op.f("uq_portfolio_imports_owner_idempotency_key")),
    )
    op.create_index("ix_portfolio_imports_owner_created", "portfolio_imports", ["owner_user_id", sa.text("created_at DESC")])

    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_user_id", UUID, nullable=False),
        sa.Column("import_id", UUID, nullable=False),
        sa.Column("brokerage", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False, server_default=sa.text("'RUB'")),
        sa.Column("free_cash", MONEY, nullable=False),
        sa.Column("monthly_contribution", MONEY, nullable=False),
        sa.Column("total_value", MONEY, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("currency = 'RUB'", name=op.f("ck_portfolio_snapshots_currency_rub_only")),
        sa.CheckConstraint("free_cash >= 0", name=op.f("ck_portfolio_snapshots_free_cash_non_negative")),
        sa.CheckConstraint("monthly_contribution >= 0", name=op.f("ck_portfolio_snapshots_monthly_contribution_non_negative")),
        sa.CheckConstraint("total_value >= 0", name=op.f("ck_portfolio_snapshots_total_value_non_negative")),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_portfolio_snapshots_owner_user_id_users")),
        sa.ForeignKeyConstraint(["import_id"], ["portfolio_imports.id"], name=op.f("fk_portfolio_snapshots_import_id_portfolio_imports")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portfolio_snapshots")),
        sa.UniqueConstraint("import_id", name=op.f("uq_portfolio_snapshots_import_id")),
    )
    op.create_index("ix_portfolio_snapshots_owner_observed", "portfolio_snapshots", ["owner_user_id", sa.text("observed_at DESC")])

    op.create_table(
        "portfolio_positions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("snapshot_id", UUID, nullable=False),
        sa.Column("instrument_name", sa.Text(), nullable=False),
        sa.Column("ticker", sa.Text(), nullable=True),
        sa.Column("isin", sa.Text(), nullable=True),
        sa.Column("instrument_type", sa.Text(), nullable=False),
        sa.Column("risk_bucket", sa.Text(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False, server_default=sa.text("'RUB'")),
        sa.Column("quantity", MONEY, nullable=False),
        sa.Column("market_price", MONEY, nullable=True),
        sa.Column("market_value", MONEY, nullable=False),
        sa.Column("average_price", MONEY, nullable=True),
        sa.Column("nominal", MONEY, nullable=True),
        sa.Column("accrued_interest", MONEY, nullable=True),
        sa.Column("coupon_rate", PERCENT, nullable=True),
        sa.Column("maturity_date", sa.Date(), nullable=True),
        sa.Column("tax_account_type", sa.Text(), nullable=False, server_default=sa.text("'brokerage'")),
        sa.Column("holding_started_at", sa.Date(), nullable=True),
        sa.Column("estimated_fee_rate", PERCENT, nullable=True),
        sa.CheckConstraint("instrument_type IN ('stock', 'bond', 'fund')", name=op.f("ck_portfolio_positions_instrument_type_valid")),
        sa.CheckConstraint("risk_bucket IN ('conservative', 'moderate', 'aggressive')", name=op.f("ck_portfolio_positions_risk_bucket_valid")),
        sa.CheckConstraint("currency = 'RUB'", name=op.f("ck_portfolio_positions_currency_rub_only")),
        sa.CheckConstraint("quantity >= 0", name=op.f("ck_portfolio_positions_quantity_non_negative")),
        sa.CheckConstraint("market_value >= 0", name=op.f("ck_portfolio_positions_market_value_non_negative")),
        sa.ForeignKeyConstraint(["snapshot_id"], ["portfolio_snapshots.id"], name=op.f("fk_portfolio_positions_snapshot_id_portfolio_snapshots")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portfolio_positions")),
    )
    op.create_index("ix_portfolio_positions_snapshot", "portfolio_positions", ["snapshot_id"])


def downgrade() -> None:
    op.drop_index("ix_portfolio_positions_snapshot", table_name="portfolio_positions")
    op.drop_table("portfolio_positions")
    op.drop_index("ix_portfolio_snapshots_owner_observed", table_name="portfolio_snapshots")
    op.drop_table("portfolio_snapshots")
    op.drop_index("ix_portfolio_imports_owner_created", table_name="portfolio_imports")
    op.drop_table("portfolio_imports")
    op.drop_table("investment_policies")
