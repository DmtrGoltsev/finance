from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.accounts import router as accounts_router
from app.asset_categories import router as asset_categories_router
from app.api.error_contract import ErrorEnvelopeRoute, error_response, request_id_for
from app.auth.router import router as auth_router
from app.capture_drafts import router as capture_drafts_router
from app.categories import router as categories_router
from app.planning import router as planning_router
from app.reports import router as reports_router
from app.transactions import router as transactions_router

api_router = APIRouter(route_class=ErrorEnvelopeRoute)


def _include_router_with_error_envelope(router: APIRouter) -> None:
    for route in router.routes:
        if not isinstance(route, APIRoute):
            api_router.routes.append(route)
            continue

        api_router.add_api_route(
            route.path,
            route.endpoint,
            response_model=route.response_model,
            status_code=route.status_code,
            tags=route.tags,
            dependencies=route.dependencies,
            summary=route.summary,
            description=route.description,
            response_description=route.response_description,
            responses=route.responses,
            deprecated=route.deprecated,
            methods=route.methods,
            operation_id=route.operation_id,
            response_model_include=route.response_model_include,
            response_model_exclude=route.response_model_exclude,
            response_model_by_alias=route.response_model_by_alias,
            response_model_exclude_unset=route.response_model_exclude_unset,
            response_model_exclude_defaults=route.response_model_exclude_defaults,
            response_model_exclude_none=route.response_model_exclude_none,
            include_in_schema=route.include_in_schema,
            response_class=route.response_class,
            name=route.name,
            route_class_override=ErrorEnvelopeRoute,
            callbacks=route.callbacks,
            openapi_extra=route.openapi_extra,
        )


_include_router_with_error_envelope(auth_router)
_include_router_with_error_envelope(accounts_router)
_include_router_with_error_envelope(asset_categories_router)
_include_router_with_error_envelope(categories_router)
_include_router_with_error_envelope(transactions_router)
_include_router_with_error_envelope(capture_drafts_router)
_include_router_with_error_envelope(reports_router)
_include_router_with_error_envelope(planning_router)


@api_router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def api_not_found(request: Request) -> JSONResponse:
    return error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        request_id=request_id_for(request),
    )
