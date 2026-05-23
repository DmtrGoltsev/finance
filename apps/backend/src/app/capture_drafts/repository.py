from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import CaptureDraft as CaptureDraftModel


@dataclass(frozen=True, slots=True)
class CaptureDraftRecord:
    id: str
    owner_user_id: str
    status: str
    idempotency_key: str
    capture_source: str
    captured_at: datetime
    occurred_at: datetime | None
    amount: Decimal
    currency: str
    description: str
    merchant_name: str | None
    account_id: str | None
    category_id: str | None
    transaction_id: str | None
    confidence: Decimal | None
    source_app_package: str | None
    source_app_label: str | None
    evidence_hash: str | None
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class CaptureDraftCreateValues:
    owner_user_id: str
    idempotency_key: str
    capture_source: str
    captured_at: datetime
    occurred_at: datetime | None
    amount: Decimal
    currency: str
    description: str
    merchant_name: str | None
    account_id: str | None
    category_id: str | None
    confidence: Decimal | None
    source_app_package: str | None
    source_app_label: str | None
    evidence_hash: str | None


class CaptureDraftRepository(Protocol):
    def create_or_get_existing(self, values: CaptureDraftCreateValues) -> CaptureDraftRecord:
        """Persist a pending draft or return the owner/idempotency-key duplicate."""

    def list_by_owner(
        self,
        *,
        owner_user_id: str,
        status: str | None,
        limit: int,
    ) -> list[CaptureDraftRecord]:
        """Return drafts for one owner only."""

    def get(
        self,
        draft_id: str,
        *,
        lock_for_update: bool = False,
    ) -> CaptureDraftRecord | None:
        """Return a draft by public ID."""

    def save(self, record: CaptureDraftRecord) -> CaptureDraftRecord:
        """Persist mutable fields and increment version."""


class InMemoryCaptureDraftRepository:
    def __init__(self) -> None:
        self._records: dict[str, CaptureDraftRecord] = {}
        self._lock = RLock()

    def reset(self, records: Iterable[CaptureDraftRecord] = ()) -> None:
        with self._lock:
            self._records = {record.id: deepcopy(record) for record in records}

    def create_or_get_existing(self, values: CaptureDraftCreateValues) -> CaptureDraftRecord:
        with self._lock:
            for record in self._records.values():
                if (
                    record.owner_user_id == values.owner_user_id
                    and record.idempotency_key == values.idempotency_key
                ):
                    return deepcopy(record)

            now = datetime.now(UTC)
            record = CaptureDraftRecord(
                id=f"draft_{uuid4().hex}",
                owner_user_id=values.owner_user_id,
                status="pending",
                idempotency_key=values.idempotency_key,
                capture_source=values.capture_source,
                captured_at=values.captured_at,
                occurred_at=values.occurred_at,
                amount=values.amount,
                currency=values.currency,
                description=values.description,
                merchant_name=values.merchant_name,
                account_id=values.account_id,
                category_id=values.category_id,
                transaction_id=None,
                confidence=values.confidence,
                source_app_package=values.source_app_package,
                source_app_label=values.source_app_label,
                evidence_hash=values.evidence_hash,
                created_at=now,
                updated_at=now,
                version=1,
            )
            self._records[record.id] = record
            return deepcopy(record)

    def list_by_owner(
        self,
        *,
        owner_user_id: str,
        status: str | None,
        limit: int,
    ) -> list[CaptureDraftRecord]:
        with self._lock:
            records = [
                deepcopy(record)
                for record in self._records.values()
                if record.owner_user_id == owner_user_id
                and (status is None or record.status == status)
            ]
        return sorted(records, key=lambda record: (record.created_at, record.id), reverse=True)[
            :limit
        ]

    def get(
        self,
        draft_id: str,
        *,
        lock_for_update: bool = False,
    ) -> CaptureDraftRecord | None:
        with self._lock:
            record = self._records.get(draft_id)
            return deepcopy(record) if record is not None else None

    def save(self, record: CaptureDraftRecord) -> CaptureDraftRecord:
        with self._lock:
            stored = replace(record, updated_at=datetime.now(UTC), version=record.version + 1)
            self._records[stored.id] = stored
            return deepcopy(stored)


class SqlAlchemyCaptureDraftRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_or_get_existing(self, values: CaptureDraftCreateValues) -> CaptureDraftRecord:
        existing = self._get_by_owner_idempotency_key(
            owner_user_id=values.owner_user_id,
            idempotency_key=values.idempotency_key,
        )
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        model = CaptureDraftModel(
            id=uuid4(),
            owner_user_id=_required_uuid(values.owner_user_id, "owner_user_id"),
            status="pending",
            idempotency_key=values.idempotency_key,
            capture_source=values.capture_source,
            captured_at=values.captured_at,
            occurred_at=values.occurred_at,
            amount=values.amount,
            currency=values.currency,
            description=values.description,
            merchant_name=values.merchant_name,
            account_id=_nullable_uuid(values.account_id, "account_id"),
            category_id=_nullable_uuid(values.category_id, "category_id"),
            transaction_id=None,
            confidence=values.confidence,
            source_app_package=values.source_app_package,
            source_app_label=values.source_app_label,
            evidence_hash=values.evidence_hash,
            created_at=now,
            updated_at=now,
            version=1,
        )
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            existing = self._get_by_owner_idempotency_key(
                owner_user_id=values.owner_user_id,
                idempotency_key=values.idempotency_key,
            )
            if existing is not None:
                return existing
            raise
        return _record_from_model(model)

    def list_by_owner(
        self,
        *,
        owner_user_id: str,
        status: str | None,
        limit: int,
    ) -> list[CaptureDraftRecord]:
        owner_id = _optional_uuid(owner_user_id)
        if owner_id is None:
            return []

        statement: Select[tuple[CaptureDraftModel]] = (
            select(CaptureDraftModel)
            .where(CaptureDraftModel.owner_user_id == owner_id)
            .order_by(CaptureDraftModel.created_at.desc(), CaptureDraftModel.id.desc())
            .limit(limit)
        )
        if status is not None:
            statement = statement.where(CaptureDraftModel.status == status)
        return [_record_from_model(row) for row in self._session.execute(statement).scalars()]

    def get(
        self,
        draft_id: str,
        *,
        lock_for_update: bool = False,
    ) -> CaptureDraftRecord | None:
        parsed_id = _optional_uuid(draft_id)
        if parsed_id is None:
            return None
        if lock_for_update:
            model = self._session.execute(
                select(CaptureDraftModel)
                .where(CaptureDraftModel.id == parsed_id)
                .with_for_update()
            ).scalar_one_or_none()
        else:
            model = self._session.get(CaptureDraftModel, parsed_id)
        return _record_from_model(model) if model is not None else None

    def save(self, record: CaptureDraftRecord) -> CaptureDraftRecord:
        model = self._session.get(CaptureDraftModel, _required_uuid(record.id, "id"))
        if model is None:
            raise KeyError(f"capture draft record does not exist: {record.id}")

        model.status = record.status
        model.occurred_at = record.occurred_at
        model.amount = record.amount
        model.currency = record.currency
        model.description = record.description
        model.merchant_name = record.merchant_name
        model.account_id = _nullable_uuid(record.account_id, "account_id")
        model.category_id = _nullable_uuid(record.category_id, "category_id")
        model.transaction_id = _nullable_uuid(record.transaction_id, "transaction_id")
        model.confidence = record.confidence
        model.source_app_package = record.source_app_package
        model.source_app_label = record.source_app_label
        model.evidence_hash = record.evidence_hash
        model.updated_at = datetime.now(UTC)
        model.version = int(record.version) + 1

        self._session.flush()
        return _record_from_model(model)

    def _get_by_owner_idempotency_key(
        self,
        *,
        owner_user_id: str,
        idempotency_key: str,
    ) -> CaptureDraftRecord | None:
        owner_id = _optional_uuid(owner_user_id)
        if owner_id is None:
            return None
        model = self._session.execute(
            select(CaptureDraftModel).where(
                CaptureDraftModel.owner_user_id == owner_id,
                CaptureDraftModel.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        return _record_from_model(model) if model is not None else None


def _record_from_model(model: CaptureDraftModel) -> CaptureDraftRecord:
    return CaptureDraftRecord(
        id=str(model.id),
        owner_user_id=str(model.owner_user_id),
        status=model.status,
        idempotency_key=model.idempotency_key,
        capture_source=model.capture_source,
        captured_at=model.captured_at,
        occurred_at=model.occurred_at,
        amount=Decimal(model.amount),
        currency=model.currency,
        description=model.description,
        merchant_name=model.merchant_name,
        account_id=str(model.account_id) if model.account_id is not None else None,
        category_id=str(model.category_id) if model.category_id is not None else None,
        transaction_id=str(model.transaction_id) if model.transaction_id is not None else None,
        confidence=Decimal(model.confidence) if model.confidence is not None else None,
        source_app_package=model.source_app_package,
        source_app_label=model.source_app_label,
        evidence_hash=model.evidence_hash,
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


repository = InMemoryCaptureDraftRepository()


def reset_capture_drafts_for_tests(records: Iterable[CaptureDraftRecord] = ()) -> None:
    repository.reset(records)
