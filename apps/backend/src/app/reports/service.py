from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
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
    ReportRequest,
    ResourceStatus,
    canReadCategory,
    canReadReport,
    canReadTransaction,
)
from app.authz import (
    Category as AuthzCategory,
)
from app.authz import (
    CategoryScope as AuthzCategoryScope,
)
from app.authz import (
    ReportMode as AuthzReportMode,
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
from app.transactions.repository import TransactionFilters, TransactionRecord, TransactionRepository
from app.transactions.repository import repository as transaction_repository

from .schemas import ReportBucket

ZERO = Decimal("0.0000")


@dataclass(frozen=True, slots=True)
class ReportQuery:
    report_mode: str
    household_id: str
    start: datetime | None = None
    end: datetime | None = None
    start_date: date | None = None
    end_date: date | None = None
    timezone: str = "UTC"
    account_ids: tuple[str, ...] = ()
    category_ids: tuple[str, ...] = ()
    transaction_types: tuple[str, ...] = ()
    currency: str | None = None
    bucket: ReportBucket = ReportBucket.MONTH
    sort: str | None = None


@dataclass(frozen=True, slots=True)
class ReportContext:
    actor: Actor
    query: ReportQuery
    generated_at: datetime
    visible_accounts: tuple[AccountRecord, ...]
    visible_categories: tuple[CategoryRecord, ...]


@dataclass(frozen=True, slots=True)
class CategoryBreakdownRow:
    category: CategoryRecord | None
    currency: str
    amount: Decimal
    transaction_count: int
    share_of_visible_total: Decimal


@dataclass(frozen=True, slots=True)
class CashFlowPoint:
    period_start_date: date
    period_end_date: date
    totals_by_currency: tuple[tuple[str, Decimal, Decimal, Decimal, Decimal], ...]


@dataclass(frozen=True, slots=True)
class AccountBalanceGroup:
    account_type: str
    currency: str
    current_balance_total: Decimal
    account_count: int


class ReportServiceError(Exception):
    def __init__(self, reason: DenialReason, *, code: str | None = None) -> None:
        self.reason = reason
        self.code = code


class ReportNotFoundOrInaccessible(ReportServiceError):
    def __init__(self) -> None:
        super().__init__(DenialReason.RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE)


class ReportReferencedResourceError(ReportServiceError):
    def __init__(self) -> None:
        super().__init__(DenialReason.REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE)


class ReportValidationError(ReportServiceError):
    pass


class ReportService:
    def __init__(
        self,
        transactions: TransactionRepository = transaction_repository,
        accounts: AccountRepository = account_repository,
        categories: CategoryRepository = category_repository,
    ) -> None:
        self._transactions = transactions
        self._accounts = accounts
        self._categories = categories

    def context(self, *, actor: Actor, query: ReportQuery) -> ReportContext:
        try:
            authz_mode = AuthzReportMode(query.report_mode)
        except ValueError as exc:
            raise ReportValidationError(DenialReason.VALIDATION_FAILED) from exc

        decision = canReadReport(
            actor,
            ReportRequest(mode=authz_mode, household_id=query.household_id),
        )
        if not decision.allowed:
            raise ReportNotFoundOrInaccessible()

        visible_accounts = self._resolve_visible_accounts(actor=actor, query=query)
        visible_categories = self._resolve_visible_categories(actor=actor, query=query)
        if query.account_ids and len(visible_accounts) != len(set(query.account_ids)):
            raise ReportReferencedResourceError()
        if query.category_ids and len(visible_categories) != len(set(query.category_ids)):
            raise ReportReferencedResourceError()

        return ReportContext(
            actor=actor,
            query=query,
            generated_at=datetime.now(UTC),
            visible_accounts=tuple(visible_accounts),
            visible_categories=tuple(visible_categories),
        )

    def visible_report_transactions(self, context: ReportContext) -> list[TransactionRecord]:
        visible_account_ids = {account.id for account in context.visible_accounts}
        visible_category_ids = {category.id for category in context.visible_categories}
        if not visible_account_ids:
            return []

        filters = TransactionFilters(
            status="active",
            sort=context.query.sort,
        )
        candidates = self._transactions.list_by_visible_accounts(
            visible_account_ids,
            filters=filters,
        )
        rows: list[TransactionRecord] = []
        for record in candidates:
            if record.record_status != "active":
                continue
            if not _record_inside_date_range(record, context.query):
                continue
            if context.query.transaction_types and (
                record.transaction_type not in context.query.transaction_types
            ):
                continue
            if context.query.currency is not None and record.currency != context.query.currency:
                continue
            if context.query.category_ids and record.category_id not in visible_category_ids:
                continue
            if not self._record_is_inside_visible_report_scope(record, context):
                continue
            rows.append(record)

        return rows

    def summary_totals(
        self,
        context: ReportContext,
    ) -> tuple[tuple[str, Decimal, Decimal, Decimal, Decimal], ...]:
        totals = _totals_by_currency(self.visible_report_transactions(context))
        return tuple(
            (currency, income, expense, transfer, income - expense)
            for currency, (income, expense, transfer) in sorted(totals.items())
        )

    def category_breakdown(self, context: ReportContext) -> tuple[CategoryBreakdownRow, ...]:
        category_by_id = {category.id: category for category in context.visible_categories}
        grouped: dict[tuple[str | None, str], tuple[Decimal, int]] = defaultdict(lambda: (ZERO, 0))
        for record in self.visible_report_transactions(context):
            if record.transaction_type not in {"income", "expense"}:
                continue
            key = (record.category_id, record.currency)
            amount, count = grouped[key]
            grouped[key] = (amount + record.amount, count + 1)

        visible_totals_by_currency: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for (_category_id, currency), (amount, _count) in grouped.items():
            visible_totals_by_currency[currency] += amount

        rows: list[CategoryBreakdownRow] = []
        for (category_id, currency), (amount, count) in sorted(grouped.items()):
            visible_total = visible_totals_by_currency[currency]
            share = ZERO if visible_total == ZERO else (amount / visible_total)
            rows.append(
                CategoryBreakdownRow(
                    category=category_by_id.get(category_id) if category_id else None,
                    currency=currency,
                    amount=amount,
                    transaction_count=count,
                    share_of_visible_total=share,
                )
            )
        return tuple(rows)

    def expenses_by_category(self, context: ReportContext) -> tuple[CategoryBreakdownRow, ...]:
        category_by_id = {category.id: category for category in context.visible_categories}
        grouped: dict[tuple[str | None, str], tuple[Decimal, int]] = defaultdict(lambda: (ZERO, 0))
        for record in self.visible_report_transactions(context):
            if record.transaction_type != "expense":
                continue
            key = (record.category_id, record.currency)
            amount, count = grouped[key]
            grouped[key] = (amount + record.amount, count + 1)

        totals_by_currency: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for (_category_id, currency), (amount, _count) in grouped.items():
            totals_by_currency[currency] += amount

        rows: list[CategoryBreakdownRow] = []
        for (category_id, currency), (amount, count) in sorted(grouped.items()):
            visible_total = totals_by_currency[currency]
            share = ZERO if visible_total == ZERO else (amount / visible_total)
            rows.append(
                CategoryBreakdownRow(
                    category=category_by_id.get(category_id) if category_id else None,
                    currency=currency,
                    amount=amount,
                    transaction_count=count,
                    share_of_visible_total=share,
                )
            )
        return tuple(rows)

    def account_balances(self, context: ReportContext) -> tuple[AccountRecord, ...]:
        return tuple(
            sorted(
                context.visible_accounts,
                key=lambda account: (account.currency, account.name.casefold(), account.id),
            )
        )

    def balance_groups(self, context: ReportContext) -> tuple[AccountBalanceGroup, ...]:
        grouped: dict[tuple[str, str], tuple[Decimal, int]] = defaultdict(lambda: (ZERO, 0))
        for account in context.visible_accounts:
            key = (account.account_type, account.currency)
            amount, count = grouped[key]
            grouped[key] = (amount + account.current_balance, count + 1)
        return tuple(
            AccountBalanceGroup(
                account_type=account_type,
                currency=currency,
                current_balance_total=amount,
                account_count=count,
            )
            for (account_type, currency), (amount, count) in sorted(grouped.items())
        )

    def net_worth_totals(self, context: ReportContext) -> tuple[tuple[str, Decimal], ...]:
        grouped: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for account in context.visible_accounts:
            grouped[account.currency] += account.current_balance
        return tuple(sorted(grouped.items()))

    def cash_flow(self, context: ReportContext) -> tuple[CashFlowPoint, ...]:
        grouped: dict[tuple[date, date], list[TransactionRecord]] = defaultdict(list)
        for record in self.visible_report_transactions(context):
            if record.transaction_type not in {"income", "expense", "interest", "dividend"}:
                continue
            period = _bucket_bounds(record.occurred_at.date(), context.query.bucket)
            grouped[period].append(record)

        points: list[CashFlowPoint] = []
        for (period_start, period_end), records in sorted(grouped.items()):
            totals = _totals_by_currency(records)
            points.append(
                CashFlowPoint(
                    period_start_date=period_start,
                    period_end_date=period_end,
                    totals_by_currency=tuple(
                        (currency, income, expense, transfer, income - expense)
                        for currency, (income, expense, transfer) in sorted(totals.items())
                    ),
                )
            )
        return tuple(points)

    def paged_transactions(
        self,
        context: ReportContext,
        *,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[TransactionRecord], str | None, bool]:
        rows = self.visible_report_transactions(context)
        offset = _decode_cursor(cursor)
        page = rows[offset : offset + limit]
        next_offset = offset + len(page)
        has_more = next_offset < len(rows)
        return page, str(next_offset) if has_more else None, has_more

    def _resolve_visible_accounts(
        self,
        *,
        actor: Actor,
        query: ReportQuery,
    ) -> list[AccountRecord]:
        requested_ids = set(query.account_ids)
        records: list[AccountRecord] = []
        for account in self._accounts.list():
            if account.status != ResourceStatus.ACTIVE:
                continue
            if query.currency is not None and account.currency != query.currency:
                continue
            if requested_ids and account.id not in requested_ids:
                continue
            if _account_in_report_scope(actor, account, query):
                records.append(account)
        return records

    def _resolve_visible_categories(
        self,
        *,
        actor: Actor,
        query: ReportQuery,
    ) -> list[CategoryRecord]:
        requested_ids = set(query.category_ids)
        records: list[CategoryRecord] = []
        for category in self._categories.list():
            if category.status != CategoryRecordStatus.ACTIVE:
                continue
            if requested_ids and category.id not in requested_ids:
                continue
            if _category_in_report_scope(actor, category, query):
                records.append(category)
        return records

    def _record_is_inside_visible_report_scope(
        self,
        record: TransactionRecord,
        context: ReportContext,
    ) -> bool:
        account_by_id = {account.id: account for account in context.visible_accounts}
        account = account_by_id.get(record.account_id)
        counterparty = (
            account_by_id.get(record.counterparty_account_id)
            if record.counterparty_account_id is not None
            else None
        )
        if account is None:
            return False
        if record.transaction_type == "transfer" and counterparty is None:
            return False

        transaction = AuthzTransaction(
            id=record.id,
            transaction_type=AuthzTransactionType(record.transaction_type),
            account=_authz_account(account),
            counterparty_account=_authz_account(counterparty) if counterparty else None,
            category=None,
            status=ResourceStatus.ACTIVE,
        )
        return canReadTransaction(context.actor, transaction).allowed


def _account_in_report_scope(actor: Actor, account: AccountRecord, query: ReportQuery) -> bool:
    if not actor.user_id:
        return False
    if query.report_mode == AuthzReportMode.SHARED_FAMILY_REPORT.value:
        return (
            account.ownership_type == AccountOwnershipType.SHARED
            and account.household_id == query.household_id
        )
    if query.report_mode == AuthzReportMode.COMBINED_VIEWER_OVERVIEW.value:
        if (
            account.ownership_type == AccountOwnershipType.SHARED
            and account.household_id == query.household_id
        ):
            return True
        return (
            account.ownership_type == AccountOwnershipType.PERSONAL
            and account.owner_user_id == actor.user_id
        )
    return False


def _category_in_report_scope(actor: Actor, category: CategoryRecord, query: ReportQuery) -> bool:
    if not canReadCategory(actor, _authz_category(category)).allowed:
        return False
    if query.report_mode == AuthzReportMode.SHARED_FAMILY_REPORT.value:
        return (
            category.scope == CategoryScope.HOUSEHOLD
            and category.household_id == query.household_id
        )
    if query.report_mode == AuthzReportMode.COMBINED_VIEWER_OVERVIEW.value:
        if (
            category.scope == CategoryScope.HOUSEHOLD
            and category.household_id == query.household_id
        ):
            return True
        return category.scope == CategoryScope.PERSONAL and category.owner_user_id == actor.user_id
    return False


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


def _totals_by_currency(
    records: list[TransactionRecord],
) -> dict[str, tuple[Decimal, Decimal, Decimal]]:
    totals: dict[str, tuple[Decimal, Decimal, Decimal]] = defaultdict(
        lambda: (ZERO, ZERO, ZERO)
    )
    for record in records:
        income, expense, transfer = totals[record.currency]
        if record.transaction_type in {"income", "interest", "dividend"}:
            income += record.amount
        elif record.transaction_type == "expense":
            expense += record.amount
        elif record.transaction_type == "transfer":
            transfer += record.amount
        totals[record.currency] = (income, expense, transfer)
    return totals


def _record_inside_date_range(record: TransactionRecord, query: ReportQuery) -> bool:
    occurred_at = _as_utc_aware(record.occurred_at)
    if query.start is not None and occurred_at < query.start:
        return False
    if query.end is not None and occurred_at > query.end:
        return False
    return True


def _as_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _bucket_bounds(value: date, bucket: ReportBucket) -> tuple[date, date]:
    if bucket == ReportBucket.DAY:
        return value, value

    if value.month == 12:
        next_month = date(value.year + 1, 1, 1)
    else:
        next_month = date(value.year, value.month + 1, 1)
    month_start = date(value.year, value.month, 1)
    return month_start, date.fromordinal(next_month.toordinal() - 1)


def _decode_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        value = int(cursor)
    except ValueError as exc:
        raise ReportValidationError(DenialReason.VALIDATION_FAILED) from exc
    if value < 0:
        raise ReportValidationError(DenialReason.VALIDATION_FAILED)
    return value


def date_boundary(value: date | None, *, end: bool) -> datetime | None:
    if value is None:
        return None
    boundary = time.max if end else time.min
    return datetime.combine(value, boundary, tzinfo=UTC)


service = ReportService()
