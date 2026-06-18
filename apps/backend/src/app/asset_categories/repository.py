from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from itertools import count
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AssetCategory as AssetCategoryModel

from .schemas import AssetCategoryScope, AssetCategoryType, RecordStatus


@dataclass(frozen=True, slots=True)
class AssetCategoryRecord:
    id: str
    name: str
    scope_type: AssetCategoryScope
    owner_user_id: str | None
    household_id: str | None
    currency: str
    asset_type: AssetCategoryType
    icon_key: str | None
    manual_amount: Decimal
    is_investment: bool
    status: RecordStatus
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    deleted_at: datetime | None
    version: int


class AssetCategoryRepository(Protocol):
    def list(self) -> list[AssetCategoryRecord]:
        """Return all asset category records; service layer applies authz filtering."""

    def get(self, asset_category_id: str) -> AssetCategoryRecord | None:
        """Return one asset category record, or ``None``."""

    def create(
        self,
        *,
        asset_category_id: str | None = None,
        name: str,
        scope_type: AssetCategoryScope,
        owner_user_id: str | None,
        household_id: str | None,
        currency: str,
        asset_type: AssetCategoryType,
        manual_amount: Decimal,
        is_investment: bool,
        created_by_user_id: str,
        icon_key: str | None = None,
    ) -> AssetCategoryRecord:
        """Persist a new asset category."""

    def save(self, record: AssetCategoryRecord) -> AssetCategoryRecord:
        """Persist mutable fields from an existing asset category."""


class InMemoryAssetCategoryRepository:
    def __init__(self) -> None:
        self._records: dict[str, AssetCategoryRecord] = {}
        self._counter = count(1)
        self._lock = RLock()

    def reset(self) -> None:
        with self._lock:
            self._records = {}
            self._counter = count(1)

    def list(self) -> list[AssetCategoryRecord]:
        with self._lock:
            return [deepcopy(record) for record in self._records.values()]

    def get(self, asset_category_id: str) -> AssetCategoryRecord | None:
        with self._lock:
            record = self._records.get(asset_category_id)
            return deepcopy(record) if record is not None else None

    def create(
        self,
        *,
        asset_category_id: str | None = None,
        name: str,
        scope_type: AssetCategoryScope,
        owner_user_id: str | None,
        household_id: str | None,
        currency: str,
        asset_type: AssetCategoryType,
        manual_amount: Decimal,
        is_investment: bool,
        created_by_user_id: str,
        icon_key: str | None = None,
    ) -> AssetCategoryRecord:
        now = datetime.now(UTC)
        with self._lock:
            record_id = asset_category_id or f"assetcat_{next(self._counter)}"
            while record_id in self._records:
                record_id = f"assetcat_{next(self._counter)}"

            record = AssetCategoryRecord(
                id=record_id,
                name=name,
                scope_type=scope_type,
                owner_user_id=owner_user_id,
                household_id=household_id,
                currency=currency,
                asset_type=asset_type,
                icon_key=icon_key,
                manual_amount=manual_amount,
                is_investment=is_investment,
                status=RecordStatus.ACTIVE,
                created_by_user_id=created_by_user_id,
                created_at=now,
                updated_at=now,
                archived_at=None,
                deleted_at=None,
                version=1,
            )
            self._records[record.id] = record
            return deepcopy(record)

    def save(self, record: AssetCategoryRecord) -> AssetCategoryRecord:
        with self._lock:
            stored = replace(record, updated_at=datetime.now(UTC), version=record.version + 1)
            self._records[stored.id] = stored
            return deepcopy(stored)


class SqlAlchemyAssetCategoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self) -> list[AssetCategoryRecord]:
        rows = self._session.execute(select(AssetCategoryModel)).scalars().all()
        return [_record_from_model(row) for row in rows]

    def get(self, asset_category_id: str) -> AssetCategoryRecord | None:
        parsed_id = _optional_uuid(asset_category_id)
        if parsed_id is None:
            return None
        model = self._session.get(AssetCategoryModel, parsed_id)
        return _record_from_model(model) if model is not None else None

    def create(
        self,
        *,
        asset_category_id: str | None = None,
        name: str,
        scope_type: AssetCategoryScope,
        owner_user_id: str | None,
        household_id: str | None,
        currency: str,
        asset_type: AssetCategoryType,
        manual_amount: Decimal,
        is_investment: bool,
        created_by_user_id: str,
        icon_key: str | None = None,
    ) -> AssetCategoryRecord:
        now = datetime.now(UTC)
        model = AssetCategoryModel(
            id=(
                _required_uuid(asset_category_id, "asset_category_id")
                if asset_category_id
                else uuid4()
            ),
            name=name,
            scope_type=scope_type.value,
            owner_user_id=_nullable_uuid(owner_user_id, "owner_user_id"),
            household_id=_nullable_uuid(household_id, "household_id"),
            currency=currency,
            asset_type=asset_type.value,
            icon_key=icon_key,
            manual_amount=manual_amount,
            is_investment=is_investment,
            record_status=RecordStatus.ACTIVE.value,
            created_by_user_id=_required_uuid(created_by_user_id, "created_by_user_id"),
            created_at=now,
            updated_at=now,
            version=1,
            archived_at=None,
            deleted_at=None,
        )
        self._session.add(model)
        self._session.flush()
        return _record_from_model(model)

    def save(self, record: AssetCategoryRecord) -> AssetCategoryRecord:
        model = self._session.get(AssetCategoryModel, _required_uuid(record.id, "id"))
        if model is None:
            raise KeyError(f"asset category record does not exist: {record.id}")

        model.name = record.name
        model.asset_type = record.asset_type.value
        model.icon_key = record.icon_key
        model.manual_amount = record.manual_amount
        model.is_investment = record.is_investment
        model.record_status = record.status.value
        model.archived_at = record.archived_at
        model.deleted_at = record.deleted_at
        model.updated_at = datetime.now(UTC)
        model.version = int(record.version) + 1
        self._session.flush()
        return _record_from_model(model)


def _record_from_model(model: AssetCategoryModel) -> AssetCategoryRecord:
    return AssetCategoryRecord(
        id=str(model.id),
        name=model.name,
        scope_type=AssetCategoryScope(model.scope_type),
        owner_user_id=str(model.owner_user_id) if model.owner_user_id is not None else None,
        household_id=str(model.household_id) if model.household_id is not None else None,
        currency=model.currency,
        asset_type=AssetCategoryType(model.asset_type),
        icon_key=model.icon_key,
        manual_amount=Decimal(model.manual_amount),
        is_investment=bool(model.is_investment),
        status=RecordStatus(model.record_status),
        created_by_user_id=str(model.created_by_user_id),
        created_at=model.created_at,
        updated_at=model.updated_at,
        archived_at=model.archived_at,
        deleted_at=model.deleted_at,
        version=int(model.version or 1),
    )


def _optional_uuid(value: str | UUID | None) -> UUID | None:
    if value is None or isinstance(value, UUID):
        return value
    try:
        return UUID(value)
    except ValueError:
        return None


def _nullable_uuid(value: str | UUID | None, field_name: str) -> UUID | None:
    if value is None:
        return None
    parsed = _optional_uuid(value)
    if parsed is None:
        raise ValueError(f"{field_name} must be a canonical UUID for DB-backed repositories")
    return parsed


def _required_uuid(value: str | UUID, field_name: str) -> UUID:
    parsed = _optional_uuid(value)
    if parsed is None:
        raise ValueError(f"{field_name} must be a canonical UUID for DB-backed repositories")
    return parsed


repository = InMemoryAssetCategoryRepository()
