from __future__ import annotations

from app.authz import (
    Actor,
    CategoryKind,
    DenialReason,
    ResourceStatus,
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

from .aggregate_parser import external_label_hash, normalize_aggregate_label
from .category_mappings_repository import (
    CaptureCategoryMappingRecord,
    CaptureCategoryMappingRepository,
    CaptureCategoryMappingUpsertValues,
    repository,
)
from .schemas import CaptureCategoryMappingPutRequest


class CaptureCategoryMappingServiceError(Exception):
    def __init__(self, reason: DenialReason, *, code: str | None = None) -> None:
        self.reason = reason
        self.code = code


class CaptureCategoryMappingReferencedResourceError(CaptureCategoryMappingServiceError):
    def __init__(self) -> None:
        super().__init__(DenialReason.REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE)


class CaptureCategoryMappingValidationError(CaptureCategoryMappingServiceError):
    pass


class CaptureCategoryMappingService:
    def __init__(
        self,
        mappings: CaptureCategoryMappingRepository = repository,
        categories: CategoryRepository | None = None,
    ) -> None:
        if categories is None:
            from app.categories.repository import repository as category_repository

            categories = category_repository
        self._mappings = mappings
        self._categories = categories

    def upsert_mapping(
        self,
        *,
        actor: Actor,
        request: CaptureCategoryMappingPutRequest,
    ) -> CaptureCategoryMappingRecord:
        owner_user_id = _require_user_id(actor)
        normalized_label = normalize_aggregate_label(request.external_label)
        if not normalized_label:
            raise CaptureCategoryMappingValidationError(DenialReason.VALIDATION_FAILED)

        household_id = self._validated_context(actor, request.household_id)
        category = self._categories.get(request.category_id)
        if not self._is_usable_category(actor, category, household_id=household_id):
            raise CaptureCategoryMappingReferencedResourceError()

        return self._mappings.upsert(
            CaptureCategoryMappingUpsertValues(
                owner_user_id=owner_user_id,
                household_id=household_id,
                external_label_hash=external_label_hash(request.external_label),
                category_id=request.category_id,
            )
        )

    def lookup_suggested_category_id(
        self,
        *,
        actor: Actor,
        external_label: str,
        household_id: str | None,
    ) -> str | None:
        owner_user_id = actor.user_id
        if not owner_user_id:
            return None
        try:
            validated_household_id = self._validated_context(actor, household_id)
        except CaptureCategoryMappingServiceError:
            return None

        category_id = self._mappings.find_category_id(
            owner_user_id=owner_user_id,
            household_id=validated_household_id,
            external_label_hash=external_label_hash(external_label),
        )
        if category_id is None:
            return None

        category = self._categories.get(category_id)
        if not self._is_usable_category(
            actor,
            category,
            household_id=validated_household_id,
        ):
            return None
        return category.id

    def _validated_context(self, actor: Actor, household_id: str | None) -> str | None:
        if household_id is None:
            return None
        if _is_active_household_member(actor, household_id):
            return household_id
        raise CaptureCategoryMappingReferencedResourceError()

    def _is_usable_category(
        self,
        actor: Actor,
        category: CategoryRecord | None,
        *,
        household_id: str | None,
    ) -> bool:
        if category is None:
            return False
        if category.status != RecordStatus.ACTIVE or category.type != CategoryType.EXPENSE:
            return False
        if not canReadCategory(actor, _authz_category(category)).allowed:
            return False
        if household_id is None:
            return (
                category.scope == CategoryScope.PERSONAL
                and category.owner_user_id == actor.user_id
                and category.household_id is None
            )
        return (
            category.scope == CategoryScope.HOUSEHOLD
            and category.household_id == household_id
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


def _is_active_household_member(actor: Actor, household_id: str | None) -> bool:
    if not actor.user_id or not household_id:
        return False
    return any(
        membership.user_id == actor.user_id
        and membership.household_id == household_id
        and str(membership.status) == "active"
        for membership in actor.memberships
    )


def _require_user_id(actor: Actor) -> str:
    if not actor.user_id:
        raise CaptureCategoryMappingReferencedResourceError()
    return actor.user_id
