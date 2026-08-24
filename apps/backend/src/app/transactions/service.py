from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time
from decimal import Decimal

from app.accounts.repository import AccountRecord, AccountRepository, account_repository
from app.authz import (
    Account as AuthzAccount,
)
from app.authz import (
    AccountOwnershipType,
    Actor,
    CategoryKind,
    DenialReason,
    ResourceStatus,
    TransactionDraft,
    canCreateTransaction,
    canMutateTransaction,
    canReadAccount,
    canReadCategory,
    canReadTransaction,
)
from app.authz import (
    Category as AuthzCategory,
)
from app.authz import (
    CategoryScope as AuthzCategoryScope,
)
from app.authz import (
    SourceType as AuthzSourceType,
)
from app.authz import (
    Transaction as AuthzTransaction,
)
from app.authz import (
    TransactionType as AuthzTransactionType,
)
from app.categories.repository import CategoryRecord, CategoryRepository
from app.categories.repository import repository as category_repository
from app.categories.schemas import CategoryScope
from app.categories.schemas import RecordStatus as CategoryRecordStatus
from app.sync.domain_changes import SyncChangeRecorder

from .repository import TransactionFilters, TransactionRecord, TransactionRepository, repository
from .schemas import TransactionCreateRequest, TransactionUpdateRequest


class TransactionServiceError(Exception):
    def __init__(self, reason: DenialReason, *, code: str | None = None) -> None:
        self.reason = reason
        self.code = code


class TransactionNotFoundOrInaccessible(TransactionServiceError):
    def __init__(self) -> None:
        super().__init__(DenialReason.RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE)


class TransactionReferencedResourceError(TransactionServiceError):
    def __init__(self) -> None:
        super().__init__(DenialReason.REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE)


class TransactionValidationError(TransactionServiceError):
    pass


class TransactionInvalidCurrencyError(TransactionValidationError):
    def __init__(self) -> None:
        super().__init__(DenialReason.VALIDATION_FAILED, code="INVALID_CURRENCY")


class TransactionTransferCounterpartyRequiredError(TransactionValidationError):
    def __init__(self) -> None:
        super().__init__(
            DenialReason.VALIDATION_FAILED,
            code="TRANSFER_COUNTERPARTY_REQUIRED",
        )


class TransactionConflictError(TransactionServiceError):
    def __init__(self, code: str = "CONFLICTING_UPDATE") -> None:
        super().__init__(DenialReason.ACTION_NOT_ALLOWED, code=code)


class TransactionService:
    def __init__(
        self,
        transactions: TransactionRepository = repository,
        accounts: AccountRepository = account_repository,
        categories: CategoryRepository = category_repository,
        sync_change_recorder: SyncChangeRecorder | None = None,
    ) -> None:
        self._transactions = transactions
        self._accounts = accounts
        self._categories = categories
        self._sync_change_recorder = sync_change_recorder

    def list_transactions(
        self,
        *,
        actor: Actor,
        limit: int,
        cursor: str | None,
        account_id: str | None,
        category_id: str | None,
        transaction_type: str | None,
        household_id: str | None,
        ownership_type: str | None,
        status: str | None,
        start_date: date | None,
        end_date: date | None,
        q: str | None,
        sort: str | None,
    ) -> tuple[list[TransactionRecord], str | None, bool]:
        visible_accounts = self._visible_accounts(
            actor,
            household_id=household_id,
            ownership_type=ownership_type,
        )

        if account_id is not None:
            account = self._require_visible_account(actor, account_id)
            if account.id not in {record.id for record in visible_accounts}:
                raise TransactionReferencedResourceError()
            visible_accounts = [account]

        if category_id is not None:
            self._require_visible_category(actor, category_id)

        effective_status = status or "active"
        if effective_status != "active":
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)

        filters = TransactionFilters(
            account_id=account_id,
            category_id=category_id,
            transaction_type=transaction_type,
            status=effective_status,
            start_date=start_date,
            end_date=end_date,
            q=q,
            sort=sort,
        )
        all_visible = self._transactions.list_by_visible_accounts(
            [record.id for record in visible_accounts],
            filters=filters,
        )
        offset = _decode_cursor(cursor)
        page = all_visible[offset : offset + limit]
        next_offset = offset + len(page)
        has_more = next_offset < len(all_visible)
        next_cursor = str(next_offset) if has_more else None
        return page, next_cursor, has_more

    def autocomplete_transactions(
        self,
        *,
        actor: Actor,
        limit: int,
        q: str | None,
    ) -> list[TransactionRecord]:
        records, _, _ = self.list_transactions(
            actor=actor,
            limit=limit,
            cursor=None,
            account_id=None,
            category_id=None,
            transaction_type=None,
            household_id=None,
            ownership_type=None,
            status="active",
            start_date=None,
            end_date=None,
            q=q,
            sort="-occurredAt",
        )
        return records

    def create_transaction(
        self,
        *,
        actor: Actor,
        request: TransactionCreateRequest,
        transaction_id: str | None = None,
    ) -> TransactionRecord:
        if not actor.user_id:
            raise TransactionNotFoundOrInaccessible()

        if str(request.transaction_type) == "transfer":
            return self._create_transfer(
                actor=actor,
                request=request,
                transaction_id=transaction_id,
            )

        self._validate_manual_non_transfer_shape(
            transaction_type=str(request.transaction_type),
            source_type=str(request.source_type),
            counterparty_account_id=request.counterparty_account_id,
            category_id=request.category_id,
        )
        account = self._require_visible_account(actor, request.account_id)
        category = self._visible_category_for_transaction(
            actor,
            transaction_type=str(request.transaction_type),
            category_id=request.category_id,
        )
        self._validate_currency(account, request.currency)
        transaction_date, occurred_at = _date_fields_for_create(request)

        decision = canCreateTransaction(
            actor,
            TransactionDraft(
                transaction_type=AuthzTransactionType(str(request.transaction_type)),
                account=_authz_account(account),
                category=_authz_category(category) if category is not None else None,
                source_type=AuthzSourceType(str(request.source_type)),
            ),
        )
        if not decision.allowed:
            raise _service_error_for_decision(decision.reason)

        record = self._transactions.create(
            transaction_id=transaction_id,
            transaction_type=str(request.transaction_type),
            account_id=account.id,
            counterparty_account_id=None,
            category_id=category.id if category is not None else None,
            amount=Decimal(request.amount),
            currency=request.currency,
            occurred_at=occurred_at,
            transaction_date=transaction_date,
            description=request.description,
            source_type=str(request.source_type),
            transfer_scope=None,
            transfer_status=None,
            created_by_user_id=actor.user_id,
        )
        self._record_sync_change(actor=actor, operation="create", record=record)
        return record

    def validate_capture_draft_references(
        self,
        *,
        actor: Actor,
        account_id: str | None,
        category_id: str | None,
        currency: str | None,
    ) -> None:
        account = (
            self._require_visible_account(actor, account_id)
            if account_id is not None
            else None
        )
        category = (
            self._require_visible_category(actor, category_id)
            if category_id is not None
            else None
        )

        if account is not None and currency is not None:
            self._validate_currency(account, currency)

        if account is None or category is None:
            return

        decision = canCreateTransaction(
            actor,
            TransactionDraft(
                transaction_type=AuthzTransactionType.EXPENSE,
                account=_authz_account(account),
                category=_authz_category(category),
                source_type=AuthzSourceType.MANUAL,
            ),
        )
        if not decision.allowed:
            raise _service_error_for_decision(decision.reason)

    def get_transaction(self, *, actor: Actor, transaction_id: str) -> TransactionRecord:
        record = self._transactions.get(transaction_id)
        if record is None or not self._can_read_record(actor, record):
            raise TransactionNotFoundOrInaccessible()
        return record

    def update_transaction(
        self,
        *,
        actor: Actor,
        transaction_id: str,
        request: TransactionUpdateRequest,
    ) -> TransactionRecord:
        record = self.get_transaction(actor=actor, transaction_id=transaction_id)
        if request.version is not None and request.version != record.version:
            raise TransactionConflictError()

        transaction_type = (
            str(request.transaction_type) if request.transaction_type else record.transaction_type
        )
        if transaction_type != record.transaction_type:
            raise TransactionValidationError(DenialReason.ACTION_NOT_ALLOWED)
        if transaction_type == "transfer":
            return self._update_transfer(actor=actor, record=record, request=request)

        source_type = str(request.source_type) if request.source_type else record.source_type
        account_id = request.account_id or record.account_id
        category_id = request.category_id if request.category_id is not None else record.category_id
        currency = request.currency or record.currency

        self._validate_manual_non_transfer_shape(
            transaction_type=transaction_type,
            source_type=source_type,
            counterparty_account_id=(
                request.counterparty_account_id or record.counterparty_account_id
            ),
            category_id=category_id,
        )
        account = self._require_visible_account(actor, account_id)
        category = self._visible_category_for_transaction(
            actor,
            transaction_type=transaction_type,
            category_id=category_id,
        )
        self._validate_currency(account, currency)

        transaction = self._authz_transaction(record)
        decision = canMutateTransaction(
            actor,
            transaction,
            proposed_account=_authz_account(account),
            proposed_category=_authz_category(category) if category is not None else None,
        )
        if not decision.allowed:
            raise _service_error_for_decision(decision.reason)
        transaction_date, occurred_at = _date_fields_for_update(record, request)

        updated = replace(
            record,
            transaction_type=transaction_type,
            account_id=account.id,
            counterparty_account_id=None,
            category_id=category.id if category is not None else None,
            amount=Decimal(request.amount) if request.amount is not None else record.amount,
            currency=currency,
            occurred_at=occurred_at,
            transaction_date=transaction_date,
            description=(
                request.description if request.description is not None else record.description
            ),
            source_type=source_type,
            transfer_scope=None,
            transfer_status=None,
            last_edited_by_user_id=actor.user_id or record.last_edited_by_user_id,
        )
        saved = self._transactions.save(updated)
        self._record_sync_change(actor=actor, operation="update", record=saved)
        return saved

    def delete_transaction(
        self,
        *,
        actor: Actor,
        transaction_id: str,
        version: int | None = None,
    ) -> None:
        record = self.get_transaction(actor=actor, transaction_id=transaction_id)
        decision = canMutateTransaction(actor, self._authz_transaction(record))
        if not decision.allowed:
            raise _service_error_for_decision(decision.reason)
        if version is not None and version != record.version:
            raise TransactionConflictError()
        if record.transaction_type == "transfer":
            source, counterparty = self._require_transfer_accounts_for_existing(actor, record)
            deleted = replace(
                record,
                record_status="deleted",
                deleted_at=datetime.now(UTC),
                last_edited_by_user_id=actor.user_id or record.last_edited_by_user_id,
            )
            saved = self._transactions.save(deleted)
            self._apply_transfer_balance_delta(
                source,
                counterparty,
                record.amount,
                posting=False,
            )
            self._record_sync_change(
                actor=actor,
                operation="delete",
                record=saved,
                changed_account_ids=(source.id, counterparty.id),
            )
            return

        deleted = self._transactions.save(
            replace(
                record,
                record_status="deleted",
                deleted_at=datetime.now(UTC),
                last_edited_by_user_id=actor.user_id or record.last_edited_by_user_id,
            )
        )
        self._record_sync_change(actor=actor, operation="delete", record=deleted)

    def restore_transaction(
        self,
        *,
        actor: Actor,
        transaction_id: str,
        version: int | None = None,
        allowed_transaction_types: frozenset[str] | None = None,
    ) -> TransactionRecord:
        record = self._transactions.get(transaction_id)
        if record is None:
            raise TransactionNotFoundOrInaccessible()
        if record.record_status != "deleted":
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)

        if record.transaction_type == "transfer":
            source, counterparty = self._require_transfer_accounts_for_existing(actor, record)
            self._validate_transfer_currency(source, counterparty, record.currency)
            decision = canCreateTransaction(
                actor,
                TransactionDraft(
                    transaction_type=AuthzTransactionType.TRANSFER,
                    account=_authz_account(source),
                    counterparty_account=_authz_account(counterparty),
                    category=None,
                    source_type=AuthzSourceType(record.source_type),
                ),
            )
            if not decision.allowed:
                raise _service_error_for_decision(decision.reason)
            if version is not None and version != record.version:
                raise TransactionConflictError()
            if (
                allowed_transaction_types is not None
                and record.transaction_type not in allowed_transaction_types
            ):
                raise TransactionValidationError(
                    DenialReason.ACTION_NOT_ALLOWED,
                    code="UNSUPPORTED_TRANSACTION_TYPE",
                )

            restored = replace(
                record,
                record_status="active",
                deleted_at=None,
                last_edited_by_user_id=actor.user_id or record.last_edited_by_user_id,
            )
            saved = self._transactions.save(restored)
            self._apply_transfer_balance_delta(source, counterparty, record.amount, posting=True)
            self._record_sync_change(
                actor=actor,
                operation="restore",
                record=saved,
                changed_account_ids=(source.id, counterparty.id),
            )
            return saved

        account = self._accounts.get(record.account_id)
        category = (
            self._categories.get(record.category_id) if record.category_id is not None else None
        )
        if account is None:
            raise TransactionNotFoundOrInaccessible()
        if record.transaction_type in {"income", "expense"} and category is None:
            raise TransactionNotFoundOrInaccessible()
        if not canReadAccount(actor, _authz_account(account)).allowed:
            raise TransactionNotFoundOrInaccessible()
        if category is not None and not canReadCategory(actor, _authz_category(category)).allowed:
            raise TransactionNotFoundOrInaccessible()
        if version is not None and version != record.version:
            raise TransactionConflictError()
        if (
            allowed_transaction_types is not None
            and record.transaction_type not in allowed_transaction_types
        ):
            raise TransactionValidationError(
                DenialReason.ACTION_NOT_ALLOWED,
                code="UNSUPPORTED_TRANSACTION_TYPE",
            )

        restored = replace(
            record,
            record_status="active",
            deleted_at=None,
            last_edited_by_user_id=actor.user_id or record.last_edited_by_user_id,
        )
        saved = self._transactions.save(restored)
        self._record_sync_change(actor=actor, operation="restore", record=saved)
        return saved

    def _create_transfer(
        self,
        *,
        actor: Actor,
        request: TransactionCreateRequest,
        transaction_id: str | None = None,
    ) -> TransactionRecord:
        self._validate_transfer_shape(
            source_type=str(request.source_type),
            counterparty_account_id=request.counterparty_account_id,
            category_id=request.category_id,
            same_account=request.account_id == request.counterparty_account_id,
        )
        source, counterparty = self._resolve_transfer_accounts(
            actor,
            account_id=request.account_id,
            counterparty_account_id=request.counterparty_account_id,
        )
        self._validate_transfer_currency(source, counterparty, request.currency)

        decision = canCreateTransaction(
            actor,
            TransactionDraft(
                transaction_type=AuthzTransactionType.TRANSFER,
                account=_authz_account(source),
                counterparty_account=_authz_account(counterparty),
                category=None,
                source_type=AuthzSourceType(str(request.source_type)),
            ),
        )
        if not decision.allowed:
            raise _service_error_for_decision(decision.reason)
        if decision.transfer_scope is None:
            raise TransactionValidationError(DenialReason.TRANSFER_SCOPE_NOT_SUPPORTED)

        amount = Decimal(request.amount)
        transaction_date, occurred_at = _date_fields_for_create(request)
        record = self._transactions.create(
            transaction_id=transaction_id,
            transaction_type="transfer",
            account_id=source.id,
            counterparty_account_id=counterparty.id,
            category_id=None,
            amount=amount,
            currency=request.currency,
            occurred_at=occurred_at,
            transaction_date=transaction_date,
            description=request.description,
            source_type=str(request.source_type),
            transfer_scope=decision.transfer_scope.value,
            transfer_status="posted",
            created_by_user_id=actor.user_id,
        )
        self._apply_transfer_balance_delta(source, counterparty, amount, posting=True)
        self._record_sync_change(
            actor=actor,
            operation="create",
            record=record,
            changed_account_ids=(source.id, counterparty.id),
        )
        return record

    def _update_transfer(
        self,
        *,
        actor: Actor,
        record: TransactionRecord,
        request: TransactionUpdateRequest,
    ) -> TransactionRecord:
        fields_set = request.model_fields_set
        if "category_id" in fields_set and request.category_id is not None:
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)

        source_type = str(request.source_type) if request.source_type else record.source_type
        account_id = request.account_id or record.account_id
        if "counterparty_account_id" in fields_set and request.counterparty_account_id is None:
            raise TransactionTransferCounterpartyRequiredError()
        counterparty_account_id = request.counterparty_account_id or record.counterparty_account_id
        if counterparty_account_id is None:
            raise TransactionTransferCounterpartyRequiredError()

        self._validate_transfer_shape(
            source_type=source_type,
            counterparty_account_id=counterparty_account_id,
            category_id=None,
            same_account=account_id == counterparty_account_id,
        )
        source, counterparty = self._resolve_transfer_accounts(
            actor,
            account_id=account_id,
            counterparty_account_id=counterparty_account_id,
        )
        currency = request.currency or record.currency
        self._validate_transfer_currency(source, counterparty, currency)

        decision = canMutateTransaction(
            actor,
            self._authz_transaction(record),
            proposed_account=_authz_account(source),
            proposed_counterparty_account=_authz_account(counterparty),
        )
        if not decision.allowed:
            raise _service_error_for_decision(decision.reason)
        if decision.transfer_scope is None:
            raise TransactionValidationError(DenialReason.TRANSFER_SCOPE_NOT_SUPPORTED)

        old_source, old_counterparty = self._require_transfer_accounts_for_existing(actor, record)
        amount = Decimal(request.amount) if request.amount is not None else record.amount
        transaction_date, occurred_at = _date_fields_for_update(record, request)
        updated = replace(
            record,
            account_id=source.id,
            counterparty_account_id=counterparty.id,
            category_id=None,
            amount=amount,
            currency=currency,
            occurred_at=occurred_at,
            transaction_date=transaction_date,
            description=(
                request.description if request.description is not None else record.description
            ),
            source_type=source_type,
            transfer_scope=decision.transfer_scope.value,
            transfer_status=record.transfer_status or "posted",
            last_edited_by_user_id=actor.user_id or record.last_edited_by_user_id,
        )
        saved = self._transactions.save(updated)
        self._apply_transfer_balance_delta(
            old_source,
            old_counterparty,
            record.amount,
            posting=False,
        )
        fresh_source = self._require_visible_account(actor, source.id)
        fresh_counterparty = self._require_visible_account(actor, counterparty.id)
        self._apply_transfer_balance_delta(fresh_source, fresh_counterparty, amount, posting=True)
        self._record_sync_change(
            actor=actor,
            operation="update",
            record=saved,
            changed_account_ids=(
                old_source.id,
                old_counterparty.id,
                source.id,
                counterparty.id,
            ),
        )
        return saved

    def _visible_accounts(
        self,
        actor: Actor,
        *,
        household_id: str | None,
        ownership_type: str | None,
    ) -> list[AccountRecord]:
        records: list[AccountRecord] = []
        for record in self._accounts.list():
            if not canReadAccount(actor, _authz_account(record)).allowed:
                continue
            if record.status == ResourceStatus.DELETED:
                continue
            if household_id is not None and record.household_id != household_id:
                continue
            if ownership_type is not None and record.ownership_type.value != ownership_type:
                continue
            records.append(record)
        return records

    def _require_visible_account(self, actor: Actor, account_id: str) -> AccountRecord:
        record = self._accounts.get(account_id)
        if record is None or not canReadAccount(actor, _authz_account(record)).allowed:
            raise TransactionReferencedResourceError()
        if record.status != ResourceStatus.ACTIVE:
            raise TransactionValidationError(DenialReason.ARCHIVED_RECORD_NOT_MUTABLE)
        return record

    def _require_visible_category(
        self,
        actor: Actor,
        category_id: str | None,
    ) -> CategoryRecord:
        if category_id is None:
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)
        record = self._categories.get(category_id)
        if record is None or not canReadCategory(actor, _authz_category(record)).allowed:
            raise TransactionReferencedResourceError()
        if record.status != CategoryRecordStatus.ACTIVE:
            raise TransactionValidationError(DenialReason.ARCHIVED_RECORD_NOT_MUTABLE)
        return record

    def _visible_category_for_transaction(
        self,
        actor: Actor,
        *,
        transaction_type: str,
        category_id: str | None,
    ) -> CategoryRecord | None:
        if transaction_type in {"income", "expense"}:
            return self._require_visible_category(actor, category_id)
        if category_id is not None:
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)
        return None

    def _resolve_transfer_accounts(
        self,
        actor: Actor,
        *,
        account_id: str,
        counterparty_account_id: str | None,
    ) -> tuple[AccountRecord, AccountRecord]:
        if counterparty_account_id is None:
            raise TransactionTransferCounterpartyRequiredError()
        source = self._require_visible_account(actor, account_id)
        counterparty = self._accounts.get(counterparty_account_id)
        if counterparty is None or not canReadAccount(actor, _authz_account(counterparty)).allowed:
            raise TransactionReferencedResourceError()
        if counterparty.status != ResourceStatus.ACTIVE:
            raise TransactionValidationError(DenialReason.ARCHIVED_RECORD_NOT_MUTABLE)
        return source, counterparty

    def _require_transfer_accounts_for_existing(
        self,
        actor: Actor,
        record: TransactionRecord,
    ) -> tuple[AccountRecord, AccountRecord]:
        return self._resolve_transfer_accounts(
            actor,
            account_id=record.account_id,
            counterparty_account_id=record.counterparty_account_id,
        )

    def _can_read_record(self, actor: Actor, record: TransactionRecord) -> bool:
        return canReadTransaction(actor, self._authz_transaction(record)).allowed

    def _authz_transaction(self, record: TransactionRecord) -> AuthzTransaction:
        account = self._accounts.get(record.account_id)
        counterparty = (
            self._accounts.get(record.counterparty_account_id)
            if record.counterparty_account_id is not None
            else None
        )
        category = (
            self._categories.get(record.category_id) if record.category_id is not None else None
        )
        if account is None:
            return AuthzTransaction(
                id=record.id,
                transaction_type=AuthzTransactionType(record.transaction_type),
                account=AuthzAccount(
                    id=record.account_id,
                    ownership_type=AccountOwnershipType.PERSONAL,
                ),
                status=ResourceStatus.DELETED,
            )

        status = (
            ResourceStatus.ACTIVE
            if record.record_status == "active"
            else ResourceStatus.DELETED
        )
        return AuthzTransaction(
            id=record.id,
            transaction_type=AuthzTransactionType(record.transaction_type),
            account=_authz_account(account),
            counterparty_account=_authz_account(counterparty) if counterparty is not None else None,
            category=_authz_category(category) if category is not None else None,
            source_type=AuthzSourceType(record.source_type),
            status=status,
        )

    def _validate_transfer_shape(
        self,
        *,
        source_type: str,
        counterparty_account_id: str | None,
        category_id: str | None,
        same_account: bool,
    ) -> None:
        if source_type != "manual":
            raise TransactionValidationError(DenialReason.ACTION_NOT_ALLOWED)
        if counterparty_account_id is None:
            raise TransactionTransferCounterpartyRequiredError()
        if same_account:
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)
        if category_id is not None:
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)

    def _validate_manual_non_transfer_shape(
        self,
        *,
        transaction_type: str,
        source_type: str,
        counterparty_account_id: str | None,
        category_id: str | None,
    ) -> None:
        if source_type != "manual":
            raise TransactionValidationError(DenialReason.ACTION_NOT_ALLOWED)
        if transaction_type == "transfer":
            raise TransactionValidationError(DenialReason.TRANSFER_SCOPE_NOT_SUPPORTED)
        category_required_types = {"income", "expense"}
        categoryless_types = {
            "brokerage",
            "asset_buy",
            "asset_sell",
            "interest",
            "dividend",
            "adjustment",
        }
        if transaction_type not in category_required_types | categoryless_types:
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)
        if counterparty_account_id is not None:
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)
        if transaction_type in category_required_types and category_id is None:
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)
        if transaction_type in categoryless_types and category_id is not None:
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)

    def _validate_currency(self, account: AccountRecord, currency: str) -> None:
        if account.currency != currency:
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)

    def _validate_transfer_currency(
        self,
        source: AccountRecord,
        counterparty: AccountRecord,
        currency: str,
    ) -> None:
        if source.currency != currency or counterparty.currency != currency:
            raise TransactionInvalidCurrencyError()

    def _apply_transfer_balance_delta(
        self,
        source: AccountRecord,
        counterparty: AccountRecord,
        amount: Decimal,
        *,
        posting: bool,
    ) -> None:
        source_delta = -amount if posting else amount
        counterparty_delta = amount if posting else -amount
        self._accounts.save(replace(source, current_balance=source.current_balance + source_delta))
        self._accounts.save(
            replace(
                counterparty,
                current_balance=counterparty.current_balance + counterparty_delta,
            )
        )

    def _record_sync_change(
        self,
        *,
        actor: Actor,
        operation: str,
        record: TransactionRecord,
        changed_account_ids: tuple[str, ...] | None = None,
    ) -> None:
        if self._sync_change_recorder is None:
            return
        account = self._accounts.get(record.account_id)
        if account is None:
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)
        self._sync_change_recorder.record_transaction_change(
            actor_user_id=actor.user_id,
            operation=operation,
            record=record,
            account=account,
        )
        if record.transaction_type != "transfer":
            return
        account_ids = changed_account_ids or (
            record.account_id,
            record.counterparty_account_id,
        )
        seen_account_ids: set[str] = set()
        for account_id in account_ids:
            if account_id is None or account_id in seen_account_ids:
                continue
            changed_account = self._accounts.get(account_id)
            if changed_account is None:
                raise TransactionValidationError(DenialReason.VALIDATION_FAILED)
            seen_account_ids.add(account_id)
            self._sync_change_recorder.record_account_change(
                actor_user_id=actor.user_id,
                operation="update",
                record=changed_account,
            )


def _authz_account(record: AccountRecord) -> AuthzAccount:
    return AuthzAccount(
        id=record.id,
        ownership_type=record.ownership_type,
        owner_user_id=record.owner_user_id,
        household_id=record.household_id,
        status=record.status,
    )


def _authz_category(record: CategoryRecord) -> AuthzCategory:
    return AuthzCategory(
        id=record.id,
        scope=(
            AuthzCategoryScope.PERSONAL
            if record.scope == CategoryScope.PERSONAL
            else AuthzCategoryScope.HOUSEHOLD
        ),
        owner_user_id=record.owner_user_id,
        household_id=record.household_id,
        kind=CategoryKind(record.type.value),
        status={
            CategoryRecordStatus.ACTIVE: ResourceStatus.ACTIVE,
            CategoryRecordStatus.ARCHIVED: ResourceStatus.ARCHIVED,
            CategoryRecordStatus.DELETED: ResourceStatus.DELETED,
        }[record.status],
    )


def _service_error_for_decision(reason: DenialReason | None) -> TransactionServiceError:
    if reason == DenialReason.RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE:
        return TransactionNotFoundOrInaccessible()
    if reason == DenialReason.REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE:
        return TransactionReferencedResourceError()
    return TransactionValidationError(reason or DenialReason.ACTION_NOT_ALLOWED)


def _decode_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        value = int(cursor)
    except ValueError as exc:
        raise TransactionValidationError(DenialReason.VALIDATION_FAILED) from exc
    if value < 0:
        raise TransactionValidationError(DenialReason.VALIDATION_FAILED)
    return value


def _date_fields_for_create(request: TransactionCreateRequest) -> tuple[date, datetime]:
    if request.transaction_date is not None:
        return request.transaction_date, _stable_utc_noon(request.transaction_date)
    if request.occurred_at is None:
        raise TransactionValidationError(DenialReason.VALIDATION_FAILED)
    occurred_at = _utc(request.occurred_at)
    return occurred_at.date(), occurred_at


def _date_fields_for_update(
    record: TransactionRecord,
    request: TransactionUpdateRequest,
) -> tuple[date, datetime]:
    if "transaction_date" in request.model_fields_set:
        if request.transaction_date is None:
            raise TransactionValidationError(DenialReason.VALIDATION_FAILED)
        return request.transaction_date, _stable_utc_noon(request.transaction_date)
    if request.occurred_at is not None:
        occurred_at = _utc(request.occurred_at)
        return occurred_at.date(), occurred_at
    if record.transaction_date is not None:
        return record.transaction_date, record.occurred_at
    occurred_at = _utc(record.occurred_at)
    return occurred_at.date(), occurred_at


def _stable_utc_noon(value: date) -> datetime:
    return datetime.combine(value, time(hour=12), tzinfo=UTC)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


service = TransactionService()
