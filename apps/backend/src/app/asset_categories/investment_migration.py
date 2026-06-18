from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from fastapi import status

from app.accounts.repository import AccountRecord, AccountRepository, account_repository
from app.accounts.schemas import AccountDto
from app.authz import (
    Account as AuthzAccount,
)
from app.authz import (
    AccountOwnershipType,
    Actor,
    DenialReason,
    ResourceStatus,
    canMutateAccount,
    canReadAccount,
)
from app.sync.domain_changes import (
    SyncChangeRecorder,
    account_payload,
    asset_category_payload,
)

from .investment_migration_schemas import InvestmentMigrationCreateRequest, InvestmentMigrationDto
from .repository import AssetCategoryRecord, AssetCategoryRepository, repository
from .schemas import AssetCategoryDto, AssetCategoryScope, AssetCategoryType
from .service import can_read_asset_category

ACCOUNT_ALREADY_LINKED_CODE = "ACCOUNT_ALREADY_LINKED_TO_ASSET_CATEGORY"
ACCOUNT_ASSET_TYPE_MISMATCH_CODE = "ACCOUNT_ASSET_TYPE_MISMATCH"
ACCOUNT_CURRENCY_MISMATCH_CODE = "ACCOUNT_CURRENCY_MISMATCH"
ACCOUNT_SCOPE_MISMATCH_CODE = "ACCOUNT_SCOPE_MISMATCH"
ACCOUNT_VERSION_REQUIRED_CODE = "ACCOUNT_VERSION_REQUIRED"
ARCHIVED_NOT_MUTABLE_CODE = "ARCHIVED_RECORD_NOT_MUTABLE"
ASSET_CATEGORY_ALREADY_EXISTS_CODE = "ASSET_CATEGORY_ALREADY_EXISTS"
CONFLICTING_UPDATE_CODE = "CONFLICTING_UPDATE"
DUPLICATE_ACCOUNT_ID_CODE = "DUPLICATE_ACCOUNT_ID"
RESOURCE_NOT_FOUND_CODE = "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE"


@dataclass(frozen=True, slots=True)
class InvestmentMigrationResult:
    asset_category: AssetCategoryRecord
    accounts: tuple[AccountRecord, ...]
    change_seq: int | None = None


@dataclass(frozen=True, slots=True)
class _ResolvedScope:
    scope_type: AssetCategoryScope
    owner_user_id: str | None
    household_id: str | None


class InvestmentMigrationServiceError(Exception):
    def __init__(self, *, code: str, message: str, http_status: int) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status


class InvestmentMigrationService:
    def __init__(
        self,
        asset_categories: AssetCategoryRepository = repository,
        accounts: AccountRepository = account_repository,
        sync_change_recorder: SyncChangeRecorder | None = None,
    ) -> None:
        self._asset_categories = asset_categories
        self._accounts = accounts
        self._sync_change_recorder = sync_change_recorder

    def create(
        self,
        *,
        actor: Actor,
        request: InvestmentMigrationCreateRequest,
        client_mutation_id: str | None = None,
    ) -> InvestmentMigrationResult:
        if not actor.user_id:
            raise _error(
                RESOURCE_NOT_FOUND_CODE,
                "Resource not found or not accessible.",
                status.HTTP_404_NOT_FOUND,
            )

        account_ids = _unique_account_ids(request.account_ids)
        _validate_account_version_keys(account_ids, request.account_versions)
        self._require_asset_category_id_available(actor, request.asset_category_id)

        accounts = tuple(
            self._visible_mutable_account(actor, account_id)
            for account_id in account_ids
        )
        resolved_scope = _resolve_scope(actor=actor, request=request, accounts=accounts)
        self._validate_accounts_against_request(
            request=request,
            accounts=accounts,
            scope=resolved_scope,
        )

        asset_category = self._asset_categories.create(
            asset_category_id=request.asset_category_id,
            name=request.name,
            scope_type=resolved_scope.scope_type,
            owner_user_id=resolved_scope.owner_user_id,
            household_id=resolved_scope.household_id,
            currency=request.currency,
            asset_type=AssetCategoryType(request.asset_type),
            icon_key=request.icon_key,
            manual_amount=Decimal("0.0000"),
            is_investment=True,
            created_by_user_id=actor.user_id,
        )

        changes = []
        if self._sync_change_recorder is not None:
            changes.append(
                self._sync_change_recorder.record_asset_category_change(
                    actor_user_id=actor.user_id,
                    operation="create",
                    record=asset_category,
                    client_mutation_id=client_mutation_id,
                )
            )

        updated_accounts: list[AccountRecord] = []
        for account in accounts:
            updated = self._accounts.save(
                replace(account, asset_category_id=asset_category.id)
            )
            updated_accounts.append(updated)
            if self._sync_change_recorder is not None:
                changes.append(
                    self._sync_change_recorder.record_account_change(
                        actor_user_id=actor.user_id,
                        operation="update",
                        record=updated,
                        client_mutation_id=client_mutation_id,
                    )
                )

        return InvestmentMigrationResult(
            asset_category=asset_category,
            accounts=tuple(updated_accounts),
            change_seq=changes[-1].seq if changes else None,
        )

    def _require_asset_category_id_available(
        self,
        actor: Actor,
        asset_category_id: str,
    ) -> None:
        existing = self._asset_categories.get(asset_category_id)
        if existing is None:
            return
        if can_read_asset_category(actor, existing):
            raise _error(
                ASSET_CATEGORY_ALREADY_EXISTS_CODE,
                "Asset category already exists.",
                status.HTTP_409_CONFLICT,
            )
        raise _error(
            ASSET_CATEGORY_ALREADY_EXISTS_CODE,
            "Asset category already exists.",
            status.HTTP_409_CONFLICT,
        )

    def _visible_mutable_account(self, actor: Actor, account_id: str) -> AccountRecord:
        account = self._accounts.get(account_id)
        if account is None or not canReadAccount(actor, _authz_account(account)).allowed:
            raise _error(
                RESOURCE_NOT_FOUND_CODE,
                "Resource not found or not accessible.",
                status.HTTP_404_NOT_FOUND,
            )

        decision = canMutateAccount(actor, _authz_account(account))
        if decision.allowed:
            return account
        if decision.reason == DenialReason.ARCHIVED_RECORD_NOT_MUTABLE:
            raise _error(
                ARCHIVED_NOT_MUTABLE_CODE,
                "Archived or deleted records are not mutable.",
                status.HTTP_409_CONFLICT,
            )
        raise _error(
            RESOURCE_NOT_FOUND_CODE,
            "Resource not found or not accessible.",
            status.HTTP_404_NOT_FOUND,
        )

    def _validate_accounts_against_request(
        self,
        *,
        request: InvestmentMigrationCreateRequest,
        accounts: tuple[AccountRecord, ...],
        scope: _ResolvedScope,
    ) -> None:
        for account in accounts:
            expected_version = request.account_versions[account.id]
            if account.version != expected_version:
                raise _error(
                    CONFLICTING_UPDATE_CODE,
                    "Account version is stale.",
                    status.HTTP_409_CONFLICT,
                )
            if account.status != ResourceStatus.ACTIVE:
                raise _error(
                    ARCHIVED_NOT_MUTABLE_CODE,
                    "Archived or deleted records are not mutable.",
                    status.HTTP_409_CONFLICT,
                )
            if account.asset_category_id is not None:
                raise _error(
                    ACCOUNT_ALREADY_LINKED_CODE,
                    "Account is already linked to an asset category.",
                    status.HTTP_409_CONFLICT,
                )
            if account.currency != request.currency:
                raise _error(
                    ACCOUNT_CURRENCY_MISMATCH_CODE,
                    "Account currency does not match requested asset category currency.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            if account.account_type != str(request.asset_type):
                raise _error(
                    ACCOUNT_ASSET_TYPE_MISMATCH_CODE,
                    "Account type does not match requested asset category asset type.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            if not _account_matches_scope(account, scope):
                raise _error(
                    ACCOUNT_SCOPE_MISMATCH_CODE,
                    "Account scope does not match requested asset category scope.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )


def investment_migration_dto(result: InvestmentMigrationResult) -> InvestmentMigrationDto:
    return InvestmentMigrationDto(
        asset_category=_asset_category_dto(result.asset_category),
        accounts=[_account_dto(record) for record in result.accounts],
    )


def investment_migration_payload(result: InvestmentMigrationResult) -> dict[str, object]:
    return {
        "assetCategory": asset_category_payload(result.asset_category),
        "accounts": [account_payload(record) for record in result.accounts],
    }


def _unique_account_ids(account_ids: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique: list[str] = []
    for account_id in account_ids:
        if account_id in seen:
            raise _error(
                DUPLICATE_ACCOUNT_ID_CODE,
                "accountIds must not contain duplicates.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        seen.add(account_id)
        unique.append(account_id)
    return tuple(unique)


def _validate_account_version_keys(
    account_ids: tuple[str, ...],
    account_versions: dict[str, int],
) -> None:
    if set(account_versions) != set(account_ids):
        raise _error(
            ACCOUNT_VERSION_REQUIRED_CODE,
            "accountVersions must include exactly one version for each accountId.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


def _resolve_scope(
    *,
    actor: Actor,
    request: InvestmentMigrationCreateRequest,
    accounts: tuple[AccountRecord, ...],
) -> _ResolvedScope:
    first = accounts[0]
    scope_type = request.scope_type
    if scope_type is None and request.household_id is not None:
        scope_type = AssetCategoryScope.HOUSEHOLD
    if scope_type is None:
        scope_type = (
            AssetCategoryScope.PERSONAL
            if first.ownership_type == AccountOwnershipType.PERSONAL
            else AssetCategoryScope.HOUSEHOLD
        )

    if scope_type == AssetCategoryScope.PERSONAL:
        if request.household_id is not None:
            raise _error(
                ACCOUNT_SCOPE_MISMATCH_CODE,
                "Personal investment migration must not include householdId.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return _ResolvedScope(
            scope_type=AssetCategoryScope.PERSONAL,
            owner_user_id=actor.user_id,
            household_id=None,
        )

    household_id = request.household_id or first.household_id
    if household_id is None:
        raise _error(
            ACCOUNT_SCOPE_MISMATCH_CODE,
            "Household investment migration requires householdId or shared accounts.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return _ResolvedScope(
        scope_type=AssetCategoryScope.HOUSEHOLD,
        owner_user_id=None,
        household_id=household_id,
    )


def _account_matches_scope(account: AccountRecord, scope: _ResolvedScope) -> bool:
    if scope.scope_type == AssetCategoryScope.PERSONAL:
        return (
            account.ownership_type == AccountOwnershipType.PERSONAL
            and account.owner_user_id == scope.owner_user_id
            and account.household_id is None
        )
    return (
        account.ownership_type == AccountOwnershipType.SHARED
        and account.household_id == scope.household_id
        and account.owner_user_id is None
    )


def _authz_account(record: AccountRecord) -> AuthzAccount:
    return AuthzAccount(
        id=record.id,
        ownership_type=record.ownership_type,
        owner_user_id=record.owner_user_id,
        household_id=record.household_id,
        status=record.status,
    )


def _asset_category_dto(record: AssetCategoryRecord) -> AssetCategoryDto:
    return AssetCategoryDto(
        id=record.id,
        name=record.name,
        scope_type=record.scope_type,
        owner_user_id=record.owner_user_id,
        household_id=record.household_id,
        currency=record.currency,
        asset_type=record.asset_type,
        iconKey=record.icon_key,
        manual_amount=Decimal(record.manual_amount),
        is_investment=record.is_investment,
        record_status=record.status,
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        archived_at=record.archived_at,
        deleted_at=record.deleted_at,
        version=record.version,
    )


def _account_dto(record: AccountRecord) -> AccountDto:
    return AccountDto(
        id=record.id,
        name=record.name,
        account_type=record.account_type,
        ownership_type=record.ownership_type.value,
        owner_user_id=record.owner_user_id,
        household_id=record.household_id,
        asset_category_id=record.asset_category_id,
        is_payment_account=record.is_payment_account,
        currency=record.currency,
        initial_balance=record.initial_balance,
        current_balance=record.current_balance,
        status=record.status.value,
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        archived_at=record.archived_at,
        deleted_at=record.deleted_at,
        version=record.version,
    )


def _error(code: str, message: str, http_status: int) -> InvestmentMigrationServiceError:
    return InvestmentMigrationServiceError(
        code=code,
        message=message,
        http_status=http_status,
    )


investment_migration_service = InvestmentMigrationService()
