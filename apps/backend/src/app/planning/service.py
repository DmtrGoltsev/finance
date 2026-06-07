from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.accounts.repository import AccountRecord, AccountRepository
from app.asset_categories.repository import AssetCategoryRecord, AssetCategoryRepository
from app.asset_categories.schemas import AssetCategoryScope
from app.asset_categories.schemas import RecordStatus as AssetCategoryRecordStatus
from app.asset_categories.service import can_read_asset_category
from app.authz import (
    Account as AuthzAccount,
)
from app.authz import (
    AccountOwnershipType,
    Actor,
    CategoryKind,
    DenialReason,
    ResourceStatus,
    canReadAccount,
    canReadCategory,
)
from app.authz import (
    Category as AuthzCategory,
)
from app.authz import (
    CategoryScope as AuthzCategoryScope,
)
from app.categories.repository import CategoryRecord, CategoryRepository
from app.categories.schemas import CategoryScope, CategoryType, RecordStatus

from .repository import (
    PlanningAllocationRecord,
    PlanningIncomeSourceRecord,
    PlanningPlanAggregate,
    PlanningPlanRecord,
    SqlAlchemyPlanningRepository,
)
from .schemas import (
    PlanningAllocationCreateRequest,
    PlanningAllocationUpdateRequest,
    PlanningIncomeSourceCreateRequest,
    PlanningIncomeSourceUpdateRequest,
    PlanningPlanCopyRequest,
    PlanningPlanCreateRequest,
)

MONEY_QUANT = Decimal("0.0001")
ZERO_MONEY = Decimal("0.0000")
ACCOUNT_BACKED_TARGET_TYPES = frozenset({"account", "asset"})
ASSET_ACCOUNT_TYPES = frozenset({"deposit", "brokerage", "metal", "other"})


@dataclass(frozen=True, slots=True)
class PlanningSummary:
    total_planned_income: Decimal
    total_confirmed_income: Decimal
    total_allocated_amount: Decimal
    unallocated_amount: Decimal
    underallocated: bool
    overallocated: bool


@dataclass(frozen=True, slots=True)
class PlanningAllocationWithAmount:
    record: PlanningAllocationRecord
    calculated_amount: Decimal


@dataclass(frozen=True, slots=True)
class PlanningPlanView:
    plan: PlanningPlanRecord
    income_sources: list[PlanningIncomeSourceRecord]
    allocations: list[PlanningAllocationWithAmount]
    summary: PlanningSummary


class PlanningServiceError(Exception):
    def __init__(self, reason: DenialReason, *, code: str | None = None) -> None:
        self.reason = reason
        self.code = code


class PlanningNotFoundOrInaccessible(PlanningServiceError):
    def __init__(self) -> None:
        super().__init__(DenialReason.RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE)


class PlanningReferencedResourceError(PlanningServiceError):
    def __init__(self) -> None:
        super().__init__(DenialReason.REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE)


class PlanningValidationError(PlanningServiceError):
    pass


class PlanningConflictError(PlanningServiceError):
    def __init__(self, code: str = "CONFLICTING_UPDATE") -> None:
        super().__init__(DenialReason.ACTION_NOT_ALLOWED, code=code)


class PlanningService:
    def __init__(
        self,
        plans: SqlAlchemyPlanningRepository,
        accounts: AccountRepository,
        categories: CategoryRepository,
        asset_categories: AssetCategoryRepository,
    ) -> None:
        self._plans = plans
        self._accounts = accounts
        self._categories = categories
        self._asset_categories = asset_categories

    def get_plan_for_scope_month(
        self,
        *,
        actor: Actor,
        scope: str,
        household_id: str | None,
        month: str | None,
    ) -> PlanningPlanView:
        plan_month = parse_plan_month(month) if month is not None else next_month()
        scope_ref = self._resolve_requested_scope(actor, scope=scope, household_id=household_id)
        plan = self._plans.get_plan_by_scope_month(
            scope_type=scope_ref.scope_type,
            owner_user_id=scope_ref.owner_user_id,
            household_id=scope_ref.household_id,
            plan_month=plan_month,
        )
        if plan is None:
            raise PlanningNotFoundOrInaccessible()
        return self._view(self._require_visible_plan(actor, plan.id))

    def history(
        self,
        *,
        actor: Actor,
        scope: str,
        household_id: str | None,
    ) -> list[PlanningPlanView]:
        scope_ref = self._resolve_requested_scope(actor, scope=scope, household_id=household_id)
        plans = self._plans.list_plans_by_scope(
            scope_type=scope_ref.scope_type,
            owner_user_id=scope_ref.owner_user_id,
            household_id=scope_ref.household_id,
        )
        return [self._view(self._plans.aggregate(plan)) for plan in plans]

    def create_plan(self, *, actor: Actor, request: PlanningPlanCreateRequest) -> PlanningPlanView:
        if actor.user_id is None:
            raise PlanningNotFoundOrInaccessible()
        scope_ref = self._resolve_requested_scope(
            actor,
            scope=str(request.scope),
            household_id=request.household_id,
        )
        plan_month = parse_plan_month(request.month)
        existing = self._plans.get_plan_by_scope_month(
            scope_type=scope_ref.scope_type,
            owner_user_id=scope_ref.owner_user_id,
            household_id=scope_ref.household_id,
            plan_month=plan_month,
        )
        if existing is not None:
            raise PlanningConflictError("PLANNING_PLAN_ALREADY_EXISTS")

        plan = self._plans.create_plan(
            scope_type=scope_ref.scope_type,
            owner_user_id=scope_ref.owner_user_id,
            household_id=scope_ref.household_id,
            plan_month=plan_month,
            currency=request.currency,
            created_by_user_id=actor.user_id,
        )
        return self._view(self._plans.aggregate(plan))

    def get_plan(self, *, actor: Actor, plan_id: str) -> PlanningPlanView:
        return self._view(self._require_visible_plan(actor, plan_id))

    def add_income_source(
        self,
        *,
        actor: Actor,
        plan_id: str,
        request: PlanningIncomeSourceCreateRequest,
    ) -> PlanningIncomeSourceRecord:
        aggregate = self._require_visible_plan(actor, plan_id)
        if actor.user_id is None:
            raise PlanningNotFoundOrInaccessible()
        record = self._plans.create_income_source(
            plan_id=aggregate.plan.id,
            amount=money(request.amount),
            source=request.source,
            description=request.description,
            day_of_month=request.day_of_month,
            created_by_user_id=actor.user_id,
        )
        return record

    def update_income_source(
        self,
        *,
        actor: Actor,
        income_source_id: str,
        request: PlanningIncomeSourceUpdateRequest,
    ) -> PlanningIncomeSourceRecord:
        record = self._require_visible_income_source(actor, income_source_id)
        if request.version is not None and request.version != record.version:
            raise PlanningConflictError()
        updated = record
        if request.amount is not None:
            updated = replace(updated, amount=money(request.amount))
        if request.source is not None:
            updated = replace(updated, source=request.source)
        if "description" in request.model_fields_set:
            updated = replace(updated, description=request.description)
        if request.day_of_month is not None:
            updated = replace(updated, day_of_month=request.day_of_month)
        return self._plans.save_income_source(updated)

    def confirm_income_source(
        self,
        *,
        actor: Actor,
        income_source_id: str,
    ) -> PlanningIncomeSourceRecord:
        record = self._require_visible_income_source(actor, income_source_id)
        if actor.user_id is None:
            raise PlanningNotFoundOrInaccessible()
        if record.confirmation_state == "confirmed":
            return record
        return self._plans.save_income_source(
            replace(
                record,
                confirmation_state="confirmed",
                confirmed_at=datetime.now(UTC),
                confirmed_by_user_id=actor.user_id,
            )
        )

    def delete_income_source(self, *, actor: Actor, income_source_id: str) -> None:
        record = self._require_visible_income_source(actor, income_source_id)
        self._plans.delete_income_source(record)

    def add_allocation(
        self,
        *,
        actor: Actor,
        plan_id: str,
        request: PlanningAllocationCreateRequest,
    ) -> PlanningAllocationRecord:
        aggregate = self._require_visible_plan(actor, plan_id)
        if actor.user_id is None:
            raise PlanningNotFoundOrInaccessible()
        target = self._resolve_target_for_write(
            actor,
            plan=aggregate.plan,
            target_type=str(request.target_type),
            target_id=request.target_id,
        )
        return self._plans.create_allocation(
            plan_id=aggregate.plan.id,
            target_type=str(request.target_type),
            target_id=request.target_id,
            target_snapshot=target.snapshot,
            requires_attention=False,
            attention_reason=None,
            comment=request.comment,
            allocation_mode=str(request.allocation_mode),
            allocation_value=money(request.allocation_value),
            created_by_user_id=actor.user_id,
        )

    def update_allocation(
        self,
        *,
        actor: Actor,
        allocation_id: str,
        request: PlanningAllocationUpdateRequest,
    ) -> PlanningAllocationRecord:
        aggregate, record = self._require_visible_allocation(actor, allocation_id)
        if request.version is not None and request.version != record.version:
            raise PlanningConflictError()

        target_type = (
            str(request.target_type)
            if request.target_type is not None
            else record.target_type
        )
        target_id = request.target_id if request.target_id is not None else record.target_id
        updated = record
        if request.target_type is not None or request.target_id is not None:
            if target_id is None:
                raise PlanningValidationError(DenialReason.VALIDATION_FAILED)
            target = self._resolve_target_for_write(
                actor,
                plan=aggregate.plan,
                target_type=target_type,
                target_id=target_id,
            )
            updated = replace(
                updated,
                target_type=target_type,
                target_id=target_id,
                target_snapshot=target.snapshot,
                requires_attention=False,
                attention_reason=None,
            )
        if "comment" in request.model_fields_set:
            updated = replace(updated, comment=request.comment)
        if request.allocation_mode is not None:
            updated = replace(updated, allocation_mode=str(request.allocation_mode))
        if request.allocation_value is not None:
            updated = replace(updated, allocation_value=money(request.allocation_value))
        return self._plans.save_allocation(updated)

    def delete_allocation(self, *, actor: Actor, allocation_id: str) -> None:
        _aggregate, record = self._require_visible_allocation(actor, allocation_id)
        self._plans.delete_allocation(record)

    def copy_plan(
        self,
        *,
        actor: Actor,
        plan_id: str,
        request: PlanningPlanCopyRequest,
    ) -> PlanningPlanView:
        source = self._require_visible_plan(actor, plan_id)
        if actor.user_id is None:
            raise PlanningNotFoundOrInaccessible()
        target_month = parse_plan_month(request.target_month)
        existing = self._plans.get_plan_by_scope_month(
            scope_type=source.plan.scope_type,
            owner_user_id=source.plan.owner_user_id,
            household_id=source.plan.household_id,
            plan_month=target_month,
        )
        if existing is not None:
            raise PlanningConflictError("PLANNING_PLAN_ALREADY_EXISTS")

        target_plan = self._plans.create_plan(
            scope_type=source.plan.scope_type,
            owner_user_id=source.plan.owner_user_id,
            household_id=source.plan.household_id,
            plan_month=target_month,
            currency=source.plan.currency,
            created_by_user_id=actor.user_id,
        )
        for income in source.income_sources:
            self._plans.create_income_source(
                plan_id=target_plan.id,
                amount=income.amount,
                source=income.source,
                description=income.description,
                day_of_month=income.day_of_month,
                created_by_user_id=actor.user_id,
                confirmation_state="planned",
                confirmed_at=None,
                confirmed_by_user_id=None,
            )
        for allocation in source.allocations:
            copied_target = self._target_for_copy(actor, source.plan, allocation)
            self._plans.create_allocation(
                plan_id=target_plan.id,
                target_type=allocation.target_type,
                target_id=copied_target.target_id,
                target_snapshot=copied_target.snapshot,
                requires_attention=copied_target.requires_attention,
                attention_reason=copied_target.attention_reason,
                comment=allocation.comment,
                allocation_mode=allocation.allocation_mode,
                allocation_value=allocation.allocation_value,
                created_by_user_id=actor.user_id,
            )
        return self._view(self._plans.aggregate(target_plan))

    def _require_visible_plan(self, actor: Actor, plan_id: str) -> PlanningPlanAggregate:
        plan = self._plans.get_plan(plan_id)
        if plan is None or not _can_read_plan(actor, plan):
            raise PlanningNotFoundOrInaccessible()
        return self._plans.aggregate(plan)

    def _require_visible_income_source(
        self,
        actor: Actor,
        income_source_id: str,
    ) -> PlanningIncomeSourceRecord:
        record = self._plans.get_income_source(income_source_id)
        if record is None:
            raise PlanningNotFoundOrInaccessible()
        aggregate = self._require_visible_plan(actor, record.plan_id)
        for income in aggregate.income_sources:
            if income.id == record.id:
                return income
        raise PlanningNotFoundOrInaccessible()

    def _require_visible_allocation(
        self,
        actor: Actor,
        allocation_id: str,
    ) -> tuple[PlanningPlanAggregate, PlanningAllocationRecord]:
        record = self._plans.get_allocation(allocation_id)
        if record is None:
            raise PlanningNotFoundOrInaccessible()
        aggregate = self._require_visible_plan(actor, record.plan_id)
        for allocation in aggregate.allocations:
            if allocation.id == record.id:
                return aggregate, allocation
        raise PlanningNotFoundOrInaccessible()

    def _resolve_requested_scope(
        self,
        actor: Actor,
        *,
        scope: str,
        household_id: str | None,
    ) -> _Scope:
        if not actor.user_id:
            raise PlanningNotFoundOrInaccessible()
        if scope == "personal":
            if household_id is not None:
                raise PlanningValidationError(DenialReason.VALIDATION_FAILED)
            return _Scope(scope_type="personal", owner_user_id=actor.user_id, household_id=None)
        if scope == "household":
            if not _has_active_membership(actor, household_id):
                raise PlanningNotFoundOrInaccessible()
            return _Scope(scope_type="household", owner_user_id=None, household_id=household_id)
        raise PlanningValidationError(DenialReason.VALIDATION_FAILED)

    def _resolve_target_for_write(
        self,
        actor: Actor,
        *,
        plan: PlanningPlanRecord,
        target_type: str,
        target_id: str,
    ) -> _ResolvedTarget:
        if target_type == "expense_category":
            category = self._categories.get(target_id)
            if category is None or not canReadCategory(actor, _authz_category(category)).allowed:
                raise PlanningReferencedResourceError()
            if category.status != RecordStatus.ACTIVE or category.type != CategoryType.EXPENSE:
                raise PlanningReferencedResourceError()
            if not _category_in_plan_scope(category, plan):
                raise PlanningReferencedResourceError()
            return _ResolvedTarget(
                target_id=category.id,
                snapshot=_category_snapshot(category),
                requires_attention=False,
                attention_reason=None,
            )

        if target_type in ACCOUNT_BACKED_TARGET_TYPES:
            account = self._accounts.get(target_id)
            if account is None or not canReadAccount(actor, _authz_account(account)).allowed:
                raise PlanningReferencedResourceError()
            if account.status != ResourceStatus.ACTIVE:
                raise PlanningReferencedResourceError()
            if account.currency != plan.currency or not _account_in_plan_scope(account, plan):
                raise PlanningReferencedResourceError()
            if target_type == "asset" and account.account_type not in ASSET_ACCOUNT_TYPES:
                raise PlanningReferencedResourceError()
            return _ResolvedTarget(
                target_id=account.id,
                snapshot=_account_snapshot(account, target_type=target_type),
                requires_attention=False,
                attention_reason=None,
            )

        if target_type == "investment_asset_category":
            asset_category = self._asset_categories.get(target_id)
            if asset_category is None or not can_read_asset_category(actor, asset_category):
                raise PlanningReferencedResourceError()
            if (
                asset_category.status != AssetCategoryRecordStatus.ACTIVE
                or not asset_category.is_investment
                or asset_category.currency != plan.currency
                or not _asset_category_in_plan_scope(asset_category, plan)
            ):
                raise PlanningReferencedResourceError()
            return _ResolvedTarget(
                target_id=asset_category.id,
                snapshot=_asset_category_snapshot(asset_category),
                requires_attention=False,
                attention_reason=None,
            )

        raise PlanningValidationError(DenialReason.VALIDATION_FAILED)

    def _target_for_copy(
        self,
        actor: Actor,
        plan: PlanningPlanRecord,
        allocation: PlanningAllocationRecord,
    ) -> _ResolvedTarget:
        if allocation.requires_attention or allocation.target_id is None:
            return _ResolvedTarget(
                target_id=None,
                snapshot=allocation.target_snapshot,
                requires_attention=True,
                attention_reason=allocation.attention_reason or "TARGET_REQUIRES_ATTENTION",
            )

        try:
            return self._resolve_target_for_write(
                actor,
                plan=plan,
                target_type=allocation.target_type,
                target_id=allocation.target_id,
            )
        except PlanningServiceError:
            snapshot = allocation.target_snapshot or {
                "targetType": allocation.target_type,
                "id": allocation.target_id,
            }
            return _ResolvedTarget(
                target_id=None,
                snapshot=snapshot,
                requires_attention=True,
                attention_reason="TARGET_MISSING_OR_INACCESSIBLE",
            )

    def _view(self, aggregate: PlanningPlanAggregate) -> PlanningPlanView:
        total_income = money(sum((item.amount for item in aggregate.income_sources), ZERO_MONEY))
        confirmed_income = money(
            sum(
                (
                    item.amount
                    for item in aggregate.income_sources
                    if item.confirmation_state == "confirmed"
                ),
                ZERO_MONEY,
            )
        )
        allocations = [
            PlanningAllocationWithAmount(
                record=allocation,
                calculated_amount=_calculated_allocation_amount(allocation, total_income),
            )
            for allocation in aggregate.allocations
        ]
        allocated = money(
            sum((allocation.calculated_amount for allocation in allocations), ZERO_MONEY)
        )
        unallocated = money(total_income - allocated)
        summary = PlanningSummary(
            total_planned_income=total_income,
            total_confirmed_income=confirmed_income,
            total_allocated_amount=allocated,
            unallocated_amount=unallocated,
            underallocated=allocated < total_income,
            overallocated=allocated > total_income,
        )
        return PlanningPlanView(
            plan=aggregate.plan,
            income_sources=aggregate.income_sources,
            allocations=allocations,
            summary=summary,
        )


@dataclass(frozen=True, slots=True)
class _Scope:
    scope_type: str
    owner_user_id: str | None
    household_id: str | None


@dataclass(frozen=True, slots=True)
class _ResolvedTarget:
    target_id: str | None
    snapshot: dict[str, Any]
    requires_attention: bool
    attention_reason: str | None


def parse_plan_month(value: str) -> date:
    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise PlanningValidationError(DenialReason.VALIDATION_FAILED) from exc
    if parsed.month < 1 or parsed.month > 12:
        raise PlanningValidationError(DenialReason.VALIDATION_FAILED)
    return parsed


def plan_month_text(value: date) -> str:
    return value.strftime("%Y-%m")


def effective_income_date(plan_month: date, day_of_month: int) -> date:
    last_day = monthrange(plan_month.year, plan_month.month)[1]
    return date(plan_month.year, plan_month.month, min(day_of_month, last_day))


def next_month(today: date | None = None) -> date:
    current = today or datetime.now(UTC).date()
    if current.month == 12:
        return date(current.year + 1, 1, 1)
    return date(current.year, current.month + 1, 1)


def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _calculated_allocation_amount(
    allocation: PlanningAllocationRecord,
    total_income: Decimal,
) -> Decimal:
    if allocation.allocation_mode == "percent":
        return money(total_income * allocation.allocation_value / Decimal("100"))
    return money(allocation.allocation_value)


def _has_active_membership(actor: Actor, household_id: str | None) -> bool:
    if not actor.user_id or not household_id:
        return False
    return any(
        membership.user_id == actor.user_id
        and membership.household_id == household_id
        and membership.status.value == "active"
        for membership in actor.memberships
    )


def _can_read_plan(actor: Actor, plan: PlanningPlanRecord) -> bool:
    if plan.scope_type == "personal":
        return bool(actor.user_id and plan.owner_user_id == actor.user_id)
    if plan.scope_type == "household":
        return _has_active_membership(actor, plan.household_id)
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
            RecordStatus.ACTIVE: ResourceStatus.ACTIVE,
            RecordStatus.ARCHIVED: ResourceStatus.ARCHIVED,
            RecordStatus.DELETED: ResourceStatus.DELETED,
        }[record.status],
    )


def _category_in_plan_scope(category: CategoryRecord, plan: PlanningPlanRecord) -> bool:
    if plan.scope_type == "personal":
        return (
            category.scope == CategoryScope.PERSONAL
            and category.owner_user_id == plan.owner_user_id
        )
    return category.scope == CategoryScope.HOUSEHOLD and category.household_id == plan.household_id


def _account_in_plan_scope(account: AccountRecord, plan: PlanningPlanRecord) -> bool:
    if plan.scope_type == "personal":
        return (
            account.ownership_type == AccountOwnershipType.PERSONAL
            and account.owner_user_id == plan.owner_user_id
        )
    return (
        account.ownership_type == AccountOwnershipType.SHARED
        and account.household_id == plan.household_id
    )


def _asset_category_in_plan_scope(
    category: AssetCategoryRecord,
    plan: PlanningPlanRecord,
) -> bool:
    if plan.scope_type == "personal":
        return (
            category.scope_type == AssetCategoryScope.PERSONAL
            and category.owner_user_id == plan.owner_user_id
        )
    return (
        category.scope_type == AssetCategoryScope.HOUSEHOLD
        and category.household_id == plan.household_id
    )


def _category_snapshot(category: CategoryRecord) -> dict[str, Any]:
    return {
        "targetType": "expense_category",
        "id": category.id,
        "name": category.name,
        "categoryType": category.type.value,
        "scope": category.scope.value,
        "ownerUserId": category.owner_user_id,
        "householdId": category.household_id,
    }


def _account_snapshot(account: AccountRecord, *, target_type: str = "account") -> dict[str, Any]:
    return {
        "targetType": target_type,
        "id": account.id,
        "name": account.name,
        "accountType": account.account_type,
        "ownershipType": account.ownership_type.value,
        "ownerUserId": account.owner_user_id,
        "householdId": account.household_id,
        "currency": account.currency,
    }


def _asset_category_snapshot(category: AssetCategoryRecord) -> dict[str, Any]:
    return {
        "targetType": "investment_asset_category",
        "id": category.id,
        "name": category.name,
        "assetType": category.asset_type.value,
        "scopeType": category.scope_type.value,
        "ownerUserId": category.owner_user_id,
        "householdId": category.household_id,
        "currency": category.currency,
        "isInvestment": category.is_investment,
    }
