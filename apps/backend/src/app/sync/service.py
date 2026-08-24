from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.accounts.repository import AccountRecord, SqlAlchemyAccountRepository
from app.accounts.schemas import AccountCreateRequest, AccountUpdateRequest
from app.accounts.service import (
    AccountConflictError,
    AccountNotFoundOrInaccessible,
    AccountService,
    AccountServiceError,
    AccountValidationError,
)
from app.asset_categories.investment_migration import (
    InvestmentMigrationService,
    InvestmentMigrationServiceError,
    investment_migration_payload,
)
from app.asset_categories.investment_migration_schemas import (
    InvestmentMigrationCreateRequest,
)
from app.asset_categories.repository import (
    AssetCategoryRecord,
    SqlAlchemyAssetCategoryRepository,
)
from app.asset_categories.schemas import (
    AssetCategoryCreateRequest,
    AssetCategoryUpdateRequest,
)
from app.asset_categories.service import AssetCategoryService
from app.authz import Actor, MembershipStatus
from app.categories.repository import CategoryRecord, SqlAlchemyCategoryRepository
from app.categories.schemas import CategoryCreateRequest, CategoryUpdateRequest
from app.categories.service import CategoryService
from app.db.models import SyncChange, SyncClient, SyncClientMutation
from app.planning.repository import (
    PlanningAllocationRecord,
    PlanningIncomeSourceRecord,
    PlanningPlanRecord,
    SqlAlchemyPlanningRepository,
)
from app.planning.schemas import (
    PlanningAllocationCreateRequest,
    PlanningAllocationUpdateRequest,
    PlanningIncomeSourceCreateRequest,
    PlanningIncomeSourceUpdateRequest,
    PlanningPlanCreateRequest,
)
from app.planning.service import (
    PlanningConflictError,
    PlanningNotFoundOrInaccessible,
    PlanningReferencedResourceError,
    PlanningService,
    PlanningServiceError,
    PlanningValidationError,
)
from app.transactions.repository import SqlAlchemyTransactionRepository, TransactionRecord
from app.transactions.schemas import TransactionCreateRequest, TransactionUpdateRequest
from app.transactions.service import (
    TransactionConflictError,
    TransactionNotFoundOrInaccessible,
    TransactionReferencedResourceError,
    TransactionService,
    TransactionServiceError,
    TransactionValidationError,
)

from .domain_changes import (
    SYNC_ENTITY_ACCOUNTS,
    SYNC_ENTITY_ASSET_CATEGORIES,
    SYNC_ENTITY_CATEGORIES,
    SYNC_ENTITY_INVESTMENT_MIGRATIONS,
    SYNC_ENTITY_PLANNING_ALLOCATIONS,
    SYNC_ENTITY_PLANNING_INCOME_SOURCES,
    SYNC_ENTITY_PLANNING_PLANS,
    SYNC_ENTITY_TRANSACTIONS,
    SyncChangeRecorder,
    account_payload,
    asset_category_payload,
    category_payload,
    planning_allocation_payload,
    planning_income_source_payload,
    planning_plan_payload,
    transaction_payload,
)
from .schemas import (
    MutationStatus,
    SyncChangeDto,
    SyncMutationRequest,
    SyncMutationResult,
    SyncPullRequest,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
)

SYNC_CATEGORY_REQUIRED_TRANSACTION_TYPES = frozenset({"income", "expense"})
SYNC_CATEGORYLESS_TRANSACTION_TYPES = frozenset(
    {"transfer", "brokerage", "asset_buy", "asset_sell", "interest", "dividend", "adjustment"}
)
SYNC_TRANSACTION_TYPES = (
    SYNC_CATEGORY_REQUIRED_TRANSACTION_TYPES | SYNC_CATEGORYLESS_TRANSACTION_TYPES
)
SYNC_TRANSACTION_OPERATIONS = frozenset({"create", "update", "delete", "restore"})
SYNC_DOMAIN_OPERATIONS = frozenset({"create", "update", "archive", "restore", "delete"})
SYNC_PLANNING_PLAN_OPERATIONS = frozenset({"create"})
SYNC_PLANNING_INCOME_SOURCE_OPERATIONS = frozenset(
    {"create", "update", "delete", "confirm"}
)
SYNC_PLANNING_ALLOCATION_OPERATIONS = frozenset({"create", "update", "delete"})
SYNC_PUSH_ENTITY_TYPES = frozenset(
    {
        SYNC_ENTITY_TRANSACTIONS,
        SYNC_ENTITY_ACCOUNTS,
        SYNC_ENTITY_CATEGORIES,
        SYNC_ENTITY_ASSET_CATEGORIES,
        SYNC_ENTITY_INVESTMENT_MIGRATIONS,
        SYNC_ENTITY_PLANNING_PLANS,
        SYNC_ENTITY_PLANNING_INCOME_SOURCES,
        SYNC_ENTITY_PLANNING_ALLOCATIONS,
    }
)
SYNC_ONLINE_ONLY_ENTITY_TYPES = frozenset(
    {
        "capture",
        "captures",
        "capture_drafts",
        "ocr",
        "screenshot",
        "screenshots",
        "screenshot_ocr",
    }
)


class SyncServiceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


class SyncIdempotencyKeyReused(SyncServiceError):
    def __init__(self) -> None:
        super().__init__(
            "IDEMPOTENCY_KEY_REUSED",
            "Idempotency key was reused with a different request.",
        )


class SyncValidationError(SyncServiceError):
    pass


class SyncService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._accounts = SqlAlchemyAccountRepository(session)
        self._asset_categories = SqlAlchemyAssetCategoryRepository(session)
        self._categories = SqlAlchemyCategoryRepository(session)
        self._planning = SqlAlchemyPlanningRepository(session)
        self._transactions = SqlAlchemyTransactionRepository(session)
        self._sync_changes = SyncChangeRecorder(session)
        self._account_service = AccountService(
            self._accounts,
            self._transactions,
            self._asset_categories,
        )
        self._category_service = CategoryService(self._categories)
        self._asset_category_service = AssetCategoryService(self._asset_categories)
        self._investment_migration_service = InvestmentMigrationService(
            self._asset_categories,
            self._accounts,
            self._sync_changes,
        )
        self._planning_service = PlanningService(
            self._planning,
            self._accounts,
            self._categories,
            self._asset_categories,
            self._transactions,
        )
        self._transaction_service = TransactionService(
            self._transactions,
            self._accounts,
            self._categories,
        )

    def push(self, *, actor: Actor, request: SyncPushRequest) -> SyncPushResponse:
        actor_id = _actor_uuid(actor)
        _guard_unique_client_mutation_ids(request)
        _guard_syncable_entity_types(request)
        hashes = {
            mutation.client_mutation_id: _request_hash(
                client_schema_version=request.client_schema_version,
                mutation=mutation,
            )
            for mutation in request.mutations
        }
        self._guard_idempotency_reuse(
            actor_id=actor_id,
            device_id=request.device_id,
            hashes=hashes,
        )
        self._touch_client(
            actor_id=actor_id,
            device_id=request.device_id,
            client_schema_version=request.client_schema_version,
        )

        results: list[SyncMutationResult] = []
        for mutation in request.mutations:
            existing = self._client_mutation(
                actor_id=actor_id,
                device_id=request.device_id,
                client_mutation_id=mutation.client_mutation_id,
            )
            if existing is not None:
                results.append(_stored_result(existing))
                continue

            mutation_row = SyncClientMutation(
                actor_user_id=actor_id,
                device_id=request.device_id,
                client_mutation_id=mutation.client_mutation_id,
                request_hash=hashes[mutation.client_mutation_id],
                entity_type=mutation.entity_type,
                entity_id=mutation.entity_id,
                operation=mutation.operation,
                status="pending",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self._session.add(mutation_row)
            self._session.flush()

            result = self._apply_mutation(
                actor=actor,
                actor_id=actor_id,
                mutation=mutation,
            )
            mutation_row.status = "applied" if result.status == MutationStatus.APPLIED else "failed"
            mutation_row.response_payload = result.model_dump(mode="json", by_alias=True)
            mutation_row.error_code = result.error_code
            mutation_row.change_seq = result.change_seq
            mutation_row.updated_at = datetime.now(UTC)
            self._session.flush()
            results.append(result)

            if result.status == MutationStatus.REJECTED:
                break

        return SyncPushResponse(
            device_id=request.device_id,
            server_time=datetime.now(UTC),
            results=results,
        )

    def pull(self, *, actor: Actor, request: SyncPullRequest) -> SyncPullResponse:
        actor_id = _actor_uuid(actor)
        self._touch_client(
            actor_id=actor_id,
            device_id=request.device_id,
            client_schema_version=request.client_schema_version,
        )

        statement: Select[tuple[SyncChange]] = (
            select(SyncChange)
            .where(SyncChange.seq > request.cursor)
            .where(self._visibility_clause(actor=actor, actor_id=actor_id))
            .order_by(SyncChange.seq.asc())
            .limit(request.limit + 1)
        )
        if request.entity_types is not None:
            if not request.entity_types:
                return SyncPullResponse(
                    changes=[],
                    next_cursor=request.cursor,
                    has_more=False,
                    server_time=datetime.now(UTC),
                )
            statement = statement.where(SyncChange.entity_type.in_(set(request.entity_types)))

        rows = list(self._session.execute(statement).scalars())
        visible_rows = rows[: request.limit]
        has_more = len(rows) > request.limit
        next_cursor = visible_rows[-1].seq if visible_rows else request.cursor
        self._update_client_cursor(
            actor_id=actor_id,
            device_id=request.device_id,
            cursor=next_cursor,
        )

        return SyncPullResponse(
            changes=[_change_dto(row) for row in visible_rows],
            next_cursor=next_cursor,
            has_more=has_more,
            server_time=datetime.now(UTC),
        )

    def _guard_idempotency_reuse(
        self,
        *,
        actor_id: UUID,
        device_id: str,
        hashes: dict[str, str],
    ) -> None:
        for client_mutation_id, request_hash in hashes.items():
            existing = self._client_mutation(
                actor_id=actor_id,
                device_id=device_id,
                client_mutation_id=client_mutation_id,
            )
            if existing is not None and existing.request_hash != request_hash:
                raise SyncIdempotencyKeyReused()

    def _client_mutation(
        self,
        *,
        actor_id: UUID,
        device_id: str,
        client_mutation_id: str,
    ) -> SyncClientMutation | None:
        statement = select(SyncClientMutation).where(
            SyncClientMutation.actor_user_id == actor_id,
            SyncClientMutation.device_id == device_id,
            SyncClientMutation.client_mutation_id == client_mutation_id,
        )
        return self._session.execute(statement).scalar_one_or_none()

    def _touch_client(
        self,
        *,
        actor_id: UUID,
        device_id: str,
        client_schema_version: int,
    ) -> None:
        client = self._session.get(
            SyncClient,
            {"actor_user_id": actor_id, "device_id": device_id},
        )
        now = datetime.now(UTC)
        if client is None:
            self._session.add(
                SyncClient(
                    actor_user_id=actor_id,
                    device_id=device_id,
                    client_schema_version=client_schema_version,
                    last_seen_at=now,
                    server_cursor=0,
                )
            )
            self._session.flush()
            return

        client.client_schema_version = client_schema_version
        client.last_seen_at = now
        self._session.flush()

    def _update_client_cursor(self, *, actor_id: UUID, device_id: str, cursor: int) -> None:
        client = self._session.get(
            SyncClient,
            {"actor_user_id": actor_id, "device_id": device_id},
        )
        if client is not None and cursor > client.server_cursor:
            client.server_cursor = cursor
            self._session.flush()

    def _visibility_clause(self, *, actor: Actor, actor_id: UUID):
        active_household_ids = [
            UUID(membership.household_id)
            for membership in actor.memberships
            if membership.status == MembershipStatus.ACTIVE
        ]
        clauses = [
            (SyncChange.scope_type == "personal") & (SyncChange.owner_user_id == actor_id),
            SyncChange.scope_type == "system",
        ]
        if active_household_ids:
            clauses.append(
                (SyncChange.scope_type == "household")
                & (SyncChange.household_id.in_(active_household_ids))
            )
        return or_(*clauses)

    def _apply_mutation(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        try:
            if mutation.entity_type == SYNC_ENTITY_TRANSACTIONS:
                return self._apply_transaction_mutation(
                    actor=actor,
                    actor_id=actor_id,
                    mutation=mutation,
                )
            if mutation.entity_type == SYNC_ENTITY_ACCOUNTS:
                return self._apply_account_mutation(
                    actor=actor,
                    actor_id=actor_id,
                    mutation=mutation,
                )
            if mutation.entity_type == SYNC_ENTITY_CATEGORIES:
                return self._apply_category_mutation(
                    actor=actor,
                    actor_id=actor_id,
                    mutation=mutation,
                )
            if mutation.entity_type == SYNC_ENTITY_ASSET_CATEGORIES:
                return self._apply_asset_category_mutation(
                    actor=actor,
                    actor_id=actor_id,
                    mutation=mutation,
                )
            if mutation.entity_type == SYNC_ENTITY_INVESTMENT_MIGRATIONS:
                return self._apply_investment_migration_mutation(
                    actor=actor,
                    mutation=mutation,
                )
            if mutation.entity_type == SYNC_ENTITY_PLANNING_PLANS:
                return self._apply_planning_plan_mutation(
                    actor=actor,
                    actor_id=actor_id,
                    mutation=mutation,
                )
            if mutation.entity_type == SYNC_ENTITY_PLANNING_INCOME_SOURCES:
                return self._apply_planning_income_source_mutation(
                    actor=actor,
                    actor_id=actor_id,
                    mutation=mutation,
                )
            if mutation.entity_type == SYNC_ENTITY_PLANNING_ALLOCATIONS:
                return self._apply_planning_allocation_mutation(
                    actor=actor,
                    actor_id=actor_id,
                    mutation=mutation,
                )
            return _rejected(
                mutation,
                "UNSUPPORTED_ENTITY_TYPE",
                "Unsupported sync entity type.",
            )
        except TransactionServiceError as error:
            return _rejected_for_transaction_error(mutation, error)
        except AccountServiceError as error:
            return _rejected_for_account_error(mutation, error)
        except PlanningServiceError as error:
            return _rejected_for_planning_error(mutation, error)
        except InvestmentMigrationServiceError as error:
            return _rejected_for_investment_migration_error(mutation, error)
        except HTTPException as error:
            return _rejected_for_http_exception(mutation, error)
        except ValidationError:
            return _rejected(mutation, "VALIDATION_FAILED", "Invalid sync mutation payload.")
        except ValueError:
            return _rejected(mutation, "VALIDATION_FAILED", "Invalid sync mutation payload.")

    def _apply_transaction_mutation(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.operation not in SYNC_TRANSACTION_OPERATIONS:
            return _rejected(mutation, "UNSUPPORTED_OPERATION", "Unsupported sync operation.")

        if mutation.operation == "create":
            return self._create_transaction(actor=actor, actor_id=actor_id, mutation=mutation)
        if mutation.operation == "update":
            return self._update_transaction(actor=actor, actor_id=actor_id, mutation=mutation)
        if mutation.operation == "delete":
            return self._delete_transaction(actor=actor, actor_id=actor_id, mutation=mutation)
        return self._restore_transaction(actor=actor, actor_id=actor_id, mutation=mutation)

    def _apply_account_mutation(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.operation not in SYNC_DOMAIN_OPERATIONS:
            return _rejected(mutation, "UNSUPPORTED_OPERATION", "Unsupported sync operation.")
        if mutation.operation == "create":
            return self._create_account(actor=actor, actor_id=actor_id, mutation=mutation)
        if mutation.operation == "update":
            return self._update_account(actor=actor, actor_id=actor_id, mutation=mutation)
        if mutation.operation == "archive":
            return self._archive_account(actor=actor, actor_id=actor_id, mutation=mutation)
        if mutation.operation == "delete":
            return self._delete_account(actor=actor, actor_id=actor_id, mutation=mutation)
        return self._restore_account(actor=actor, actor_id=actor_id, mutation=mutation)

    def _create_account(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.payload is None:
            return _rejected(mutation, "PAYLOAD_REQUIRED", "Mutation payload is required.")
        if self._accounts.get(str(mutation.entity_id)) is not None:
            try:
                self._account_service.get_account(
                    actor=actor,
                    account_id=str(mutation.entity_id),
                )
            except AccountNotFoundOrInaccessible:
                return _resource_not_found(mutation)
            return _rejected(mutation, "ENTITY_ALREADY_EXISTS", "Entity already exists.")

        request = AccountCreateRequest.model_validate(mutation.payload)
        record = self._account_service.create_account(
            actor=actor,
            request=request,
            account_id=str(mutation.entity_id),
        )
        return self._applied_account_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _update_account(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        payload = _versioned_payload_for_update(mutation)
        if isinstance(payload, SyncMutationResult):
            return payload
        if _has_any_key(payload, "currentBalance", "current_balance"):
            return _rejected(
                mutation,
                "UNSUPPORTED_FIELD",
                "currentBalance is not supported for offline account sync.",
            )
        if _has_any_key(payload, "status"):
            return _rejected(
                mutation,
                "UNSUPPORTED_FIELD",
                "Use archive, restore, or delete for offline account status changes.",
            )

        request = AccountUpdateRequest.model_validate(payload)
        record = self._account_service.update_account(
            actor=actor,
            account_id=str(mutation.entity_id),
            request=request,
        )
        return self._applied_account_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _archive_account(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        rejection = self._reject_if_base_version_stale_for_account(actor=actor, mutation=mutation)
        if rejection is not None:
            return rejection
        record = self._account_service.archive_account(
            actor=actor,
            account_id=str(mutation.entity_id),
        )
        return self._applied_account_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _restore_account(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        rejection = self._reject_if_base_version_stale_for_account(actor=actor, mutation=mutation)
        if rejection is not None:
            return rejection
        record = self._account_service.restore_account(
            actor=actor,
            account_id=str(mutation.entity_id),
        )
        return self._applied_account_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _delete_account(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        rejection = self._reject_if_base_version_stale_for_account(actor=actor, mutation=mutation)
        if rejection is not None:
            return rejection
        self._account_service.delete_account(actor=actor, account_id=str(mutation.entity_id))
        record = self._accounts.get(str(mutation.entity_id))
        if record is None:
            return _rejected(mutation, "VALIDATION_FAILED", "Unable to load deleted entity.")
        return self._applied_account_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _reject_if_base_version_stale_for_account(
        self,
        *,
        actor: Actor,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult | None:
        if mutation.base_version is None:
            return _rejected(
                mutation,
                "BASE_VERSION_REQUIRED",
                "baseVersion is required for sync mutation.",
            )
        record = self._account_service.get_account(
            actor=actor,
            account_id=str(mutation.entity_id),
        )
        if record.version != mutation.base_version:
            return _rejected(mutation, "CONFLICTING_UPDATE", "Conflicting update.")
        return None

    def _apply_category_mutation(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.operation not in SYNC_DOMAIN_OPERATIONS:
            return _rejected(mutation, "UNSUPPORTED_OPERATION", "Unsupported sync operation.")
        if mutation.operation == "create":
            return self._create_category(actor=actor, actor_id=actor_id, mutation=mutation)
        if mutation.operation == "update":
            return self._update_category(actor=actor, actor_id=actor_id, mutation=mutation)
        if mutation.operation == "archive":
            return self._archive_category(actor=actor, actor_id=actor_id, mutation=mutation)
        if mutation.operation == "delete":
            return self._delete_category(actor=actor, actor_id=actor_id, mutation=mutation)
        return self._restore_category(actor=actor, actor_id=actor_id, mutation=mutation)

    def _create_category(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.payload is None:
            return _rejected(mutation, "PAYLOAD_REQUIRED", "Mutation payload is required.")
        if self._categories.get(str(mutation.entity_id)) is not None:
            try:
                self._category_service.get(actor=actor, category_id=str(mutation.entity_id))
            except HTTPException:
                return _resource_not_found(mutation)
            return _rejected(mutation, "ENTITY_ALREADY_EXISTS", "Entity already exists.")

        request = CategoryCreateRequest.model_validate(mutation.payload)
        self._category_service.create(
            actor=actor,
            request=request,
            category_id=str(mutation.entity_id),
        )
        record = self._categories.get(str(mutation.entity_id))
        if record is None:
            return _rejected(mutation, "VALIDATION_FAILED", "Unable to load created entity.")
        return self._applied_category_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _update_category(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        payload = _versioned_payload_for_update(mutation)
        if isinstance(payload, SyncMutationResult):
            return payload
        if _has_any_key(payload, "status"):
            return _rejected(
                mutation,
                "UNSUPPORTED_FIELD",
                "Use archive, restore, or delete for offline category status changes.",
            )

        request = CategoryUpdateRequest.model_validate(payload)
        self._category_service.update(
            actor=actor,
            category_id=str(mutation.entity_id),
            request=request,
        )
        record = self._categories.get(str(mutation.entity_id))
        if record is None:
            return _rejected(mutation, "VALIDATION_FAILED", "Unable to load updated entity.")
        return self._applied_category_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _archive_category(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        rejection = self._reject_if_base_version_stale_for_category(
            actor=actor,
            mutation=mutation,
        )
        if rejection is not None:
            return rejection
        self._category_service.archive(actor=actor, category_id=str(mutation.entity_id))
        record = self._categories.get(str(mutation.entity_id))
        if record is None:
            return _rejected(mutation, "VALIDATION_FAILED", "Unable to load archived entity.")
        return self._applied_category_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _restore_category(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        rejection = self._reject_if_base_version_stale_for_category(
            actor=actor,
            mutation=mutation,
        )
        if rejection is not None:
            return rejection
        self._category_service.restore(actor=actor, category_id=str(mutation.entity_id))
        record = self._categories.get(str(mutation.entity_id))
        if record is None:
            return _rejected(mutation, "VALIDATION_FAILED", "Unable to load restored entity.")
        return self._applied_category_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _delete_category(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        rejection = self._reject_if_base_version_stale_for_category(
            actor=actor,
            mutation=mutation,
        )
        if rejection is not None:
            return rejection
        self._category_service.delete(actor=actor, category_id=str(mutation.entity_id))
        record = self._categories.get(str(mutation.entity_id))
        if record is None:
            return _rejected(mutation, "VALIDATION_FAILED", "Unable to load deleted entity.")
        return self._applied_category_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _reject_if_base_version_stale_for_category(
        self,
        *,
        actor: Actor,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult | None:
        if mutation.base_version is None:
            return _rejected(
                mutation,
                "BASE_VERSION_REQUIRED",
                "baseVersion is required for sync mutation.",
            )
        dto = self._category_service.get(actor=actor, category_id=str(mutation.entity_id))
        if dto.version != mutation.base_version:
            return _rejected(mutation, "CONFLICTING_UPDATE", "Conflicting update.")
        return None

    def _apply_asset_category_mutation(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.operation not in SYNC_DOMAIN_OPERATIONS:
            return _rejected(mutation, "UNSUPPORTED_OPERATION", "Unsupported sync operation.")
        if mutation.operation == "create":
            return self._create_asset_category(actor=actor, actor_id=actor_id, mutation=mutation)
        if mutation.operation == "update":
            return self._update_asset_category(actor=actor, actor_id=actor_id, mutation=mutation)
        if mutation.operation == "archive":
            return self._archive_asset_category(actor=actor, actor_id=actor_id, mutation=mutation)
        if mutation.operation == "delete":
            return self._delete_asset_category(actor=actor, actor_id=actor_id, mutation=mutation)
        return self._restore_asset_category(actor=actor, actor_id=actor_id, mutation=mutation)

    def _create_asset_category(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.payload is None:
            return _rejected(mutation, "PAYLOAD_REQUIRED", "Mutation payload is required.")
        if self._asset_categories.get(str(mutation.entity_id)) is not None:
            try:
                self._asset_category_service.get(
                    actor=actor,
                    asset_category_id=str(mutation.entity_id),
                )
            except HTTPException:
                return _resource_not_found(mutation)
            return _rejected(mutation, "ENTITY_ALREADY_EXISTS", "Entity already exists.")

        request = AssetCategoryCreateRequest.model_validate(mutation.payload)
        self._asset_category_service.create(
            actor=actor,
            request=request,
            asset_category_id=str(mutation.entity_id),
        )
        record = self._asset_categories.get(str(mutation.entity_id))
        if record is None:
            return _rejected(mutation, "VALIDATION_FAILED", "Unable to load created entity.")
        return self._applied_asset_category_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _update_asset_category(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        payload = _versioned_payload_for_update(mutation)
        if isinstance(payload, SyncMutationResult):
            return payload
        if _has_any_key(payload, "recordStatus", "record_status"):
            return _rejected(
                mutation,
                "UNSUPPORTED_FIELD",
                "Use archive, restore, or delete for offline asset category status changes.",
            )

        request = AssetCategoryUpdateRequest.model_validate(payload)
        self._asset_category_service.update(
            actor=actor,
            asset_category_id=str(mutation.entity_id),
            request=request,
        )
        record = self._asset_categories.get(str(mutation.entity_id))
        if record is None:
            return _rejected(mutation, "VALIDATION_FAILED", "Unable to load updated entity.")
        return self._applied_asset_category_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _archive_asset_category(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        rejection = self._reject_if_base_version_stale_for_asset_category(
            actor=actor,
            mutation=mutation,
        )
        if rejection is not None:
            return rejection
        self._asset_category_service.archive(
            actor=actor,
            asset_category_id=str(mutation.entity_id),
        )
        record = self._asset_categories.get(str(mutation.entity_id))
        if record is None:
            return _rejected(mutation, "VALIDATION_FAILED", "Unable to load archived entity.")
        return self._applied_asset_category_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _restore_asset_category(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        rejection = self._reject_if_base_version_stale_for_asset_category(
            actor=actor,
            mutation=mutation,
        )
        if rejection is not None:
            return rejection
        self._asset_category_service.restore(
            actor=actor,
            asset_category_id=str(mutation.entity_id),
        )
        record = self._asset_categories.get(str(mutation.entity_id))
        if record is None:
            return _rejected(mutation, "VALIDATION_FAILED", "Unable to load restored entity.")
        return self._applied_asset_category_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _delete_asset_category(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        rejection = self._reject_if_base_version_stale_for_asset_category(
            actor=actor,
            mutation=mutation,
        )
        if rejection is not None:
            return rejection
        self._asset_category_service.delete(
            actor=actor,
            asset_category_id=str(mutation.entity_id),
        )
        record = self._asset_categories.get(str(mutation.entity_id))
        if record is None:
            return _rejected(mutation, "VALIDATION_FAILED", "Unable to load deleted entity.")
        return self._applied_asset_category_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _reject_if_base_version_stale_for_asset_category(
        self,
        *,
        actor: Actor,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult | None:
        if mutation.base_version is None:
            return _rejected(
                mutation,
                "BASE_VERSION_REQUIRED",
                "baseVersion is required for sync mutation.",
            )
        dto = self._asset_category_service.get(
            actor=actor,
            asset_category_id=str(mutation.entity_id),
        )
        if dto.version != mutation.base_version:
            return _rejected(mutation, "CONFLICTING_UPDATE", "Conflicting update.")
        return None

    def _apply_investment_migration_mutation(
        self,
        *,
        actor: Actor,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.operation != "create":
            return _rejected(mutation, "UNSUPPORTED_OPERATION", "Unsupported sync operation.")
        if mutation.payload is None:
            return _rejected(mutation, "PAYLOAD_REQUIRED", "Mutation payload is required.")

        request = InvestmentMigrationCreateRequest.model_validate(mutation.payload)
        if request.asset_category_id != str(mutation.entity_id):
            return _rejected(
                mutation,
                "VALIDATION_FAILED",
                "payload.assetCategoryId must match mutation.entityId.",
            )

        result = self._investment_migration_service.create(
            actor=actor,
            request=request,
            client_mutation_id=mutation.client_mutation_id,
        )
        return SyncMutationResult(
            client_mutation_id=mutation.client_mutation_id,
            entity_type=mutation.entity_type,
            entity_id=mutation.entity_id,
            operation=mutation.operation,
            status=MutationStatus.APPLIED,
            server_version=result.asset_category.version,
            change_seq=result.change_seq,
            data=investment_migration_payload(result),
        )

    def _apply_planning_plan_mutation(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.operation not in SYNC_PLANNING_PLAN_OPERATIONS:
            return _rejected(mutation, "UNSUPPORTED_OPERATION", "Unsupported sync operation.")
        return self._create_planning_plan(actor=actor, actor_id=actor_id, mutation=mutation)

    def _apply_planning_income_source_mutation(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.operation not in SYNC_PLANNING_INCOME_SOURCE_OPERATIONS:
            return _rejected(mutation, "UNSUPPORTED_OPERATION", "Unsupported sync operation.")
        if mutation.operation == "create":
            return self._create_planning_income_source(
                actor=actor,
                actor_id=actor_id,
                mutation=mutation,
            )
        if mutation.operation == "update":
            return self._update_planning_income_source(
                actor=actor,
                actor_id=actor_id,
                mutation=mutation,
            )
        if mutation.operation == "delete":
            return self._delete_planning_income_source(
                actor=actor,
                actor_id=actor_id,
                mutation=mutation,
            )
        return self._confirm_planning_income_source(
            actor=actor,
            actor_id=actor_id,
            mutation=mutation,
        )

    def _apply_planning_allocation_mutation(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.operation not in SYNC_PLANNING_ALLOCATION_OPERATIONS:
            return _rejected(mutation, "UNSUPPORTED_OPERATION", "Unsupported sync operation.")
        if mutation.operation == "create":
            return self._create_planning_allocation(
                actor=actor,
                actor_id=actor_id,
                mutation=mutation,
            )
        if mutation.operation == "update":
            return self._update_planning_allocation(
                actor=actor,
                actor_id=actor_id,
                mutation=mutation,
            )
        return self._delete_planning_allocation(
            actor=actor,
            actor_id=actor_id,
            mutation=mutation,
        )

    def _create_planning_plan(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.payload is None:
            return _rejected(mutation, "PAYLOAD_REQUIRED", "Mutation payload is required.")
        payload = dict(mutation.payload)
        id_rejection = _reject_if_payload_id_conflicts(mutation, payload)
        if id_rejection is not None:
            return id_rejection
        if self._planning.get_plan(str(mutation.entity_id)) is not None:
            try:
                self._planning_service.get_plan(actor=actor, plan_id=str(mutation.entity_id))
            except PlanningNotFoundOrInaccessible:
                return _resource_not_found(mutation)
            return _rejected(mutation, "ENTITY_ALREADY_EXISTS", "Entity already exists.")

        request = PlanningPlanCreateRequest.model_validate(payload)
        view = self._planning_service.create_plan(
            actor=actor,
            request=request,
            plan_id=str(mutation.entity_id),
        )
        return self._applied_planning_plan_result(
            actor_id=actor_id,
            mutation=mutation,
            record=view.plan,
        )

    def _create_planning_income_source(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        payload_with_plan = _payload_with_required_plan_id(mutation)
        if isinstance(payload_with_plan, SyncMutationResult):
            return payload_with_plan
        plan_id, payload = payload_with_plan
        id_rejection = _reject_if_payload_id_conflicts(mutation, payload)
        if id_rejection is not None:
            return id_rejection
        existing = self._planning.get_income_source(str(mutation.entity_id))
        if existing is not None:
            try:
                self._planning_service.get_plan(actor=actor, plan_id=existing.plan_id)
            except PlanningNotFoundOrInaccessible:
                return _resource_not_found(mutation)
            return _rejected(mutation, "ENTITY_ALREADY_EXISTS", "Entity already exists.")

        request = PlanningIncomeSourceCreateRequest.model_validate(payload)
        record = self._planning_service.add_income_source(
            actor=actor,
            plan_id=plan_id,
            request=request,
            income_source_id=str(mutation.entity_id),
        )
        return self._applied_planning_income_source_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _update_planning_income_source(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        payload = _versioned_payload_for_update(mutation)
        if isinstance(payload, SyncMutationResult):
            return payload

        request = PlanningIncomeSourceUpdateRequest.model_validate(payload)
        record = self._planning_service.update_income_source(
            actor=actor,
            income_source_id=str(mutation.entity_id),
            request=request,
        )
        return self._applied_planning_income_source_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _confirm_planning_income_source(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.base_version is None:
            return _rejected(
                mutation,
                "BASE_VERSION_REQUIRED",
                "baseVersion is required for sync confirm.",
            )
        record = self._planning_service.confirm_income_source(
            actor=actor,
            income_source_id=str(mutation.entity_id),
            version=mutation.base_version,
        )
        return self._applied_planning_income_source_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _delete_planning_income_source(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.base_version is None:
            return _rejected(
                mutation,
                "BASE_VERSION_REQUIRED",
                "baseVersion is required for sync delete.",
            )
        record = self._planning_service.delete_income_source(
            actor=actor,
            income_source_id=str(mutation.entity_id),
            version=mutation.base_version,
        )
        return self._applied_planning_income_source_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _create_planning_allocation(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        payload_with_plan = _payload_with_required_plan_id(mutation)
        if isinstance(payload_with_plan, SyncMutationResult):
            return payload_with_plan
        plan_id, payload = payload_with_plan
        id_rejection = _reject_if_payload_id_conflicts(mutation, payload)
        if id_rejection is not None:
            return id_rejection
        existing = self._planning.get_allocation(str(mutation.entity_id))
        if existing is not None:
            try:
                self._planning_service.get_plan(actor=actor, plan_id=existing.plan_id)
            except PlanningNotFoundOrInaccessible:
                return _resource_not_found(mutation)
            return _rejected(mutation, "ENTITY_ALREADY_EXISTS", "Entity already exists.")

        request = PlanningAllocationCreateRequest.model_validate(payload)
        record = self._planning_service.add_allocation(
            actor=actor,
            plan_id=plan_id,
            request=request,
            allocation_id=str(mutation.entity_id),
        )
        return self._applied_planning_allocation_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _update_planning_allocation(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        payload = _versioned_payload_for_update(mutation)
        if isinstance(payload, SyncMutationResult):
            return payload

        request = PlanningAllocationUpdateRequest.model_validate(payload)
        record = self._planning_service.update_allocation(
            actor=actor,
            allocation_id=str(mutation.entity_id),
            request=request,
        )
        return self._applied_planning_allocation_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _delete_planning_allocation(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.base_version is None:
            return _rejected(
                mutation,
                "BASE_VERSION_REQUIRED",
                "baseVersion is required for sync delete.",
            )
        record = self._planning_service.delete_allocation(
            actor=actor,
            allocation_id=str(mutation.entity_id),
            version=mutation.base_version,
        )
        return self._applied_planning_allocation_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
        )

    def _create_transaction(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.payload is None:
            return _rejected(mutation, "PAYLOAD_REQUIRED", "Mutation payload is required.")
        if self._transactions.get(str(mutation.entity_id)) is not None:
            try:
                self._transaction_service.get_transaction(
                    actor=actor,
                    transaction_id=str(mutation.entity_id),
                )
            except TransactionNotFoundOrInaccessible:
                return _rejected(
                    mutation,
                    "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
                    "Resource not found or not accessible.",
                )
            return _rejected(mutation, "ENTITY_ALREADY_EXISTS", "Entity already exists.")

        request = TransactionCreateRequest.model_validate(mutation.payload)
        if str(request.transaction_type) not in SYNC_TRANSACTION_TYPES:
            return _rejected(
                mutation,
                "UNSUPPORTED_TRANSACTION_TYPE",
                "Transaction type is not supported by sync MVP.",
            )

        record = self._transaction_service.create_transaction(
            actor=actor,
            request=request,
            transaction_id=str(mutation.entity_id),
        )
        return self._applied_transaction_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
            changed_account_ids=_transfer_account_ids(record),
        )

    def _update_transaction(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.payload is None:
            return _rejected(mutation, "PAYLOAD_REQUIRED", "Mutation payload is required.")
        payload = dict(mutation.payload)
        payload_version = payload.get("version")
        if mutation.base_version is not None:
            if payload_version is not None and payload_version != mutation.base_version:
                return _rejected(
                    mutation,
                    "VALIDATION_FAILED",
                    "baseVersion and payload.version must match.",
                )
            payload.setdefault("version", mutation.base_version)
        if payload.get("version") is None:
            return _rejected(
                mutation,
                "BASE_VERSION_REQUIRED",
                "baseVersion is required for sync update.",
            )

        existing = self._transaction_service.get_transaction(
            actor=actor,
            transaction_id=str(mutation.entity_id),
        )
        if existing.transaction_type not in SYNC_TRANSACTION_TYPES:
            return _rejected(
                mutation,
                "UNSUPPORTED_TRANSACTION_TYPE",
                "Transaction type is not supported by sync MVP.",
            )
        if payload.get("transactionType") not in (None, *SYNC_TRANSACTION_TYPES):
            return _rejected(
                mutation,
                "UNSUPPORTED_TRANSACTION_TYPE",
                "Transaction type is not supported by sync MVP.",
            )

        request = TransactionUpdateRequest.model_validate(payload)
        record = self._transaction_service.update_transaction(
            actor=actor,
            transaction_id=str(mutation.entity_id),
            request=request,
        )
        return self._applied_transaction_result(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
            changed_account_ids=_transfer_account_ids(existing, record),
        )

    def _delete_transaction(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.base_version is None:
            return _rejected(
                mutation,
                "BASE_VERSION_REQUIRED",
                "baseVersion is required for sync delete.",
            )

        existing = self._transaction_service.get_transaction(
            actor=actor,
            transaction_id=str(mutation.entity_id),
        )
        if existing.transaction_type not in SYNC_TRANSACTION_TYPES:
            return _rejected(
                mutation,
                "UNSUPPORTED_TRANSACTION_TYPE",
                "Transaction type is not supported by sync MVP.",
            )
        self._transaction_service.delete_transaction(
            actor=actor,
            transaction_id=str(mutation.entity_id),
            version=mutation.base_version,
        )
        deleted = self._transactions.get(str(mutation.entity_id))
        if deleted is None:
            return _rejected(mutation, "VALIDATION_FAILED", "Unable to load deleted entity.")
        return self._applied_transaction_result(
            actor_id=actor_id,
            mutation=mutation,
            record=deleted,
            changed_account_ids=_transfer_account_ids(existing, deleted),
        )

    def _restore_transaction(
        self,
        *,
        actor: Actor,
        actor_id: UUID,
        mutation: SyncMutationRequest,
    ) -> SyncMutationResult:
        if mutation.base_version is None:
            return _rejected(
                mutation,
                "BASE_VERSION_REQUIRED",
                "baseVersion is required for sync restore.",
            )
        restored = self._transaction_service.restore_transaction(
            actor=actor,
            transaction_id=str(mutation.entity_id),
            version=mutation.base_version,
            allowed_transaction_types=SYNC_TRANSACTION_TYPES,
        )
        return self._applied_transaction_result(
            actor_id=actor_id,
            mutation=mutation,
            record=restored,
            changed_account_ids=_transfer_account_ids(restored),
        )

    def _applied_transaction_result(
        self,
        *,
        actor_id: UUID,
        mutation: SyncMutationRequest,
        record: TransactionRecord,
        changed_account_ids: tuple[str, ...] = (),
    ) -> SyncMutationResult:
        change = self._write_transaction_change(
            actor_id=actor_id,
            mutation=mutation,
            record=record,
            changed_account_ids=changed_account_ids,
        )
        return SyncMutationResult(
            client_mutation_id=mutation.client_mutation_id,
            entity_type=mutation.entity_type,
            entity_id=mutation.entity_id,
            operation=mutation.operation,
            status=MutationStatus.APPLIED,
            server_version=record.version,
            change_seq=change.seq,
            data=transaction_payload(record),
        )

    def _applied_account_result(
        self,
        *,
        actor_id: UUID,
        mutation: SyncMutationRequest,
        record: AccountRecord,
    ) -> SyncMutationResult:
        change = self._sync_changes.record_account_change(
            actor_user_id=actor_id,
            operation=mutation.operation,
            record=record,
            client_mutation_id=mutation.client_mutation_id,
        )
        return SyncMutationResult(
            client_mutation_id=mutation.client_mutation_id,
            entity_type=mutation.entity_type,
            entity_id=mutation.entity_id,
            operation=mutation.operation,
            status=MutationStatus.APPLIED,
            server_version=record.version,
            change_seq=change.seq,
            data=account_payload(record),
        )

    def _applied_category_result(
        self,
        *,
        actor_id: UUID,
        mutation: SyncMutationRequest,
        record: CategoryRecord,
    ) -> SyncMutationResult:
        change = self._sync_changes.record_category_change(
            actor_user_id=actor_id,
            operation=mutation.operation,
            record=record,
            client_mutation_id=mutation.client_mutation_id,
        )
        return SyncMutationResult(
            client_mutation_id=mutation.client_mutation_id,
            entity_type=mutation.entity_type,
            entity_id=mutation.entity_id,
            operation=mutation.operation,
            status=MutationStatus.APPLIED,
            server_version=record.version,
            change_seq=change.seq,
            data=category_payload(record),
        )

    def _applied_asset_category_result(
        self,
        *,
        actor_id: UUID,
        mutation: SyncMutationRequest,
        record: AssetCategoryRecord,
    ) -> SyncMutationResult:
        change = self._sync_changes.record_asset_category_change(
            actor_user_id=actor_id,
            operation=mutation.operation,
            record=record,
            client_mutation_id=mutation.client_mutation_id,
        )
        return SyncMutationResult(
            client_mutation_id=mutation.client_mutation_id,
            entity_type=mutation.entity_type,
            entity_id=mutation.entity_id,
            operation=mutation.operation,
            status=MutationStatus.APPLIED,
            server_version=record.version,
            change_seq=change.seq,
            data=asset_category_payload(record),
        )

    def _applied_planning_plan_result(
        self,
        *,
        actor_id: UUID,
        mutation: SyncMutationRequest,
        record: PlanningPlanRecord,
    ) -> SyncMutationResult:
        change = self._sync_changes.record_planning_plan_change(
            actor_user_id=actor_id,
            operation=mutation.operation,
            record=record,
            client_mutation_id=mutation.client_mutation_id,
        )
        return SyncMutationResult(
            client_mutation_id=mutation.client_mutation_id,
            entity_type=mutation.entity_type,
            entity_id=mutation.entity_id,
            operation=mutation.operation,
            status=MutationStatus.APPLIED,
            server_version=record.version,
            change_seq=change.seq,
            data=planning_plan_payload(record),
        )

    def _applied_planning_income_source_result(
        self,
        *,
        actor_id: UUID,
        mutation: SyncMutationRequest,
        record: PlanningIncomeSourceRecord,
    ) -> SyncMutationResult:
        plan = self._planning_plan_for_child(record.plan_id)
        change = self._sync_changes.record_planning_income_source_change(
            actor_user_id=actor_id,
            operation=mutation.operation,
            record=record,
            plan=plan,
            client_mutation_id=mutation.client_mutation_id,
        )
        return SyncMutationResult(
            client_mutation_id=mutation.client_mutation_id,
            entity_type=mutation.entity_type,
            entity_id=mutation.entity_id,
            operation=mutation.operation,
            status=MutationStatus.APPLIED,
            server_version=record.version,
            change_seq=change.seq,
            data=planning_income_source_payload(record),
        )

    def _applied_planning_allocation_result(
        self,
        *,
        actor_id: UUID,
        mutation: SyncMutationRequest,
        record: PlanningAllocationRecord,
    ) -> SyncMutationResult:
        plan = self._planning_plan_for_child(record.plan_id)
        change = self._sync_changes.record_planning_allocation_change(
            actor_user_id=actor_id,
            operation=mutation.operation,
            record=record,
            plan=plan,
            client_mutation_id=mutation.client_mutation_id,
        )
        return SyncMutationResult(
            client_mutation_id=mutation.client_mutation_id,
            entity_type=mutation.entity_type,
            entity_id=mutation.entity_id,
            operation=mutation.operation,
            status=MutationStatus.APPLIED,
            server_version=record.version,
            change_seq=change.seq,
            data=planning_allocation_payload(record),
        )

    def _write_transaction_change(
        self,
        *,
        actor_id: UUID,
        mutation: SyncMutationRequest,
        record: TransactionRecord,
        changed_account_ids: tuple[str, ...] = (),
    ) -> SyncChange:
        account = self._accounts.get(record.account_id)
        if account is None:
            raise ValueError("transaction account is unavailable")

        change = self._sync_changes.record_transaction_change(
            actor_user_id=actor_id,
            operation=mutation.operation,
            record=record,
            account=account,
            client_mutation_id=mutation.client_mutation_id,
        )
        if record.transaction_type != "transfer":
            return change
        if record.counterparty_account_id is None:
            raise ValueError("transfer counterparty account is unavailable")
        for account_id in changed_account_ids or _transfer_account_ids(record):
            changed_account = self._accounts.get(account_id)
            if changed_account is None:
                raise ValueError("transfer account is unavailable")
            change = self._sync_changes.record_account_change(
                actor_user_id=actor_id,
                operation="update",
                record=changed_account,
                client_mutation_id=mutation.client_mutation_id,
            )
        return change

    def _planning_plan_for_child(self, plan_id: str) -> PlanningPlanRecord:
        plan = self._planning.get_plan(plan_id)
        if plan is None:
            raise ValueError("planning child plan is unavailable")
        return plan


def _request_hash(*, client_schema_version: int, mutation: SyncMutationRequest) -> str:
    canonical = {
        "clientSchemaVersion": client_schema_version,
        "mutation": mutation.model_dump(mode="json", by_alias=True),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _guard_unique_client_mutation_ids(request: SyncPushRequest) -> None:
    seen: set[str] = set()
    for mutation in request.mutations:
        if mutation.client_mutation_id in seen:
            raise SyncValidationError(
                "VALIDATION_FAILED",
                "clientMutationId values must be unique within one sync push.",
            )
        seen.add(mutation.client_mutation_id)


def _guard_syncable_entity_types(request: SyncPushRequest) -> None:
    for mutation in request.mutations:
        if mutation.entity_type in SYNC_PUSH_ENTITY_TYPES:
            continue
        if mutation.entity_type in SYNC_ONLINE_ONLY_ENTITY_TYPES:
            raise SyncValidationError(
                "ONLINE_ONLY_ENTITY_TYPE",
                "OCR/screenshot capture is online-only and must not be queued through sync.",
            )
        raise SyncValidationError(
            "UNSUPPORTED_ENTITY_TYPE",
            "Unsupported sync entity type.",
        )


def _stored_result(row: SyncClientMutation) -> SyncMutationResult:
    if row.response_payload:
        return SyncMutationResult.model_validate(row.response_payload)
    return SyncMutationResult(
        client_mutation_id=row.client_mutation_id,
        entity_type=row.entity_type,
        entity_id=row.entity_id or UUID(int=0),
        operation=row.operation,
        status=MutationStatus.REJECTED,
        error_code=row.error_code or "SYNC_MUTATION_INCOMPLETE",
        message="Stored sync mutation result is incomplete.",
    )


def _rejected(mutation: SyncMutationRequest, code: str, message: str) -> SyncMutationResult:
    return SyncMutationResult(
        client_mutation_id=mutation.client_mutation_id,
        entity_type=mutation.entity_type,
        entity_id=mutation.entity_id,
        operation=mutation.operation,
        status=MutationStatus.REJECTED,
        error_code=code,
        message=message,
    )


def _resource_not_found(mutation: SyncMutationRequest) -> SyncMutationResult:
    return _rejected(
        mutation,
        "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
        "Resource not found or not accessible.",
    )


def _versioned_payload_for_update(
    mutation: SyncMutationRequest,
) -> dict[str, Any] | SyncMutationResult:
    if mutation.payload is None:
        return _rejected(mutation, "PAYLOAD_REQUIRED", "Mutation payload is required.")
    payload = dict(mutation.payload)
    payload_version = payload.get("version")
    if mutation.base_version is None:
        return _rejected(
            mutation,
            "BASE_VERSION_REQUIRED",
            "baseVersion is required for sync update.",
        )
    if payload_version is not None and payload_version != mutation.base_version:
        return _rejected(
            mutation,
            "VALIDATION_FAILED",
            "baseVersion and payload.version must match.",
        )
    payload.setdefault("version", mutation.base_version)
    return payload


def _payload_with_required_plan_id(
    mutation: SyncMutationRequest,
) -> tuple[str, dict[str, Any]] | SyncMutationResult:
    if mutation.payload is None:
        return _rejected(mutation, "PAYLOAD_REQUIRED", "Mutation payload is required.")
    payload = dict(mutation.payload)
    plan_id = payload.pop("planId", None)
    if plan_id is None:
        plan_id = payload.pop("plan_id", None)
    if plan_id is None:
        return _rejected(mutation, "VALIDATION_FAILED", "planId is required.")
    return str(plan_id), payload


def _reject_if_payload_id_conflicts(
    mutation: SyncMutationRequest,
    payload: dict[str, Any],
) -> SyncMutationResult | None:
    payload_id = payload.get("id")
    if payload_id is not None and str(payload_id) != str(mutation.entity_id):
        return _rejected(
            mutation,
            "VALIDATION_FAILED",
            "payload.id must match mutation.entityId.",
        )
    return None


def _has_any_key(payload: dict[str, Any], *keys: str) -> bool:
    return any(key in payload for key in keys)


def _rejected_for_transaction_error(
    mutation: SyncMutationRequest,
    error: TransactionServiceError,
) -> SyncMutationResult:
    if isinstance(error, TransactionNotFoundOrInaccessible):
        return _rejected(
            mutation,
            "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
            "Resource not found or not accessible.",
        )
    if isinstance(error, TransactionReferencedResourceError):
        return _rejected(
            mutation,
            "REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
            "Referenced resource not found or not accessible.",
        )
    if isinstance(error, TransactionConflictError):
        return _rejected(mutation, error.code or "CONFLICTING_UPDATE", "Conflicting update.")
    if isinstance(error, TransactionValidationError):
        return _rejected(
            mutation,
            error.code or error.reason.value.upper(),
            "Invalid transaction request.",
        )
    return _rejected(mutation, error.reason.value.upper(), "Unable to apply sync mutation.")


def _rejected_for_account_error(
    mutation: SyncMutationRequest,
    error: AccountServiceError,
) -> SyncMutationResult:
    if isinstance(error, AccountNotFoundOrInaccessible):
        return _resource_not_found(mutation)
    if isinstance(error, AccountConflictError):
        return _rejected(mutation, error.code, "Conflicting update.")
    if isinstance(error, AccountValidationError):
        return _rejected(mutation, error.reason.value.upper(), "Invalid account request.")
    return _rejected(mutation, error.reason.value.upper(), "Unable to apply sync mutation.")


def _rejected_for_planning_error(
    mutation: SyncMutationRequest,
    error: PlanningServiceError,
) -> SyncMutationResult:
    if isinstance(error, PlanningNotFoundOrInaccessible):
        return _resource_not_found(mutation)
    if isinstance(error, PlanningReferencedResourceError):
        return _rejected(
            mutation,
            "REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
            "Referenced resource not found or not accessible.",
        )
    if isinstance(error, PlanningConflictError):
        return _rejected(mutation, error.code or "CONFLICTING_UPDATE", "Conflicting update.")
    if isinstance(error, PlanningValidationError):
        return _rejected(
            mutation,
            error.code or error.reason.value.upper(),
            "Invalid planning request.",
        )
    return _rejected(mutation, error.reason.value.upper(), "Unable to apply sync mutation.")


def _rejected_for_investment_migration_error(
    mutation: SyncMutationRequest,
    error: InvestmentMigrationServiceError,
) -> SyncMutationResult:
    return _rejected(mutation, error.code, error.message)


def _rejected_for_http_exception(
    mutation: SyncMutationRequest,
    error: HTTPException,
) -> SyncMutationResult:
    detail = error.detail if isinstance(error.detail, dict) else {}
    code = str(detail.get("code") or "VALIDATION_FAILED")
    if error.status_code == 404:
        return _resource_not_found(mutation)
    if error.status_code == 409:
        return _rejected(mutation, code, "Conflicting update.")
    return _rejected(mutation, code, "Invalid sync mutation request.")


def _actor_uuid(actor: Actor) -> UUID:
    if actor.user_id is None:
        raise SyncValidationError("AUTHENTICATION_REQUIRED", "Authentication required.")
    try:
        return UUID(actor.user_id)
    except ValueError as exc:
        raise SyncValidationError(
            "VALIDATION_FAILED",
            "Authenticated actor must use a canonical UUID for sync.",
        ) from exc


def _transfer_account_ids(*records: TransactionRecord) -> tuple[str, ...]:
    account_ids: list[str] = []
    seen: set[str] = set()
    for record in records:
        if record.transaction_type != "transfer":
            continue
        for account_id in (record.account_id, record.counterparty_account_id):
            if account_id is None or account_id in seen:
                continue
            account_ids.append(account_id)
            seen.add(account_id)
    return tuple(account_ids)


def _change_dto(row: SyncChange) -> SyncChangeDto:
    return SyncChangeDto(
        seq=row.seq,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        change_type=row.change_type,
        entity_version=row.entity_version,
        entity_updated_at=row.entity_updated_at,
        changed_by_user_id=row.changed_by_user_id,
        client_mutation_id=row.client_mutation_id,
        payload=row.payload,
        tombstone_payload=row.tombstone_payload,
        created_at=row.created_at,
    )
