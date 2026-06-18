from __future__ import annotations

from typing import Annotated

from pydantic import AliasChoices, Field, StringConstraints

from app.accounts.schemas import AccountDto

from .schemas import (
    ApiModel,
    AssetCategoryDto,
    AssetCategoryScope,
    AssetCategoryType,
    CurrencyCode,
    IconKey,
    ResourceId,
)

ColorValue = Annotated[str, StringConstraints(min_length=1, max_length=32)]


class InvestmentMigrationCreateRequest(ApiModel):
    asset_category_id: ResourceId
    name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    icon_key: IconKey | None = Field(
        default=None,
        validation_alias=AliasChoices("icon", "iconKey"),
        serialization_alias="icon",
    )
    color: ColorValue | None = Field(
        default=None,
        description=(
            "Accepted for client command parity. Asset categories do not persist color yet."
        ),
    )
    asset_type: AssetCategoryType
    currency: CurrencyCode
    scope_type: AssetCategoryScope | None = Field(
        default=None,
        validation_alias=AliasChoices("scope", "scopeType"),
        serialization_alias="scope",
    )
    household_id: ResourceId | None = None
    account_ids: Annotated[list[ResourceId], Field(min_length=1, max_length=100)]
    account_versions: dict[str, Annotated[int, Field(ge=1)]]


class InvestmentMigrationDto(ApiModel):
    asset_category: AssetCategoryDto
    accounts: list[AccountDto]


class InvestmentMigrationEnvelope(ApiModel):
    data: InvestmentMigrationDto
