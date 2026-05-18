from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from itertools import count
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Category as CategoryModel

from .schemas import CategoryScope, CategoryType, RecordStatus


@dataclass(frozen=True)
class CategoryRecord:
    id: str
    name: str
    type: CategoryType
    scope: CategoryScope
    owner_user_id: str | None
    household_id: str | None
    icon_key: str | None
    color: str | None
    status: RecordStatus
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    deleted_at: datetime | None
    version: int


class CategoryRepository(Protocol):
    def list(self) -> list[CategoryRecord]:
        """Return all category records; service layer applies authz filtering."""

    def get(self, category_id: str) -> CategoryRecord | None:
        """Return one category record by public ID, or ``None``."""

    def create(
        self,
        *,
        name: str,
        type: CategoryType,
        scope: CategoryScope,
        owner_user_id: str | None,
        household_id: str | None,
        icon_key: str | None,
        color: str | None,
        created_by_user_id: str,
    ) -> CategoryRecord:
        """Persist a new category record."""

    def save(self, record: CategoryRecord) -> CategoryRecord:
        """Persist mutable fields from an existing category record."""


class InMemoryCategoryRepository:
    def __init__(self) -> None:
        self._records: dict[str, CategoryRecord] = {}
        self._counter = count(1)
        self._lock = RLock()

    def reset(self, records: Iterable[CategoryRecord] = ()) -> None:
        with self._lock:
            self._records = {record.id: deepcopy(record) for record in records}
            self._counter = count(len(self._records) + 1)

    def list(self) -> list[CategoryRecord]:
        with self._lock:
            return [deepcopy(record) for record in self._records.values()]

    def get(self, category_id: str) -> CategoryRecord | None:
        with self._lock:
            record = self._records.get(category_id)
            return deepcopy(record) if record is not None else None

    def create(
        self,
        *,
        name: str,
        type: CategoryType,
        scope: CategoryScope,
        owner_user_id: str | None,
        household_id: str | None,
        icon_key: str | None,
        color: str | None,
        created_by_user_id: str,
    ) -> CategoryRecord:
        now = datetime.now(UTC)
        with self._lock:
            category_id = f"cat_{next(self._counter)}"
            while category_id in self._records:
                category_id = f"cat_{next(self._counter)}"

            record = CategoryRecord(
                id=category_id,
                name=name,
                type=type,
                scope=scope,
                owner_user_id=owner_user_id,
                household_id=household_id,
                icon_key=icon_key,
                color=color,
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

    def save(self, record: CategoryRecord) -> CategoryRecord:
        with self._lock:
            stored = replace(record, updated_at=datetime.now(UTC), version=record.version + 1)
            self._records[stored.id] = stored
            return deepcopy(stored)


class SqlAlchemyCategoryRepository:
    """SQLAlchemy-backed category repository for the DB foundation slice.

    Runtime endpoints still use ``InMemoryCategoryRepository`` until an
    integration worker wires request-scoped sessions into the FastAPI routes.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self) -> list[CategoryRecord]:
        rows = self._session.execute(select(CategoryModel)).scalars().all()
        return [_record_from_model(row) for row in rows]

    def get(self, category_id: str) -> CategoryRecord | None:
        parsed_id = _optional_uuid(category_id)
        if parsed_id is None:
            return None

        model = self._session.get(CategoryModel, parsed_id)
        return _record_from_model(model) if model is not None else None

    def create(
        self,
        *,
        name: str,
        type: CategoryType,
        scope: CategoryScope,
        owner_user_id: str | None,
        household_id: str | None,
        icon_key: str | None,
        color: str | None,
        created_by_user_id: str,
    ) -> CategoryRecord:
        now = datetime.now(UTC)
        model = CategoryModel(
            id=uuid4(),
            name=name,
            category_type=type.value,
            category_scope=scope.value,
            owner_user_id=_nullable_uuid(owner_user_id, "owner_user_id"),
            household_id=_nullable_uuid(household_id, "household_id"),
            icon_key=icon_key,
            color=color,
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

    def save(self, record: CategoryRecord) -> CategoryRecord:
        parsed_id = _required_uuid(record.id, "id")
        model = self._session.get(CategoryModel, parsed_id)
        if model is None:
            raise KeyError(f"category record does not exist: {record.id}")

        model.name = record.name
        model.category_type = record.type.value
        model.icon_key = record.icon_key
        model.color = record.color
        model.record_status = record.status.value
        model.archived_at = record.archived_at
        model.deleted_at = record.deleted_at
        model.updated_at = datetime.now(UTC)
        model.version = int(record.version) + 1

        self._session.flush()
        return _record_from_model(model)


def _record_from_model(model: CategoryModel) -> CategoryRecord:
    return CategoryRecord(
        id=str(model.id),
        name=model.name,
        type=CategoryType(model.category_type),
        scope=CategoryScope(model.category_scope),
        owner_user_id=str(model.owner_user_id) if model.owner_user_id is not None else None,
        household_id=str(model.household_id) if model.household_id is not None else None,
        icon_key=model.icon_key,
        color=model.color,
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


repository = InMemoryCategoryRepository()
