from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse

from app.accounts.repository import SqlAlchemyAccountRepository
from app.api.auth_context import CurrentActor
from app.authz import DenialReason
from app.categories.repository import SqlAlchemyCategoryRepository
from app.config import get_settings
from app.db.session import sync_session_scope

from .repository import (
    PlanningAllocationRecord,
    PlanningIncomeSourceRecord,
    SqlAlchemyPlanningRepository,
)
from .schemas import (
    PlanningAllocationCreateRequest,
    PlanningAllocationDto,
    PlanningAllocationEnvelope,
    PlanningAllocationUpdateRequest,
    PlanningIncomeSourceCreateRequest,
    PlanningIncomeSourceDto,
    PlanningIncomeSourceEnvelope,
    PlanningIncomeSourceUpdateRequest,
    PlanningPlanCopyRequest,
    PlanningPlanCreateRequest,
    PlanningPlanDto,
    PlanningPlanEnvelope,
    PlanningPlanSummaryDto,
    PlanningPlanSummaryListEnvelope,
    PlanningSummaryDto,
)
from .service import (
    PlanningAllocationWithAmount,
    PlanningConflictError,
    PlanningNotFoundOrInaccessible,
    PlanningPlanView,
    PlanningReferencedResourceError,
    PlanningService,
    PlanningServiceError,
    PlanningValidationError,
    effective_income_date,
    plan_month_text,
)

router = APIRouter(prefix="/planning", tags=["Planning"])


def planning_service_for_request() -> Iterator[PlanningService]:
    with sync_session_scope(get_settings()) as session:
        yield PlanningService(
            SqlAlchemyPlanningRepository(session),
            SqlAlchemyAccountRepository(session),
            SqlAlchemyCategoryRepository(session),
        )


PlanningServiceDependency = Annotated[PlanningService, Depends(planning_service_for_request)]
ScopeQuery = Annotated[str, Query(pattern=r"^(personal|household)$")]
MonthQuery = Annotated[str | None, Query(pattern=r"^[0-9]{4}-[0-9]{2}$")]
HouseholdIdQuery = Annotated[str | None, Query(alias="householdId", min_length=1, max_length=128)]


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


def _planning_error_response(error: PlanningServiceError, request_id: str | None) -> JSONResponse:
    if isinstance(error, PlanningNotFoundOrInaccessible):
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
            request_id=request_id,
            message="Resource not found or not accessible.",
        )
    if isinstance(error, PlanningReferencedResourceError):
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
            request_id=request_id,
            message="Referenced resource not found or not accessible.",
        )
    if isinstance(error, PlanningConflictError):
        return _error_response(
            status.HTTP_409_CONFLICT,
            error.code or "CONFLICTING_UPDATE",
            request_id=request_id,
            message="Planning resource conflict.",
        )
    if isinstance(error, PlanningValidationError):
        status_code = (
            status.HTTP_409_CONFLICT
            if error.reason == DenialReason.ARCHIVED_RECORD_NOT_MUTABLE
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        return _error_response(
            status_code,
            error.code or error.reason.value.upper(),
            request_id=request_id,
            message="Invalid planning request.",
        )
    return _error_response(
        status.HTTP_403_FORBIDDEN,
        error.reason.value.upper(),
        request_id=request_id,
        message="Unable to complete the request.",
    )


def _summary_dto(view: PlanningPlanView) -> PlanningSummaryDto:
    return PlanningSummaryDto(
        total_planned_income=view.summary.total_planned_income,
        total_confirmed_income=view.summary.total_confirmed_income,
        total_allocated_amount=view.summary.total_allocated_amount,
        unallocated_amount=view.summary.unallocated_amount,
        underallocated=view.summary.underallocated,
        overallocated=view.summary.overallocated,
    )


def _income_dto(
    record: PlanningIncomeSourceRecord,
    *,
    plan_month,
) -> PlanningIncomeSourceDto:
    return PlanningIncomeSourceDto(
        id=record.id,
        plan_id=record.plan_id,
        amount=record.amount,
        source=record.source,
        description=record.description,
        day_of_month=record.day_of_month,
        effective_date=effective_income_date(plan_month, record.day_of_month),
        confirmation_state=record.confirmation_state,
        confirmed_at=record.confirmed_at,
        confirmed_by_user_id=record.confirmed_by_user_id,
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        version=record.version,
    )


def _allocation_dto(item: PlanningAllocationWithAmount) -> PlanningAllocationDto:
    record = item.record
    return PlanningAllocationDto(
        id=record.id,
        plan_id=record.plan_id,
        target_type=record.target_type,
        target_id=record.target_id,
        target_snapshot=record.target_snapshot,
        requires_attention=record.requires_attention,
        attention_reason=record.attention_reason,
        comment=record.comment,
        allocation_mode=record.allocation_mode,
        allocation_value=record.allocation_value,
        calculated_amount=item.calculated_amount,
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        version=record.version,
    )


def _plan_dto(view: PlanningPlanView) -> PlanningPlanDto:
    plan = view.plan
    return PlanningPlanDto(
        id=plan.id,
        scope=plan.scope_type,
        owner_user_id=plan.owner_user_id,
        household_id=plan.household_id,
        month=plan_month_text(plan.plan_month),
        currency=plan.currency,
        income_sources=[
            _income_dto(income, plan_month=plan.plan_month) for income in view.income_sources
        ],
        allocations=[_allocation_dto(allocation) for allocation in view.allocations],
        summary=_summary_dto(view),
        created_by_user_id=plan.created_by_user_id,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        version=plan.version,
    )


def _plan_summary_dto(view: PlanningPlanView) -> PlanningPlanSummaryDto:
    plan = view.plan
    return PlanningPlanSummaryDto(
        id=plan.id,
        scope=plan.scope_type,
        owner_user_id=plan.owner_user_id,
        household_id=plan.household_id,
        month=plan_month_text(plan.plan_month),
        currency=plan.currency,
        summary=_summary_dto(view),
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        version=plan.version,
    )


def _single_income_view(
    svc: PlanningService,
    *,
    actor,
    plan_id: str,
    record: PlanningIncomeSourceRecord,
) -> PlanningIncomeSourceDto:
    view = svc.get_plan(actor=actor, plan_id=plan_id)
    return _income_dto(record, plan_month=view.plan.plan_month)


def _single_allocation_view(
    svc: PlanningService,
    *,
    actor,
    plan_id: str,
    record: PlanningAllocationRecord,
) -> PlanningAllocationDto:
    view = svc.get_plan(actor=actor, plan_id=plan_id)
    for item in view.allocations:
        if item.record.id == record.id:
            return _allocation_dto(item)
    raise PlanningNotFoundOrInaccessible()


@router.get(
    "/plans",
    response_model=PlanningPlanEnvelope,
    response_model_by_alias=True,
    operation_id="getPlanningPlanForScopeMonth",
)
async def get_planning_plan_for_scope_month(
    actor: CurrentActor,
    svc: PlanningServiceDependency,
    scope: ScopeQuery,
    month: MonthQuery = None,
    household_id: HouseholdIdQuery = None,
) -> PlanningPlanEnvelope | JSONResponse:
    try:
        view = svc.get_plan_for_scope_month(
            actor=actor,
            scope=scope,
            household_id=household_id,
            month=month,
        )
    except PlanningServiceError as error:
        return _planning_error_response(error, actor.request_id)
    return PlanningPlanEnvelope(data=_plan_dto(view))


@router.get(
    "/plans/history",
    response_model=PlanningPlanSummaryListEnvelope,
    response_model_by_alias=True,
    operation_id="listPlanningPlanHistory",
)
async def list_planning_plan_history(
    actor: CurrentActor,
    svc: PlanningServiceDependency,
    scope: ScopeQuery,
    household_id: HouseholdIdQuery = None,
) -> PlanningPlanSummaryListEnvelope | JSONResponse:
    try:
        views = svc.history(actor=actor, scope=scope, household_id=household_id)
    except PlanningServiceError as error:
        return _planning_error_response(error, actor.request_id)
    return PlanningPlanSummaryListEnvelope(items=[_plan_summary_dto(view) for view in views])


@router.post(
    "/plans",
    response_model=PlanningPlanEnvelope,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    operation_id="createPlanningPlan",
)
async def create_planning_plan(
    request: PlanningPlanCreateRequest,
    actor: CurrentActor,
    svc: PlanningServiceDependency,
) -> PlanningPlanEnvelope | JSONResponse:
    try:
        view = svc.create_plan(actor=actor, request=request)
    except PlanningServiceError as error:
        return _planning_error_response(error, actor.request_id)
    return PlanningPlanEnvelope(data=_plan_dto(view))


@router.get(
    "/plans/{planId}",
    response_model=PlanningPlanEnvelope,
    response_model_by_alias=True,
    operation_id="getPlanningPlan",
)
async def get_planning_plan(
    planId: str,
    actor: CurrentActor,
    svc: PlanningServiceDependency,
) -> PlanningPlanEnvelope | JSONResponse:
    try:
        view = svc.get_plan(actor=actor, plan_id=planId)
    except PlanningServiceError as error:
        return _planning_error_response(error, actor.request_id)
    return PlanningPlanEnvelope(data=_plan_dto(view))


@router.post(
    "/plans/{planId}/income-sources",
    response_model=PlanningIncomeSourceEnvelope,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    operation_id="createPlanningIncomeSource",
)
async def create_planning_income_source(
    planId: str,
    request: PlanningIncomeSourceCreateRequest,
    actor: CurrentActor,
    svc: PlanningServiceDependency,
) -> PlanningIncomeSourceEnvelope | JSONResponse:
    try:
        record = svc.add_income_source(actor=actor, plan_id=planId, request=request)
        data = _single_income_view(svc, actor=actor, plan_id=record.plan_id, record=record)
    except PlanningServiceError as error:
        return _planning_error_response(error, actor.request_id)
    return PlanningIncomeSourceEnvelope(data=data)


@router.patch(
    "/income-sources/{incomeSourceId}",
    response_model=PlanningIncomeSourceEnvelope,
    response_model_by_alias=True,
    operation_id="updatePlanningIncomeSource",
)
async def update_planning_income_source(
    incomeSourceId: str,
    request: PlanningIncomeSourceUpdateRequest,
    actor: CurrentActor,
    svc: PlanningServiceDependency,
) -> PlanningIncomeSourceEnvelope | JSONResponse:
    try:
        record = svc.update_income_source(
            actor=actor,
            income_source_id=incomeSourceId,
            request=request,
        )
        data = _single_income_view(svc, actor=actor, plan_id=record.plan_id, record=record)
    except PlanningServiceError as error:
        return _planning_error_response(error, actor.request_id)
    return PlanningIncomeSourceEnvelope(data=data)


@router.post(
    "/income-sources/{incomeSourceId}/confirm",
    response_model=PlanningIncomeSourceEnvelope,
    response_model_by_alias=True,
    operation_id="confirmPlanningIncomeSource",
)
async def confirm_planning_income_source(
    incomeSourceId: str,
    actor: CurrentActor,
    svc: PlanningServiceDependency,
) -> PlanningIncomeSourceEnvelope | JSONResponse:
    try:
        record = svc.confirm_income_source(actor=actor, income_source_id=incomeSourceId)
        data = _single_income_view(svc, actor=actor, plan_id=record.plan_id, record=record)
    except PlanningServiceError as error:
        return _planning_error_response(error, actor.request_id)
    return PlanningIncomeSourceEnvelope(data=data)


@router.delete(
    "/income-sources/{incomeSourceId}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deletePlanningIncomeSource",
)
async def delete_planning_income_source(
    incomeSourceId: str,
    actor: CurrentActor,
    svc: PlanningServiceDependency,
):
    try:
        svc.delete_income_source(actor=actor, income_source_id=incomeSourceId)
    except PlanningServiceError as error:
        return _planning_error_response(error, actor.request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/plans/{planId}/allocations",
    response_model=PlanningAllocationEnvelope,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    operation_id="createPlanningAllocation",
)
async def create_planning_allocation(
    planId: str,
    request: PlanningAllocationCreateRequest,
    actor: CurrentActor,
    svc: PlanningServiceDependency,
) -> PlanningAllocationEnvelope | JSONResponse:
    try:
        record = svc.add_allocation(actor=actor, plan_id=planId, request=request)
        data = _single_allocation_view(svc, actor=actor, plan_id=record.plan_id, record=record)
    except PlanningServiceError as error:
        return _planning_error_response(error, actor.request_id)
    return PlanningAllocationEnvelope(data=data)


@router.patch(
    "/allocations/{allocationId}",
    response_model=PlanningAllocationEnvelope,
    response_model_by_alias=True,
    operation_id="updatePlanningAllocation",
)
async def update_planning_allocation(
    allocationId: str,
    request: PlanningAllocationUpdateRequest,
    actor: CurrentActor,
    svc: PlanningServiceDependency,
) -> PlanningAllocationEnvelope | JSONResponse:
    try:
        record = svc.update_allocation(actor=actor, allocation_id=allocationId, request=request)
        data = _single_allocation_view(svc, actor=actor, plan_id=record.plan_id, record=record)
    except PlanningServiceError as error:
        return _planning_error_response(error, actor.request_id)
    return PlanningAllocationEnvelope(data=data)


@router.delete(
    "/allocations/{allocationId}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deletePlanningAllocation",
)
async def delete_planning_allocation(
    allocationId: str,
    actor: CurrentActor,
    svc: PlanningServiceDependency,
):
    try:
        svc.delete_allocation(actor=actor, allocation_id=allocationId)
    except PlanningServiceError as error:
        return _planning_error_response(error, actor.request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/plans/{planId}/copy",
    response_model=PlanningPlanEnvelope,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    operation_id="copyPlanningPlan",
)
async def copy_planning_plan(
    planId: str,
    request: PlanningPlanCopyRequest,
    actor: CurrentActor,
    svc: PlanningServiceDependency,
) -> PlanningPlanEnvelope | JSONResponse:
    try:
        view = svc.copy_plan(actor=actor, plan_id=planId, request=request)
    except PlanningServiceError as error:
        return _planning_error_response(error, actor.request_id)
    return PlanningPlanEnvelope(data=_plan_dto(view))
