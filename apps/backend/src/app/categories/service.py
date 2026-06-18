from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.authz import (
    Actor,
    Category,
    CategoryKind,
    ResourceStatus,
    canMutateCategory,
    canReadCategory,
)
from app.sync.domain_changes import SyncChangeRecorder

from .repository import CategoryRecord, CategoryRepository, repository
from .schemas import (
    CategoryAutocompleteDto,
    CategoryCreateRequest,
    CategoryDto,
    CategoryListSort,
    CategoryScope,
    CategoryType,
    CategoryUpdateRequest,
    ErrorDto,
    ErrorEnvelope,
    PageInfo,
    RecordStatus,
)

NOT_FOUND_CODE = "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE"
VALIDATION_CODE = "VALIDATION_FAILED"
ACTION_NOT_ALLOWED_CODE = "ACTION_NOT_ALLOWED"
ARCHIVED_NOT_MUTABLE_CODE = "ARCHIVED_RECORD_NOT_MUTABLE"
CONFLICTING_UPDATE_CODE = "CONFLICTING_UPDATE"


def _request_id(actor: Actor) -> str:
    return actor.request_id or "request-unavailable"


def _error(code: str, message: str, actor: Actor, http_status: int) -> HTTPException:
    body = ErrorEnvelope(
        error=ErrorDto(
            code=code,
            message=message,
            requestId=_request_id(actor),
        )
    )
    return HTTPException(
        status_code=http_status,
        detail=body.model_dump(mode="json", by_alias=True)["error"],
    )


def _not_found(actor: Actor) -> HTTPException:
    return _error(
        NOT_FOUND_CODE,
        "Resource not found or not accessible.",
        actor,
        status.HTTP_404_NOT_FOUND,
    )


def _validation(actor: Actor, message: str = "Validation failed.") -> HTTPException:
    return _error(VALIDATION_CODE, message, actor, status.HTTP_400_BAD_REQUEST)


def _conflict(actor: Actor, code: str, message: str) -> HTTPException:
    return _error(code, message, actor, status.HTTP_409_CONFLICT)


def _is_active_household_member(actor: Actor, household_id: str | None) -> bool:
    if not actor.user_id or not household_id:
        return False

    return any(
        membership.user_id == actor.user_id
        and membership.household_id == household_id
        and membership.status.value == "active"
        for membership in actor.memberships
    )


def _to_authz_category(record: CategoryRecord) -> Category:
    status = {
        RecordStatus.ACTIVE: ResourceStatus.ACTIVE,
        RecordStatus.ARCHIVED: ResourceStatus.ARCHIVED,
        RecordStatus.DELETED: ResourceStatus.DELETED,
    }[record.status]
    kind = CategoryKind(record.type.value)
    return Category(
        id=record.id,
        scope=record.scope.value,
        owner_user_id=record.owner_user_id,
        household_id=record.household_id,
        kind=kind,
        status=status,
    )


def _can_read(actor: Actor, record: CategoryRecord) -> bool:
    return canReadCategory(actor, _to_authz_category(record)).allowed


def _can_mutate(actor: Actor, record: CategoryRecord) -> bool:
    return canMutateCategory(actor, _to_authz_category(record)).allowed


def _dto(record: CategoryRecord) -> CategoryDto:
    return CategoryDto(
        id=record.id,
        name=record.name,
        type=record.type,
        scope=record.scope,
        ownerUserId=record.owner_user_id,
        householdId=record.household_id,
        iconKey=record.icon_key,
        color=record.color,
        status=record.status,
        createdByUserId=record.created_by_user_id,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        archivedAt=record.archived_at,
        deletedAt=record.deleted_at,
        version=record.version,
    )


def _autocomplete_dto(record: CategoryRecord) -> CategoryAutocompleteDto:
    return CategoryAutocompleteDto(
        id=record.id,
        name=record.name,
        type=record.type,
        scope=record.scope,
        householdId=record.household_id,
        iconKey=record.icon_key,
        color=record.color,
    )


class CategoryService:
    def __init__(
        self,
        store: CategoryRepository = repository,
        sync_change_recorder: SyncChangeRecorder | None = None,
    ) -> None:
        self._store = store
        self._sync_change_recorder = sync_change_recorder

    def list(
        self,
        *,
        actor: Actor,
        limit: int,
        cursor: str | None,
        scope: CategoryScope | None,
        type: CategoryType | None,
        household_id: str | None,
        status_filter: RecordStatus | None,
        q: str | None,
        sort: CategoryListSort | None,
    ) -> tuple[list[CategoryDto], PageInfo]:
        records = self._visible_records(
            actor=actor,
            scope=scope,
            type=type,
            household_id=household_id,
            status_filter=status_filter,
            q=q,
        )
        records = self._sort(records, sort)
        start = self._decode_cursor(cursor, actor)
        page_records = records[start : start + limit]
        next_index = start + len(page_records)
        has_more = next_index < len(records)
        next_cursor = str(next_index) if has_more else None
        return [_dto(record) for record in page_records], PageInfo(
            limit=limit,
            nextCursor=next_cursor,
            hasMore=has_more,
        )

    def autocomplete(
        self,
        *,
        actor: Actor,
        limit: int,
        scope: CategoryScope | None,
        type: CategoryType | None,
        household_id: str | None,
        q: str | None,
    ) -> list[CategoryAutocompleteDto]:
        records = self._visible_records(
            actor=actor,
            scope=scope,
            type=type,
            household_id=household_id,
            status_filter=RecordStatus.ACTIVE,
            q=q,
        )
        records = self._sort(records, CategoryListSort.NAME_ASC)
        return [_autocomplete_dto(record) for record in records[:limit]]

    def create(
        self,
        *,
        actor: Actor,
        request: CategoryCreateRequest,
        category_id: str | None = None,
    ) -> CategoryDto:
        if not actor.user_id:
            raise _not_found(actor)

        if request.scope == CategoryScope.PERSONAL:
            if request.household_id is not None:
                raise _validation(actor)
            owner_user_id = actor.user_id
            household_id = None
        else:
            if not _is_active_household_member(actor, request.household_id):
                raise _not_found(actor)
            owner_user_id = None
            household_id = request.household_id

        record = self._store.create(
            category_id=category_id,
            name=request.name,
            type=request.type,
            scope=request.scope,
            owner_user_id=owner_user_id,
            household_id=household_id,
            icon_key=request.icon_key,
            color=request.color,
            created_by_user_id=actor.user_id,
        )
        self._record_sync_change(actor=actor, operation="create", record=record)
        return _dto(record)

    def get(self, *, actor: Actor, category_id: str) -> CategoryDto:
        return _dto(self._require_visible(actor, category_id))

    def update(
        self,
        *,
        actor: Actor,
        category_id: str,
        request: CategoryUpdateRequest,
    ) -> CategoryDto:
        record = self._require_visible(actor, category_id)
        if not _can_mutate(actor, record):
            raise _conflict(
                actor,
                ARCHIVED_NOT_MUTABLE_CODE,
                "Archived or deleted records are not mutable.",
            )
        if request.version is not None and request.version != record.version:
            raise _conflict(actor, CONFLICTING_UPDATE_CODE, "Conflicting update.")

        updated = record
        if request.name is not None:
            updated = replace(updated, name=request.name)
        if request.icon_key is not None:
            updated = replace(updated, icon_key=request.icon_key)
        if request.color is not None:
            updated = replace(updated, color=request.color)
        if request.status is not None:
            updated = self._record_with_status(updated, request.status)

        saved = self._store.save(updated)
        self._record_sync_change(actor=actor, operation="update", record=saved)
        return _dto(saved)

    def delete(self, *, actor: Actor, category_id: str) -> None:
        record = self._require_visible(actor, category_id)
        if not _can_mutate(actor, record):
            raise _conflict(
                actor,
                ARCHIVED_NOT_MUTABLE_CODE,
                "Archived or deleted records are not mutable.",
            )
        deleted = self._store.save(self._record_with_status(record, RecordStatus.DELETED))
        self._record_sync_change(actor=actor, operation="delete", record=deleted)

    def archive(self, *, actor: Actor, category_id: str) -> CategoryDto:
        record = self._require_visible(actor, category_id)
        if not _can_mutate(actor, record):
            raise _conflict(
                actor,
                ARCHIVED_NOT_MUTABLE_CODE,
                "Archived or deleted records are not mutable.",
            )
        archived = self._store.save(self._record_with_status(record, RecordStatus.ARCHIVED))
        self._record_sync_change(actor=actor, operation="archive", record=archived)
        return _dto(archived)

    def restore(self, *, actor: Actor, category_id: str) -> CategoryDto:
        record = self._require_visible(actor, category_id)
        if record.status == RecordStatus.DELETED:
            raise _not_found(actor)
        restored = self._store.save(self._record_with_status(record, RecordStatus.ACTIVE))
        self._record_sync_change(actor=actor, operation="restore", record=restored)
        return _dto(restored)

    def _require_visible(self, actor: Actor, category_id: str) -> CategoryRecord:
        record = self._store.get(category_id)
        if record is None or not _can_read(actor, record):
            raise _not_found(actor)
        return record

    def _visible_records(
        self,
        *,
        actor: Actor,
        scope: CategoryScope | None,
        type: CategoryType | None,
        household_id: str | None,
        status_filter: RecordStatus | None,
        q: str | None,
    ) -> list[CategoryRecord]:
        q_lower = q.casefold() if q else None
        records: list[CategoryRecord] = []
        for record in self._store.list():
            if not _can_read(actor, record):
                continue
            if record.status == RecordStatus.DELETED:
                continue
            if scope is not None and record.scope != scope:
                continue
            if type is not None and record.type != type:
                continue
            if household_id is not None and record.household_id != household_id:
                continue
            if status_filter is not None and record.status != status_filter:
                continue
            if q_lower is not None and q_lower not in record.name.casefold():
                continue
            records.append(record)
        return records

    def _sort(
        self,
        records: list[CategoryRecord],
        sort: CategoryListSort | None,
    ) -> list[CategoryRecord]:
        selected = sort or CategoryListSort.NAME_ASC
        reverse = selected.value.startswith("-")
        key_name = selected.value.removeprefix("-")
        if key_name == "updatedAt":
            return sorted(
                records,
                key=lambda record: (record.updated_at, record.id),
                reverse=reverse,
            )
        if key_name == "createdAt":
            return sorted(
                records,
                key=lambda record: (record.created_at, record.id),
                reverse=reverse,
            )
        return sorted(
            records,
            key=lambda record: (record.name.casefold(), record.id),
            reverse=reverse,
        )

    def _decode_cursor(self, cursor: str | None, actor: Actor) -> int:
        if cursor is None:
            return 0
        try:
            value = int(cursor)
        except ValueError as exc:
            raise _validation(actor, "Invalid cursor.") from exc
        if value < 0:
            raise _validation(actor, "Invalid cursor.")
        return value

    def _record_with_status(
        self,
        record: CategoryRecord,
        new_status: RecordStatus,
    ) -> CategoryRecord:
        now = datetime.now(UTC)
        if new_status == RecordStatus.ACTIVE:
            return replace(record, status=new_status, archived_at=None, deleted_at=None)
        if new_status == RecordStatus.ARCHIVED:
            return replace(record, status=new_status, archived_at=record.archived_at or now)
        if new_status == RecordStatus.DELETED:
            return replace(record, status=new_status, deleted_at=record.deleted_at or now)
        return record

    def _record_sync_change(
        self,
        *,
        actor: Actor,
        operation: str,
        record: CategoryRecord,
    ) -> None:
        if self._sync_change_recorder is None:
            return
        self._sync_change_recorder.record_category_change(
            actor_user_id=actor.user_id,
            operation=operation,
            record=record,
        )


service = CategoryService()
