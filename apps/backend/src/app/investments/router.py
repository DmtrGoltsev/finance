from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.auth_context import CurrentActor
from app.config import get_settings
from app.db.session import sync_session_scope

from .hmac_auth import HmacVerificationError, verify_callback
from .models import PortfolioImportModel, PortfolioPositionModel, PortfolioSnapshotModel
from .repository import InvestmentRepository
from .schemas import (
    BrokerageAccountProfileDto,
    BucketAdjustmentDto,
    InvestmentPolicyDto,
    InvestmentPolicyEnvelope,
    InvestmentPolicyPutRequest,
    PageInfo,
    PortfolioImportConfirmRequest,
    PortfolioImportCreateRequest,
    PortfolioImportDto,
    PortfolioImportEnvelope,
    PortfolioPositionDto,
    PortfolioSnapshotDto,
    PortfolioSnapshotEnvelope,
    RecommendationActionDto,
    RecommendationCallbackRequest,
    RecommendationHistoryItemDto,
    RecommendationHistoryPageEnvelope,
    RecommendationJobCreateRequest,
    RecommendationJobDto,
    RecommendationJobEnvelope,
    RecommendationReportDto,
    RecommendationReportEnvelope,
    RecommendationSourceDto,
)
from .service import (
    AccountProfileConflict,
    ConcurrentTransition,
    ConfirmedImportNotDiscardable,
    IdempotencyConflict,
    InvalidObservedAt,
    InvalidPagination,
    InvalidRecommendationPayload,
    InvalidTransition,
    InvestmentService,
    InvestmentServiceError,
    ReplayDetected,
    ResourceNotFoundOrInaccessible,
    StaleMarketData,
    StalePortfolio,
)

router = APIRouter(prefix="/investments", tags=["Investments"])

CALLBACK_OPENAPI_EXTRA = {
    "parameters": [
        {
            "name": "X-Finance-Timestamp",
            "in": "header",
            "required": True,
            "schema": {"type": "string"},
        },
        {
            "name": "X-Finance-Nonce",
            "in": "header",
            "required": True,
            "schema": {"type": "string", "minLength": 16, "maxLength": 128},
        },
        {
            "name": "X-Finance-Signature",
            "in": "header",
            "required": True,
            "schema": {"type": "string", "pattern": "^[a-fA-F0-9]{64}$"},
        },
    ],
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/RecommendationCallbackRequest"}
            }
        },
    },
}


def investment_service_for_request() -> Iterator[InvestmentService]:
    settings = get_settings()
    with sync_session_scope(settings) as session:
        yield InvestmentService(
            InvestmentRepository(session),
            issuer_source_hosts=settings.investment_source_allowed_issuer_hosts,
        )


InvestmentServiceDependency = Annotated[InvestmentService, Depends(investment_service_for_request)]


def _error(error: InvestmentServiceError, request_id: str | None = None) -> JSONResponse:
    if isinstance(error, ResourceNotFoundOrInaccessible):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(
        error,
        (
            IdempotencyConflict,
            InvalidTransition,
            ReplayDetected,
            ConcurrentTransition,
            AccountProfileConflict,
            ConfirmedImportNotDiscardable,
        ),
    ):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(
        error,
        (
            StalePortfolio,
            StaleMarketData,
            InvalidObservedAt,
            InvalidRecommendationPayload,
            InvalidPagination,
        ),
    ):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": error.code,
                "message": "Unable to complete the investment request.",
                "requestId": request_id or "unknown",
            }
        },
    )


def _policy_dto(model: Any) -> InvestmentPolicyDto:
    return InvestmentPolicyDto(
        id=str(model.id),
        owner_user_id=str(model.owner_user_id),
        conservative_percent=model.conservative_percent,
        moderate_percent=model.moderate_percent,
        aggressive_percent=model.aggressive_percent,
        tolerance_percent=model.tolerance_percent,
        created_at=model.created_at,
        updated_at=model.updated_at,
        version=model.version,
    )


def _profile_dto(model: Any | None) -> BrokerageAccountProfileDto | None:
    if model is None:
        return None
    return BrokerageAccountProfileDto(
        id=str(model.id),
        brokerage=model.brokerage,
        user_label=model.user_label,
        account_type=model.account_type,
    )


def _import_dto(service: InvestmentService, model: PortfolioImportModel) -> PortfolioImportDto:
    return PortfolioImportDto(
        id=str(model.id),
        account_profile=_profile_dto(
            service.repo.get_account_profile(model.account_profile_id)
            if model.account_profile_id else None
        ),
        screenshot_count=model.screenshot_count,
        observed_at=model.observed_at,
        status=model.status,
        confirmed_at=model.confirmed_at,
        created_at=model.created_at,
    )


def _position_dto(model: PortfolioPositionModel) -> PortfolioPositionDto:
    return PortfolioPositionDto(
        id=str(model.id),
        instrument_name=model.instrument_name,
        ticker=model.ticker,
        isin=model.isin,
        instrument_type=model.instrument_type,
        risk_bucket=model.risk_bucket,
        quantity=model.quantity,
        market_price=model.market_price,
        market_value=model.market_value,
        average_price=model.average_price,
        nominal=model.nominal,
        accrued_interest=model.accrued_interest,
        coupon_rate=model.coupon_rate,
        maturity_date=model.maturity_date,
        tax_account_type=model.tax_account_type,
        holding_started_at=model.holding_started_at,
        estimated_fee_rate=model.estimated_fee_rate,
    )


def _snapshot_dto(
    service: InvestmentService, model: PortfolioSnapshotModel
) -> PortfolioSnapshotDto:
    return PortfolioSnapshotDto(
        id=str(model.id),
        import_id=str(model.import_id),
        account_profile=_profile_dto(
            service.repo.get_account_profile(model.account_profile_id)
            if model.account_profile_id else None
        ),
        observed_at=model.observed_at,
        currency=model.currency,
        free_cash=model.free_cash,
        monthly_contribution=model.monthly_contribution,
        total_value=model.total_value,
        positions=[_position_dto(item) for item in service.repo.positions(model.id)],
        created_at=model.created_at,
    )


def _job_dto(service: InvestmentService, model: Any) -> RecommendationJobDto:
    return RecommendationJobDto(
        id=str(model.id),
        snapshot_ids=[str(item) for item in service.repo.job_snapshot_ids(model.id)],
        status=model.status,
        attempt_count=model.attempt_count,
        market_data_as_of=model.market_data_as_of,
        cash_first_adjustments=[
            BucketAdjustmentDto(
                risk_bucket=item.bucket,
                add_amount=item.add_amount,
                reduce_amount=item.reduce_amount,
                current_percent=item.current_percent,
                projected_percent=item.projected_percent,
                target_percent=item.target_percent,
                within_tolerance=item.within_tolerance,
            )
            for item in service.cash_first_adjustments(model)
        ],
        created_at=model.created_at,
        updated_at=model.updated_at,
        completed_at=model.completed_at,
    )


def _history_item_dto(
    service: InvestmentService, model: Any
) -> RecommendationHistoryItemDto:
    report = service.repo.report_for_job(model.id)
    return RecommendationHistoryItemDto(
        job=_job_dto(service, model),
        account_profiles=[
            profile
            for account in service.repo.job_account_profiles(model.id)
            if (profile := _profile_dto(account)) is not None
        ],
        report_summary=report.summary if report else None,
        report_path=(
            f"{get_settings().api_v1_prefix}/investments/"
            f"recommendation-jobs/{model.id}/report"
            if report
            else None
        ),
    )


@router.get("/policy", response_model=InvestmentPolicyEnvelope, operation_id="getInvestmentPolicy")
async def get_policy(
    actor: CurrentActor, service: InvestmentServiceDependency
) -> InvestmentPolicyEnvelope:
    return InvestmentPolicyEnvelope(data=_policy_dto(service.policy(actor)))


@router.put("/policy", response_model=InvestmentPolicyEnvelope, operation_id="putInvestmentPolicy")
async def put_policy(
    request: InvestmentPolicyPutRequest,
    actor: CurrentActor,
    service: InvestmentServiceDependency,
) -> InvestmentPolicyEnvelope:
    return InvestmentPolicyEnvelope(data=_policy_dto(service.put_policy(actor, request)))


@router.post(
    "/portfolio-imports",
    response_model=PortfolioImportEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="createPortfolioImport",
)
async def create_portfolio_import(
    request: PortfolioImportCreateRequest,
    actor: CurrentActor,
    service: InvestmentServiceDependency,
) -> PortfolioImportEnvelope | JSONResponse:
    try:
        model = service.create_import(actor, request)
        return PortfolioImportEnvelope(data=_import_dto(service, model))
    except InvestmentServiceError as error:
        return _error(error, actor.request_id)


@router.delete(
    "/portfolio-imports/{importId}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="discardPortfolioImport",
)
async def discard_portfolio_import(
    importId: UUID,
    actor: CurrentActor,
    service: InvestmentServiceDependency,
) -> Response | JSONResponse:
    try:
        service.discard_import(actor, importId)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except InvestmentServiceError as error:
        return _error(error, actor.request_id)


@router.post(
    "/portfolio-imports/{importId}/confirm",
    response_model=PortfolioSnapshotEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="confirmPortfolioImport",
)
async def confirm_portfolio_import(
    importId: UUID,
    request: PortfolioImportConfirmRequest,
    actor: CurrentActor,
    service: InvestmentServiceDependency,
) -> PortfolioSnapshotEnvelope | JSONResponse:
    try:
        model = service.confirm_import(actor, importId, request)
        return PortfolioSnapshotEnvelope(data=_snapshot_dto(service, model))
    except InvestmentServiceError as error:
        return _error(error, actor.request_id)


@router.get(
    "/portfolio-snapshots",
    response_model=list[PortfolioSnapshotDto],
    operation_id="listPortfolioSnapshots",
)
async def list_portfolio_snapshots(
    actor: CurrentActor, service: InvestmentServiceDependency
) -> list[PortfolioSnapshotDto]:
    return [_snapshot_dto(service, item) for item in service.snapshots(actor)]


@router.get(
    "/portfolio-snapshots/{snapshotId}",
    response_model=PortfolioSnapshotEnvelope,
    operation_id="getPortfolioSnapshot",
)
async def get_portfolio_snapshot(
    snapshotId: UUID,
    actor: CurrentActor,
    service: InvestmentServiceDependency,
) -> PortfolioSnapshotEnvelope | JSONResponse:
    try:
        return PortfolioSnapshotEnvelope(
            data=_snapshot_dto(service, service.snapshot(actor, snapshotId))
        )
    except InvestmentServiceError as error:
        return _error(error, actor.request_id)


@router.post(
    "/recommendation-jobs",
    response_model=RecommendationJobEnvelope,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="createRecommendationJob",
)
async def create_recommendation_job(
    request: RecommendationJobCreateRequest,
    actor: CurrentActor,
    service: InvestmentServiceDependency,
) -> RecommendationJobEnvelope | JSONResponse:
    try:
        return RecommendationJobEnvelope(data=_job_dto(service, service.create_job(actor, request)))
    except InvestmentServiceError as error:
        return _error(error, actor.request_id)


@router.get(
    "/recommendation-jobs",
    response_model=RecommendationHistoryPageEnvelope,
    operation_id="listRecommendationJobs",
)
async def list_recommendation_jobs(
    actor: CurrentActor,
    service: InvestmentServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(min_length=1)] = None,
) -> RecommendationHistoryPageEnvelope | JSONResponse:
    try:
        jobs, next_cursor, has_more = service.jobs(actor, limit=limit, cursor=cursor)
        return RecommendationHistoryPageEnvelope(
            items=[_history_item_dto(service, job) for job in jobs],
            page=PageInfo(limit=limit, next_cursor=next_cursor, has_more=has_more),
        )
    except InvestmentServiceError as error:
        return _error(error, actor.request_id)


@router.get(
    "/recommendation-jobs/{jobId}",
    response_model=RecommendationJobEnvelope,
    operation_id="getRecommendationJob",
)
async def get_recommendation_job(
    jobId: UUID,
    actor: CurrentActor,
    service: InvestmentServiceDependency,
) -> RecommendationJobEnvelope | JSONResponse:
    try:
        return RecommendationJobEnvelope(data=_job_dto(service, service.job(actor, jobId)))
    except InvestmentServiceError as error:
        return _error(error, actor.request_id)


@router.get(
    "/recommendation-jobs/{jobId}/report",
    response_model=RecommendationReportEnvelope,
    operation_id="getRecommendationReport",
)
async def get_recommendation_report(
    jobId: UUID,
    actor: CurrentActor,
    service: InvestmentServiceDependency,
) -> RecommendationReportEnvelope | JSONResponse:
    try:
        model = service.report(actor, jobId)
        dto = RecommendationReportDto(
            id=str(model.id),
            job_id=str(model.job_id),
            summary=model.summary,
            assumptions=model.assumptions,
            generated_at=_utc(model.generated_at),
            valid_until=_utc(model.valid_until),
            is_stale=_utc(model.valid_until) < datetime.now(UTC),
            disclaimer=model.disclaimer,
            actions=[
                RecommendationActionDto(
                    instrument_name=item.instrument_name,
                    ticker=item.ticker,
                    isin=item.isin,
                    risk_bucket=item.risk_bucket,
                    action=item.action,
                    current_percent=item.current_percent,
                    target_percent=item.target_percent,
                    amount=item.amount,
                    priority=item.priority,
                    rationale=item.rationale,
                    risks=item.risks,
                )
                for item in service.repo.report_actions(model.id)
            ],
            sources=[
                RecommendationSourceDto(
                    title=item.title,
                    url=item.url,
                    publisher=item.publisher,
                    trust_tier=item.trust_tier,
                    published_at=item.published_at,
                    fetched_at=item.fetched_at,
                )
                for item in service.repo.report_sources(model.id)
            ],
        )
        return RecommendationReportEnvelope(data=dto)
    except InvestmentServiceError as error:
        return _error(error, actor.request_id)


@router.post(
    "/internal/recommendation-jobs/{jobId}/callback",
    response_model=RecommendationJobEnvelope,
    operation_id="receiveRecommendationCallback",
    include_in_schema=True,
    openapi_extra=CALLBACK_OPENAPI_EXTRA,
)
async def recommendation_callback(
    jobId: UUID,
    raw_request: Request,
    service: InvestmentServiceDependency,
) -> RecommendationJobEnvelope | JSONResponse:
    body = await raw_request.body()
    settings = getattr(raw_request.app.state, "settings", None) or get_settings()
    try:
        canonical_path = raw_request.url.path
        expected_path = (
            f"{settings.api_v1_prefix}/investments/internal/recommendation-jobs/{jobId}/callback"
        )
        if canonical_path != expected_path:
            raise HmacVerificationError("callback path does not match configured prefix")
        verified = verify_callback(
            secret=settings.investment_callback_hmac_secret,
            method=raw_request.method,
            canonical_path=canonical_path,
            timestamp_text=raw_request.headers.get("X-Finance-Timestamp"),
            nonce=raw_request.headers.get("X-Finance-Nonce"),
            signature=raw_request.headers.get("X-Finance-Signature"),
            body=body,
            max_clock_skew_seconds=settings.investment_callback_max_clock_skew_seconds,
        )
        callback = RecommendationCallbackRequest.model_validate_json(body)
        model = service.apply_callback(job_id=jobId, nonce=verified.nonce, request=callback)
        return RecommendationJobEnvelope(data=_job_dto(service, model))
    except HmacVerificationError:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": {
                    "code": "INVALID_SERVICE_CALLBACK",
                    "message": "Invalid service callback.",
                    "requestId": "internal",
                }
            },
        )
    except ValidationError:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "INVALID_RECOMMENDATION_CALLBACK",
                    "message": "Invalid recommendation callback.",
                    "requestId": "internal",
                }
            },
        )
    except InvestmentServiceError as error:
        return _error(error, "internal")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
