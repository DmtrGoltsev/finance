from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.db.models import Transaction as TransactionModel


@dataclass(frozen=True, slots=True)
class TransactionRecord:
    id: str
    transaction_type: str
    account_id: str
    counterparty_account_id: str | None
    category_id: str | None
    amount: Decimal
    currency: str
    occurred_at: datetime
    description: str | None
    source_type: str
    transfer_scope: str | None
    transfer_status: str | None
    record_status: str
    created_by_user_id: str
    last_edited_by_user_id: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    version: int
    transaction_date: date | None = None


@dataclass(frozen=True, slots=True)
class TransactionFilters:
    account_id: str | None = None
    category_id: str | None = None
    transaction_type: str | None = None
    status: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    q: str | None = None
    sort: str | None = None


class TransactionRepository(Protocol):
    def has_for_account(self, account_id: str) -> bool:
        """Return whether any transaction references the account."""

    def list_by_visible_accounts(
        self,
        visible_account_ids: Iterable[str],
        *,
        filters: TransactionFilters,
    ) -> list[TransactionRecord]:
        """Return rows after the service has resolved visible account ids."""

    def get(self, transaction_id: str) -> TransactionRecord | None:
        """Return one transaction by public ID, including deleted rows."""

    def create(
        self,
        *,
        transaction_type: str,
        account_id: str,
        counterparty_account_id: str | None,
        category_id: str | None,
        amount: Decimal,
        currency: str,
        occurred_at: datetime,
        transaction_date: date,
        description: str | None,
        source_type: str,
        transfer_scope: str | None,
        transfer_status: str | None,
        created_by_user_id: str,
    ) -> TransactionRecord:
        """Persist a new transaction."""

    def save(self, record: TransactionRecord) -> TransactionRecord:
        """Persist mutable fields and increment optimistic version."""


class InMemoryTransactionRepository:
    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, TransactionRecord] = {}

    def reset(self, records: Iterable[TransactionRecord] = ()) -> None:
        with self._lock:
            self._records = {record.id: deepcopy(record) for record in records}

    def has_for_account(self, account_id: str) -> bool:
        with self._lock:
            return any(
                row.account_id == account_id or row.counterparty_account_id == account_id
                for row in self._records.values()
            )

    def list_by_visible_accounts(
        self,
        visible_account_ids: Iterable[str],
        *,
        filters: TransactionFilters,
    ) -> list[TransactionRecord]:
        visible_ids = set(visible_account_ids)
        with self._lock:
            rows = [
                deepcopy(row)
                for row in self._records.values()
                if row.account_id in visible_ids or row.counterparty_account_id in visible_ids
            ]
        return _filter_and_sort(rows, filters)

    def get(self, transaction_id: str) -> TransactionRecord | None:
        with self._lock:
            record = self._records.get(transaction_id)
            return deepcopy(record) if record is not None else None

    def create(
        self,
        *,
        transaction_type: str,
        account_id: str,
        counterparty_account_id: str | None,
        category_id: str | None,
        amount: Decimal,
        currency: str,
        occurred_at: datetime,
        transaction_date: date,
        description: str | None,
        source_type: str,
        transfer_scope: str | None,
        transfer_status: str | None,
        created_by_user_id: str,
    ) -> TransactionRecord:
        now = datetime.now(UTC)
        record = TransactionRecord(
            id=f"txn_{uuid4().hex}",
            transaction_type=transaction_type,
            account_id=account_id,
            counterparty_account_id=counterparty_account_id,
            category_id=category_id,
            amount=amount,
            currency=currency,
            occurred_at=occurred_at,
            transaction_date=transaction_date,
            description=description,
            source_type=source_type,
            transfer_scope=transfer_scope,
            transfer_status=transfer_status,
            record_status="active",
            created_by_user_id=created_by_user_id,
            last_edited_by_user_id=created_by_user_id,
            created_at=now,
            updated_at=now,
            deleted_at=None,
            version=1,
        )
        with self._lock:
            self._records[record.id] = record
        return deepcopy(record)

    def save(self, record: TransactionRecord) -> TransactionRecord:
        with self._lock:
            stored = replace(record, updated_at=datetime.now(UTC), version=record.version + 1)
            self._records[stored.id] = stored
            return deepcopy(stored)


class SqlAlchemyTransactionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def has_for_account(self, account_id: str) -> bool:
        parsed_id = _optional_uuid(account_id)
        if parsed_id is None:
            return False

        statement = (
            select(TransactionModel.id)
            .where(
                or_(
                    TransactionModel.account_id == parsed_id,
                    TransactionModel.counterparty_account_id == parsed_id,
                )
            )
            .limit(1)
        )
        return self._session.execute(statement).first() is not None

    def list_by_visible_accounts(
        self,
        visible_account_ids: Iterable[str],
        *,
        filters: TransactionFilters,
    ) -> list[TransactionRecord]:
        parsed_ids = [_required_uuid(value, "visible_account_id") for value in visible_account_ids]
        if not parsed_ids:
            return []

        statement: Select[tuple[TransactionModel]] = select(TransactionModel).where(
            or_(
                TransactionModel.account_id.in_(parsed_ids),
                TransactionModel.counterparty_account_id.in_(parsed_ids),
            )
        )
        if filters.account_id is not None:
            account_id = _optional_uuid(filters.account_id)
            if account_id is None:
                return []
            statement = statement.where(
                or_(
                    TransactionModel.account_id == account_id,
                    TransactionModel.counterparty_account_id == account_id,
                )
            )
        if filters.category_id is not None:
            category_id = _optional_uuid(filters.category_id)
            if category_id is None:
                return []
            statement = statement.where(TransactionModel.category_id == category_id)
        if filters.transaction_type is not None:
            statement = statement.where(
                TransactionModel.transaction_type == filters.transaction_type
            )
        if filters.status is not None:
            statement = statement.where(TransactionModel.record_status == filters.status)
        if filters.start_date is not None:
            statement = statement.where(TransactionModel.transaction_date >= filters.start_date)
        if filters.end_date is not None:
            statement = statement.where(TransactionModel.transaction_date <= filters.end_date)

        rows = [_record_from_model(row) for row in self._session.execute(statement).scalars()]
        return _filter_and_sort(rows, filters)

    def get(self, transaction_id: str) -> TransactionRecord | None:
        parsed_id = _optional_uuid(transaction_id)
        if parsed_id is None:
            return None
        model = self._session.get(TransactionModel, parsed_id)
        return _record_from_model(model) if model is not None else None

    def create(
        self,
        *,
        transaction_type: str,
        account_id: str,
        counterparty_account_id: str | None,
        category_id: str | None,
        amount: Decimal,
        currency: str,
        occurred_at: datetime,
        transaction_date: date,
        description: str | None,
        source_type: str,
        transfer_scope: str | None,
        transfer_status: str | None,
        created_by_user_id: str,
    ) -> TransactionRecord:
        now = datetime.now(UTC)
        actor_id = _required_uuid(created_by_user_id, "created_by_user_id")
        model = TransactionModel(
            id=uuid4(),
            transaction_type=transaction_type,
            account_id=_required_uuid(account_id, "account_id"),
            counterparty_account_id=_nullable_uuid(
                counterparty_account_id,
                "counterparty_account_id",
            ),
            category_id=_nullable_uuid(category_id, "category_id"),
            amount=amount,
            currency=currency,
            occurred_at=occurred_at,
            transaction_date=transaction_date,
            description=description,
            source_type=source_type,
            transfer_scope=transfer_scope,
            transfer_status=transfer_status,
            record_status="active",
            created_by_user_id=actor_id,
            last_edited_by_user_id=actor_id,
            created_at=now,
            updated_at=now,
            deleted_at=None,
            version=1,
        )
        self._session.add(model)
        self._session.flush()
        return _record_from_model(model)

    def save(self, record: TransactionRecord) -> TransactionRecord:
        model = self._session.get(TransactionModel, _required_uuid(record.id, "id"))
        if model is None:
            raise KeyError(f"transaction record does not exist: {record.id}")

        model.transaction_type = record.transaction_type
        model.account_id = _required_uuid(record.account_id, "account_id")
        model.counterparty_account_id = _nullable_uuid(
            record.counterparty_account_id,
            "counterparty_account_id",
        )
        model.category_id = _nullable_uuid(record.category_id, "category_id")
        model.amount = record.amount
        model.currency = record.currency
        model.occurred_at = record.occurred_at
        model.transaction_date = transaction_record_date(record)
        model.description = record.description
        model.source_type = record.source_type
        model.transfer_scope = record.transfer_scope
        model.transfer_status = record.transfer_status
        model.record_status = record.record_status
        model.last_edited_by_user_id = _required_uuid(
            record.last_edited_by_user_id,
            "last_edited_by_user_id",
        )
        model.deleted_at = record.deleted_at
        model.updated_at = datetime.now(UTC)
        model.version = int(record.version) + 1

        self._session.flush()
        return _record_from_model(model)


def _filter_and_sort(
    records: list[TransactionRecord],
    filters: TransactionFilters,
) -> list[TransactionRecord]:
    filtered = records
    if filters.account_id is not None:
        filtered = [
            record
            for record in filtered
            if record.account_id == filters.account_id
            or record.counterparty_account_id == filters.account_id
        ]
    if filters.category_id is not None:
        filtered = [record for record in filtered if record.category_id == filters.category_id]
    if filters.transaction_type is not None:
        filtered = [
            record for record in filtered if record.transaction_type == filters.transaction_type
        ]
    if filters.status is not None:
        filtered = [record for record in filtered if record.record_status == filters.status]
    if filters.start_date is not None:
        filtered = [
            record for record in filtered if transaction_record_date(record) >= filters.start_date
        ]
    if filters.end_date is not None:
        filtered = [
            record for record in filtered if transaction_record_date(record) <= filters.end_date
        ]
    if filters.q:
        needle = filters.q.casefold()
        filtered = [
            record
            for record in filtered
            if record.description is not None and needle in record.description.casefold()
        ]

    sort = filters.sort or "-occurredAt"
    reverse = sort.startswith("-")
    key = sort.removeprefix("-")
    if key == "amount":
        return sorted(filtered, key=lambda record: (record.amount, record.id), reverse=reverse)
    if key == "createdAt":
        return sorted(filtered, key=lambda record: (record.created_at, record.id), reverse=reverse)
    return sorted(filtered, key=lambda record: (record.occurred_at, record.id), reverse=reverse)


def _record_from_model(model: TransactionModel) -> TransactionRecord:
    return TransactionRecord(
        id=str(model.id),
        transaction_type=model.transaction_type,
        account_id=str(model.account_id),
        counterparty_account_id=(
            str(model.counterparty_account_id)
            if model.counterparty_account_id is not None
            else None
        ),
        category_id=str(model.category_id) if model.category_id is not None else None,
        amount=Decimal(model.amount),
        currency=model.currency,
        occurred_at=model.occurred_at,
        transaction_date=model.transaction_date,
        description=model.description,
        source_type=model.source_type,
        transfer_scope=model.transfer_scope,
        transfer_status=model.transfer_status,
        record_status=model.record_status,
        created_by_user_id=str(model.created_by_user_id),
        last_edited_by_user_id=str(model.last_edited_by_user_id),
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
        version=int(model.version or 1),
    )


def transaction_record_date(record: TransactionRecord) -> date:
    if record.transaction_date is not None:
        return record.transaction_date
    occurred_at = record.occurred_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    return occurred_at.astimezone(UTC).date()


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


repository = InMemoryTransactionRepository()


def reset_transactions_for_tests(records: Iterable[TransactionRecord] = ()) -> None:
    repository.reset(records)
