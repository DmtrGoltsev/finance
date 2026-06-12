from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse

from app.accounts.repository import SqlAlchemyAccountRepository
from app.api.auth_context import CurrentActor
from app.authz import DenialReason
from app.categories.repository import SqlAlchemyCategoryRepository
from app.config import get_settings
from app.db.session import accounts_categories_repository_mode, sync_session_scope

from .repository import (
    SqlAlchemyTransactionRepository,
    TransactionRecord,
    transaction_record_date,
)
from .schemas import (
    OwnershipType,
    PageInfo,
    RecordStatus,
    SortOrder,
    TransactionAutocompleteDto,
    TransactionAutocompleteListEnvelope,
    TransactionCreateRequest,
    TransactionDto,
    TransactionEnvelope,
    TransactionPageEnvelope,
    TransactionType,
    TransactionUpdateRequest,
)
from .service import (
    TransactionConflictError,
    TransactionNotFoundOrInaccessible,
    TransactionReferencedResourceError,
    TransactionService,
    TransactionServiceError,
    TransactionValidationError,
    service,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


def transaction_service_for_request() -> Iterator[TransactionService]:
    if accounts_categories_repository_mode() != "db":
        yield service
        return

    with sync_session_scope(get_settings()) as session:
        yield TransactionService(
            SqlAlchemyTransactionRepository(session),
            SqlAlchemyAccountRepository(session),
            SqlAlchemyCategoryRepository(session),
        )


TransactionServiceDependency = Annotated[
    TransactionService,
    Depends(transaction_service_for_request),
]


def _transaction_dto(record: TransactionRecord) -> TransactionDto:
    return TransactionDto(
        id=record.id,
        transaction_type=record.transaction_type,
        account_id=record.account_id,
        counterparty_account_id=record.counterparty_account_id,
        category_id=record.category_id,
        amount=record.amount,
        currency=record.currency,
        occurred_at=record.occurred_at,
        transaction_date=transaction_record_date(record),
        description=record.description,
        source_type=record.source_type,
        transfer_scope=record.transfer_scope,
        transfer_status=record.transfer_status,
        created_by_user_id=record.created_by_user_id,
        last_edited_by_user_id=record.last_edited_by_user_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        deleted_at=record.deleted_at,
        version=record.version,
    )


def _autocomplete_dto(record: TransactionRecord) -> TransactionAutocompleteDto:
    return TransactionAutocompleteDto(
        id=record.id,
        transaction_type=record.transaction_type,
        account_id=record.account_id,
        category_id=record.category_id,
        occurred_at=record.occurred_at,
        transaction_date=transaction_record_date(record),
        source_type=record.source_type,
    )


def _error_response(
    status_code: int,
    code: str,
    *,
    request_id: str | None,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "requestId": request_id or "unknown",
            }
        },
    )


def _transaction_error_response(
    error: TransactionServiceError,
    request_id: str | None,
) -> JSONResponse:
    if isinstance(error, TransactionNotFoundOrInaccessible):
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
            request_id=request_id,
            message="Resource not found or not accessible.",
        )
    if isinstance(error, TransactionReferencedResourceError):
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
            request_id=request_id,
            message="Referenced resource not found or not accessible.",
        )
    if isinstance(error, TransactionConflictError):
        return _error_response(
            status.HTTP_409_CONFLICT,
            error.code or "CONFLICTING_UPDATE",
            request_id=request_id,
            message="Conflicting update.",
        )
    if isinstance(error, TransactionValidationError):
        if error.reason == DenialReason.ARCHIVED_RECORD_NOT_MUTABLE:
            status_code = status.HTTP_409_CONFLICT
        elif error.code in {"INVALID_CURRENCY", "TRANSFER_COUNTERPARTY_REQUIRED"}:
            status_code = status.HTTP_400_BAD_REQUEST
        else:
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        return _error_response(
            status_code,
            error.code or error.reason.value.upper(),
            request_id=request_id,
            message="Invalid transaction request.",
        )
    return _error_response(
        status.HTTP_403_FORBIDDEN,
        error.reason.value.upper(),
        request_id=request_id,
        message="Unable to complete the request.",
    )


@router.get(
    "",
    response_model=TransactionPageEnvelope,
    response_model_by_alias=True,
    operation_id="listTransactions",
)
async def list_transactions(
    actor: CurrentActor,
    svc: TransactionServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1)] = None,
    accountId: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    categoryId: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    transactionType: TransactionType | None = None,
    householdId: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    ownershipType: OwnershipType | None = None,
    status: RecordStatus | None = None,
    startDate: Annotated[str | None, Query(min_length=1)] = None,
    endDate: Annotated[str | None, Query(min_length=1)] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    sort: SortOrder | None = None,
) -> TransactionPageEnvelope | JSONResponse:
    try:
        items, next_cursor, has_more = svc.list_transactions(
            actor=actor,
            limit=limit,
            cursor=cursor,
            account_id=accountId,
            category_id=categoryId,
            transaction_type=str(transactionType) if transactionType else None,
            household_id=householdId,
            ownership_type=str(ownershipType) if ownershipType else None,
            status=str(status) if status else None,
            start_date=_date_only(startDate),
            end_date=_date_only(endDate),
            q=q,
            sort=str(sort) if sort else None,
        )
    except TransactionServiceError as error:
        return _transaction_error_response(error, actor.request_id)

    return TransactionPageEnvelope(
        items=[_transaction_dto(item) for item in items],
        page=PageInfo(limit=limit, next_cursor=next_cursor, has_more=has_more),
    )


@router.post(
    "",
    response_model=TransactionEnvelope,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    operation_id="createTransaction",
)
async def create_transaction(
    request: TransactionCreateRequest,
    actor: CurrentActor,
    svc: TransactionServiceDependency,
) -> TransactionEnvelope | JSONResponse:
    try:
        record = svc.create_transaction(actor=actor, request=request)
    except TransactionServiceError as error:
        return _transaction_error_response(error, actor.request_id)
    return TransactionEnvelope(data=_transaction_dto(record))


@router.get(
    "/autocomplete",
    response_model=TransactionAutocompleteListEnvelope,
    response_model_by_alias=True,
    operation_id="autocompleteTransactions",
)
async def autocomplete_transactions(
    actor: CurrentActor,
    svc: TransactionServiceDependency,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TransactionAutocompleteListEnvelope | JSONResponse:
    try:
        items = svc.autocomplete_transactions(actor=actor, limit=limit, q=q)
    except TransactionServiceError as error:
        return _transaction_error_response(error, actor.request_id)
    return TransactionAutocompleteListEnvelope(items=[_autocomplete_dto(item) for item in items])


@router.get(
    "/{transactionId}",
    response_model=TransactionEnvelope,
    response_model_by_alias=True,
    operation_id="getTransaction",
)
async def get_transaction(
    transactionId: str,
    actor: CurrentActor,
    svc: TransactionServiceDependency,
) -> TransactionEnvelope | JSONResponse:
    try:
        record = svc.get_transaction(actor=actor, transaction_id=transactionId)
    except TransactionServiceError as error:
        return _transaction_error_response(error, actor.request_id)
    return TransactionEnvelope(data=_transaction_dto(record))


@router.patch(
    "/{transactionId}",
    response_model=TransactionEnvelope,
    response_model_by_alias=True,
    operation_id="updateTransaction",
)
async def update_transaction(
    transactionId: str,
    request: TransactionUpdateRequest,
    actor: CurrentActor,
    svc: TransactionServiceDependency,
) -> TransactionEnvelope | JSONResponse:
    try:
        record = svc.update_transaction(actor=actor, transaction_id=transactionId, request=request)
    except TransactionServiceError as error:
        return _transaction_error_response(error, actor.request_id)
    return TransactionEnvelope(data=_transaction_dto(record))


@router.delete(
    "/{transactionId}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteTransaction",
)
async def delete_transaction(
    transactionId: str,
    actor: CurrentActor,
    svc: TransactionServiceDependency,
):
    try:
        svc.delete_transaction(actor=actor, transaction_id=transactionId)
    except TransactionServiceError as error:
        return _transaction_error_response(error, actor.request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{transactionId}/restore",
    response_model=TransactionEnvelope,
    response_model_by_alias=True,
    operation_id="restoreTransaction",
)
async def restore_transaction(
    transactionId: str,
    actor: CurrentActor,
    svc: TransactionServiceDependency,
) -> TransactionEnvelope | JSONResponse:
    try:
        record = svc.restore_transaction(actor=actor, transaction_id=transactionId)
    except TransactionServiceError as error:
        return _transaction_error_response(error, actor.request_id)
    return TransactionEnvelope(data=_transaction_dto(record))


def _date_only(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise TransactionValidationError(DenialReason.VALIDATION_FAILED) from exc
