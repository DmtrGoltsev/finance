from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import SyncChange

if TYPE_CHECKING:
    from app.accounts.repository import AccountRecord
    from app.asset_categories.repository import AssetCategoryRecord
    from app.categories.repository import CategoryRecord
    from app.planning.repository import (
        PlanningAllocationRecord,
        PlanningIncomeSourceRecord,
        PlanningPlanRecord,
    )
    from app.transactions.repository import TransactionRecord

SYNC_ENTITY_ACCOUNTS = "accounts"
SYNC_ENTITY_ASSET_CATEGORIES = "asset_categories"
SYNC_ENTITY_CATEGORIES = "categories"
SYNC_ENTITY_INVESTMENT_MIGRATIONS = "investment_migrations"
SYNC_ENTITY_PLANNING_ALLOCATIONS = "planning_allocations"
SYNC_ENTITY_PLANNING_INCOME_SOURCES = "planning_income_sources"
SYNC_ENTITY_PLANNING_PLANS = "planning_plans"
SYNC_ENTITY_TRANSACTIONS = "transactions"


class SyncChangeRecorder:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record_account_change(
        self,
        *,
        actor_user_id: str | UUID | None,
        operation: str,
        record: AccountRecord,
        client_mutation_id: str | None = None,
    ) -> SyncChange:
        return self._record_change(
            entity_type=SYNC_ENTITY_ACCOUNTS,
            entity_id=record.id,
            change_type=operation,
            scope_type=_account_scope_type(record),
            owner_user_id=record.owner_user_id,
            household_id=record.household_id,
            entity_version=record.version,
            entity_updated_at=record.updated_at,
            changed_by_user_id=actor_user_id,
            client_mutation_id=client_mutation_id,
            payload=None if _status_value(record.status) == "deleted" else account_payload(record),
            tombstone_payload=_tombstone_payload(SYNC_ENTITY_ACCOUNTS, record)
            if _status_value(record.status) == "deleted"
            else None,
        )

    def record_category_change(
        self,
        *,
        actor_user_id: str | UUID | None,
        operation: str,
        record: CategoryRecord,
        client_mutation_id: str | None = None,
    ) -> SyncChange:
        return self._record_change(
            entity_type=SYNC_ENTITY_CATEGORIES,
            entity_id=record.id,
            change_type=operation,
            scope_type=_status_value(record.scope),
            owner_user_id=record.owner_user_id,
            household_id=record.household_id,
            entity_version=record.version,
            entity_updated_at=record.updated_at,
            changed_by_user_id=actor_user_id,
            client_mutation_id=client_mutation_id,
            payload=None
            if _status_value(record.status) == "deleted"
            else category_payload(record),
            tombstone_payload=_tombstone_payload(SYNC_ENTITY_CATEGORIES, record)
            if _status_value(record.status) == "deleted"
            else None,
        )

    def record_asset_category_change(
        self,
        *,
        actor_user_id: str | UUID | None,
        operation: str,
        record: AssetCategoryRecord,
        client_mutation_id: str | None = None,
    ) -> SyncChange:
        return self._record_change(
            entity_type=SYNC_ENTITY_ASSET_CATEGORIES,
            entity_id=record.id,
            change_type=operation,
            scope_type=_status_value(record.scope_type),
            owner_user_id=record.owner_user_id,
            household_id=record.household_id,
            entity_version=record.version,
            entity_updated_at=record.updated_at,
            changed_by_user_id=actor_user_id,
            client_mutation_id=client_mutation_id,
            payload=None
            if _status_value(record.status) == "deleted"
            else asset_category_payload(record),
            tombstone_payload=_tombstone_payload(SYNC_ENTITY_ASSET_CATEGORIES, record)
            if _status_value(record.status) == "deleted"
            else None,
        )

    def record_transaction_change(
        self,
        *,
        actor_user_id: str | UUID | None,
        operation: str,
        record: TransactionRecord,
        account: AccountRecord,
        client_mutation_id: str | None = None,
    ) -> SyncChange:
        return self._record_change(
            entity_type=SYNC_ENTITY_TRANSACTIONS,
            entity_id=record.id,
            change_type=operation,
            scope_type=_account_scope_type(account),
            owner_user_id=account.owner_user_id,
            household_id=account.household_id,
            entity_version=record.version,
            entity_updated_at=record.updated_at,
            changed_by_user_id=actor_user_id,
            client_mutation_id=client_mutation_id,
            payload=None
            if record.record_status == "deleted"
            else transaction_payload(record),
            tombstone_payload=_tombstone_payload(SYNC_ENTITY_TRANSACTIONS, record)
            if record.record_status == "deleted"
            else None,
        )

    def record_planning_plan_change(
        self,
        *,
        actor_user_id: str | UUID | None,
        operation: str,
        record: PlanningPlanRecord,
        client_mutation_id: str | None = None,
    ) -> SyncChange:
        return self._record_change(
            entity_type=SYNC_ENTITY_PLANNING_PLANS,
            entity_id=record.id,
            change_type=operation,
            scope_type=record.scope_type,
            owner_user_id=record.owner_user_id,
            household_id=record.household_id,
            entity_version=record.version,
            entity_updated_at=record.updated_at,
            changed_by_user_id=actor_user_id,
            client_mutation_id=client_mutation_id,
            payload=planning_plan_payload(record),
            tombstone_payload=None,
        )

    def record_planning_income_source_change(
        self,
        *,
        actor_user_id: str | UUID | None,
        operation: str,
        record: PlanningIncomeSourceRecord,
        plan: PlanningPlanRecord,
        client_mutation_id: str | None = None,
    ) -> SyncChange:
        is_deleted = record.record_status == "deleted"
        return self._record_change(
            entity_type=SYNC_ENTITY_PLANNING_INCOME_SOURCES,
            entity_id=record.id,
            change_type=operation,
            scope_type=plan.scope_type,
            owner_user_id=plan.owner_user_id,
            household_id=plan.household_id,
            entity_version=record.version,
            entity_updated_at=record.updated_at,
            changed_by_user_id=actor_user_id,
            client_mutation_id=client_mutation_id,
            payload=None if is_deleted else planning_income_source_payload(record),
            tombstone_payload=(
                _tombstone_payload(SYNC_ENTITY_PLANNING_INCOME_SOURCES, record)
                if is_deleted
                else None
            ),
        )

    def record_planning_allocation_change(
        self,
        *,
        actor_user_id: str | UUID | None,
        operation: str,
        record: PlanningAllocationRecord,
        plan: PlanningPlanRecord,
        client_mutation_id: str | None = None,
    ) -> SyncChange:
        is_deleted = record.record_status == "deleted"
        return self._record_change(
            entity_type=SYNC_ENTITY_PLANNING_ALLOCATIONS,
            entity_id=record.id,
            change_type=operation,
            scope_type=plan.scope_type,
            owner_user_id=plan.owner_user_id,
            household_id=plan.household_id,
            entity_version=record.version,
            entity_updated_at=record.updated_at,
            changed_by_user_id=actor_user_id,
            client_mutation_id=client_mutation_id,
            payload=None if is_deleted else planning_allocation_payload(record),
            tombstone_payload=(
                _tombstone_payload(SYNC_ENTITY_PLANNING_ALLOCATIONS, record)
                if is_deleted
                else None
            ),
        )

    def _record_change(
        self,
        *,
        entity_type: str,
        entity_id: str | UUID,
        change_type: str,
        scope_type: str,
        owner_user_id: str | UUID | None,
        household_id: str | UUID | None,
        entity_version: int,
        entity_updated_at: datetime,
        changed_by_user_id: str | UUID | None,
        client_mutation_id: str | None,
        payload: dict[str, Any] | None,
        tombstone_payload: dict[str, Any] | None,
    ) -> SyncChange:
        change = SyncChange(
            entity_type=entity_type,
            entity_id=_required_uuid(entity_id, "entity_id"),
            change_type=change_type,
            scope_type=scope_type,
            owner_user_id=_nullable_uuid(owner_user_id, "owner_user_id"),
            household_id=_nullable_uuid(household_id, "household_id"),
            entity_version=entity_version,
            entity_updated_at=entity_updated_at,
            changed_by_user_id=_nullable_uuid(changed_by_user_id, "changed_by_user_id"),
            client_mutation_id=client_mutation_id,
            payload=payload,
            tombstone_payload=tombstone_payload,
            created_at=datetime.now(UTC),
        )
        self._session.add(change)
        self._session.flush()
        return change


def account_payload(record: AccountRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "accountType": record.account_type,
        "ownershipType": _status_value(record.ownership_type),
        "ownerUserId": record.owner_user_id,
        "householdId": record.household_id,
        "assetCategoryId": record.asset_category_id,
        "isPaymentAccount": record.is_payment_account,
        "currency": record.currency,
        "initialBalance": _money(record.initial_balance),
        "currentBalance": _money(record.current_balance),
        "status": _status_value(record.status),
        "createdByUserId": record.created_by_user_id,
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
        "archivedAt": record.archived_at.isoformat() if record.archived_at else None,
        "deletedAt": record.deleted_at.isoformat() if record.deleted_at else None,
        "version": record.version,
    }


def category_payload(record: CategoryRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "type": _status_value(record.type),
        "scope": _status_value(record.scope),
        "ownerUserId": record.owner_user_id,
        "householdId": record.household_id,
        "iconKey": record.icon_key,
        "color": record.color,
        "status": _status_value(record.status),
        "createdByUserId": record.created_by_user_id,
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
        "archivedAt": record.archived_at.isoformat() if record.archived_at else None,
        "deletedAt": record.deleted_at.isoformat() if record.deleted_at else None,
        "version": record.version,
    }


def asset_category_payload(record: AssetCategoryRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "scopeType": _status_value(record.scope_type),
        "ownerUserId": record.owner_user_id,
        "householdId": record.household_id,
        "currency": record.currency,
        "assetType": _status_value(record.asset_type),
        "iconKey": record.icon_key,
        "manualAmount": _money(record.manual_amount),
        "isInvestment": record.is_investment,
        "recordStatus": _status_value(record.status),
        "createdByUserId": record.created_by_user_id,
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
        "archivedAt": record.archived_at.isoformat() if record.archived_at else None,
        "deletedAt": record.deleted_at.isoformat() if record.deleted_at else None,
        "version": record.version,
    }


def transaction_payload(record: TransactionRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "transactionType": record.transaction_type,
        "accountId": record.account_id,
        "counterpartyAccountId": record.counterparty_account_id,
        "categoryId": record.category_id,
        "amount": _money(record.amount),
        "currency": record.currency,
        "occurredAt": record.occurred_at.isoformat(),
        "transactionDate": record.transaction_date.isoformat()
        if record.transaction_date
        else None,
        "description": record.description,
        "sourceType": record.source_type,
        "transferScope": record.transfer_scope,
        "transferStatus": record.transfer_status,
        "recordStatus": record.record_status,
        "createdByUserId": record.created_by_user_id,
        "lastEditedByUserId": record.last_edited_by_user_id,
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
        "deletedAt": record.deleted_at.isoformat() if record.deleted_at else None,
        "version": record.version,
    }


def planning_plan_payload(record: PlanningPlanRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "scope": record.scope_type,
        "ownerUserId": record.owner_user_id,
        "householdId": record.household_id,
        "month": record.plan_month.strftime("%Y-%m"),
        "currency": record.currency,
        "createdByUserId": record.created_by_user_id,
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
        "version": record.version,
    }


def planning_income_source_payload(record: PlanningIncomeSourceRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "planId": record.plan_id,
        "amount": _money(record.amount),
        "source": record.source,
        "description": record.description,
        "dayOfMonth": record.day_of_month,
        "confirmationState": record.confirmation_state,
        "confirmedAt": record.confirmed_at.isoformat() if record.confirmed_at else None,
        "confirmedByUserId": record.confirmed_by_user_id,
        "createdByUserId": record.created_by_user_id,
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
        "recordStatus": record.record_status,
        "deletedAt": record.deleted_at.isoformat() if record.deleted_at else None,
        "version": record.version,
    }


def planning_allocation_payload(record: PlanningAllocationRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "planId": record.plan_id,
        "targetType": record.target_type,
        "targetId": record.target_id,
        "targetSnapshot": record.target_snapshot,
        "requiresAttention": record.requires_attention,
        "attentionReason": record.attention_reason,
        "comment": record.comment,
        "allocationMode": record.allocation_mode,
        "allocationValue": _money(record.allocation_value),
        "recurrenceType": record.recurrence_type,
        "isSavingsGoal": record.is_savings_goal,
        "goalTargetAmount": (
            _money(record.goal_target_amount) if record.goal_target_amount is not None else None
        ),
        "goalDueMonth": (
            record.goal_due_month.strftime("%Y-%m")
            if record.goal_due_month is not None
            else None
        ),
        "createdByUserId": record.created_by_user_id,
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
        "recordStatus": record.record_status,
        "deletedAt": record.deleted_at.isoformat() if record.deleted_at else None,
        "version": record.version,
    }


def _account_scope_type(record: AccountRecord) -> str:
    if record.owner_user_id is not None:
        return "personal"
    if record.household_id is not None:
        return "household"
    raise ValueError("sync-scoped account must have owner_user_id or household_id")


def _tombstone_payload(entity_type: str, record: Any) -> dict[str, Any]:
    deleted_at = getattr(record, "deleted_at", None)
    return {
        "id": record.id,
        "entityType": entity_type,
        "deletedAt": deleted_at.isoformat() if deleted_at else None,
        "version": record.version,
    }


def _status_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _money(value: Decimal) -> str:
    return f"{value:.4f}"


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
        raise ValueError(f"{field_name} must be a canonical UUID for sync changes")
    return parsed


def _required_uuid(value: str | UUID, field_name: str) -> UUID:
    parsed = _optional_uuid(value)
    if parsed is None:
        raise ValueError(f"{field_name} must be a canonical UUID for sync changes")
    return parsed
