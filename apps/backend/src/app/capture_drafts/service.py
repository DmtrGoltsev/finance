from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time
from decimal import Decimal
from threading import RLock

from app.authz import Actor, DenialReason
from app.transactions.schemas import SourceType, TransactionCreateRequest, TransactionType
from app.transactions.service import (
    TransactionConflictError,
    TransactionReferencedResourceError,
    TransactionService,
    TransactionServiceError,
    TransactionValidationError,
)
from app.transactions.service import (
    service as transaction_service,
)

from .repository import (
    CaptureDraftCreateValues,
    CaptureDraftRecord,
    CaptureDraftRepository,
    repository,
)
from .schemas import CaptureDraftCreateRequest, CaptureDraftUpdateRequest


class CaptureDraftServiceError(Exception):
    def __init__(self, reason: DenialReason, *, code: str | None = None) -> None:
        self.reason = reason
        self.code = code


class CaptureDraftNotFoundOrInaccessible(CaptureDraftServiceError):
    def __init__(self) -> None:
        super().__init__(DenialReason.RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE)


class CaptureDraftReferencedResourceError(CaptureDraftServiceError):
    def __init__(self) -> None:
        super().__init__(DenialReason.REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE)


class CaptureDraftValidationError(CaptureDraftServiceError):
    pass


class CaptureDraftConflictError(CaptureDraftServiceError):
    def __init__(self, code: str = "CAPTURE_DRAFT_NOT_PENDING") -> None:
        super().__init__(DenialReason.ACTION_NOT_ALLOWED, code=code)


class CaptureDraftService:
    def __init__(
        self,
        drafts: CaptureDraftRepository = repository,
        transactions: TransactionService = transaction_service,
    ) -> None:
        self._drafts = drafts
        self._transactions = transactions
        self._confirm_lock = RLock()

    def create_draft(
        self,
        *,
        actor: Actor,
        request: CaptureDraftCreateRequest,
    ) -> CaptureDraftRecord:
        owner_user_id = _require_user_id(actor)
        self._validate_referenced_resources(
            actor=actor,
            account_id=request.account_id,
            category_id=request.category_id,
            currency=request.currency,
        )
        values = CaptureDraftCreateValues(
            owner_user_id=owner_user_id,
            idempotency_key=request.idempotency_key,
            capture_source=str(request.capture_source),
            captured_at=_utc(request.captured_at),
            occurred_at=_occurred_at_from_date_fields(
                occurred_date=request.occurred_date,
                occurred_at=request.occurred_at,
            ),
            occurred_date=_occurred_date_from_date_fields(
                occurred_date=request.occurred_date,
                occurred_at=request.occurred_at,
            ),
            amount=Decimal(request.amount),
            currency=request.currency,
            description=request.description,
            merchant_name=request.merchant_name,
            account_id=request.account_id,
            category_id=request.category_id,
            confidence=Decimal(request.confidence) if request.confidence is not None else None,
            source_app_package=request.source_app_package,
            source_app_label=request.source_app_label,
            evidence_hash=request.evidence_hash,
        )
        return self._drafts.create_or_get_existing(values)

    def list_drafts(
        self,
        *,
        actor: Actor,
        status: str | None,
        limit: int,
    ) -> list[CaptureDraftRecord]:
        return self._drafts.list_by_owner(
            owner_user_id=_require_user_id(actor),
            status=status,
            limit=limit,
        )

    def update_draft(
        self,
        *,
        actor: Actor,
        draft_id: str,
        request: CaptureDraftUpdateRequest,
    ) -> CaptureDraftRecord:
        record = self._require_owned_draft(actor=actor, draft_id=draft_id)
        _require_pending(record)

        updated = record
        fields_set = request.model_fields_set
        if "occurred_date" in fields_set:
            updated = replace(
                updated,
                occurred_date=request.occurred_date,
                occurred_at=(
                    _stable_utc_noon(request.occurred_date)
                    if request.occurred_date is not None
                    else None
                ),
            )
        elif "occurred_at" in fields_set:
            occurred_at = _utc(request.occurred_at) if request.occurred_at else None
            updated = replace(
                updated,
                occurred_at=occurred_at,
                occurred_date=occurred_at.date() if occurred_at is not None else None,
            )
        if request.amount is not None:
            updated = replace(updated, amount=Decimal(request.amount))
        if request.currency is not None:
            updated = replace(updated, currency=request.currency)
        if request.description is not None:
            updated = replace(updated, description=request.description)
        if "merchant_name" in fields_set:
            updated = replace(updated, merchant_name=request.merchant_name)
        if "account_id" in fields_set:
            updated = replace(updated, account_id=request.account_id)
        if "category_id" in fields_set:
            updated = replace(updated, category_id=request.category_id)
        if "confidence" in fields_set:
            updated = replace(
                updated,
                confidence=Decimal(request.confidence) if request.confidence is not None else None,
            )
        if "source_app_package" in fields_set:
            updated = replace(updated, source_app_package=request.source_app_package)
        if "source_app_label" in fields_set:
            updated = replace(updated, source_app_label=request.source_app_label)
        if "evidence_hash" in fields_set:
            updated = replace(updated, evidence_hash=request.evidence_hash)

        self._validate_referenced_resources(
            actor=actor,
            account_id=updated.account_id,
            category_id=updated.category_id,
            currency=updated.currency,
        )
        return self._drafts.save(updated)

    def confirm_draft(self, *, actor: Actor, draft_id: str) -> CaptureDraftRecord:
        with self._confirm_lock:
            return self._confirm_draft_locked(actor=actor, draft_id=draft_id)

    def _confirm_draft_locked(self, *, actor: Actor, draft_id: str) -> CaptureDraftRecord:
        record = self._require_owned_draft(
            actor=actor,
            draft_id=draft_id,
            lock_for_update=True,
        )
        if record.status == "confirmed":
            if record.transaction_id is None:
                raise CaptureDraftConflictError()
            return record
        _require_pending(record)

        if (
            record.account_id is None
            or record.category_id is None
            or not record.description.strip()
            or record.amount <= 0
        ):
            raise CaptureDraftValidationError(
                DenialReason.VALIDATION_FAILED,
                code="CONFIRMATION_FIELDS_REQUIRED",
            )

        transaction_request = TransactionCreateRequest(
            transaction_type=TransactionType.EXPENSE,
            account_id=record.account_id,
            category_id=record.category_id,
            amount=record.amount,
            currency=record.currency,
            occurred_at=record.occurred_at or record.captured_at,
            transaction_date=_transaction_date_for_confirm(record),
            description=record.description,
            source_type=SourceType.MANUAL,
        )
        try:
            transaction = self._transactions.create_transaction(
                actor=actor,
                request=transaction_request,
            )
        except TransactionReferencedResourceError as exc:
            raise CaptureDraftReferencedResourceError() from exc
        except TransactionValidationError as exc:
            raise CaptureDraftValidationError(exc.reason, code=exc.code) from exc
        except TransactionConflictError as exc:
            raise CaptureDraftConflictError(exc.code or "CONFLICTING_UPDATE") from exc
        except TransactionServiceError as exc:
            raise CaptureDraftServiceError(exc.reason, code=exc.code) from exc

        return self._drafts.save(
            replace(record, status="confirmed", transaction_id=transaction.id)
        )

    def discard_draft(self, *, actor: Actor, draft_id: str) -> CaptureDraftRecord:
        record = self._require_owned_draft(actor=actor, draft_id=draft_id)
        _require_pending(record)
        return self._drafts.save(replace(record, status="discarded"))

    def _require_owned_draft(
        self,
        *,
        actor: Actor,
        draft_id: str,
        lock_for_update: bool = False,
    ) -> CaptureDraftRecord:
        owner_user_id = _require_user_id(actor)
        record = self._drafts.get(draft_id, lock_for_update=lock_for_update)
        if record is None or record.owner_user_id != owner_user_id:
            raise CaptureDraftNotFoundOrInaccessible()
        return record

    def _validate_referenced_resources(
        self,
        *,
        actor: Actor,
        account_id: str | None,
        category_id: str | None,
        currency: str | None,
    ) -> None:
        try:
            self._transactions.validate_capture_draft_references(
                actor=actor,
                account_id=account_id,
                category_id=category_id,
                currency=currency,
            )
        except TransactionReferencedResourceError as exc:
            raise CaptureDraftReferencedResourceError() from exc
        except TransactionValidationError as exc:
            raise CaptureDraftValidationError(exc.reason, code=exc.code) from exc
        except TransactionConflictError as exc:
            raise CaptureDraftConflictError(exc.code or "CONFLICTING_UPDATE") from exc
        except TransactionServiceError as exc:
            raise CaptureDraftServiceError(exc.reason, code=exc.code) from exc


def _require_user_id(actor: Actor) -> str:
    if not actor.user_id:
        raise CaptureDraftNotFoundOrInaccessible()
    return actor.user_id


def _require_pending(record: CaptureDraftRecord) -> None:
    if record.status != "pending":
        raise CaptureDraftConflictError()


def _occurred_date_from_date_fields(
    *,
    occurred_date: date | None,
    occurred_at: datetime | None,
) -> date | None:
    if occurred_date is not None:
        return occurred_date
    if occurred_at is None:
        return None
    return _utc(occurred_at).date()


def _occurred_at_from_date_fields(
    *,
    occurred_date: date | None,
    occurred_at: datetime | None,
) -> datetime | None:
    if occurred_date is not None:
        return _stable_utc_noon(occurred_date)
    if occurred_at is None:
        return None
    return _utc(occurred_at)


def _transaction_date_for_confirm(record: CaptureDraftRecord) -> date:
    if record.occurred_date is not None:
        return record.occurred_date
    if record.occurred_at is not None:
        return _utc(record.occurred_at).date()
    return _utc(record.captured_at).date()


def _stable_utc_noon(value: date) -> datetime:
    return datetime.combine(value, time(hour=12), tzinfo=UTC)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


service = CaptureDraftService()
