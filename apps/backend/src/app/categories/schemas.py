from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class CategoryType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class CategoryScope(StrEnum):
    PERSONAL = "personal"
    HOUSEHOLD = "household"


class RecordStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


ResourceId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_:-]+$")]
CategoryName = Annotated[str, Field(min_length=1, max_length=120)]
IconKey = Annotated[str, Field(min_length=1, max_length=80)]
Color = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class CategoryDto(ApiModel):
    id: ResourceId
    name: str = Field(max_length=120)
    type: CategoryType
    scope: CategoryScope
    owner_user_id: ResourceId | None = Field(default=None, alias="ownerUserId")
    household_id: ResourceId | None = Field(default=None, alias="householdId")
    icon_key: str | None = Field(default=None, alias="iconKey", max_length=80)
    color: Color | None = None
    status: RecordStatus
    created_by_user_id: ResourceId = Field(alias="createdByUserId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    archived_at: datetime | None = Field(default=None, alias="archivedAt")
    deleted_at: datetime | None = Field(default=None, alias="deletedAt")
    version: int = Field(ge=1)


class CategoryCreateRequest(ApiModel):
    name: CategoryName
    type: CategoryType
    scope: CategoryScope
    household_id: ResourceId | None = Field(default=None, alias="householdId")
    icon_key: IconKey | None = Field(default=None, alias="iconKey")
    color: Color | None = None


class CategoryUpdateRequest(ApiModel):
    name: CategoryName | None = None
    icon_key: IconKey | None = Field(default=None, alias="iconKey")
    color: Color | None = None
    status: RecordStatus | None = None
    version: int | None = Field(default=None, ge=1)


class CategoryAutocompleteDto(ApiModel):
    id: ResourceId
    name: str
    type: CategoryType
    scope: CategoryScope
    household_id: ResourceId | None = Field(default=None, alias="householdId")
    icon_key: str | None = Field(default=None, alias="iconKey")
    color: Color | None = None


class PageInfo(ApiModel):
    limit: int = Field(ge=1, le=100)
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    has_more: bool = Field(alias="hasMore")


class CategoryEnvelope(ApiModel):
    data: CategoryDto


class CategoryPageEnvelope(ApiModel):
    items: list[CategoryDto]
    page: PageInfo


class CategoryAutocompleteListEnvelope(ApiModel):
    items: list[CategoryAutocompleteDto]


class ErrorDetail(ApiModel):
    field: str | None = None
    reason: str | None = None
    allowed_values: list[str] | None = Field(default=None, alias="allowedValues")


class ErrorDto(ApiModel):
    code: str
    message: str
    request_id: str = Field(alias="requestId")
    details: list[ErrorDetail] | None = None


class ErrorEnvelope(ApiModel):
    error: ErrorDto


class CategoryListSort(StrEnum):
    NAME_ASC = "name"
    NAME_DESC = "-name"
    UPDATED_ASC = "updatedAt"
    UPDATED_DESC = "-updatedAt"
    CREATED_ASC = "createdAt"
    CREATED_DESC = "-createdAt"


CategoryAction = Literal["archive", "delete", "restore", "update"]
