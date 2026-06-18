from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.api.auth_context import CurrentActor
from app.api.error_contract import error_response, request_id_for
from app.config import get_settings
from app.db.session import sync_session_scope

from .schemas import SyncPullRequest, SyncPullResponse, SyncPushRequest, SyncPushResponse
from .service import SyncIdempotencyKeyReused, SyncService, SyncServiceError, SyncValidationError

router = APIRouter(prefix="/sync", tags=["Sync"])


def sync_service_for_request() -> Iterator[SyncService]:
    with sync_session_scope(get_settings()) as session:
        yield SyncService(session)


SyncServiceDependency = Annotated[SyncService, Depends(sync_service_for_request)]


@router.post(
    "/push",
    response_model=SyncPushResponse,
    response_model_by_alias=True,
    operation_id="syncPush",
)
async def sync_push(
    body: SyncPushRequest,
    request: Request,
    actor: CurrentActor,
    svc: SyncServiceDependency,
) -> SyncPushResponse | JSONResponse:
    try:
        return svc.push(actor=actor, request=body)
    except SyncIdempotencyKeyReused as error:
        return _sync_error_response(
            status.HTTP_409_CONFLICT,
            error,
            request=request,
        )
    except SyncValidationError as error:
        return _sync_error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            error,
            request=request,
        )


@router.post(
    "/pull",
    response_model=SyncPullResponse,
    response_model_by_alias=True,
    operation_id="syncPull",
)
async def sync_pull(
    body: SyncPullRequest,
    request: Request,
    actor: CurrentActor,
    svc: SyncServiceDependency,
) -> SyncPullResponse | JSONResponse:
    try:
        return svc.pull(actor=actor, request=body)
    except SyncValidationError as error:
        return _sync_error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            error,
            request=request,
        )


def _sync_error_response(
    status_code: int,
    error: SyncServiceError,
    *,
    request: Request,
) -> JSONResponse:
    return error_response(
        status_code=status_code,
        request_id=request_id_for(request),
        code=error.code,
        message=error.message,
    )

