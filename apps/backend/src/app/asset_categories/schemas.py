from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

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
MoneyDecimal = Annotated[Decimal, Field(ge=0, max_digits=20, decimal_places=4)]
IconKey = Annotated[str, StringConstraints(min_length=1, max_length=80)]


class AssetCategoryScope(StrEnum):
    PERSONAL = "personal"
    HOUSEHOLD = "household"


class AssetCategoryType(StrEnum):
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


class AssetCategoryDto(ApiModel):
    id: ResourceId
    name: Annotated[str, StringConstraints(max_length=120)]
    scope_type: AssetCategoryScope
    owner_user_id: ResourceId | None = None
    household_id: ResourceId | None = None
    currency: CurrencyCode
    asset_type: AssetCategoryType
    icon_key: str | None = Field(default=None, alias="iconKey", max_length=80)
    manual_amount: MoneyDecimal
    is_investment: bool
    record_status: RecordStatus
    created_by_user_id: ResourceId
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    deleted_at: datetime | None = None
    version: Annotated[int, Field(ge=1)]


class AssetCategoryCreateRequest(ApiModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    scope_type: AssetCategoryScope
    household_id: ResourceId | None = None
    currency: CurrencyCode
    asset_type: AssetCategoryType = AssetCategoryType.OTHER
    icon_key: IconKey | None = Field(default=None, alias="iconKey")
    manual_amount: MoneyDecimal = Decimal("0.0000")
    is_investment: bool = False


class AssetCategoryUpdateRequest(ApiModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None = None
    manual_amount: MoneyDecimal | None = None
    asset_type: AssetCategoryType | None = None
    icon_key: IconKey | None = Field(default=None, alias="iconKey")
    is_investment: bool | None = None
    record_status: RecordStatus | None = None
    version: Annotated[int, Field(ge=1)] | None = None


class PageInfo(ApiModel):
    limit: Annotated[int, Field(ge=1, le=100)]
    next_cursor: str | None = None
    has_more: bool


class AssetCategoryEnvelope(ApiModel):
    data: AssetCategoryDto


class AssetCategoryPageEnvelope(ApiModel):
    items: list[AssetCategoryDto]
    page: PageInfo
