from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.accounts.repository import SqlAlchemyAccountRepository
from app.api.auth_context import CurrentActor
from app.authz import DenialReason
from app.categories.repository import SqlAlchemyCategoryRepository
from app.config import get_settings
from app.db.session import accounts_categories_repository_mode, sync_session_scope
from app.transactions.repository import SqlAlchemyTransactionRepository
from app.transactions.service import TransactionService

from .repository import CaptureDraftRecord, SqlAlchemyCaptureDraftRepository
from .schemas import (
    CaptureDraftCreateRequest,
    CaptureDraftDto,
    CaptureDraftEnvelope,
    CaptureDraftPageEnvelope,
    CaptureDraftStatus,
    CaptureDraftUpdateRequest,
    PageInfo,
)
from .service import (
    CaptureDraftConflictError,
    CaptureDraftNotFoundOrInaccessible,
    CaptureDraftReferencedResourceError,
    CaptureDraftService,
    CaptureDraftServiceError,
    CaptureDraftValidationError,
    service,
)

router = APIRouter(prefix="/capture-drafts", tags=["CaptureDrafts"])


def capture_draft_service_for_request() -> Iterator[CaptureDraftService]:
    if accounts_categories_repository_mode() != "db":
        yield service
        return

    with sync_session_scope(get_settings()) as session:
        accounts = SqlAlchemyAccountRepository(session)
        categories = SqlAlchemyCategoryRepository(session)
        yield CaptureDraftService(
            SqlAlchemyCaptureDraftRepository(session),
            TransactionService(
                SqlAlchemyTransactionRepository(session),
                accounts,
                categories,
            ),
        )


CaptureDraftServiceDependency = Annotated[
    CaptureDraftService,
    Depends(capture_draft_service_for_request),
]


def _draft_dto(record: CaptureDraftRecord) -> CaptureDraftDto:
    return CaptureDraftDto(
        id=record.id,
        status=record.status,
        idempotency_key=record.idempotency_key,
        capture_source=record.capture_source,
        captured_at=record.captured_at,
        occurred_at=record.occurred_at,
        amount=record.amount,
        currency=record.currency,
        description=record.description,
        merchant_name=record.merchant_name,
        account_id=record.account_id,
        category_id=record.category_id,
        transaction_id=record.transaction_id,
        confidence=record.confidence,
        source_app_package=record.source_app_package,
        source_app_label=record.source_app_label,
        evidence_hash=record.evidence_hash,
        created_at=record.created_at,
        updated_at=record.updated_at,
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


def _capture_draft_error_response(
    error: CaptureDraftServiceError,
    request_id: str | None,
) -> JSONResponse:
    if isinstance(error, CaptureDraftNotFoundOrInaccessible):
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
            request_id=request_id,
            message="Resource not found or not accessible.",
        )
    if isinstance(error, CaptureDraftReferencedResourceError):
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
            request_id=request_id,
            message="Referenced resource not found or not accessible.",
        )
    if isinstance(error, CaptureDraftConflictError):
        return _error_response(
            status.HTTP_409_CONFLICT,
            error.code or "CAPTURE_DRAFT_NOT_PENDING",
            request_id=request_id,
            message="Capture draft cannot be changed in its current state.",
        )
    if isinstance(error, CaptureDraftValidationError):
        status_code = (
            status.HTTP_409_CONFLICT
            if error.reason == DenialReason.ARCHIVED_RECORD_NOT_MUTABLE
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        return _error_response(
            status_code,
            error.code or error.reason.value.upper(),
            request_id=request_id,
            message="Invalid capture draft request.",
        )
    return _error_response(
        status.HTTP_403_FORBIDDEN,
        error.reason.value.upper(),
        request_id=request_id,
        message="Unable to complete the request.",
    )


@router.post(
    "",
    response_model=CaptureDraftEnvelope,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    operation_id="createCaptureDraft",
)
async def create_capture_draft(
    request: CaptureDraftCreateRequest,
    actor: CurrentActor,
    svc: CaptureDraftServiceDependency,
) -> CaptureDraftEnvelope | JSONResponse:
    try:
        record = svc.create_draft(actor=actor, request=request)
    except CaptureDraftServiceError as error:
        return _capture_draft_error_response(error, actor.request_id)
    return CaptureDraftEnvelope(data=_draft_dto(record))


@router.get(
    "",
    response_model=CaptureDraftPageEnvelope,
    response_model_by_alias=True,
    operation_id="listCaptureDrafts",
)
async def list_capture_drafts(
    actor: CurrentActor,
    svc: CaptureDraftServiceDependency,
    status: CaptureDraftStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CaptureDraftPageEnvelope | JSONResponse:
    try:
        items = svc.list_drafts(
            actor=actor,
            status=str(status) if status else None,
            limit=limit,
        )
    except CaptureDraftServiceError as error:
        return _capture_draft_error_response(error, actor.request_id)
    return CaptureDraftPageEnvelope(
        items=[_draft_dto(item) for item in items],
        page=PageInfo(limit=limit),
    )


@router.patch(
    "/{draftId}",
    response_model=CaptureDraftEnvelope,
    response_model_by_alias=True,
    operation_id="updateCaptureDraft",
)
async def update_capture_draft(
    draftId: str,
    request: CaptureDraftUpdateRequest,
    actor: CurrentActor,
    svc: CaptureDraftServiceDependency,
) -> CaptureDraftEnvelope | JSONResponse:
    try:
        record = svc.update_draft(actor=actor, draft_id=draftId, request=request)
    except CaptureDraftServiceError as error:
        return _capture_draft_error_response(error, actor.request_id)
    return CaptureDraftEnvelope(data=_draft_dto(record))


@router.post(
    "/{draftId}/confirm",
    response_model=CaptureDraftEnvelope,
    response_model_by_alias=True,
    operation_id="confirmCaptureDraft",
)
async def confirm_capture_draft(
    draftId: str,
    actor: CurrentActor,
    svc: CaptureDraftServiceDependency,
) -> CaptureDraftEnvelope | JSONResponse:
    try:
        record = svc.confirm_draft(actor=actor, draft_id=draftId)
    except CaptureDraftServiceError as error:
        return _capture_draft_error_response(error, actor.request_id)
    return CaptureDraftEnvelope(data=_draft_dto(record))


@router.post(
    "/{draftId}/discard",
    response_model=CaptureDraftEnvelope,
    response_model_by_alias=True,
    operation_id="discardCaptureDraft",
)
async def discard_capture_draft(
    draftId: str,
    actor: CurrentActor,
    svc: CaptureDraftServiceDependency,
) -> CaptureDraftEnvelope | JSONResponse:
    try:
        record = svc.discard_draft(actor=actor, draft_id=draftId)
    except CaptureDraftServiceError as error:
        return _capture_draft_error_response(error, actor.request_id)
    return CaptureDraftEnvelope(data=_draft_dto(record))
