from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
ResourceId = Annotated[str, StringConstraints(min_length=1, max_length=128)]
DecimalString = Annotated[Decimal, Field(max_digits=24, decimal_places=6)]


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


class OwnershipType(StrEnum):
    PERSONAL = "personal"
    SHARED = "shared"


class AccountType(StrEnum):
    CASH = "cash"
    BANK = "bank"
    CARD = "card"
    DEPOSIT = "deposit"
    BROKERAGE = "brokerage"
    METAL = "metal"
    OTHER = "other"


class RecordStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class AccountDto(ApiModel):
    id: ResourceId
    name: Annotated[str, StringConstraints(max_length=120)]
    account_type: AccountType
    ownership_type: OwnershipType
    owner_user_id: ResourceId | None = None
    household_id: ResourceId | None = None
    currency: CurrencyCode
    initial_balance: DecimalString
    current_balance: DecimalString
    status: RecordStatus
    created_by_user_id: ResourceId
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    deleted_at: datetime | None = None
    version: Annotated[int, Field(ge=1)]


class AccountCreateRequest(ApiModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    account_type: AccountType
    ownership_type: OwnershipType
    household_id: ResourceId | None = None
    currency: CurrencyCode
    initial_balance: DecimalString


class AccountUpdateRequest(ApiModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None = None
    current_balance: DecimalString | None = None
    currency: CurrencyCode | None = None
    account_type: AccountType | None = None
    status: RecordStatus | None = None
    version: Annotated[int, Field(ge=1)] | None = None


class AccountAutocompleteDto(ApiModel):
    id: ResourceId
    name: str
    account_type: AccountType
    ownership_type: OwnershipType
    household_id: ResourceId | None = None
    currency: CurrencyCode


class PageInfo(ApiModel):
    limit: Annotated[int, Field(ge=1, le=100)]
    next_cursor: str | None = None
    has_more: bool


class AccountEnvelope(ApiModel):
    data: AccountDto


class AccountPageEnvelope(ApiModel):
    items: list[AccountDto]
    page: PageInfo


class AccountAutocompleteListEnvelope(ApiModel):
    items: list[AccountAutocompleteDto]
