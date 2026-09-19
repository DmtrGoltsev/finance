from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    UrlConstraints,
    field_validator,
    model_validator,
)

from .instrument_resolver import is_valid_isin, is_valid_secid


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


ResourceId = Annotated[str, StringConstraints(min_length=1, max_length=128)]
IdempotencyKey = Annotated[str, StringConstraints(min_length=8, max_length=128)]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=300)]
LongText = Annotated[str, StringConstraints(min_length=1, max_length=5000)]
Money = Annotated[Decimal, Field(ge=0, max_digits=20, decimal_places=4)]
Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=4)]
HttpsUrl = Annotated[HttpUrl, UrlConstraints(allowed_schemes=["https"])]


class Brokerage(StrEnum):
    SINARA = "sinara"
    SBER_INVESTMENTS = "sber_investments"
    FINAM = "finam"


class InstrumentType(StrEnum):
    STOCK = "stock"
    BOND = "bond"
    FUND = "fund"


class RiskBucket(StrEnum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class TaxAccountType(StrEnum):
    BROKERAGE = "brokerage"
    IIS_A = "iis_a"
    IIS_B = "iis_b"
    IIS_III = "iis_iii"


class RecommendationStatus(StrEnum):
    QUEUED = "queued"
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    READY = "ready"
    FAILED = "failed"


class RecommendationActionType(StrEnum):
    KEEP = "keep"
    REDUCE = "reduce"
    INCREASE = "increase"
    ADD = "add"


class InvestmentPolicyPutRequest(ApiModel):
    conservative_percent: Percent = Decimal("40")
    moderate_percent: Percent = Decimal("30")
    aggressive_percent: Percent = Decimal("30")
    tolerance_percent: Annotated[Decimal, Field(ge=0, le=25)] = Decimal("5")

    @model_validator(mode="after")
    def validate_total(self) -> InvestmentPolicyPutRequest:
        if self.conservative_percent + self.moderate_percent + self.aggressive_percent != 100:
            raise ValueError("allocation percentages must total 100")
        return self


class InvestmentPolicyDto(InvestmentPolicyPutRequest):
    id: ResourceId
    owner_user_id: ResourceId
    created_at: datetime
    updated_at: datetime
    version: int


class PortfolioImportCreateRequest(ApiModel):
    idempotency_key: IdempotencyKey
    brokerage: Brokerage
    screenshot_count: Annotated[int, Field(ge=1, le=20)]
    observed_at: datetime


class PortfolioImportDto(ApiModel):
    id: ResourceId
    brokerage: Brokerage
    screenshot_count: int
    observed_at: datetime
    status: str
    confirmed_at: datetime | None
    created_at: datetime


class PortfolioPositionInput(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "anyOf": [
                {"required": ["ticker"]},
                {"required": ["isin"]},
            ]
        }
    )

    instrument_name: ShortText
    ticker: Annotated[
        str | None,
        StringConstraints(min_length=1, max_length=32, pattern=r"^[A-Z0-9][A-Z0-9._-]{0,31}$"),
    ] = None
    isin: Annotated[str | None, StringConstraints(pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")] = None
    instrument_type: InstrumentType
    risk_bucket: RiskBucket
    quantity: Money
    market_price: Money | None = None
    market_value: Money
    average_price: Money | None = None
    nominal: Money | None = None
    accrued_interest: Money | None = None
    coupon_rate: Percent | None = None
    maturity_date: date | None = None
    tax_account_type: TaxAccountType = TaxAccountType.BROKERAGE
    holding_started_at: date | None = None
    estimated_fee_rate: Percent | None = None

    @model_validator(mode="after")
    def require_canonical_identifier(self) -> PortfolioPositionInput:
        if not self.ticker and not self.isin:
            raise ValueError("ticker/SECID or ISIN is required")
        return self

    @field_validator("ticker")
    @classmethod
    def validate_secid(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_secid(value):
            raise ValueError("invalid SECID format")
        return value

    @field_validator("isin")
    @classmethod
    def validate_isin(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_isin(value):
            raise ValueError("invalid ISIN")
        return value


class PortfolioImportConfirmRequest(ApiModel):
    free_cash: Money = Decimal("0")
    monthly_contribution: Money = Decimal("0")
    positions: Annotated[list[PortfolioPositionInput], Field(min_length=1, max_length=500)]


class PortfolioPositionDto(PortfolioPositionInput):
    id: ResourceId


class PortfolioSnapshotDto(ApiModel):
    id: ResourceId
    import_id: ResourceId
    brokerage: Brokerage
    observed_at: datetime
    currency: str
    free_cash: Money
    monthly_contribution: Money
    total_value: Money
    positions: list[PortfolioPositionDto]
    created_at: datetime


class RecommendationJobCreateRequest(ApiModel):
    idempotency_key: IdempotencyKey
    snapshot_ids: Annotated[list[UUID], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def unique_snapshots(self) -> RecommendationJobCreateRequest:
        if len(set(self.snapshot_ids)) != len(self.snapshot_ids):
            raise ValueError("snapshotIds must be unique")
        return self


class BucketAdjustmentDto(ApiModel):
    risk_bucket: RiskBucket
    add_amount: Money
    reduce_amount: Money
    current_percent: Percent
    projected_percent: Percent
    target_percent: Percent
    within_tolerance: bool


class RecommendationJobDto(ApiModel):
    id: ResourceId
    snapshot_ids: list[ResourceId]
    status: RecommendationStatus
    attempt_count: int
    market_data_as_of: datetime | None
    cash_first_adjustments: list[BucketAdjustmentDto]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class RecommendationActionInput(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "anyOf": [
                {"required": ["ticker"]},
                {"required": ["isin"]},
            ]
        }
    )

    instrument_name: ShortText
    ticker: Annotated[
        str | None,
        StringConstraints(min_length=1, max_length=32, pattern=r"^[A-Z0-9][A-Z0-9._-]{0,31}$"),
    ] = None
    isin: Annotated[str | None, StringConstraints(pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")] = None
    risk_bucket: RiskBucket
    action: RecommendationActionType
    current_percent: Percent
    target_percent: Percent
    amount: Money
    priority: Annotated[int, Field(ge=1, le=100)]
    rationale: LongText
    risks: LongText

    @model_validator(mode="after")
    def require_canonical_identifier(self) -> RecommendationActionInput:
        if not self.ticker and not self.isin:
            raise ValueError("ticker/SECID or ISIN is required")
        return self

    @field_validator("ticker")
    @classmethod
    def validate_secid(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_secid(value):
            raise ValueError("invalid SECID format")
        return value

    @field_validator("isin")
    @classmethod
    def validate_isin(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_isin(value):
            raise ValueError("invalid ISIN")
        return value


class RecommendationActionDto(RecommendationActionInput):
    pass


class RecommendationSourceInput(ApiModel):
    title: ShortText
    url: HttpsUrl
    publisher: ShortText
    published_at: datetime | None = None
    fetched_at: datetime


class RecommendationSourceDto(RecommendationSourceInput):
    trust_tier: Annotated[str, StringConstraints(pattern=r"^(official|issuer|disclosure|news)$")]


class RecommendationAggregateInput(ApiModel):
    risk_bucket: RiskBucket
    current_percent: Percent
    proposed_percent: Percent


class RecommendationReportDto(ApiModel):
    id: ResourceId
    job_id: ResourceId
    summary: LongText
    assumptions: dict[str, Any]
    generated_at: datetime
    valid_until: datetime
    is_stale: bool
    disclaimer: str
    actions: list[RecommendationActionDto]
    sources: list[RecommendationSourceDto]


class RecommendationCallbackRequest(ApiModel):
    status: RecommendationStatus
    retryable: bool = False
    error_code: Annotated[str | None, StringConstraints(min_length=1, max_length=100)] = None
    market_data_as_of: datetime | None = None
    summary: LongText | None = None
    assumptions: dict[str, Any] = Field(default_factory=dict)
    aggregates: list[RecommendationAggregateInput] = Field(default_factory=list, max_length=3)
    actions: list[RecommendationActionInput] = Field(default_factory=list, max_length=200)
    sources: list[RecommendationSourceInput] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_terminal_payload(self) -> RecommendationCallbackRequest:
        if self.status == RecommendationStatus.READY:
            if (
                self.market_data_as_of is None
                or self.summary is None
                or not self.sources
                or len(self.aggregates) != 3
            ):
                raise ValueError(
                    "ready callback requires market data, summary, three aggregates, and sources"
                )
            buckets = {item.risk_bucket for item in self.aggregates}
            if buckets != set(RiskBucket):
                raise ValueError("ready callback requires one aggregate per risk bucket")
        if self.status == RecommendationStatus.FAILED and not self.error_code:
            raise ValueError("failed callback requires errorCode")
        return self


class InvestmentPolicyEnvelope(ApiModel):
    data: InvestmentPolicyDto


class PortfolioImportEnvelope(ApiModel):
    data: PortfolioImportDto


class PortfolioSnapshotEnvelope(ApiModel):
    data: PortfolioSnapshotDto


class RecommendationJobEnvelope(ApiModel):
    data: RecommendationJobDto


class RecommendationReportEnvelope(ApiModel):
    data: RecommendationReportDto
