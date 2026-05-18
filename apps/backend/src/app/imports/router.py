from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.auth_context import CurrentActor
from app.authz import Actor, MembershipStatus

from .schemas import (
    ImportFileMetadataDto,
    ImportReportPreviewRequest,
    ImportReportPreviewResponse,
    ImportReportType,
    ImportScopeDto,
    ImportSourceType,
    ImportSummaryDto,
    ImportSummarySectionDto,
    ImportTargetScope,
    ImportWarningDto,
)

router = APIRouter(prefix="/imports", tags=["Imports"])


def _error_response(
    status_code: int,
    code: str,
    *,
    request_id: str | None,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "requestId": request_id or "unknown",
            }
        },
    )


@router.post(
    "/report-preview",
    response_model=ImportReportPreviewResponse,
    response_model_by_alias=True,
    operation_id="previewImportReport",
)
async def preview_import_report(
    request: ImportReportPreviewRequest,
    actor: CurrentActor,
) -> ImportReportPreviewResponse | JSONResponse:
    enum_error = _enum_error(request)
    if enum_error is not None:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "INVALID_ENUM_VALUE",
            request_id=actor.request_id,
            message="Unsupported import preview enum value.",
        )

    target_scope = ImportTargetScope(request.target_scope)
    if target_scope == ImportTargetScope.PERSONAL:
        if request.household_id is not None:
            return _error_response(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_FAILED",
                request_id=actor.request_id,
                message="Personal import preview must not include householdId.",
            )
    elif not _has_active_membership(actor, request.household_id):
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
            request_id=actor.request_id,
            message="Resource not found or not accessible.",
        )

    return _preview_response(request, target_scope=target_scope)


def _enum_error(
    request: ImportReportPreviewRequest,
) -> Literal["reportType", "sourceType", "targetScope"] | None:
    if request.report_type not in {item.value for item in ImportReportType}:
        return "reportType"
    if request.source_type not in {item.value for item in ImportSourceType}:
        return "sourceType"
    if request.target_scope not in {item.value for item in ImportTargetScope}:
        return "targetScope"
    return None


def _has_active_membership(actor: Actor, household_id: str | None) -> bool:
    if not actor.user_id or not household_id:
        return False

    return any(
        membership.user_id == actor.user_id
        and membership.household_id == household_id
        and membership.status == MembershipStatus.ACTIVE
        for membership in actor.memberships
    )


def _preview_response(
    request: ImportReportPreviewRequest,
    *,
    target_scope: ImportTargetScope,
) -> ImportReportPreviewResponse:
    return ImportReportPreviewResponse(
        status="preview_placeholder",
        can_confirm=False,
        will_change_data=False,
        message="Файл не импортирован. Сейчас показана только предварительная сводка.",
        scope=ImportScopeDto(
            target_scope=target_scope,
            household_id=request.household_id if target_scope == ImportTargetScope.SHARED else None,
        ),
        file=ImportFileMetadataDto(
            file_name=_safe_display_file_name(request.file_name),
            file_size_bytes=request.file_size_bytes,
            mime_type=request.mime_type,
        ),
        summary=ImportSummaryDto(
            title="Предварительный просмотр импорта",
            status_text="Импорт пока не выполняется",
            sections=[
                ImportSummarySectionDto(
                    key="accounts_assets",
                    title="Счета и активы",
                    status="not_recognized_yet",
                    text="Счета и активы пока не распознаны и не созданы.",
                ),
                ImportSummarySectionDto(
                    key="transactions",
                    title="Операции",
                    status="not_recognized_yet",
                    text="Операции не распознаны и не добавлены.",
                ),
                ImportSummarySectionDto(
                    key="categories",
                    title="Категории",
                    status="not_recognized_yet",
                    text="Категории не распознаны и не созданы.",
                ),
                ImportSummarySectionDto(
                    key="transfers",
                    title="Переводы",
                    status="not_recognized_yet",
                    text="Переводы не распознаны и не созданы.",
                ),
                ImportSummarySectionDto(
                    key="brokerage_deposits_metals",
                    title="Брокеры, вклады и металлы",
                    status="not_recognized_yet",
                    text="Брокерские отчеты, вклады и металлы пока не обрабатываются.",
                ),
            ],
        ),
        warnings=[
            ImportWarningDto(
                code="PLACEHOLDER_ONLY",
                text="Импорт пока не выполняется.",
            ),
            ImportWarningDto(
                code="NO_FILE_STORAGE_OR_PARSING",
                text="Содержимое файла не сохраняется и не разбирается.",
            ),
            ImportWarningDto(
                code="NO_DATA_CHANGES_WITHOUT_CONFIRMATION",
                text="Данные не изменятся без подтверждения.",
            ),
        ],
    )


def _safe_display_file_name(value: str | None) -> str | None:
    if value is None:
        return None
    without_nul = value.replace("\x00", "")
    normalized = re.split(r"[\\/]+", without_nul.strip())[-1]
    return normalized[:255] or None

