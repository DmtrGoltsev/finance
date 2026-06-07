from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse

from app.api.auth_context import CurrentActor
from app.asset_categories.repository import SqlAlchemyAssetCategoryRepository
from app.authz import AccountOwnershipType, DenialReason, ResourceStatus
from app.config import get_settings
from app.db.session import accounts_categories_repository_mode, sync_session_scope
from app.transactions.repository import SqlAlchemyTransactionRepository

from .repository import AccountRecord, SqlAlchemyAccountRepository
from .schemas import (
    AccountAutocompleteDto,
    AccountAutocompleteListEnvelope,
    AccountCreateRequest,
    AccountDto,
    AccountEnvelope,
    AccountPageEnvelope,
    AccountUpdateRequest,
    PageInfo,
)
from .service import (
    AccountConflictError,
    AccountNotFoundOrInaccessible,
    AccountService,
    AccountServiceError,
    AccountValidationError,
    account_service,
)

router = APIRouter(prefix="/accounts", tags=["Accounts"])


def account_service_for_request() -> Iterator[AccountService]:
    if accounts_categories_repository_mode() != "db":
        yield account_service
        return

    with sync_session_scope(get_settings()) as session:
        yield AccountService(
            SqlAlchemyAccountRepository(session),
            SqlAlchemyTransactionRepository(session),
            SqlAlchemyAssetCategoryRepository(session),
        )


AccountServiceDependency = Annotated[AccountService, Depends(account_service_for_request)]


def _account_dto(record: AccountRecord) -> AccountDto:
    return AccountDto(
        id=record.id,
        name=record.name,
        account_type=record.account_type,
        ownership_type=record.ownership_type.value,
        owner_user_id=record.owner_user_id,
        household_id=record.household_id,
        asset_category_id=record.asset_category_id,
        currency=record.currency,
        initial_balance=record.initial_balance,
        current_balance=record.current_balance,
        status=record.status.value,
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        archived_at=record.archived_at,
        deleted_at=record.deleted_at,
        version=record.version,
    )


def _autocomplete_dto(record: AccountRecord) -> AccountAutocompleteDto:
    return AccountAutocompleteDto(
        id=record.id,
        name=record.name,
        account_type=record.account_type,
        ownership_type=record.ownership_type.value,
        household_id=record.household_id,
        currency=record.currency,
    )


def _error_response(
    status_code: int,
    code: str,
    *,
    request_id: str | None,
    message: str = "Unable to complete the request.",
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


def _account_error_response(error: AccountServiceError, request_id: str | None) -> JSONResponse:
    if isinstance(error, AccountNotFoundOrInaccessible):
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            DenialReason.RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE.value.upper(),
            request_id=request_id,
            message="Resource not found or not accessible.",
        )
    if isinstance(error, AccountValidationError):
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            error.reason.value.upper(),
            request_id=request_id,
            message="Invalid account request.",
        )
    if isinstance(error, AccountConflictError):
        return _error_response(
            status.HTTP_409_CONFLICT,
            error.code,
            request_id=request_id,
            message=error.message,
        )

    status_code = (
        status.HTTP_409_CONFLICT
        if error.reason
        in {
            DenialReason.ARCHIVED_RECORD_NOT_MUTABLE,
            DenialReason.ACCOUNT_OWNERSHIP_IMMUTABLE,
        }
        else status.HTTP_403_FORBIDDEN
    )
    return _error_response(
        status_code,
        error.reason.value.upper(),
        request_id=request_id,
    )


@router.get(
    "",
    response_model=AccountPageEnvelope,
    response_model_by_alias=True,
    operation_id="listAccounts",
)
async def list_accounts(
    actor: CurrentActor,
    service: AccountServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1)] = None,
    ownershipType: AccountOwnershipType | None = None,
    householdId: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    status: ResourceStatus | None = None,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    sort: Annotated[str | None, Query(min_length=1)] = None,
) -> AccountPageEnvelope:
    try:
        items, next_cursor, has_more = service.list_accounts(
            actor=actor,
            limit=limit,
            cursor=cursor,
            ownership_type=ownershipType,
            household_id=householdId,
            status=status,
            q=q,
            sort=sort,
        )
    except AccountServiceError as error:
        return _account_error_response(error, actor.request_id)

    return AccountPageEnvelope(
        items=[_account_dto(item) for item in items],
        page=PageInfo(limit=limit, next_cursor=next_cursor, has_more=has_more),
    )


@router.post(
    "",
    response_model=AccountEnvelope,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    operation_id="createAccount",
)
async def create_account(
    request: AccountCreateRequest,
    actor: CurrentActor,
    service: AccountServiceDependency,
) -> AccountEnvelope:
    try:
        record = service.create_account(actor=actor, request=request)
    except AccountServiceError as error:
        return _account_error_response(error, actor.request_id)

    return AccountEnvelope(data=_account_dto(record))


@router.get(
    "/autocomplete",
    response_model=AccountAutocompleteListEnvelope,
    response_model_by_alias=True,
    operation_id="autocompleteAccounts",
)
async def autocomplete_accounts(
    actor: CurrentActor,
    service: AccountServiceDependency,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ownershipType: AccountOwnershipType | None = None,
    householdId: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
) -> AccountAutocompleteListEnvelope:
    try:
        items = service.autocomplete_accounts(
            actor=actor,
            limit=limit,
            ownership_type=ownershipType,
            household_id=householdId,
            q=q,
        )
    except AccountServiceError as error:
        return _account_error_response(error, actor.request_id)

    return AccountAutocompleteListEnvelope(items=[_autocomplete_dto(item) for item in items])


@router.get(
    "/{accountId}",
    response_model=AccountEnvelope,
    response_model_by_alias=True,
    operation_id="getAccount",
)
async def get_account(
    accountId: str,
    actor: CurrentActor,
    service: AccountServiceDependency,
) -> AccountEnvelope:
    try:
        record = service.get_account(actor=actor, account_id=accountId)
    except AccountServiceError as error:
        return _account_error_response(error, actor.request_id)
    return AccountEnvelope(data=_account_dto(record))


@router.patch(
    "/{accountId}",
    response_model=AccountEnvelope,
    response_model_by_alias=True,
    operation_id="updateAccount",
)
async def update_account(
    accountId: str,
    request: AccountUpdateRequest,
    actor: CurrentActor,
    service: AccountServiceDependency,
) -> AccountEnvelope:
    try:
        record = service.update_account(actor=actor, account_id=accountId, request=request)
    except AccountServiceError as error:
        return _account_error_response(error, actor.request_id)
    return AccountEnvelope(data=_account_dto(record))


@router.delete(
    "/{accountId}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteAccount",
)
async def delete_account(
    accountId: str,
    actor: CurrentActor,
    service: AccountServiceDependency,
) -> Response:
    try:
        service.delete_account(actor=actor, account_id=accountId)
    except AccountServiceError as error:
        return _account_error_response(error, actor.request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{accountId}/archive",
    response_model=AccountEnvelope,
    response_model_by_alias=True,
    operation_id="archiveAccount",
)
async def archive_account(
    accountId: str,
    actor: CurrentActor,
    service: AccountServiceDependency,
) -> AccountEnvelope:
    try:
        record = service.archive_account(actor=actor, account_id=accountId)
    except AccountServiceError as error:
        return _account_error_response(error, actor.request_id)
    return AccountEnvelope(data=_account_dto(record))


@router.post(
    "/{accountId}/restore",
    response_model=AccountEnvelope,
    response_model_by_alias=True,
    operation_id="restoreAccount",
)
async def restore_account(
    accountId: str,
    actor: CurrentActor,
    service: AccountServiceDependency,
) -> AccountEnvelope:
    try:
        record = service.restore_account(actor=actor, account_id=accountId)
    except AccountServiceError as error:
        return _account_error_response(error, actor.request_id)
    return AccountEnvelope(data=_account_dto(record))
