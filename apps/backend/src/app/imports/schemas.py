from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ResourceId = Annotated[str, StringConstraints(min_length=1, max_length=128)]


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
        use_enum_values=True,
    )


class ImportReportType(StrEnum):
    GENERIC_FINANCE_REPORT = "generic_finance_report"
    BANK_STATEMENT = "bank_statement"
    BROKERAGE_REPORT = "brokerage_report"
    DEPOSIT_REPORT = "deposit_report"
    METALS_REPORT = "metals_report"


class ImportSourceType(StrEnum):
    FILE_METADATA_ONLY = "file_metadata_only"


class ImportTargetScope(StrEnum):
    PERSONAL = "personal"
    SHARED = "shared"


class ImportReportPreviewRequest(ApiModel):
    report_type: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    source_type: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    target_scope: Annotated[str, StringConstraints(min_length=1, max_length=20)]
    household_id: ResourceId | None = None
    file_name: Annotated[str, StringConstraints(max_length=255)] | None = None
    file_size_bytes: Annotated[int, Field(ge=0)] | None = None
    mime_type: Annotated[str, StringConstraints(max_length=255)] | None = None


class ImportScopeDto(ApiModel):
    target_scope: ImportTargetScope
    household_id: ResourceId | None = None


class ImportFileMetadataDto(ApiModel):
    file_name: Annotated[str, StringConstraints(max_length=255)] | None = None
    file_size_bytes: Annotated[int, Field(ge=0)] | None = None
    mime_type: Annotated[str, StringConstraints(max_length=255)] | None = None


class ImportSummarySectionDto(ApiModel):
    key: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    title: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    status: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    text: Annotated[str, StringConstraints(min_length=1, max_length=500)]


class ImportSummaryDto(ApiModel):
    title: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    status_text: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    sections: list[ImportSummarySectionDto]


class ImportWarningDto(ApiModel):
    code: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    text: Annotated[str, StringConstraints(min_length=1, max_length=300)]


class ImportReportPreviewResponse(ApiModel):
    status: Annotated[str, StringConstraints(pattern=r"^preview_placeholder$")]
    can_confirm: bool
    will_change_data: bool
    message: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    scope: ImportScopeDto
    file: ImportFileMetadataDto
    summary: ImportSummaryDto
    warnings: list[ImportWarningDto]

