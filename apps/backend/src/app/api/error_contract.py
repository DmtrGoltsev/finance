from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

REQUEST_ID_HEADER = "x-request-id"
REQUEST_ID_FALLBACK = "request-unavailable"

ERROR_CODE_BY_STATUS = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "AUTHENTICATION_REQUIRED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
    422: "VALIDATION_FAILED",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_ERROR",
}

ERROR_MESSAGE_BY_STATUS = {
    status.HTTP_400_BAD_REQUEST: "Bad request.",
    status.HTTP_401_UNAUTHORIZED: "Authentication required.",
    status.HTTP_403_FORBIDDEN: "Forbidden.",
    status.HTTP_404_NOT_FOUND: "Resource not found or not accessible.",
    422: "Validation failed.",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal server error.",
}


def request_id_for(request: Request) -> str:
    request_id = request.headers.get(REQUEST_ID_HEADER)
    if request_id:
        return request_id
    return REQUEST_ID_FALLBACK


def error_envelope(
    *,
    code: str,
    message: str,
    request_id: str,
    details: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "requestId": request_id,
    }
    if details:
        error["details"] = details
    return {"error": error}


def error_response(
    *,
    status_code: int,
    request_id: str,
    code: str | None = None,
    message: str | None = None,
    details: list[dict[str, str]] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_envelope(
            code=code or ERROR_CODE_BY_STATUS.get(status_code, "REQUEST_FAILED"),
            message=message or ERROR_MESSAGE_BY_STATUS.get(status_code, "Request failed."),
            request_id=request_id,
            details=details,
        ),
    )


def _safe_details(value: object) -> list[dict[str, str]] | None:
    if not isinstance(value, list):
        return None

    details: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        safe_item: dict[str, str] = {}
        for key in ("field", "message", "code"):
            child = item.get(key)
            if isinstance(child, str):
                safe_item[key] = child
        if safe_item:
            details.append(safe_item)
    return details or None


def normalize_http_exception(exc: HTTPException, request: Request) -> JSONResponse:
    status_code = exc.status_code
    request_id = request_id_for(request)
    detail = exc.detail

    if isinstance(detail, dict):
        if "error" in detail and isinstance(detail["error"], dict):
            detail = detail["error"]

        code = detail.get("code") if isinstance(detail.get("code"), str) else None
        message = detail.get("message") if isinstance(detail.get("message"), str) else None
        detail_request_id = (
            detail.get("requestId") if isinstance(detail.get("requestId"), str) else None
        )
        details = _safe_details(detail.get("details"))
        return error_response(
            status_code=status_code,
            code=code,
            message=message,
            request_id=detail_request_id or request_id,
            details=details,
        )

    code = ERROR_CODE_BY_STATUS.get(status_code)
    message = ERROR_MESSAGE_BY_STATUS.get(status_code)
    if isinstance(detail, str) and detail == "authentication_required":
        code = "AUTHENTICATION_REQUIRED"
        message = "Authentication required."

    return error_response(
        status_code=status_code,
        request_id=request_id,
        code=code,
        message=message,
    )


def normalize_validation_exception(
    exc: RequestValidationError,
    request: Request,
) -> JSONResponse:
    details: list[dict[str, str]] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
        if not loc:
            loc = "request"
        details.append(
            {
                "field": loc,
                "message": "Invalid value.",
                "code": str(error.get("type", "validation_error")),
            }
        )

    return error_response(
        status_code=422,
        request_id=request_id_for(request),
        details=details,
    )


class ErrorEnvelopeRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Any]:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                return normalize_validation_exception(exc, request)
            except HTTPException as exc:
                return normalize_http_exception(exc, request)
            except Exception:
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    request_id=request_id_for(request),
                )

        return custom_route_handler
