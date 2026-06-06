from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from app.authz import (
    Account as AuthzAccount,
)
from app.authz import (
    AccountOwnershipType,
    Actor,
    DenialReason,
    ResourceStatus,
    canMutateAccount,
    canReadAccount,
)
from app.transactions.repository import TransactionRepository
from app.transactions.repository import repository as transaction_repository

from .repository import AccountRecord, AccountRepository, account_repository
from .schemas import AccountCreateRequest, AccountUpdateRequest


class AccountServiceError(Exception):
    def __init__(self, reason: DenialReason) -> None:
        self.reason = reason


class AccountNotFoundOrInaccessible(AccountServiceError):
    def __init__(self) -> None:
        super().__init__(DenialReason.RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE)


class AccountValidationError(AccountServiceError):
    pass


class AccountConflictError(AccountServiceError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(DenialReason.ACTION_NOT_ALLOWED)
        self.code = code
        self.message = message


def _authz_account(record: AccountRecord) -> AuthzAccount:
    return AuthzAccount(
        id=record.id,
        ownership_type=record.ownership_type,
        owner_user_id=record.owner_user_id,
        household_id=record.household_id,
        status=record.status,
    )


def _has_active_membership(actor: Actor, household_id: str | None) -> bool:
    if not actor.user_id or not household_id:
        return False
    return any(
        membership.user_id == actor.user_id
        and membership.household_id == household_id
        and membership.status.value == "active"
        for membership in actor.memberships
    )


def _is_visible(actor: Actor, record: AccountRecord) -> bool:
    return canReadAccount(actor, _authz_account(record)).allowed


CONFLICTING_UPDATE_CODE = "CONFLICTING_UPDATE"
CURRENCY_IMMUTABLE_CODE = "ACCOUNT_CURRENCY_IMMUTABLE_AFTER_TRANSACTIONS"


class AccountService:
    def __init__(
        self,
        repository: AccountRepository = account_repository,
        transactions: TransactionRepository = transaction_repository,
    ) -> None:
        self._repository = repository
        self._transactions = transactions

    def list_accounts(
        self,
        *,
        actor: Actor,
        limit: int,
        cursor: str | None = None,
        ownership_type: AccountOwnershipType | None = None,
        household_id: str | None = None,
        status: ResourceStatus | None = None,
        q: str | None = None,
        sort: str | None = None,
    ) -> tuple[list[AccountRecord], str | None, bool]:
        visible = [
            record
            for record in self._repository.list()
            if _is_visible(actor, record)
            and (ownership_type is None or record.ownership_type == ownership_type)
            and (household_id is None or record.household_id == household_id)
            and (status is None or record.status == status)
            and (status is not None or record.status != ResourceStatus.DELETED)
        ]

        if q:
            needle = q.casefold()
            visible = [record for record in visible if needle in record.name.casefold()]

        reverse = sort in {"-name", "name_desc"}
        visible.sort(key=lambda record: (record.name.casefold(), record.id), reverse=reverse)

        offset = _decode_cursor(cursor)
        page = visible[offset : offset + limit]
        next_offset = offset + len(page)
        has_more = next_offset < len(visible)
        next_cursor = str(next_offset) if has_more else None
        return page, next_cursor, has_more

    def autocomplete_accounts(
        self,
        *,
        actor: Actor,
        limit: int,
        ownership_type: AccountOwnershipType | None = None,
        household_id: str | None = None,
        q: str | None = None,
    ) -> list[AccountRecord]:
        records, _, _ = self.list_accounts(
            actor=actor,
            limit=limit,
            ownership_type=ownership_type,
            household_id=household_id,
            status=ResourceStatus.ACTIVE,
            q=q,
            sort="name",
        )
        return records

    def create_account(self, *, actor: Actor, request: AccountCreateRequest) -> AccountRecord:
        if actor.user_id is None:
            raise AccountValidationError(DenialReason.UNAUTHENTICATED)

        ownership_type = AccountOwnershipType(request.ownership_type)
        if ownership_type == AccountOwnershipType.PERSONAL:
            if request.household_id is not None:
                raise AccountValidationError(DenialReason.VALIDATION_FAILED)
            owner_user_id = actor.user_id
            household_id = None
        else:
            if not request.household_id or not _has_active_membership(actor, request.household_id):
                raise AccountNotFoundOrInaccessible()
            owner_user_id = None
            household_id = request.household_id

        return self._repository.create(
            name=request.name,
            account_type=str(request.account_type),
            ownership_type=ownership_type,
            currency=request.currency,
            initial_balance=Decimal(request.initial_balance),
            created_by_user_id=actor.user_id,
            owner_user_id=owner_user_id,
            household_id=household_id,
        )

    def get_account(self, *, actor: Actor, account_id: str) -> AccountRecord:
        record = self._repository.get(account_id)
        if record is None or not _is_visible(actor, record):
            raise AccountNotFoundOrInaccessible()
        return record

    def update_account(
        self,
        *,
        actor: Actor,
        account_id: str,
        request: AccountUpdateRequest,
    ) -> AccountRecord:
        record = self.get_account(actor=actor, account_id=account_id)
        decision = canMutateAccount(actor, _authz_account(record))
        if not decision.allowed:
            raise AccountServiceError(decision.reason or DenialReason.ACTION_NOT_ALLOWED)
        if request.version is not None and request.version != record.version:
            raise AccountConflictError(CONFLICTING_UPDATE_CODE, "Conflicting update.")

        next_record = record
        if request.name is not None:
            next_record = replace(next_record, name=request.name)
        if request.current_balance is not None:
            next_record = replace(next_record, current_balance=Decimal(request.current_balance))
        if request.currency is not None and request.currency != record.currency:
            if self._transactions.has_for_account(record.id):
                raise AccountConflictError(
                    CURRENCY_IMMUTABLE_CODE,
                    "Account currency cannot be changed after transactions exist.",
                )
            next_record = replace(next_record, currency=request.currency)
        if request.account_type is not None:
            next_record = replace(next_record, account_type=str(request.account_type))
        if request.status is not None:
            next_record = _with_status(next_record, ResourceStatus(request.status))

        return self._repository.save(next_record)

    def delete_account(self, *, actor: Actor, account_id: str) -> None:
        record = self.get_account(actor=actor, account_id=account_id)
        decision = canMutateAccount(actor, _authz_account(record))
        if not decision.allowed:
            raise AccountServiceError(decision.reason or DenialReason.ACTION_NOT_ALLOWED)
        self._repository.save(_with_status(record, ResourceStatus.DELETED))

    def archive_account(self, *, actor: Actor, account_id: str) -> AccountRecord:
        record = self.get_account(actor=actor, account_id=account_id)
        decision = canMutateAccount(actor, _authz_account(record))
        if not decision.allowed:
            raise AccountServiceError(decision.reason or DenialReason.ACTION_NOT_ALLOWED)
        return self._repository.save(_with_status(record, ResourceStatus.ARCHIVED))

    def restore_account(self, *, actor: Actor, account_id: str) -> AccountRecord:
        record = self.get_account(actor=actor, account_id=account_id)
        if record.status != ResourceStatus.ARCHIVED:
            raise AccountServiceError(DenialReason.ACTION_NOT_ALLOWED)
        return self._repository.save(_with_status(record, ResourceStatus.ACTIVE))


def _decode_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        offset = int(cursor)
    except ValueError as exc:
        raise AccountValidationError(DenialReason.VALIDATION_FAILED) from exc
    if offset < 0:
        raise AccountValidationError(DenialReason.VALIDATION_FAILED)
    return offset


def _with_status(record: AccountRecord, status: ResourceStatus) -> AccountRecord:
    if status == ResourceStatus.ARCHIVED and record.archived_at is None:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        return replace(record, status=status, archived_at=now, deleted_at=None)
    if status == ResourceStatus.DELETED:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        return replace(record, status=status, deleted_at=now)
    if status == ResourceStatus.ACTIVE:
        return replace(record, status=status, archived_at=None, deleted_at=None)
    return replace(record, status=status)


account_service = AccountService()
