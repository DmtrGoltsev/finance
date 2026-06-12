from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.authz import AccountOwnershipType, ResourceStatus
from app.db.models import Account as AccountModel
from app.db.models import AccountBalanceSnapshot as AccountBalanceSnapshotModel


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
    asset_category_id: str | None = None
    status: ResourceStatus = ResourceStatus.ACTIVE
    archived_at: datetime | None = None
    deleted_at: datetime | None = None
    is_payment_account: bool = True


@dataclass(frozen=True, slots=True)
class AccountBalanceSnapshotRecord:
    id: str
    account_id: str
    snapshot_date: date
    balance: Decimal
    currency: str
    created_at: datetime
    updated_at: datetime
    version: int = 1


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
        asset_category_id: str | None = None,
        is_payment_account: bool = True,
    ) -> AccountRecord:
        """Persist a new account record."""

    def save(self, record: AccountRecord) -> AccountRecord:
        """Persist mutable fields from an existing account record."""

    def balance_as_of(self, account_id: str, as_of_date: date | None) -> Decimal | None:
        """Return current balance or the latest durable balance snapshot on/before a date."""

    def balance_snapshot_as_of(
        self,
        account_id: str,
        as_of_date: date | None,
    ) -> AccountBalanceSnapshotRecord | None:
        """Return current balance metadata or the latest durable snapshot on/before a date."""


class InMemoryAccountRepository:
    """Small process-local repository for this service slice only."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, AccountRecord] = {}
        self._balance_snapshots: dict[str, list[AccountBalanceSnapshotRecord]] = {}

    def reset(self) -> None:
        with self._lock:
            self._records = {}
            self._balance_snapshots = {}

    def seed(self, records: list[AccountRecord]) -> None:
        with self._lock:
            self._records.update({record.id: record for record in records})
            for record in records:
                self._record_balance_snapshot(
                    account_id=record.id,
                    snapshot_date=record.updated_at.date(),
                    balance=record.current_balance,
                    currency=record.currency,
                    observed_at=record.updated_at,
                )

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
        asset_category_id: str | None = None,
        is_payment_account: bool = True,
    ) -> AccountRecord:
        now = datetime.now(UTC)
        record = AccountRecord(
            id=f"acct_{uuid4().hex}",
            name=name,
            account_type=account_type,
            ownership_type=ownership_type,
            owner_user_id=owner_user_id,
            household_id=household_id,
            asset_category_id=asset_category_id,
            currency=currency,
            initial_balance=initial_balance,
            current_balance=initial_balance,
            is_payment_account=is_payment_account,
            created_by_user_id=created_by_user_id,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._records[record.id] = record
            self._record_balance_snapshot(
                account_id=record.id,
                snapshot_date=now.date(),
                balance=record.current_balance,
                currency=record.currency,
                observed_at=now,
            )
        return record

    def save(self, record: AccountRecord) -> AccountRecord:
        with self._lock:
            existing = self._records.get(record.id)
            now = datetime.now(UTC)
            next_record = replace(
                record,
                version=record.version + 1,
                updated_at=now,
            )
            self._records[next_record.id] = next_record
            if (
                existing is None
                or existing.current_balance != next_record.current_balance
                or existing.currency != next_record.currency
            ):
                self._record_balance_snapshot(
                    account_id=next_record.id,
                    snapshot_date=now.date(),
                    balance=next_record.current_balance,
                    currency=next_record.currency,
                    observed_at=now,
                )
            return next_record

    def balance_as_of(self, account_id: str, as_of_date: date | None) -> Decimal | None:
        snapshot = self.balance_snapshot_as_of(account_id, as_of_date)
        return snapshot.balance if snapshot is not None else None

    def balance_snapshot_as_of(
        self,
        account_id: str,
        as_of_date: date | None,
    ) -> AccountBalanceSnapshotRecord | None:
        with self._lock:
            if as_of_date is None:
                record = self._records.get(account_id)
                if record is None:
                    return None
                return AccountBalanceSnapshotRecord(
                    id=f"current_{record.id}",
                    account_id=record.id,
                    snapshot_date=record.updated_at.date(),
                    balance=record.current_balance,
                    currency=record.currency,
                    created_at=record.updated_at,
                    updated_at=record.updated_at,
                    version=record.version,
                )
            snapshots = [
                snapshot
                for snapshot in self._balance_snapshots.get(account_id, [])
                if snapshot.snapshot_date <= as_of_date
            ]
        if not snapshots:
            return None
        latest = max(snapshots, key=lambda row: (row.snapshot_date, row.created_at, row.id))
        return latest

    def _record_balance_snapshot(
        self,
        *,
        account_id: str,
        snapshot_date: date,
        balance: Decimal,
        currency: str,
        observed_at: datetime,
    ) -> None:
        snapshot = AccountBalanceSnapshotRecord(
            id=f"acctbal_{uuid4().hex}",
            account_id=account_id,
            snapshot_date=snapshot_date,
            balance=balance,
            currency=currency,
            created_at=observed_at,
            updated_at=observed_at,
        )
        self._balance_snapshots.setdefault(account_id, []).append(snapshot)


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
        asset_category_id: str | None = None,
        is_payment_account: bool = True,
    ) -> AccountRecord:
        now = datetime.now(UTC)
        model = AccountModel(
            id=uuid4(),
            name=name,
            account_type=account_type,
            ownership_type=ownership_type.value,
            owner_user_id=_nullable_uuid(owner_user_id, "owner_user_id"),
            household_id=_nullable_uuid(household_id, "household_id"),
            asset_category_id=_nullable_uuid(asset_category_id, "asset_category_id"),
            is_payment_account=is_payment_account,
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
        self._create_balance_snapshot(
            account_id=model.id,
            snapshot_date=now.date(),
            balance=_current_model_balance(model),
            currency=model.currency,
            observed_at=now,
        )
        return _record_from_model(model)

    def save(self, record: AccountRecord) -> AccountRecord:
        parsed_id = _required_uuid(record.id, "id")
        model = self._session.get(AccountModel, parsed_id)
        if model is None:
            raise KeyError(f"account record does not exist: {record.id}")

        previous_balance = _current_model_balance(model)
        previous_currency = model.currency
        now = datetime.now(UTC)
        model.name = record.name
        model.account_type = record.account_type
        model.asset_category_id = _nullable_uuid(record.asset_category_id, "asset_category_id")
        model.is_payment_account = record.is_payment_account
        model.currency = record.currency
        model.current_balance_amount = record.current_balance
        model.record_status = record.status.value
        model.archived_at = record.archived_at
        model.deleted_at = record.deleted_at
        model.updated_at = now
        model.version = int(record.version) + 1

        self._session.flush()
        if previous_balance != record.current_balance or previous_currency != record.currency:
            self._create_balance_snapshot(
                account_id=model.id,
                snapshot_date=now.date(),
                balance=_current_model_balance(model),
                currency=model.currency,
                observed_at=now,
            )
        return _record_from_model(model)

    def balance_as_of(self, account_id: str, as_of_date: date | None) -> Decimal | None:
        snapshot = self.balance_snapshot_as_of(account_id, as_of_date)
        return snapshot.balance if snapshot is not None else None

    def balance_snapshot_as_of(
        self,
        account_id: str,
        as_of_date: date | None,
    ) -> AccountBalanceSnapshotRecord | None:
        parsed_id = _optional_uuid(account_id)
        if parsed_id is None:
            return None
        if as_of_date is None:
            record = self.get(account_id)
            if record is None:
                return None
            return AccountBalanceSnapshotRecord(
                id=f"current_{record.id}",
                account_id=record.id,
                snapshot_date=record.updated_at.date(),
                balance=record.current_balance,
                currency=record.currency,
                created_at=record.updated_at,
                updated_at=record.updated_at,
                version=record.version,
            )

        statement = (
            select(AccountBalanceSnapshotModel)
            .where(
                AccountBalanceSnapshotModel.account_id == parsed_id,
                AccountBalanceSnapshotModel.snapshot_date <= as_of_date,
            )
            .order_by(
                AccountBalanceSnapshotModel.snapshot_date.desc(),
                AccountBalanceSnapshotModel.created_at.desc(),
                AccountBalanceSnapshotModel.id.desc(),
            )
            .limit(1)
        )
        snapshot = self._session.execute(statement).scalar_one_or_none()
        if snapshot is None:
            return None
        return AccountBalanceSnapshotRecord(
            id=str(snapshot.id),
            account_id=str(snapshot.account_id),
            snapshot_date=snapshot.snapshot_date,
            balance=Decimal(snapshot.balance_amount),
            currency=snapshot.currency,
            created_at=snapshot.created_at,
            updated_at=snapshot.updated_at,
            version=int(snapshot.version or 1),
        )

    def _create_balance_snapshot(
        self,
        *,
        account_id: UUID,
        snapshot_date: date,
        balance: Decimal,
        currency: str,
        observed_at: datetime,
    ) -> None:
        self._session.add(
            AccountBalanceSnapshotModel(
                id=uuid4(),
                account_id=account_id,
                snapshot_date=snapshot_date,
                balance_amount=balance,
                currency=currency,
                created_at=observed_at,
                updated_at=observed_at,
                version=1,
            )
        )
        self._session.flush()


def _record_from_model(model: AccountModel) -> AccountRecord:
    current_balance = _current_model_balance(model)

    return AccountRecord(
        id=str(model.id),
        name=model.name,
        account_type=model.account_type,
        ownership_type=AccountOwnershipType(model.ownership_type),
        owner_user_id=str(model.owner_user_id) if model.owner_user_id is not None else None,
        household_id=str(model.household_id) if model.household_id is not None else None,
        asset_category_id=(
            str(model.asset_category_id) if model.asset_category_id is not None else None
        ),
        is_payment_account=bool(model.is_payment_account),
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


def _current_model_balance(model: AccountModel) -> Decimal:
    current_balance = model.current_balance_amount
    if current_balance is None:
        current_balance = model.initial_balance_amount
    return Decimal(current_balance)


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
