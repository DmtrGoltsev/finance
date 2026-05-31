from __future__ import annotations

from io import BytesIO
from typing import Protocol

from app.config import Settings

SUPPORTED_IMAGE_CONTENT_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})
SUPPORTED_PIL_FORMATS = frozenset({"PNG", "JPEG", "WEBP"})


class ScreenshotOcrError(Exception):
    status_code = 500
    code = "OCR_FAILED"
    message = "Screenshot OCR failed."


class ScreenshotOcrDisabledError(ScreenshotOcrError):
    status_code = 503
    code = "OCR_DISABLED"
    message = "Screenshot OCR is disabled."


class ScreenshotOcrUnavailableError(ScreenshotOcrError):
    status_code = 503
    code = "OCR_ENGINE_UNAVAILABLE"
    message = "Screenshot OCR engine is unavailable."


class ScreenshotOcrTimeoutError(ScreenshotOcrError):
    status_code = 504
    code = "OCR_TIMEOUT"
    message = "Screenshot OCR timed out."


class UnsupportedScreenshotImageError(ScreenshotOcrError):
    status_code = 415
    code = "UNSUPPORTED_MEDIA_TYPE"
    message = "Unsupported image media type."


class ScreenshotUploadTooLargeError(ScreenshotOcrError):
    status_code = 413
    code = "UPLOAD_TOO_LARGE"
    message = "Screenshot upload is too large."


class ScreenshotImageTooLargeError(ScreenshotOcrError):
    status_code = 413
    code = "IMAGE_TOO_LARGE"
    message = "Screenshot image dimensions are too large."


class InvalidScreenshotImageError(ScreenshotOcrError):
    status_code = 422
    code = "INVALID_IMAGE"
    message = "Invalid screenshot image."


class ScreenshotOcrEngine(Protocol):
    def extract_text(self, image_bytes: bytes, *, content_type: str | None) -> str:
        """Return OCR text for a validated screenshot image."""


def validate_screenshot_upload(
    image_bytes: bytes,
    *,
    content_type: str | None,
    settings: Settings,
) -> None:
    if len(image_bytes) > settings.capture_screenshot_ocr_max_upload_bytes:
        raise ScreenshotUploadTooLargeError()

    normalized_content_type = _normalized_content_type(content_type)
    if normalized_content_type not in SUPPORTED_IMAGE_CONTENT_TYPES:
        raise UnsupportedScreenshotImageError()

    try:
        from PIL import Image, UnidentifiedImageError
    except ModuleNotFoundError as exc:  # pragma: no cover - covered by deployment smoke
        raise ScreenshotOcrUnavailableError() from exc

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = (image.format or "").upper()
            if image_format not in SUPPORTED_PIL_FORMATS:
                raise UnsupportedScreenshotImageError()
            if image.width * image.height > settings.capture_screenshot_ocr_max_pixels:
                raise ScreenshotImageTooLargeError()
            image.verify()
    except ScreenshotOcrError:
        raise
    except UnidentifiedImageError as exc:
        raise InvalidScreenshotImageError() from exc
    except OSError as exc:
        raise InvalidScreenshotImageError() from exc


class TesseractScreenshotOcrEngine:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def extract_text(self, image_bytes: bytes, *, content_type: str | None) -> str:
        del content_type
        if not self._settings.capture_screenshot_ocr_enabled:
            raise ScreenshotOcrDisabledError()

        try:
            import pytesseract
            from PIL import Image
            from pytesseract import TesseractError, TesseractNotFoundError
        except ModuleNotFoundError as exc:  # pragma: no cover - covered by deployment smoke
            raise ScreenshotOcrUnavailableError() from exc

        if self._settings.capture_screenshot_ocr_tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = (
                self._settings.capture_screenshot_ocr_tesseract_cmd
            )

        try:
            with Image.open(BytesIO(image_bytes)) as image:
                return str(
                    pytesseract.image_to_string(
                        image,
                        lang=self._settings.capture_screenshot_ocr_lang,
                        timeout=self._settings.capture_screenshot_ocr_timeout_seconds,
                    )
                )
        except TesseractNotFoundError as exc:
            raise ScreenshotOcrUnavailableError() from exc
        except TesseractError as exc:
            raise ScreenshotOcrUnavailableError() from exc
        except RuntimeError as exc:
            message = str(exc).casefold()
            if "timeout" in message or "timed out" in message:
                raise ScreenshotOcrTimeoutError() from exc
            raise ScreenshotOcrUnavailableError() from exc
        except OSError as exc:
            raise InvalidScreenshotImageError() from exc


def _normalized_content_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().casefold()
