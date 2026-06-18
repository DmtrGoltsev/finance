from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import (
    PlanningAllocation as PlanningAllocationModel,
)
from app.db.models import (
    PlanningIncomeSource as PlanningIncomeSourceModel,
)
from app.db.models import (
    PlanningPlan as PlanningPlanModel,
)


@dataclass(frozen=True, slots=True)
class PlanningPlanRecord:
    id: str
    scope_type: str
    owner_user_id: str | None
    household_id: str | None
    plan_month: date
    currency: str
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class PlanningIncomeSourceRecord:
    id: str
    plan_id: str
    amount: Decimal
    source: str
    description: str | None
    day_of_month: int
    confirmation_state: str
    confirmed_at: datetime | None
    confirmed_by_user_id: str | None
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    version: int
    record_status: str = "active"
    deleted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PlanningAllocationRecord:
    id: str
    plan_id: str
    target_type: str
    target_id: str | None
    target_snapshot: dict[str, Any]
    requires_attention: bool
    attention_reason: str | None
    comment: str | None
    allocation_mode: str
    allocation_value: Decimal
    recurrence_type: str
    is_savings_goal: bool
    goal_target_amount: Decimal | None
    goal_due_month: date | None
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    version: int
    record_status: str = "active"
    deleted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PlanningPlanAggregate:
    plan: PlanningPlanRecord
    income_sources: list[PlanningIncomeSourceRecord]
    allocations: list[PlanningAllocationRecord]


class SqlAlchemyPlanningRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_plan(self, plan_id: str) -> PlanningPlanRecord | None:
        parsed_id = _optional_uuid(plan_id)
        if parsed_id is None:
            return None
        model = self._session.get(PlanningPlanModel, parsed_id)
        return _plan_from_model(model) if model is not None else None

    def get_plan_by_scope_month(
        self,
        *,
        scope_type: str,
        owner_user_id: str | None,
        household_id: str | None,
        plan_month: date,
    ) -> PlanningPlanRecord | None:
        statement = select(PlanningPlanModel).where(
            PlanningPlanModel.scope_type == scope_type,
            PlanningPlanModel.plan_month == plan_month,
        )
        if scope_type == "personal":
            owner_id = _required_uuid(owner_user_id, "owner_user_id")
            statement = statement.where(PlanningPlanModel.owner_user_id == owner_id)
        else:
            household_uuid = _required_uuid(household_id, "household_id")
            statement = statement.where(PlanningPlanModel.household_id == household_uuid)

        model = self._session.execute(statement).scalar_one_or_none()
        return _plan_from_model(model) if model is not None else None

    def list_plans_by_scope(
        self,
        *,
        scope_type: str,
        owner_user_id: str | None,
        household_id: str | None,
    ) -> list[PlanningPlanRecord]:
        statement: Select[tuple[PlanningPlanModel]] = select(PlanningPlanModel).where(
            PlanningPlanModel.scope_type == scope_type
        )
        if scope_type == "personal":
            owner_id = _required_uuid(owner_user_id, "owner_user_id")
            statement = statement.where(PlanningPlanModel.owner_user_id == owner_id)
        else:
            household_uuid = _required_uuid(household_id, "household_id")
            statement = statement.where(PlanningPlanModel.household_id == household_uuid)

        statement = statement.order_by(PlanningPlanModel.plan_month.desc(), PlanningPlanModel.id)
        return [_plan_from_model(row) for row in self._session.execute(statement).scalars()]

    def aggregate(self, plan: PlanningPlanRecord) -> PlanningPlanAggregate:
        return PlanningPlanAggregate(
            plan=plan,
            income_sources=self.list_income_sources(plan.id),
            allocations=self.list_allocations(plan.id),
        )

    def create_plan(
        self,
        *,
        plan_id: str | None = None,
        scope_type: str,
        owner_user_id: str | None,
        household_id: str | None,
        plan_month: date,
        currency: str,
        created_by_user_id: str,
    ) -> PlanningPlanRecord:
        now = datetime.now(UTC)
        model = PlanningPlanModel(
            id=_required_uuid(plan_id, "plan_id") if plan_id else uuid4(),
            scope_type=scope_type,
            owner_user_id=_nullable_uuid(owner_user_id, "owner_user_id"),
            household_id=_nullable_uuid(household_id, "household_id"),
            plan_month=plan_month,
            currency=currency,
            created_by_user_id=_required_uuid(created_by_user_id, "created_by_user_id"),
            created_at=now,
            updated_at=now,
            version=1,
        )
        self._session.add(model)
        self._session.flush()
        return _plan_from_model(model)

    def list_income_sources(self, plan_id: str) -> list[PlanningIncomeSourceRecord]:
        parsed_id = _required_uuid(plan_id, "plan_id")
        statement = (
            select(PlanningIncomeSourceModel)
            .where(PlanningIncomeSourceModel.plan_id == parsed_id)
            .where(PlanningIncomeSourceModel.record_status == "active")
            .order_by(PlanningIncomeSourceModel.day_of_month, PlanningIncomeSourceModel.created_at)
        )
        return [_income_from_model(row) for row in self._session.execute(statement).scalars()]

    def get_income_source(self, income_source_id: str) -> PlanningIncomeSourceRecord | None:
        parsed_id = _optional_uuid(income_source_id)
        if parsed_id is None:
            return None
        model = self._session.get(PlanningIncomeSourceModel, parsed_id)
        return _income_from_model(model) if model is not None else None

    def create_income_source(
        self,
        *,
        income_source_id: str | None = None,
        plan_id: str,
        amount: Decimal,
        source: str,
        description: str | None,
        day_of_month: int,
        created_by_user_id: str,
        confirmation_state: str = "planned",
        confirmed_at: datetime | None = None,
        confirmed_by_user_id: str | None = None,
    ) -> PlanningIncomeSourceRecord:
        now = datetime.now(UTC)
        model = PlanningIncomeSourceModel(
            id=(
                _required_uuid(income_source_id, "income_source_id")
                if income_source_id
                else uuid4()
            ),
            plan_id=_required_uuid(plan_id, "plan_id"),
            amount=amount,
            source=source,
            description=description,
            day_of_month=day_of_month,
            confirmation_state=confirmation_state,
            confirmed_at=confirmed_at,
            confirmed_by_user_id=_nullable_uuid(confirmed_by_user_id, "confirmed_by_user_id"),
            created_by_user_id=_required_uuid(created_by_user_id, "created_by_user_id"),
            created_at=now,
            updated_at=now,
            version=1,
            record_status="active",
            deleted_at=None,
        )
        self._session.add(model)
        self._session.flush()
        return _income_from_model(model)

    def save_income_source(
        self,
        record: PlanningIncomeSourceRecord,
    ) -> PlanningIncomeSourceRecord:
        model = self._session.get(
            PlanningIncomeSourceModel,
            _required_uuid(record.id, "id"),
        )
        if model is None:
            raise KeyError(f"planning income source does not exist: {record.id}")
        model.amount = record.amount
        model.source = record.source
        model.description = record.description
        model.day_of_month = record.day_of_month
        model.confirmation_state = record.confirmation_state
        model.confirmed_at = record.confirmed_at
        model.confirmed_by_user_id = _nullable_uuid(
            record.confirmed_by_user_id,
            "confirmed_by_user_id",
        )
        model.record_status = record.record_status
        model.deleted_at = record.deleted_at
        model.updated_at = datetime.now(UTC)
        model.version = int(record.version) + 1
        self._session.flush()
        return _income_from_model(model)

    def delete_income_source(
        self,
        record: PlanningIncomeSourceRecord,
    ) -> PlanningIncomeSourceRecord:
        model = self._session.get(
            PlanningIncomeSourceModel,
            _required_uuid(record.id, "id"),
        )
        if model is None:
            raise KeyError(f"planning income source does not exist: {record.id}")
        model.record_status = "deleted"
        model.deleted_at = model.deleted_at or datetime.now(UTC)
        model.updated_at = datetime.now(UTC)
        model.version = int(model.version or record.version) + 1
        self._session.flush()
        return _income_from_model(model)

    def list_allocations(self, plan_id: str) -> list[PlanningAllocationRecord]:
        parsed_id = _required_uuid(plan_id, "plan_id")
        statement = (
            select(PlanningAllocationModel)
            .where(PlanningAllocationModel.plan_id == parsed_id)
            .where(PlanningAllocationModel.record_status == "active")
            .order_by(PlanningAllocationModel.created_at, PlanningAllocationModel.id)
        )
        return [_allocation_from_model(row) for row in self._session.execute(statement).scalars()]

    def get_allocation(self, allocation_id: str) -> PlanningAllocationRecord | None:
        parsed_id = _optional_uuid(allocation_id)
        if parsed_id is None:
            return None
        model = self._session.get(PlanningAllocationModel, parsed_id)
        return _allocation_from_model(model) if model is not None else None

    def create_allocation(
        self,
        *,
        allocation_id: str | None = None,
        plan_id: str,
        target_type: str,
        target_id: str | None,
        target_snapshot: dict[str, Any],
        requires_attention: bool,
        attention_reason: str | None,
        comment: str | None,
        allocation_mode: str,
        allocation_value: Decimal,
        recurrence_type: str,
        is_savings_goal: bool,
        goal_target_amount: Decimal | None,
        goal_due_month: date | None,
        created_by_user_id: str,
    ) -> PlanningAllocationRecord:
        now = datetime.now(UTC)
        model = PlanningAllocationModel(
            id=_required_uuid(allocation_id, "allocation_id") if allocation_id else uuid4(),
            plan_id=_required_uuid(plan_id, "plan_id"),
            target_type=target_type,
            target_id=_nullable_uuid(target_id, "target_id"),
            target_snapshot=target_snapshot,
            requires_attention=requires_attention,
            attention_reason=attention_reason,
            comment=comment,
            allocation_mode=allocation_mode,
            allocation_value=allocation_value,
            recurrence_type=recurrence_type,
            is_savings_goal=is_savings_goal,
            goal_target_amount=goal_target_amount,
            goal_due_month=goal_due_month,
            created_by_user_id=_required_uuid(created_by_user_id, "created_by_user_id"),
            created_at=now,
            updated_at=now,
            version=1,
            record_status="active",
            deleted_at=None,
        )
        self._session.add(model)
        self._session.flush()
        return _allocation_from_model(model)

    def save_allocation(self, record: PlanningAllocationRecord) -> PlanningAllocationRecord:
        model = self._session.get(
            PlanningAllocationModel,
            _required_uuid(record.id, "id"),
        )
        if model is None:
            raise KeyError(f"planning allocation does not exist: {record.id}")
        model.target_type = record.target_type
        model.target_id = _nullable_uuid(record.target_id, "target_id")
        model.target_snapshot = record.target_snapshot
        model.requires_attention = record.requires_attention
        model.attention_reason = record.attention_reason
        model.comment = record.comment
        model.allocation_mode = record.allocation_mode
        model.allocation_value = record.allocation_value
        model.recurrence_type = record.recurrence_type
        model.is_savings_goal = record.is_savings_goal
        model.goal_target_amount = record.goal_target_amount
        model.goal_due_month = record.goal_due_month
        model.record_status = record.record_status
        model.deleted_at = record.deleted_at
        model.updated_at = datetime.now(UTC)
        model.version = int(record.version) + 1
        self._session.flush()
        return _allocation_from_model(model)

    def delete_allocation(self, record: PlanningAllocationRecord) -> PlanningAllocationRecord:
        model = self._session.get(
            PlanningAllocationModel,
            _required_uuid(record.id, "id"),
        )
        if model is None:
            raise KeyError(f"planning allocation does not exist: {record.id}")
        model.record_status = "deleted"
        model.deleted_at = model.deleted_at or datetime.now(UTC)
        model.updated_at = datetime.now(UTC)
        model.version = int(model.version or record.version) + 1
        self._session.flush()
        return _allocation_from_model(model)


def _plan_from_model(model: PlanningPlanModel) -> PlanningPlanRecord:
    return PlanningPlanRecord(
        id=str(model.id),
        scope_type=model.scope_type,
        owner_user_id=str(model.owner_user_id) if model.owner_user_id is not None else None,
        household_id=str(model.household_id) if model.household_id is not None else None,
        plan_month=model.plan_month,
        currency=model.currency,
        created_by_user_id=str(model.created_by_user_id),
        created_at=model.created_at,
        updated_at=model.updated_at,
        version=int(model.version or 1),
    )


def _income_from_model(model: PlanningIncomeSourceModel) -> PlanningIncomeSourceRecord:
    return PlanningIncomeSourceRecord(
        id=str(model.id),
        plan_id=str(model.plan_id),
        amount=Decimal(model.amount),
        source=model.source,
        description=model.description,
        day_of_month=int(model.day_of_month),
        confirmation_state=model.confirmation_state,
        confirmed_at=model.confirmed_at,
        confirmed_by_user_id=(
            str(model.confirmed_by_user_id)
            if model.confirmed_by_user_id is not None
            else None
        ),
        created_by_user_id=str(model.created_by_user_id),
        created_at=model.created_at,
        updated_at=model.updated_at,
        version=int(model.version or 1),
        record_status=model.record_status,
        deleted_at=model.deleted_at,
    )


def _allocation_from_model(model: PlanningAllocationModel) -> PlanningAllocationRecord:
    snapshot = model.target_snapshot or {}
    return PlanningAllocationRecord(
        id=str(model.id),
        plan_id=str(model.plan_id),
        target_type=model.target_type,
        target_id=str(model.target_id) if model.target_id is not None else None,
        target_snapshot=dict(snapshot),
        requires_attention=bool(model.requires_attention),
        attention_reason=model.attention_reason,
        comment=model.comment,
        allocation_mode=model.allocation_mode,
        allocation_value=Decimal(model.allocation_value),
        recurrence_type=model.recurrence_type or "regular",
        is_savings_goal=bool(model.is_savings_goal),
        goal_target_amount=(
            Decimal(model.goal_target_amount) if model.goal_target_amount is not None else None
        ),
        goal_due_month=model.goal_due_month,
        created_by_user_id=str(model.created_by_user_id),
        created_at=model.created_at,
        updated_at=model.updated_at,
        version=int(model.version or 1),
        record_status=model.record_status,
        deleted_at=model.deleted_at,
    )


def _optional_uuid(value: str | UUID | None) -> UUID | None:
    if value is None or isinstance(value, UUID):
        return value
    try:
        return UUID(value)
    except ValueError:
        return None


def _nullable_uuid(value: str | UUID | None, field_name: str) -> UUID | None:
    if value is None:
        return None
    parsed = _optional_uuid(value)
    if parsed is None:
        raise ValueError(f"{field_name} must be a canonical UUID for DB-backed repositories")
    return parsed


def _required_uuid(value: str | UUID | None, field_name: str) -> UUID:
    parsed = _optional_uuid(value)
    if parsed is None:
        raise ValueError(f"{field_name} must be a canonical UUID for DB-backed repositories")
    return parsed
