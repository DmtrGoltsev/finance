from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CaptureCategoryMapping as CaptureCategoryMappingModel


@dataclass(frozen=True, slots=True)
class CaptureCategoryMappingRecord:
    id: str
    owner_user_id: str
    household_id: str | None
    external_label_hash: str
    category_id: str
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class CaptureCategoryMappingUpsertValues:
    owner_user_id: str
    household_id: str | None
    external_label_hash: str
    category_id: str


class CaptureCategoryMappingRepository(Protocol):
    def upsert(
        self,
        values: CaptureCategoryMappingUpsertValues,
    ) -> CaptureCategoryMappingRecord:
        """Create or update a hash-only category aggregate mapping."""

    def find_category_id(
        self,
        *,
        owner_user_id: str,
        household_id: str | None,
        external_label_hash: str,
    ) -> str | None:
        """Return mapped category ID for one actor/context/hash."""


class InMemoryCaptureCategoryMappingRepository:
    def __init__(self) -> None:
        self._records: dict[str, CaptureCategoryMappingRecord] = {}
        self._lock = RLock()

    def reset(self, records: Iterable[CaptureCategoryMappingRecord] = ()) -> None:
        with self._lock:
            self._records = {record.id: deepcopy(record) for record in records}

    def upsert(
        self,
        values: CaptureCategoryMappingUpsertValues,
    ) -> CaptureCategoryMappingRecord:
        with self._lock:
            existing = self._find_record(
                owner_user_id=values.owner_user_id,
                household_id=values.household_id,
                external_label_hash=values.external_label_hash,
            )
            now = datetime.now(UTC)
            if existing is not None:
                stored = replace(
                    existing,
                    category_id=values.category_id,
                    updated_at=now,
                    version=existing.version + 1,
                )
                self._records[stored.id] = stored
                return deepcopy(stored)

            record = CaptureCategoryMappingRecord(
                id=f"capcatmap_{uuid4().hex}",
                owner_user_id=values.owner_user_id,
                household_id=values.household_id,
                external_label_hash=values.external_label_hash,
                category_id=values.category_id,
                created_at=now,
                updated_at=now,
                version=1,
            )
            self._records[record.id] = record
            return deepcopy(record)

    def find_category_id(
        self,
        *,
        owner_user_id: str,
        household_id: str | None,
        external_label_hash: str,
    ) -> str | None:
        with self._lock:
            record = self._find_record(
                owner_user_id=owner_user_id,
                household_id=household_id,
                external_label_hash=external_label_hash,
            )
            return record.category_id if record is not None else None

    def _find_record(
        self,
        *,
        owner_user_id: str,
        household_id: str | None,
        external_label_hash: str,
    ) -> CaptureCategoryMappingRecord | None:
        for record in self._records.values():
            if (
                record.owner_user_id == owner_user_id
                and record.household_id == household_id
                and record.external_label_hash == external_label_hash
            ):
                return record
        return None


class SqlAlchemyCaptureCategoryMappingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self,
        values: CaptureCategoryMappingUpsertValues,
    ) -> CaptureCategoryMappingRecord:
        existing = self._get_by_scope_hash(
            owner_user_id=values.owner_user_id,
            household_id=values.household_id,
            external_label_hash=values.external_label_hash,
        )
        now = datetime.now(UTC)
        if existing is not None:
            existing.category_id = _required_uuid(values.category_id, "category_id")
            existing.updated_at = now
            existing.version = int(existing.version or 1) + 1
            self._session.flush()
            return _record_from_model(existing)

        model = CaptureCategoryMappingModel(
            id=uuid4(),
            owner_user_id=_required_uuid(values.owner_user_id, "owner_user_id"),
            household_id=_nullable_uuid(values.household_id, "household_id"),
            external_label_hash=values.external_label_hash,
            category_id=_required_uuid(values.category_id, "category_id"),
            created_at=now,
            updated_at=now,
            version=1,
        )
        self._session.add(model)
        self._session.flush()
        return _record_from_model(model)

    def find_category_id(
        self,
        *,
        owner_user_id: str,
        household_id: str | None,
        external_label_hash: str,
    ) -> str | None:
        model = self._get_by_scope_hash(
            owner_user_id=owner_user_id,
            household_id=household_id,
            external_label_hash=external_label_hash,
        )
        return str(model.category_id) if model is not None else None

    def _get_by_scope_hash(
        self,
        *,
        owner_user_id: str,
        household_id: str | None,
        external_label_hash: str,
    ) -> CaptureCategoryMappingModel | None:
        owner_id = _optional_uuid(owner_user_id)
        if owner_id is None:
            return None
        household_uuid = _nullable_uuid(household_id, "household_id")
        statement = select(CaptureCategoryMappingModel).where(
            CaptureCategoryMappingModel.owner_user_id == owner_id,
            CaptureCategoryMappingModel.external_label_hash == external_label_hash,
        )
        if household_uuid is None:
            statement = statement.where(CaptureCategoryMappingModel.household_id.is_(None))
        else:
            statement = statement.where(CaptureCategoryMappingModel.household_id == household_uuid)
        return self._session.execute(statement).scalar_one_or_none()


def _record_from_model(model: CaptureCategoryMappingModel) -> CaptureCategoryMappingRecord:
    return CaptureCategoryMappingRecord(
        id=str(model.id),
        owner_user_id=str(model.owner_user_id),
        household_id=str(model.household_id) if model.household_id is not None else None,
        external_label_hash=model.external_label_hash,
        category_id=str(model.category_id),
        created_at=model.created_at,
        updated_at=model.updated_at,
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


repository = InMemoryCaptureCategoryMappingRepository()


def reset_capture_category_mappings_for_tests(
    records: Iterable[CaptureCategoryMappingRecord] = (),
) -> None:
    repository.reset(records)
