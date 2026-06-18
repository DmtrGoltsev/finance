from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status

from app.authz import Actor
from app.sync.domain_changes import SyncChangeRecorder

from .repository import AssetCategoryRecord, AssetCategoryRepository, repository
from .schemas import (
    AssetCategoryCreateRequest,
    AssetCategoryDto,
    AssetCategoryPageEnvelope,
    AssetCategoryScope,
    AssetCategoryType,
    AssetCategoryUpdateRequest,
    PageInfo,
    RecordStatus,
)

NOT_FOUND_CODE = "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE"
VALIDATION_CODE = "VALIDATION_FAILED"
ARCHIVED_NOT_MUTABLE_CODE = "ARCHIVED_RECORD_NOT_MUTABLE"
CONFLICTING_UPDATE_CODE = "CONFLICTING_UPDATE"


def _request_id(actor: Actor) -> str:
    return actor.request_id or "request-unavailable"


def _error(code: str, message: str, actor: Actor, http_status: int) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={
            "code": code,
            "message": message,
            "requestId": _request_id(actor),
        },
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


def can_read_asset_category(actor: Actor, record: AssetCategoryRecord) -> bool:
    if record.scope_type == AssetCategoryScope.PERSONAL:
        return bool(actor.user_id and record.owner_user_id == actor.user_id)
    return _is_active_household_member(actor, record.household_id)


def asset_category_in_account_scope(
    record: AssetCategoryRecord,
    *,
    ownership_type: str,
    owner_user_id: str | None,
    household_id: str | None,
    currency: str,
) -> bool:
    if record.status != RecordStatus.ACTIVE or record.currency != currency:
        return False
    if ownership_type == "personal":
        return (
            record.scope_type == AssetCategoryScope.PERSONAL
            and record.owner_user_id == owner_user_id
        )
    return (
        record.scope_type == AssetCategoryScope.HOUSEHOLD
        and record.household_id == household_id
    )


def _dto(record: AssetCategoryRecord) -> AssetCategoryDto:
    return AssetCategoryDto(
        id=record.id,
        name=record.name,
        scope_type=record.scope_type,
        owner_user_id=record.owner_user_id,
        household_id=record.household_id,
        currency=record.currency,
        asset_type=record.asset_type,
        iconKey=record.icon_key,
        manual_amount=Decimal(record.manual_amount),
        is_investment=record.is_investment,
        record_status=record.status,
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        archived_at=record.archived_at,
        deleted_at=record.deleted_at,
        version=record.version,
    )


class AssetCategoryService:
    def __init__(
        self,
        store: AssetCategoryRepository = repository,
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
        scope_type: AssetCategoryScope | None,
        household_id: str | None,
        status_filter: RecordStatus | None,
        is_investment: bool | None,
        q: str | None,
    ) -> AssetCategoryPageEnvelope:
        q_lower = q.casefold() if q else None
        records: list[AssetCategoryRecord] = []
        for record in self._store.list():
            if record.status == RecordStatus.DELETED:
                continue
            if not can_read_asset_category(actor, record):
                continue
            if scope_type is not None and record.scope_type != scope_type:
                continue
            if household_id is not None and record.household_id != household_id:
                continue
            if status_filter is not None and record.status != status_filter:
                continue
            if is_investment is not None and record.is_investment != is_investment:
                continue
            if q_lower is not None and q_lower not in record.name.casefold():
                continue
            records.append(record)

        records.sort(key=lambda item: (item.name.casefold(), item.id))
        start = _decode_cursor(cursor, actor)
        page_records = records[start : start + limit]
        next_index = start + len(page_records)
        return AssetCategoryPageEnvelope(
            items=[_dto(record) for record in page_records],
            page=PageInfo(
                limit=limit,
                next_cursor=str(next_index) if next_index < len(records) else None,
                has_more=next_index < len(records),
            ),
        )

    def create(
        self,
        *,
        actor: Actor,
        request: AssetCategoryCreateRequest,
        asset_category_id: str | None = None,
    ) -> AssetCategoryDto:
        if not actor.user_id:
            raise _not_found(actor)
        scope_type = AssetCategoryScope(request.scope_type)
        asset_type = AssetCategoryType(request.asset_type)
        if scope_type == AssetCategoryScope.PERSONAL:
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
            asset_category_id=asset_category_id,
            name=request.name,
            scope_type=scope_type,
            owner_user_id=owner_user_id,
            household_id=household_id,
            currency=request.currency,
            asset_type=asset_type,
            icon_key=request.icon_key,
            manual_amount=Decimal(request.manual_amount),
            is_investment=request.is_investment,
            created_by_user_id=actor.user_id,
        )
        self._record_sync_change(actor=actor, operation="create", record=record)
        return _dto(record)

    def get(self, *, actor: Actor, asset_category_id: str) -> AssetCategoryDto:
        return _dto(self._require_visible(actor, asset_category_id))

    def update(
        self,
        *,
        actor: Actor,
        asset_category_id: str,
        request: AssetCategoryUpdateRequest,
    ) -> AssetCategoryDto:
        record = self._require_visible(actor, asset_category_id)
        if (
            record.status != RecordStatus.ACTIVE
            and request.record_status != RecordStatus.ACTIVE
        ):
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
        if request.manual_amount is not None:
            updated = replace(updated, manual_amount=Decimal(request.manual_amount))
        if request.asset_type is not None:
            updated = replace(updated, asset_type=AssetCategoryType(request.asset_type))
        if "icon_key" in request.model_fields_set:
            updated = replace(updated, icon_key=request.icon_key)
        if request.is_investment is not None:
            updated = replace(updated, is_investment=request.is_investment)
        if request.record_status is not None:
            updated = _record_with_status(updated, RecordStatus(request.record_status))
        saved = self._store.save(updated)
        self._record_sync_change(actor=actor, operation="update", record=saved)
        return _dto(saved)

    def archive(self, *, actor: Actor, asset_category_id: str) -> AssetCategoryDto:
        record = self._require_visible(actor, asset_category_id)
        if record.status != RecordStatus.ACTIVE:
            raise _conflict(
                actor,
                ARCHIVED_NOT_MUTABLE_CODE,
                "Archived or deleted records are not mutable.",
            )
        archived = self._store.save(_record_with_status(record, RecordStatus.ARCHIVED))
        self._record_sync_change(actor=actor, operation="archive", record=archived)
        return _dto(archived)

    def restore(self, *, actor: Actor, asset_category_id: str) -> AssetCategoryDto:
        record = self._require_visible(actor, asset_category_id)
        if record.status == RecordStatus.DELETED:
            raise _not_found(actor)
        restored = self._store.save(_record_with_status(record, RecordStatus.ACTIVE))
        self._record_sync_change(actor=actor, operation="restore", record=restored)
        return _dto(restored)

    def delete(self, *, actor: Actor, asset_category_id: str) -> None:
        record = self._require_visible(actor, asset_category_id)
        if record.status != RecordStatus.ACTIVE:
            raise _conflict(
                actor,
                ARCHIVED_NOT_MUTABLE_CODE,
                "Archived or deleted records are not mutable.",
            )
        deleted = self._store.save(_record_with_status(record, RecordStatus.DELETED))
        self._record_sync_change(actor=actor, operation="delete", record=deleted)

    def _require_visible(self, actor: Actor, asset_category_id: str) -> AssetCategoryRecord:
        record = self._store.get(asset_category_id)
        if record is None or not can_read_asset_category(actor, record):
            raise _not_found(actor)
        return record

    def _record_sync_change(
        self,
        *,
        actor: Actor,
        operation: str,
        record: AssetCategoryRecord,
    ) -> None:
        if self._sync_change_recorder is None:
            return
        self._sync_change_recorder.record_asset_category_change(
            actor_user_id=actor.user_id,
            operation=operation,
            record=record,
        )


def _decode_cursor(cursor: str | None, actor: Actor) -> int:
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
    record: AssetCategoryRecord,
    new_status: RecordStatus,
) -> AssetCategoryRecord:
    new_status = RecordStatus(new_status)
    now = datetime.now(UTC)
    if new_status == RecordStatus.ACTIVE:
        return replace(record, status=new_status, archived_at=None, deleted_at=None)
    if new_status == RecordStatus.ARCHIVED:
        return replace(record, status=new_status, archived_at=record.archived_at or now)
    if new_status == RecordStatus.DELETED:
        return replace(record, status=new_status, deleted_at=record.deleted_at or now)
    return record


service = AssetCategoryService()
