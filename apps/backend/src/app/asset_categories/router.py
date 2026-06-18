from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status
from fastapi.responses import JSONResponse

from app.accounts.repository import SqlAlchemyAccountRepository
from app.api.auth_context import CurrentActor
from app.config import get_settings
from app.db.session import accounts_categories_repository_mode, sync_session_scope
from app.sync.domain_changes import SyncChangeRecorder

from .investment_migration import (
    InvestmentMigrationService,
    InvestmentMigrationServiceError,
    investment_migration_dto,
    investment_migration_service,
)
from .investment_migration_schemas import (
    InvestmentMigrationCreateRequest,
    InvestmentMigrationEnvelope,
)
from .repository import SqlAlchemyAssetCategoryRepository
from .schemas import (
    AssetCategoryCreateRequest,
    AssetCategoryEnvelope,
    AssetCategoryPageEnvelope,
    AssetCategoryScope,
    AssetCategoryUpdateRequest,
    RecordStatus,
)
from .service import AssetCategoryService, service

router = APIRouter(prefix="/asset-categories", tags=["Asset Categories"])


def asset_category_service_for_request() -> Iterator[AssetCategoryService]:
    if accounts_categories_repository_mode() != "db":
        yield service
        return

    with sync_session_scope(get_settings()) as session:
        yield AssetCategoryService(
            SqlAlchemyAssetCategoryRepository(session),
            SyncChangeRecorder(session),
        )


AssetCategoryServiceDependency = Annotated[
    AssetCategoryService,
    Depends(asset_category_service_for_request),
]


def investment_migration_service_for_request() -> Iterator[InvestmentMigrationService]:
    if accounts_categories_repository_mode() != "db":
        yield investment_migration_service
        return

    with sync_session_scope(get_settings()) as session:
        yield InvestmentMigrationService(
            SqlAlchemyAssetCategoryRepository(session),
            SqlAlchemyAccountRepository(session),
            SyncChangeRecorder(session),
        )


InvestmentMigrationServiceDependency = Annotated[
    InvestmentMigrationService,
    Depends(investment_migration_service_for_request),
]

Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(min_length=1)]
HouseholdIdFilter = Annotated[str | None, Query(alias="householdId", min_length=1, max_length=128)]
SearchQuery = Annotated[str | None, Query(alias="q", min_length=1, max_length=200)]
AssetCategoryId = Annotated[
    str,
    Path(alias="assetCategoryId", min_length=1, max_length=128),
]


@router.get(
    "",
    operation_id="listAssetCategories",
    response_model=AssetCategoryPageEnvelope,
    response_model_by_alias=True,
)
async def list_asset_categories(
    actor: CurrentActor,
    asset_category_service: AssetCategoryServiceDependency,
    limit: Limit = 50,
    cursor: Cursor = None,
    scopeType: AssetCategoryScope | None = None,
    household_id: HouseholdIdFilter = None,
    record_status_filter: Annotated[RecordStatus | None, Query(alias="recordStatus")] = None,
    isInvestment: bool | None = None,
    q: SearchQuery = None,
) -> AssetCategoryPageEnvelope:
    return asset_category_service.list(
        actor=actor,
        limit=limit,
        cursor=cursor,
        scope_type=scopeType,
        household_id=household_id,
        status_filter=record_status_filter,
        is_investment=isInvestment,
        q=q,
    )


@router.post(
    "",
    operation_id="createAssetCategory",
    response_model=AssetCategoryEnvelope,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_asset_category(
    request: AssetCategoryCreateRequest,
    actor: CurrentActor,
    asset_category_service: AssetCategoryServiceDependency,
) -> AssetCategoryEnvelope:
    return AssetCategoryEnvelope(data=asset_category_service.create(actor=actor, request=request))


@router.post(
    "/investment-migrations",
    operation_id="createInvestmentMigration",
    response_model=InvestmentMigrationEnvelope,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_investment_migration(
    request: InvestmentMigrationCreateRequest,
    actor: CurrentActor,
    investment_migration_service: InvestmentMigrationServiceDependency,
) -> InvestmentMigrationEnvelope | JSONResponse:
    try:
        result = investment_migration_service.create(actor=actor, request=request)
    except InvestmentMigrationServiceError as error:
        return JSONResponse(
            status_code=error.http_status,
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "requestId": actor.request_id or "request-unavailable",
                }
            },
        )
    return InvestmentMigrationEnvelope(data=investment_migration_dto(result))


@router.get(
    "/{assetCategoryId}",
    operation_id="getAssetCategory",
    response_model=AssetCategoryEnvelope,
    response_model_by_alias=True,
)
async def get_asset_category(
    asset_category_id: AssetCategoryId,
    actor: CurrentActor,
    asset_category_service: AssetCategoryServiceDependency,
) -> AssetCategoryEnvelope:
    return AssetCategoryEnvelope(
        data=asset_category_service.get(
            actor=actor,
            asset_category_id=asset_category_id,
        )
    )


@router.patch(
    "/{assetCategoryId}",
    operation_id="updateAssetCategory",
    response_model=AssetCategoryEnvelope,
    response_model_by_alias=True,
)
async def update_asset_category(
    asset_category_id: AssetCategoryId,
    request: AssetCategoryUpdateRequest,
    actor: CurrentActor,
    asset_category_service: AssetCategoryServiceDependency,
) -> AssetCategoryEnvelope:
    return AssetCategoryEnvelope(
        data=asset_category_service.update(
            actor=actor,
            asset_category_id=asset_category_id,
            request=request,
        )
    )


@router.delete(
    "/{assetCategoryId}",
    operation_id="deleteAssetCategory",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_asset_category(
    asset_category_id: AssetCategoryId,
    actor: CurrentActor,
    asset_category_service: AssetCategoryServiceDependency,
) -> Response:
    asset_category_service.delete(actor=actor, asset_category_id=asset_category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{assetCategoryId}/archive",
    operation_id="archiveAssetCategory",
    response_model=AssetCategoryEnvelope,
    response_model_by_alias=True,
)
async def archive_asset_category(
    asset_category_id: AssetCategoryId,
    actor: CurrentActor,
    asset_category_service: AssetCategoryServiceDependency,
) -> AssetCategoryEnvelope:
    return AssetCategoryEnvelope(
        data=asset_category_service.archive(
            actor=actor,
            asset_category_id=asset_category_id,
        )
    )


@router.post(
    "/{assetCategoryId}/restore",
    operation_id="restoreAssetCategory",
    response_model=AssetCategoryEnvelope,
    response_model_by_alias=True,
)
async def restore_asset_category(
    asset_category_id: AssetCategoryId,
    actor: CurrentActor,
    asset_category_service: AssetCategoryServiceDependency,
) -> AssetCategoryEnvelope:
    return AssetCategoryEnvelope(
        data=asset_category_service.restore(
            actor=actor,
            asset_category_id=asset_category_id,
        )
    )
