from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.transactions.schemas import ApiModel, CurrencyCode, DecimalString, ResourceId


class CaptureDraftStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISCARDED = "discarded"


class CaptureSource(StrEnum):
    SCREENSHOT = "screenshot"


ShortText = Annotated[str, StringConstraints(min_length=1, max_length=500)]
OptionalShortText = Annotated[str, StringConstraints(max_length=500)]
SourceAppText = Annotated[str, StringConstraints(max_length=255)]
EvidenceHash = Annotated[str, StringConstraints(max_length=128)]
Confidence = Annotated[Decimal, Field(ge=0, le=1, max_digits=5, decimal_places=4)]
ExternalLabel = Annotated[str, StringConstraints(min_length=1, max_length=120)]


class CaptureDraftDto(ApiModel):
    id: ResourceId
    status: CaptureDraftStatus
    idempotency_key: ResourceId
    capture_source: CaptureSource
    captured_at: datetime
    occurred_at: datetime | None = None
    occurred_date: date | None = None
    amount: DecimalString
    currency: CurrencyCode
    description: OptionalShortText
    merchant_name: SourceAppText | None = None
    account_id: ResourceId | None = None
    category_id: ResourceId | None = None
    transaction_id: ResourceId | None = None
    confidence: Confidence | None = None
    source_app_package: SourceAppText | None = None
    source_app_label: SourceAppText | None = None
    evidence_hash: EvidenceHash | None = None
    created_at: datetime
    updated_at: datetime


class CaptureDraftCreateRequest(ApiModel):
    idempotency_key: ResourceId
    capture_source: CaptureSource
    captured_at: datetime
    amount: DecimalString
    currency: CurrencyCode
    description: ShortText
    occurred_at: datetime | None = None
    occurred_date: date | None = None
    merchant_name: SourceAppText | None = None
    account_id: ResourceId | None = None
    category_id: ResourceId | None = None
    confidence: Confidence | None = None
    source_app_package: SourceAppText | None = None
    source_app_label: SourceAppText | None = None
    evidence_hash: EvidenceHash | None = None


class CaptureDraftUpdateRequest(ApiModel):
    occurred_at: datetime | None = None
    occurred_date: date | None = None
    amount: DecimalString | None = None
    currency: CurrencyCode | None = None
    description: ShortText | None = None
    merchant_name: SourceAppText | None = None
    account_id: ResourceId | None = None
    category_id: ResourceId | None = None
    confidence: Confidence | None = None
    source_app_package: SourceAppText | None = None
    source_app_label: SourceAppText | None = None
    evidence_hash: EvidenceHash | None = None


class PageInfo(ApiModel):
    limit: Annotated[int, Field(ge=1, le=100)]


class CaptureDraftEnvelope(ApiModel):
    data: CaptureDraftDto


class CaptureDraftPageEnvelope(ApiModel):
    items: list[CaptureDraftDto]
    page: PageInfo


class CategoryAggregateDto(ApiModel):
    external_label: ExternalLabel


class ScreenshotOcrCandidateDto(ApiModel):
    candidate_type: Literal["categoryAggregate"] = "categoryAggregate"
    category_aggregate: CategoryAggregateDto
    amount: DecimalString
    currency: CurrencyCode
    operation_count: Annotated[int, Field(ge=1, le=10_000)]
    description: ShortText
    confidence: Confidence
    idempotency_key: ResourceId
    evidence_hash: EvidenceHash
    suggested_category_id: ResourceId | None = None


class ScreenshotOcrWarningCode(StrEnum):
    NO_CATEGORY_AGGREGATES_FOUND = "NO_CATEGORY_AGGREGATES_FOUND"


class ScreenshotOcrWarningDto(ApiModel):
    code: ScreenshotOcrWarningCode
    message: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class ScreenshotOcrResponseDto(ApiModel):
    capture_source: CaptureSource
    parse_version: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    recognized_at: datetime
    items: list[ScreenshotOcrCandidateDto]
    warnings: list[ScreenshotOcrWarningDto] = Field(default_factory=list)


class ScreenshotOcrEnvelope(ApiModel):
    data: ScreenshotOcrResponseDto


class CaptureCategoryMappingPutRequest(ApiModel):
    external_label: ExternalLabel
    category_id: ResourceId
    household_id: ResourceId | None = None


class CaptureCategoryMappingDto(ApiModel):
    category_id: ResourceId
    household_id: ResourceId | None = None


class CaptureCategoryMappingEnvelope(ApiModel):
    data: CaptureCategoryMappingDto
