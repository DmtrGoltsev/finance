from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.api.auth_context import CurrentActor
from app.config import get_settings
from app.db.session import accounts_categories_repository_mode, sync_session_scope
from app.sync.domain_changes import SyncChangeRecorder

from .repository import SqlAlchemyCategoryRepository
from .schemas import (
    CategoryAutocompleteListEnvelope,
    CategoryCreateRequest,
    CategoryEnvelope,
    CategoryListSort,
    CategoryPageEnvelope,
    CategoryScope,
    CategoryType,
    CategoryUpdateRequest,
    RecordStatus,
)
from .service import CategoryService, service

router = APIRouter(prefix="/categories", tags=["Categories"])


def category_service_for_request() -> Iterator[CategoryService]:
    if accounts_categories_repository_mode() != "db":
        yield service
        return

    with sync_session_scope(get_settings()) as session:
        yield CategoryService(SqlAlchemyCategoryRepository(session), SyncChangeRecorder(session))


CategoryServiceDependency = Annotated[CategoryService, Depends(category_service_for_request)]


Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(min_length=1)]
SearchQuery = Annotated[str | None, Query(alias="q", min_length=1, max_length=200)]
HouseholdIdFilter = Annotated[str | None, Query(alias="householdId", min_length=1, max_length=128)]
CategoryId = Annotated[str, Path(alias="categoryId", min_length=1, max_length=128)]


@router.get("", operation_id="listCategories", response_model=CategoryPageEnvelope)
async def list_categories(
    actor: CurrentActor,
    category_service: CategoryServiceDependency,
    limit: Limit = 50,
    cursor: Cursor = None,
    scope: CategoryScope | None = None,
    type: CategoryType | None = None,
    household_id: HouseholdIdFilter = None,
    status_filter: Annotated[RecordStatus | None, Query(alias="status")] = None,
    q: SearchQuery = None,
    sort: CategoryListSort | None = None,
) -> CategoryPageEnvelope:
    items, page = category_service.list(
        actor=actor,
        limit=limit,
        cursor=cursor,
        scope=scope,
        type=type,
        household_id=household_id,
        status_filter=status_filter,
        q=q,
        sort=sort,
    )
    return CategoryPageEnvelope(items=items, page=page)


@router.post(
    "",
    operation_id="createCategory",
    response_model=CategoryEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    request: CategoryCreateRequest,
    actor: CurrentActor,
    category_service: CategoryServiceDependency,
) -> CategoryEnvelope:
    return CategoryEnvelope(data=category_service.create(actor=actor, request=request))


@router.get(
    "/autocomplete",
    operation_id="autocompleteCategories",
    response_model=CategoryAutocompleteListEnvelope,
)
async def autocomplete_categories(
    actor: CurrentActor,
    category_service: CategoryServiceDependency,
    q: SearchQuery = None,
    limit: Limit = 50,
    scope: CategoryScope | None = None,
    type: CategoryType | None = None,
    household_id: HouseholdIdFilter = None,
) -> CategoryAutocompleteListEnvelope:
    return CategoryAutocompleteListEnvelope(
        items=category_service.autocomplete(
            actor=actor,
            limit=limit,
            scope=scope,
            type=type,
            household_id=household_id,
            q=q,
        )
    )


@router.get("/{categoryId}", operation_id="getCategory", response_model=CategoryEnvelope)
async def get_category(
    category_id: CategoryId,
    actor: CurrentActor,
    category_service: CategoryServiceDependency,
) -> CategoryEnvelope:
    return CategoryEnvelope(data=category_service.get(actor=actor, category_id=category_id))


@router.patch("/{categoryId}", operation_id="updateCategory", response_model=CategoryEnvelope)
async def update_category(
    category_id: CategoryId,
    request: CategoryUpdateRequest,
    actor: CurrentActor,
    category_service: CategoryServiceDependency,
) -> CategoryEnvelope:
    return CategoryEnvelope(
        data=category_service.update(actor=actor, category_id=category_id, request=request)
    )


@router.delete(
    "/{categoryId}",
    operation_id="deleteCategory",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_category(
    category_id: CategoryId,
    actor: CurrentActor,
    category_service: CategoryServiceDependency,
) -> Response:
    category_service.delete(actor=actor, category_id=category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{categoryId}/archive",
    operation_id="archiveCategory",
    response_model=CategoryEnvelope,
)
async def archive_category(
    category_id: CategoryId,
    actor: CurrentActor,
    category_service: CategoryServiceDependency,
) -> CategoryEnvelope:
    return CategoryEnvelope(data=category_service.archive(actor=actor, category_id=category_id))


@router.post(
    "/{categoryId}/restore",
    operation_id="restoreCategory",
    response_model=CategoryEnvelope,
)
async def restore_category(
    category_id: CategoryId,
    actor: CurrentActor,
    category_service: CategoryServiceDependency,
) -> CategoryEnvelope:
    return CategoryEnvelope(data=category_service.restore(actor=actor, category_id=category_id))
