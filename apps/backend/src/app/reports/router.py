from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
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
from app.transactions.router import _transaction_dto
from app.transactions.schemas import PageInfo

from .schemas import (
    AccountBalanceDto,
    CashFlowPointDto,
    CategoryBreakdownItemDto,
    MoneyTotalDto,
    ReportAccountBalancesDto,
    ReportAccountBalancesEnvelope,
    ReportBucket,
    ReportCashFlowDto,
    ReportCashFlowEnvelope,
    ReportCategoryBreakdownDto,
    ReportCategoryBreakdownEnvelope,
    ReportMode,
    ReportPeriodDto,
    ReportScopeDto,
    ReportSummaryDto,
    ReportSummaryEnvelope,
    ReportTransactionDrillDownDto,
    ReportTransactionDrillDownEnvelope,
    ReportTransactionType,
)
from .service import (
    CashFlowPoint,
    CategoryBreakdownRow,
    ReportContext,
    ReportNotFoundOrInaccessible,
    ReportQuery,
    ReportReferencedResourceError,
    ReportService,
    ReportServiceError,
    ReportValidationError,
    date_boundary,
    service,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


def report_service_for_request() -> Iterator[ReportService]:
    if accounts_categories_repository_mode() != "db":
        yield service
        return

    with sync_session_scope(get_settings()) as session:
        yield ReportService(
            SqlAlchemyTransactionRepository(session),
            SqlAlchemyAccountRepository(session),
            SqlAlchemyCategoryRepository(session),
        )


ReportServiceDependency = Annotated[ReportService, Depends(report_service_for_request)]
CsvIds = Annotated[str | None, Query(min_length=1, max_length=2000)]


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


def _report_error_response(error: ReportServiceError, request_id: str | None) -> JSONResponse:
    if isinstance(error, ReportNotFoundOrInaccessible):
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
            request_id=request_id,
            message="Resource not found or not accessible.",
        )
    if isinstance(error, ReportReferencedResourceError):
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
            request_id=request_id,
            message="Referenced resource not found or not accessible.",
        )
    if isinstance(error, ReportValidationError):
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            error.code or error.reason.value.upper(),
            request_id=request_id,
            message="Invalid report request.",
        )
    return _error_response(
        status.HTTP_403_FORBIDDEN,
        error.reason.value.upper(),
        request_id=request_id,
        message="Unable to complete the request.",
    )


@router.get(
    "/summary",
    response_model=ReportSummaryEnvelope,
    response_model_by_alias=True,
    operation_id="getReportSummary",
)
async def get_report_summary(
    actor: CurrentActor,
    svc: ReportServiceDependency,
    reportMode: ReportMode,
    householdId: Annotated[str, Query(min_length=1, max_length=128)],
    startDate: Annotated[str | None, Query(min_length=1)] = None,
    endDate: Annotated[str | None, Query(min_length=1)] = None,
    timezone: Annotated[str, Query(min_length=1, max_length=80)] = "UTC",
    accountIds: CsvIds = None,
    categoryIds: CsvIds = None,
    transactionTypes: CsvIds = None,
    currency: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")] = None,
) -> ReportSummaryEnvelope | JSONResponse:
    try:
        context = _context(
            svc,
            actor=actor,
            report_mode=reportMode,
            household_id=householdId,
            start_date=startDate,
            end_date=endDate,
            timezone=timezone,
            account_ids=accountIds,
            category_ids=categoryIds,
            transaction_types=transactionTypes,
            currency=currency,
        )
        return ReportSummaryEnvelope(
            data=ReportSummaryDto(
                scope=_scope(context),
                period=_period(context),
                totals_by_currency=[
                    _money_total(currency, income, expense, net)
                    for currency, income, expense, net in svc.summary_totals(context)
                ],
            )
        )
    except ReportServiceError as error:
        return _report_error_response(error, actor.request_id)


@router.get(
    "/category-breakdown",
    response_model=ReportCategoryBreakdownEnvelope,
    response_model_by_alias=True,
    operation_id="getReportCategoryBreakdown",
)
async def get_report_category_breakdown(
    actor: CurrentActor,
    svc: ReportServiceDependency,
    reportMode: ReportMode,
    householdId: Annotated[str, Query(min_length=1, max_length=128)],
    startDate: Annotated[str | None, Query(min_length=1)] = None,
    endDate: Annotated[str | None, Query(min_length=1)] = None,
    timezone: Annotated[str, Query(min_length=1, max_length=80)] = "UTC",
    accountIds: CsvIds = None,
    categoryIds: CsvIds = None,
    transactionTypes: CsvIds = None,
    currency: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")] = None,
) -> ReportCategoryBreakdownEnvelope | JSONResponse:
    try:
        context = _context(
            svc,
            actor=actor,
            report_mode=reportMode,
            household_id=householdId,
            start_date=startDate,
            end_date=endDate,
            timezone=timezone,
            account_ids=accountIds,
            category_ids=categoryIds,
            transaction_types=transactionTypes,
            currency=currency,
        )
        return ReportCategoryBreakdownEnvelope(
            data=ReportCategoryBreakdownDto(
                scope=_scope(context),
                period=_period(context),
                items=[_category_breakdown_item(row) for row in svc.category_breakdown(context)],
            )
        )
    except ReportServiceError as error:
        return _report_error_response(error, actor.request_id)


@router.get(
    "/account-balances",
    response_model=ReportAccountBalancesEnvelope,
    response_model_by_alias=True,
    operation_id="getReportAccountBalances",
)
async def get_report_account_balances(
    actor: CurrentActor,
    svc: ReportServiceDependency,
    reportMode: ReportMode,
    householdId: Annotated[str, Query(min_length=1, max_length=128)],
    startDate: Annotated[str | None, Query(min_length=1)] = None,
    endDate: Annotated[str | None, Query(min_length=1)] = None,
    timezone: Annotated[str, Query(min_length=1, max_length=80)] = "UTC",
    accountIds: CsvIds = None,
    currency: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")] = None,
) -> ReportAccountBalancesEnvelope | JSONResponse:
    try:
        context = _context(
            svc,
            actor=actor,
            report_mode=reportMode,
            household_id=householdId,
            start_date=startDate,
            end_date=endDate,
            timezone=timezone,
            account_ids=accountIds,
            currency=currency,
        )
        return ReportAccountBalancesEnvelope(
            data=ReportAccountBalancesDto(
                scope=_scope(context),
                as_of_date=context.query.end_date,
                timezone=context.query.timezone,
                items=[
                    AccountBalanceDto(
                        account_id=account.id,
                        account_name=account.name,
                        account_type=account.account_type,
                        ownership_type=account.ownership_type.value,
                        household_id=account.household_id,
                        owner_user_id=(
                            account.owner_user_id
                            if account.owner_user_id == actor.user_id
                            else None
                        ),
                        currency=account.currency,
                        current_balance=account.current_balance,
                        balance_as_of=context.generated_at,
                    )
                    for account in svc.account_balances(context)
                ],
            )
        )
    except ReportServiceError as error:
        return _report_error_response(error, actor.request_id)


@router.get(
    "/cash-flow",
    response_model=ReportCashFlowEnvelope,
    response_model_by_alias=True,
    operation_id="getReportCashFlow",
)
async def get_report_cash_flow(
    actor: CurrentActor,
    svc: ReportServiceDependency,
    reportMode: ReportMode,
    householdId: Annotated[str, Query(min_length=1, max_length=128)],
    startDate: Annotated[str | None, Query(min_length=1)] = None,
    endDate: Annotated[str | None, Query(min_length=1)] = None,
    timezone: Annotated[str, Query(min_length=1, max_length=80)] = "UTC",
    bucket: ReportBucket = ReportBucket.MONTH,
    accountIds: CsvIds = None,
    categoryIds: CsvIds = None,
    transactionTypes: CsvIds = None,
    currency: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")] = None,
) -> ReportCashFlowEnvelope | JSONResponse:
    try:
        context = _context(
            svc,
            actor=actor,
            report_mode=reportMode,
            household_id=householdId,
            start_date=startDate,
            end_date=endDate,
            timezone=timezone,
            bucket=bucket,
            account_ids=accountIds,
            category_ids=categoryIds,
            transaction_types=transactionTypes,
            currency=currency,
        )
        return ReportCashFlowEnvelope(
            data=ReportCashFlowDto(
                scope=_scope(context),
                period=_period(context),
                bucket=context.query.bucket,
                points=[_cash_flow_point(point) for point in svc.cash_flow(context)],
            )
        )
    except ReportServiceError as error:
        return _report_error_response(error, actor.request_id)


@router.get(
    "/transactions",
    response_model=ReportTransactionDrillDownEnvelope,
    response_model_by_alias=True,
    operation_id="getReportTransactions",
)
async def get_report_transactions(
    actor: CurrentActor,
    svc: ReportServiceDependency,
    reportMode: ReportMode,
    householdId: Annotated[str, Query(min_length=1, max_length=128)],
    startDate: Annotated[str | None, Query(min_length=1)] = None,
    endDate: Annotated[str | None, Query(min_length=1)] = None,
    timezone: Annotated[str, Query(min_length=1, max_length=80)] = "UTC",
    accountIds: CsvIds = None,
    categoryIds: CsvIds = None,
    transactionTypes: CsvIds = None,
    currency: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1)] = None,
    sort: Annotated[str | None, Query(pattern=r"^-?(occurredAt|amount|createdAt)$")] = None,
) -> ReportTransactionDrillDownEnvelope | JSONResponse:
    try:
        context = _context(
            svc,
            actor=actor,
            report_mode=reportMode,
            household_id=householdId,
            start_date=startDate,
            end_date=endDate,
            timezone=timezone,
            account_ids=accountIds,
            category_ids=categoryIds,
            transaction_types=transactionTypes,
            currency=currency,
            sort=sort,
        )
        items, next_cursor, has_more = svc.paged_transactions(
            context,
            limit=limit,
            cursor=cursor,
        )
        return ReportTransactionDrillDownEnvelope(
            data=ReportTransactionDrillDownDto(
                scope=_scope(context),
                period=_period(context),
                items=[_transaction_dto(item) for item in items],
                page=PageInfo(limit=limit, next_cursor=next_cursor, has_more=has_more),
            )
        )
    except ReportServiceError as error:
        return _report_error_response(error, actor.request_id)


def _context(
    svc: ReportService,
    *,
    actor,
    report_mode: ReportMode,
    household_id: str,
    start_date: str | None,
    end_date: str | None,
    timezone: str,
    bucket: ReportBucket = ReportBucket.MONTH,
    account_ids: str | None = None,
    category_ids: str | None = None,
    transaction_types: str | None = None,
    currency: str | None = None,
    sort: str | None = None,
) -> ReportContext:
    start = _date(start_date)
    end = _date(end_date)
    if start is not None and end is not None and start > end:
        raise ReportValidationError(DenialReason.VALIDATION_FAILED, code="INVALID_DATE_RANGE")

    query = ReportQuery(
        report_mode=str(report_mode),
        household_id=household_id,
        start=date_boundary(start, end=False),
        end=date_boundary(end, end=True),
        start_date=start,
        end_date=end,
        timezone=timezone,
        account_ids=_csv(account_ids),
        category_ids=_csv(category_ids),
        transaction_types=_transaction_types(transaction_types),
        currency=currency,
        bucket=bucket,
        sort=sort,
    )
    return svc.context(actor=actor, query=query)


def _csv(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    if not items:
        raise ReportValidationError(DenialReason.VALIDATION_FAILED)
    return items


def _transaction_types(value: str | None) -> tuple[str, ...]:
    types = _csv(value)
    for item in types:
        try:
            ReportTransactionType(item)
        except ValueError as exc:
            raise ReportValidationError(DenialReason.VALIDATION_FAILED) from exc
    return types


def _date(value: str | None):
    if value is None:
        return None
    from datetime import date

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ReportValidationError(
            DenialReason.VALIDATION_FAILED,
            code="INVALID_DATE_RANGE",
        ) from exc


def _scope(context: ReportContext) -> ReportScopeDto:
    return ReportScopeDto(
        viewer_user_id=context.actor.user_id or "",
        household_id=context.query.household_id,
        report_mode=context.query.report_mode,
        generated_at=context.generated_at,
    )


def _period(context: ReportContext) -> ReportPeriodDto:
    return ReportPeriodDto(
        start_date=context.query.start_date,
        end_date=context.query.end_date,
        timezone=context.query.timezone,
    )


def _money_total(
    currency: str,
    income: Decimal,
    expense: Decimal,
    net: Decimal,
) -> MoneyTotalDto:
    return MoneyTotalDto(
        currency=currency,
        income_total=income,
        expense_total=expense,
        net_total=net,
    )


def _category_breakdown_item(row: CategoryBreakdownRow) -> CategoryBreakdownItemDto:
    category = row.category
    return CategoryBreakdownItemDto(
        category_id=category.id if category is not None else None,
        category_name=category.name if category is not None else None,
        category_type=category.type.value if category is not None else None,
        category_scope=category.scope.value if category is not None else None,
        currency=row.currency,
        amount=row.amount,
        transaction_count=row.transaction_count,
        share_of_visible_total=str(row.share_of_visible_total),
    )


def _cash_flow_point(point: CashFlowPoint) -> CashFlowPointDto:
    return CashFlowPointDto(
        period_start_date=point.period_start_date,
        period_end_date=point.period_end_date,
        totals_by_currency=[
            _money_total(currency, income, expense, net)
            for currency, income, expense, net in point.totals_by_currency
        ],
    )
