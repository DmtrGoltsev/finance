from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.transactions.schemas import PageInfo, TransactionDto

ResourceId = Annotated[str, StringConstraints(min_length=1, max_length=128)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
MoneyAmount = Annotated[Decimal, Field(max_digits=20, decimal_places=4)]


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
        use_enum_values=True,
    )


class ReportMode(StrEnum):
    PERSONAL = "personal"
    SHARED_FAMILY_REPORT = "shared_family_report"
    COMBINED_VIEWER_OVERVIEW = "combined_viewer_overview"


class ReportBucket(StrEnum):
    DAY = "day"
    MONTH = "month"


class ReportTransactionType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    BROKERAGE = "brokerage"
    ASSET_BUY = "asset_buy"
    ASSET_SELL = "asset_sell"
    INTEREST = "interest"
    DIVIDEND = "dividend"
    ADJUSTMENT = "adjustment"


class ReportPeriodDto(ApiModel):
    start_date: date | None = None
    end_date: date | None = None
    timezone: Annotated[str, StringConstraints(min_length=1, max_length=80)]


class ReportScopeDto(ApiModel):
    viewer_user_id: ResourceId
    household_id: ResourceId | None = None
    report_mode: ReportMode
    generated_at: datetime


class MoneyTotalDto(ApiModel):
    currency: CurrencyCode
    income_total: MoneyAmount
    expense_total: MoneyAmount
    transfer_total: MoneyAmount
    net_cash_flow: MoneyAmount
    net_total: MoneyAmount
    investments_total: MoneyAmount = Decimal("0.0000")


class ReportSummaryDto(ApiModel):
    scope: ReportScopeDto
    period: ReportPeriodDto
    totals_by_currency: list[MoneyTotalDto]


class CategoryBreakdownItemDto(ApiModel):
    category_id: ResourceId | None = None
    category_name: Annotated[str, StringConstraints(max_length=200)] | None = None
    category_type: Annotated[str, StringConstraints(max_length=20)] | None = None
    category_scope: Annotated[str, StringConstraints(max_length=20)] | None = None
    currency: CurrencyCode
    amount: MoneyAmount
    transaction_count: Annotated[int, Field(ge=0)]
    share_of_visible_total: Annotated[str, StringConstraints(pattern=r"^0(\.[0-9]+)?|1(\.0+)?$")]


class ReportCategoryBreakdownDto(ApiModel):
    scope: ReportScopeDto
    period: ReportPeriodDto
    items: list[CategoryBreakdownItemDto]
    expenses_by_category: list[CategoryBreakdownItemDto]


class AccountBalanceDto(ApiModel):
    account_id: ResourceId
    account_name: Annotated[str, StringConstraints(max_length=200)]
    account_type: Annotated[str, StringConstraints(max_length=40)]
    ownership_type: Annotated[str, StringConstraints(max_length=20)]
    household_id: ResourceId | None = None
    owner_user_id: ResourceId | None = None
    asset_category_id: ResourceId | None = None
    currency: CurrencyCode
    current_balance: MoneyAmount
    balance_as_of: datetime


class AccountBalanceGroupDto(ApiModel):
    account_type: Annotated[str, StringConstraints(max_length=40)]
    currency: CurrencyCode
    current_balance_total: MoneyAmount
    account_count: Annotated[int, Field(ge=0)]


class AssetCategoryBalanceGroupDto(ApiModel):
    asset_category_id: ResourceId
    asset_category_name: Annotated[str, StringConstraints(max_length=200)]
    asset_type: Annotated[str, StringConstraints(max_length=40)]
    scope_type: Annotated[str, StringConstraints(max_length=20)]
    household_id: ResourceId | None = None
    owner_user_id: ResourceId | None = None
    currency: CurrencyCode
    manual_amount: MoneyAmount
    linked_accounts_total: MoneyAmount
    current_balance_total: MoneyAmount
    account_count: Annotated[int, Field(ge=0)]
    is_investment: bool


class NetWorthTotalDto(ApiModel):
    currency: CurrencyCode
    net_worth_total: MoneyAmount


class InvestmentTotalDto(ApiModel):
    currency: CurrencyCode
    investments_total: MoneyAmount


class ReportAccountBalancesDto(ApiModel):
    scope: ReportScopeDto
    as_of_date: date | None = None
    timezone: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    items: list[AccountBalanceDto]
    balance_groups: list[AccountBalanceGroupDto]
    assets_by_type: list[AccountBalanceGroupDto]
    asset_category_groups: list[AssetCategoryBalanceGroupDto]
    legacy_asset_type_groups: list[AccountBalanceGroupDto]
    totals_by_currency: list[NetWorthTotalDto]
    investments_by_currency: list[InvestmentTotalDto]


class CashFlowPointDto(ApiModel):
    period_start_date: date
    period_end_date: date
    totals_by_currency: list[MoneyTotalDto]


class ReportCashFlowDto(ApiModel):
    scope: ReportScopeDto
    period: ReportPeriodDto
    bucket: ReportBucket
    points: list[CashFlowPointDto]


class ReportTransactionDrillDownDto(ApiModel):
    scope: ReportScopeDto
    period: ReportPeriodDto
    items: list[TransactionDto]
    page: PageInfo


class ReportSummaryEnvelope(ApiModel):
    data: ReportSummaryDto


class ReportCategoryBreakdownEnvelope(ApiModel):
    data: ReportCategoryBreakdownDto


class ReportAccountBalancesEnvelope(ApiModel):
    data: ReportAccountBalancesDto


class ReportCashFlowEnvelope(ApiModel):
    data: ReportCashFlowDto


class ReportTransactionDrillDownEnvelope(ApiModel):
    data: ReportTransactionDrillDownDto
