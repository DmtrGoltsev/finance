from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class ScreenshotOcrWord:
    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class ScreenshotOcrResult:
    text: str
    words: tuple[ScreenshotOcrWord, ...] = ()


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
        return self.extract_result(image_bytes, content_type=content_type).text

    def extract_result(
        self,
        image_bytes: bytes,
        *,
        content_type: str | None,
    ) -> ScreenshotOcrResult:
        del content_type
        if not self._settings.capture_screenshot_ocr_enabled:
            raise ScreenshotOcrDisabledError()

        try:
            import pytesseract
            from PIL import Image, ImageOps
            from pytesseract import TesseractError, TesseractNotFoundError
        except ModuleNotFoundError as exc:  # pragma: no cover - covered by deployment smoke
            raise ScreenshotOcrUnavailableError() from exc

        if self._settings.capture_screenshot_ocr_tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = (
                self._settings.capture_screenshot_ocr_tesseract_cmd
            )

        try:
            with Image.open(BytesIO(image_bytes)) as image:
                prepared_image = _prepare_tesseract_image(image, image_ops=ImageOps)
                data = pytesseract.image_to_data(
                    prepared_image,
                    lang=self._settings.capture_screenshot_ocr_lang,
                    timeout=self._settings.capture_screenshot_ocr_timeout_seconds,
                    output_type=pytesseract.Output.DICT,
                )
                words = _tesseract_words(data)
                return ScreenshotOcrResult(text=_text_from_words(words), words=words)
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


def _prepare_tesseract_image(image, *, image_ops):
    prepared = image.convert("L")
    prepared = image_ops.autocontrast(prepared)
    if prepared.width < 1400:
        scale = 2
        prepared = prepared.resize((prepared.width * scale, prepared.height * scale))
    return prepared


def _tesseract_words(data: dict[str, list[object]]) -> tuple[ScreenshotOcrWord, ...]:
    texts = data.get("text", [])
    words: list[ScreenshotOcrWord] = []
    for index, raw_text in enumerate(texts):
        text = str(raw_text).strip()
        if not text:
            continue
        confidence = _ocr_confidence(data.get("conf", []), index)
        if confidence is not None and confidence < 0:
            continue
        try:
            left = int(data["left"][index])
            top = int(data["top"][index])
            width = int(data["width"][index])
            height = int(data["height"][index])
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if width <= 0 or height <= 0:
            continue
        words.append(
            ScreenshotOcrWord(
                text=text,
                left=left,
                top=top,
                width=width,
                height=height,
                confidence=confidence,
            )
        )
    return tuple(words)


def _ocr_confidence(values: list[object], index: int) -> float | None:
    try:
        return float(values[index])
    except (TypeError, ValueError, IndexError):
        return None


def _text_from_words(words: tuple[ScreenshotOcrWord, ...]) -> str:
    if not words:
        return ""

    grouped: dict[int, dict[int, list[ScreenshotOcrWord]]] = {}
    for word in words:
        block_key = max(0, word.top // max(1, word.height * 3))
        line_key = max(0, (word.top + word.height // 2) // max(1, word.height * 2))
        grouped.setdefault(block_key, {}).setdefault(line_key, []).append(word)

    lines: list[str] = []
    for block in sorted(grouped):
        for line in sorted(grouped[block]):
            line_words = sorted(grouped[block][line], key=lambda item: item.left)
            line_text = " ".join(word.text for word in line_words).strip()
            if line_text:
                lines.append(line_text)
    return "\n".join(lines)
