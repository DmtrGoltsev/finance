from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.authz import AccountOwnershipType, ResourceStatus
from app.db.models import Account as AccountModel


@dataclass(frozen=True, slots=True)
class AccountRecord:
    id: str
    name: str
    account_type: str
    ownership_type: AccountOwnershipType
    currency: str
    initial_balance: Decimal
    current_balance: Decimal
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    version: int = 1
    owner_user_id: str | None = None
    household_id: str | None = None
    status: ResourceStatus = ResourceStatus.ACTIVE
    archived_at: datetime | None = None
    deleted_at: datetime | None = None


class AccountRepository(Protocol):
    def list(self) -> list[AccountRecord]:
        """Return all account records; service layer applies authz filtering."""

    def get(self, account_id: str) -> AccountRecord | None:
        """Return one account record by public ID, or ``None``."""

    def create(
        self,
        *,
        name: str,
        account_type: str,
        ownership_type: AccountOwnershipType,
        currency: str,
        initial_balance: Decimal,
        created_by_user_id: str,
        owner_user_id: str | None,
        household_id: str | None,
    ) -> AccountRecord:
        """Persist a new account record."""

    def save(self, record: AccountRecord) -> AccountRecord:
        """Persist mutable fields from an existing account record."""


class InMemoryAccountRepository:
    """Small process-local repository for this service slice only."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, AccountRecord] = {}

    def reset(self) -> None:
        with self._lock:
            self._records = {}

    def seed(self, records: list[AccountRecord]) -> None:
        with self._lock:
            self._records.update({record.id: record for record in records})

    def list(self) -> list[AccountRecord]:
        with self._lock:
            return list(self._records.values())

    def get(self, account_id: str) -> AccountRecord | None:
        with self._lock:
            return self._records.get(account_id)

    def create(
        self,
        *,
        name: str,
        account_type: str,
        ownership_type: AccountOwnershipType,
        currency: str,
        initial_balance: Decimal,
        created_by_user_id: str,
        owner_user_id: str | None,
        household_id: str | None,
    ) -> AccountRecord:
        now = datetime.now(UTC)
        record = AccountRecord(
            id=f"acct_{uuid4().hex}",
            name=name,
            account_type=account_type,
            ownership_type=ownership_type,
            owner_user_id=owner_user_id,
            household_id=household_id,
            currency=currency,
            initial_balance=initial_balance,
            current_balance=initial_balance,
            created_by_user_id=created_by_user_id,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._records[record.id] = record
        return record

    def save(self, record: AccountRecord) -> AccountRecord:
        with self._lock:
            next_record = replace(
                record,
                version=record.version + 1,
                updated_at=datetime.now(UTC),
            )
            self._records[next_record.id] = next_record
            return next_record


class SqlAlchemyAccountRepository:
    """SQLAlchemy-backed account repository for the DB foundation slice.

    The current FastAPI runtime still uses ``InMemoryAccountRepository``. This
    adapter is intentionally explicit and session-scoped so a later integration
    worker can switch runtime wiring without changing service authz semantics.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self) -> list[AccountRecord]:
        rows = self._session.execute(select(AccountModel)).scalars().all()
        return [_record_from_model(row) for row in rows]

    def get(self, account_id: str) -> AccountRecord | None:
        parsed_id = _optional_uuid(account_id)
        if parsed_id is None:
            return None

        model = self._session.get(AccountModel, parsed_id)
        return _record_from_model(model) if model is not None else None

    def create(
        self,
        *,
        name: str,
        account_type: str,
        ownership_type: AccountOwnershipType,
        currency: str,
        initial_balance: Decimal,
        created_by_user_id: str,
        owner_user_id: str | None,
        household_id: str | None,
    ) -> AccountRecord:
        now = datetime.now(UTC)
        model = AccountModel(
            id=uuid4(),
            name=name,
            account_type=account_type,
            ownership_type=ownership_type.value,
            owner_user_id=_nullable_uuid(owner_user_id, "owner_user_id"),
            household_id=_nullable_uuid(household_id, "household_id"),
            currency=currency,
            initial_balance_amount=initial_balance,
            current_balance_amount=initial_balance,
            record_status=ResourceStatus.ACTIVE.value,
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

    def save(self, record: AccountRecord) -> AccountRecord:
        parsed_id = _required_uuid(record.id, "id")
        model = self._session.get(AccountModel, parsed_id)
        if model is None:
            raise KeyError(f"account record does not exist: {record.id}")

        model.name = record.name
        model.account_type = record.account_type
        model.currency = record.currency
        model.current_balance_amount = record.current_balance
        model.record_status = record.status.value
        model.archived_at = record.archived_at
        model.deleted_at = record.deleted_at
        model.updated_at = datetime.now(UTC)
        model.version = int(record.version) + 1

        self._session.flush()
        return _record_from_model(model)


def _record_from_model(model: AccountModel) -> AccountRecord:
    current_balance = model.current_balance_amount
    if current_balance is None:
        current_balance = model.initial_balance_amount

    return AccountRecord(
        id=str(model.id),
        name=model.name,
        account_type=model.account_type,
        ownership_type=AccountOwnershipType(model.ownership_type),
        owner_user_id=str(model.owner_user_id) if model.owner_user_id is not None else None,
        household_id=str(model.household_id) if model.household_id is not None else None,
        currency=model.currency,
        initial_balance=Decimal(model.initial_balance_amount),
        current_balance=Decimal(current_balance),
        created_by_user_id=str(model.created_by_user_id),
        created_at=model.created_at,
        updated_at=model.updated_at,
        version=int(model.version or 1),
        status=ResourceStatus(model.record_status),
        archived_at=model.archived_at,
        deleted_at=model.deleted_at,
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


account_repository = InMemoryAccountRepository()


def reset_accounts_for_tests() -> None:
    account_repository.reset()


def seed_accounts_for_tests(records: list[AccountRecord]) -> None:
    account_repository.seed(records)
