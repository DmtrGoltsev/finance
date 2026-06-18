from __future__ import annotations

from datetime import datetime
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


DeviceId = Annotated[str, StringConstraints(min_length=1, max_length=160)]
ClientMutationId = Annotated[str, StringConstraints(min_length=1, max_length=160)]
EntityType = Annotated[str, StringConstraints(min_length=1, max_length=80)]
SyncOperation = Annotated[str, StringConstraints(min_length=1, max_length=40)]


class MutationStatus(StrEnum):
    APPLIED = "applied"
    REJECTED = "rejected"


class SyncMutationRequest(ApiModel):
    client_mutation_id: ClientMutationId
    entity_type: EntityType
    entity_id: UUID
    operation: SyncOperation
    base_version: Annotated[int, Field(ge=1)] | None = None
    payload: dict[str, Any] | None = None


class SyncPushRequest(ApiModel):
    device_id: DeviceId
    client_schema_version: Annotated[int, Field(ge=1)]
    mutations: Annotated[list[SyncMutationRequest], Field(min_length=1, max_length=100)]


class SyncMutationResult(ApiModel):
    client_mutation_id: ClientMutationId
    entity_type: EntityType
    entity_id: UUID
    operation: SyncOperation
    status: MutationStatus
    server_version: Annotated[int, Field(ge=1)] | None = None
    change_seq: Annotated[int, Field(ge=1)] | None = None
    error_code: str | None = None
    message: str | None = None
    data: dict[str, Any] | None = None


class SyncPushResponse(ApiModel):
    device_id: DeviceId
    server_time: datetime
    results: list[SyncMutationResult]


class SyncPullRequest(ApiModel):
    device_id: DeviceId
    client_schema_version: Annotated[int, Field(ge=1)]
    cursor: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=500)] = 100
    entity_types: list[EntityType] | None = None


class SyncChangeDto(ApiModel):
    seq: Annotated[int, Field(ge=1)]
    entity_type: EntityType
    entity_id: UUID
    change_type: SyncOperation
    entity_version: Annotated[int, Field(ge=1)] | None = None
    entity_updated_at: datetime | None = None
    changed_by_user_id: UUID | None = None
    client_mutation_id: str | None = None
    payload: dict[str, Any] | None = None
    tombstone_payload: dict[str, Any] | None = None
    created_at: datetime


class SyncPullResponse(ApiModel):
    changes: list[SyncChangeDto]
    next_cursor: Annotated[int, Field(ge=0)]
    has_more: bool
    server_time: datetime

