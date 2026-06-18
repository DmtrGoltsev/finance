from __future__ import annotations

from datetime import UTC, datetime

from app.authz import Actor
from app.config import Settings

from .aggregate_parser import PARSE_VERSION, parse_category_aggregate_screenshot_ocr
from .category_mapping_service import CaptureCategoryMappingService
from .ocr_engine import (
    ScreenshotOcrEngine,
    ScreenshotOcrResult,
    validate_screenshot_upload,
)
from .schemas import (
    CaptureSource,
    CategoryAggregateDto,
    ScreenshotOcrCandidateDto,
    ScreenshotOcrResponseDto,
    ScreenshotOcrWarningCode,
    ScreenshotOcrWarningDto,
)


class ScreenshotOcrService:
    def __init__(
        self,
        *,
        ocr_engine: ScreenshotOcrEngine,
        mappings: CaptureCategoryMappingService,
        settings: Settings,
    ) -> None:
        self._ocr_engine = ocr_engine
        self._mappings = mappings
        self._settings = settings

    @property
    def max_upload_bytes(self) -> int:
        return self._settings.capture_screenshot_ocr_max_upload_bytes

    def recognize(
        self,
        *,
        actor: Actor,
        image_bytes: bytes,
        content_type: str | None,
        captured_at: datetime | None,
        household_id: str | None,
    ) -> ScreenshotOcrResponseDto:
        recognized_at = datetime.now(UTC)
        effective_captured_at = _utc(captured_at) if captured_at else recognized_at
        validate_screenshot_upload(
            image_bytes,
            content_type=content_type,
            settings=self._settings,
        )
        ocr_result = _extract_ocr_result(
            self._ocr_engine,
            image_bytes=image_bytes,
            content_type=content_type,
        )
        parsed_candidates = parse_category_aggregate_screenshot_ocr(
            ocr_result.text,
            captured_at=effective_captured_at,
            ocr_words=ocr_result.words,
        )
        warnings: list[ScreenshotOcrWarningDto] = []
        if not parsed_candidates:
            warnings.append(
                ScreenshotOcrWarningDto(
                    code=ScreenshotOcrWarningCode.NO_CATEGORY_AGGREGATES_FOUND,
                    message="No category aggregate rows were recognized.",
                )
            )

        return ScreenshotOcrResponseDto(
            capture_source=CaptureSource.SCREENSHOT,
            parse_version=PARSE_VERSION,
            recognized_at=recognized_at,
            items=[
                ScreenshotOcrCandidateDto(
                    category_aggregate=CategoryAggregateDto(
                        external_label=candidate.external_label,
                    ),
                    amount=candidate.amount,
                    currency=candidate.currency,
                    operation_count=candidate.operation_count,
                    description=candidate.description,
                    confidence=candidate.confidence,
                    idempotency_key=candidate.idempotency_key,
                    evidence_hash=candidate.evidence_hash,
                    suggested_category_id=self._mappings.lookup_suggested_category_id(
                        actor=actor,
                        external_label=candidate.external_label,
                        household_id=household_id,
                    ),
                )
                for candidate in parsed_candidates
            ],
            warnings=warnings,
        )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _extract_ocr_result(
    ocr_engine: ScreenshotOcrEngine,
    *,
    image_bytes: bytes,
    content_type: str | None,
) -> ScreenshotOcrResult:
    extract_result = getattr(ocr_engine, "extract_result", None)
    if callable(extract_result):
        result = extract_result(image_bytes, content_type=content_type)
        if isinstance(result, ScreenshotOcrResult):
            return result
    return ScreenshotOcrResult(
        text=ocr_engine.extract_text(image_bytes, content_type=content_type),
    )
