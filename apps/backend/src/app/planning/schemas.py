from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


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
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
PlanMonth = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-[0-9]{2}(-01)?$")]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=300)]
OptionalShortText = Annotated[str, StringConstraints(max_length=500)]
MoneyDecimal = Annotated[Decimal, Field(max_digits=20, decimal_places=4)]
PositiveMoneyDecimal = Annotated[Decimal, Field(gt=0, max_digits=20, decimal_places=4)]
AllocationDecimal = Annotated[Decimal, Field(ge=0, max_digits=20, decimal_places=4)]


class PlanningScope(StrEnum):
    PERSONAL = "personal"
    HOUSEHOLD = "household"


class IncomeConfirmationState(StrEnum):
    PLANNED = "planned"
    CONFIRMED = "confirmed"


class AllocationTargetType(StrEnum):
    EXPENSE_CATEGORY = "expense_category"
    ACCOUNT = "account"
    ASSET = "asset"
    INVESTMENT_ASSET_CATEGORY = "investment_asset_category"


class AllocationMode(StrEnum):
    AMOUNT = "amount"
    PERCENT = "percent"


class AllocationRecurrenceType(StrEnum):
    REGULAR = "regular"
    ONE_OFF = "one_off"


class AllocationProgressStatus(StrEnum):
    ON_TRACK = "on_track"
    NEEDS_ATTENTION = "needs_attention"
    NO_ACTUALS = "no_actuals"
    TARGET_ATTENTION = "target_attention"
    NOT_APPLICABLE = "not_applicable"


class PlanningSummaryDto(ApiModel):
    total_planned_income: MoneyDecimal
    total_confirmed_income: MoneyDecimal
    total_allocated_amount: MoneyDecimal
    unallocated_amount: MoneyDecimal
    previous_month_surplus: MoneyDecimal
    underallocated: bool
    overallocated: bool


class PlanningIncomeSourceDto(ApiModel):
    id: ResourceId
    plan_id: ResourceId
    amount: PositiveMoneyDecimal
    source: str
    description: str | None = None
    day_of_month: Annotated[int, Field(ge=1, le=31)]
    effective_date: date
    confirmation_state: IncomeConfirmationState
    confirmed_at: datetime | None = None
    confirmed_by_user_id: ResourceId | None = None
    created_by_user_id: ResourceId
    created_at: datetime
    updated_at: datetime
    version: Annotated[int, Field(ge=1)]


class PlanningAllocationDto(ApiModel):
    id: ResourceId
    plan_id: ResourceId
    target_type: AllocationTargetType
    target_id: ResourceId | None = None
    target_snapshot: dict[str, Any]
    requires_attention: bool
    attention_reason: str | None = None
    comment: str | None = None
    allocation_mode: AllocationMode
    allocation_value: AllocationDecimal
    calculated_amount: MoneyDecimal
    recurrence_type: AllocationRecurrenceType
    is_savings_goal: bool
    goal_target_amount: MoneyDecimal | None = None
    goal_due_month: PlanMonth | None = None
    goal_monthly_amount: MoneyDecimal | None = None
    actual_amount: MoneyDecimal
    variance_amount: MoneyDecimal
    status: AllocationProgressStatus
    created_by_user_id: ResourceId
    created_at: datetime
    updated_at: datetime
    version: Annotated[int, Field(ge=1)]


class PlanningPlanDto(ApiModel):
    id: ResourceId
    scope: PlanningScope
    owner_user_id: ResourceId | None = None
    household_id: ResourceId | None = None
    month: PlanMonth
    currency: CurrencyCode
    income_sources: list[PlanningIncomeSourceDto]
    allocations: list[PlanningAllocationDto]
    summary: PlanningSummaryDto
    created_by_user_id: ResourceId
    created_at: datetime
    updated_at: datetime
    version: Annotated[int, Field(ge=1)]


class PlanningPlanSummaryDto(ApiModel):
    id: ResourceId
    scope: PlanningScope
    owner_user_id: ResourceId | None = None
    household_id: ResourceId | None = None
    month: PlanMonth
    currency: CurrencyCode
    summary: PlanningSummaryDto
    created_at: datetime
    updated_at: datetime
    version: Annotated[int, Field(ge=1)]


class PlanningPlanCreateRequest(ApiModel):
    id: UUID | None = None
    scope: PlanningScope
    month: PlanMonth
    currency: CurrencyCode
    household_id: ResourceId | None = None


class PlanningIncomeSourceCreateRequest(ApiModel):
    id: UUID | None = None
    amount: PositiveMoneyDecimal
    source: ShortText
    description: OptionalShortText | None = None
    day_of_month: Annotated[int, Field(ge=1, le=31)]


class PlanningIncomeSourceUpdateRequest(ApiModel):
    amount: PositiveMoneyDecimal | None = None
    source: ShortText | None = None
    description: OptionalShortText | None = None
    day_of_month: Annotated[int, Field(ge=1, le=31)] | None = None
    version: Annotated[int, Field(ge=1)] | None = None


class PlanningAllocationCreateRequest(ApiModel):
    id: UUID | None = None
    target_type: AllocationTargetType
    target_id: ResourceId
    comment: OptionalShortText | None = None
    allocation_mode: AllocationMode
    allocation_value: AllocationDecimal
    recurrence_type: AllocationRecurrenceType = AllocationRecurrenceType.REGULAR
    is_savings_goal: bool = False
    goal_target_amount: PositiveMoneyDecimal | None = None
    goal_due_month: PlanMonth | None = None


class PlanningAllocationUpdateRequest(ApiModel):
    target_type: AllocationTargetType | None = None
    target_id: ResourceId | None = None
    comment: OptionalShortText | None = None
    allocation_mode: AllocationMode | None = None
    allocation_value: AllocationDecimal | None = None
    recurrence_type: AllocationRecurrenceType | None = None
    is_savings_goal: bool | None = None
    goal_target_amount: PositiveMoneyDecimal | None = None
    goal_due_month: PlanMonth | None = None
    version: Annotated[int, Field(ge=1)] | None = None


class PlanningPlanCopyRequest(ApiModel):
    target_month: PlanMonth


class PlanningPlanEnvelope(ApiModel):
    data: PlanningPlanDto


class PlanningPlanSummaryListEnvelope(ApiModel):
    items: list[PlanningPlanSummaryDto]


class PlanningIncomeSourceEnvelope(ApiModel):
    data: PlanningIncomeSourceDto


class PlanningAllocationEnvelope(ApiModel):
    data: PlanningAllocationDto
