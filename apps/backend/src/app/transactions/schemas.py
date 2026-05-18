from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ResourceId = Annotated[str, StringConstraints(min_length=1, max_length=128)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
DecimalString = Annotated[Decimal, Field(gt=0, max_digits=20, decimal_places=4)]


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


class TransactionType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    BROKERAGE = "brokerage"
    ASSET_BUY = "asset_buy"
    ASSET_SELL = "asset_sell"
    INTEREST = "interest"
    DIVIDEND = "dividend"
    ADJUSTMENT = "adjustment"


class SourceType(StrEnum):
    MANUAL = "manual"


class RecordStatus(StrEnum):
    ACTIVE = "active"
    DELETED = "deleted"


class OwnershipType(StrEnum):
    PERSONAL = "personal"
    SHARED = "shared"


class SortOrder(StrEnum):
    OCCURRED_DESC = "-occurredAt"
    OCCURRED_ASC = "occurredAt"
    AMOUNT_DESC = "-amount"
    AMOUNT_ASC = "amount"
    CREATED_DESC = "-createdAt"
    CREATED_ASC = "createdAt"


class TransactionDto(ApiModel):
    id: ResourceId
    transaction_type: TransactionType
    account_id: ResourceId
    counterparty_account_id: ResourceId | None = None
    category_id: ResourceId | None = None
    amount: DecimalString
    currency: CurrencyCode
    occurred_at: datetime
    description: Annotated[str, StringConstraints(max_length=500)] | None = None
    source_type: SourceType
    transfer_scope: str | None = None
    transfer_status: str | None = None
    created_by_user_id: ResourceId
    last_edited_by_user_id: ResourceId | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    version: Annotated[int, Field(ge=1)]


class TransactionCreateRequest(ApiModel):
    transaction_type: TransactionType
    account_id: ResourceId
    counterparty_account_id: ResourceId | None = None
    category_id: ResourceId | None = None
    amount: DecimalString
    currency: CurrencyCode
    occurred_at: datetime
    description: Annotated[str, StringConstraints(max_length=500)] | None = None
    source_type: SourceType


class TransactionUpdateRequest(ApiModel):
    transaction_type: TransactionType | None = None
    account_id: ResourceId | None = None
    counterparty_account_id: ResourceId | None = None
    category_id: ResourceId | None = None
    amount: DecimalString | None = None
    currency: CurrencyCode | None = None
    occurred_at: datetime | None = None
    description: Annotated[str, StringConstraints(max_length=500)] | None = None
    source_type: SourceType | None = None
    version: Annotated[int, Field(ge=1)] | None = None


class TransactionAutocompleteDto(ApiModel):
    id: ResourceId
    transaction_type: TransactionType
    account_id: ResourceId
    category_id: ResourceId | None = None
    occurred_at: datetime
    source_type: SourceType


class PageInfo(ApiModel):
    limit: Annotated[int, Field(ge=1, le=100)]
    next_cursor: str | None = None
    has_more: bool


class TransactionEnvelope(ApiModel):
    data: TransactionDto


class TransactionPageEnvelope(ApiModel):
    items: list[TransactionDto]
    page: PageInfo


class TransactionAutocompleteListEnvelope(ApiModel):
    items: list[TransactionAutocompleteDto]
