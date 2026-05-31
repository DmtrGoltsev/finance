from __future__ import annotations

import base64
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.rate_limits import InMemoryRateLimiter, RateLimitConfig, RateLimitKey
from app.authz import Actor
from app.capture_drafts.ocr_engine import ScreenshotImageTooLargeError, validate_screenshot_upload
from app.capture_drafts.router import ocr_engine_for_request
from app.config import Settings, get_settings
from app.db.models import CaptureCategoryMapping, CaptureDraft, Category
from app.db.session import sync_engine_for_url
from tests.transactions.test_transactions_db_runtime import _app_for_actor

pytest_plugins = ["tests.transactions.test_transactions_db_runtime"]


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/"
    "AAX+Av4N70a4AAAAAElFTkSuQmCC"
)

AGGREGATE_TEXT = """
Анализ финансов
Расходы
Супермаркеты
224 584 ₽
34 операции
"""


class FakeOcrEngine:
    def __init__(self, text: str = AGGREGATE_TEXT) -> None:
        self._text = text

    def extract_text(self, image_bytes: bytes, *, content_type: str | None) -> str:
        del image_bytes, content_type
        return self._text


@contextmanager
def _client_for_actor_with_fake_ocr(
    actor: Actor,
    *,
    text: str = AGGREGATE_TEXT,
) -> Iterator[TestClient]:
    app = _app_for_actor(actor)
    app.dependency_overrides[ocr_engine_for_request] = lambda: FakeOcrEngine(text)
    with TestClient(app) as client:
        yield client


def _png_file(name: str = "screen.png") -> dict[str, tuple[str, bytes, str]]:
    return {"image": (name, PNG_1X1, "image/png")}


def _json_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys.update(_json_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(_json_keys(child))
        return keys
    return set()


def _db_scalar_count(model: type) -> int:
    engine = sync_engine_for_url(get_settings().database_url)
    with Session(engine) as session:
        return int(session.execute(select(func.count()).select_from(model)).scalar_one())


def test_screenshot_upload_validation_rejects_excess_decoded_pixels() -> None:
    from PIL import Image

    output = BytesIO()
    Image.new("RGB", (2, 1), color="white").save(output, format="PNG")

    try:
        validate_screenshot_upload(
            output.getvalue(),
            content_type="image/png",
            settings=Settings(
                capture_screenshot_ocr_max_pixels=1,
                _env_file=None,
            ),
        )
    except ScreenshotImageTooLargeError:
        pass
    else:
        raise AssertionError("expected decoded pixel limit rejection")


def test_screenshot_ocr_requires_authentication(client) -> None:
    response = client.post(
        "/api/v1/capture-drafts/screenshot-ocr",
        files=_png_file(),
    )

    assert response.status_code == 401


def test_screenshot_ocr_rejects_unsupported_invalid_and_oversized_images(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]

    with _client_for_actor_with_fake_ocr(owner) as client:
        unsupported = client.post(
            "/api/v1/capture-drafts/screenshot-ocr",
            files={"image": ("screen.heic", b"not-heic", "image/heic")},
        )
        invalid = client.post(
            "/api/v1/capture-drafts/screenshot-ocr",
            files={"image": ("screen.png", b"not an image", "image/png")},
        )
        oversized = client.post(
            "/api/v1/capture-drafts/screenshot-ocr",
            files={"image": ("screen.png", b"x" * (8 * 1024 * 1024 + 1), "image/png")},
        )

    assert unsupported.status_code == 415
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_IMAGE"
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "UPLOAD_TOO_LARGE"


def test_screenshot_ocr_happy_path_uses_hash_mapping_without_draft_writes(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    category_id = transaction_graph["categories"]["cat_a_food"]

    with _client_for_actor_with_fake_ocr(owner) as client:
        mapped = client.put(
            "/api/v1/capture-drafts/category-mappings",
            json={"externalLabel": "Супермаркеты", "categoryId": category_id},
        )
        recognized = client.post(
            "/api/v1/capture-drafts/screenshot-ocr",
            data={"capturedAt": "2026-05-17T14:00:00+00:00"},
            files=_png_file(),
        )
        drafts = client.get("/api/v1/capture-drafts")

    assert mapped.status_code == 200, mapped.text
    assert mapped.json()["data"] == {"categoryId": category_id, "householdId": None}
    assert recognized.status_code == 200, recognized.text
    body = recognized.json()["data"]
    assert body["captureSource"] == "screenshot"
    assert body["parseVersion"] == "category-aggregate-v1"
    assert body["items"][0]["categoryAggregate"]["externalLabel"] == "Супермаркеты"
    assert body["items"][0]["amount"] == "224584.00"
    assert body["items"][0]["currency"] == "RUB"
    assert body["items"][0]["operationCount"] == 34
    assert body["items"][0]["suggestedCategoryId"] == category_id
    assert body["items"][0]["description"] == "Скрин: агрегированные расходы, 34 операций"
    assert "Супермаркеты" not in body["items"][0]["description"]
    assert "Products" not in body["items"][0]["description"]
    assert body["items"][0]["evidenceHash"]
    assert drafts.status_code == 200
    assert drafts.json()["items"] == []
    assert _db_scalar_count(CaptureDraft) == 0

    keys = _json_keys(recognized.json())
    assert "externalLabel" in keys
    assert not any(key.lower().startswith("raw") for key in keys)
    assert {"ocrText", "body", "text"}.isdisjoint(keys)

    engine = sync_engine_for_url(get_settings().database_url)
    with Session(engine) as session:
        records = session.execute(select(CaptureCategoryMapping)).scalars().all()
    assert len(records) == 1
    assert records[0].external_label_hash != "Супермаркеты"
    assert len(records[0].external_label_hash) == 64
    assert not hasattr(records[0], "external_label")
    assert not hasattr(records[0], "ocr_text")


def test_screenshot_ocr_mapping_is_actor_isolated(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    member = transaction_graph["actors"]["member_b"]
    category_id = transaction_graph["categories"]["cat_a_food"]

    with _client_for_actor_with_fake_ocr(owner) as client:
        mapped = client.put(
            "/api/v1/capture-drafts/category-mappings",
            json={"externalLabel": "Супермаркеты", "categoryId": category_id},
        )
    with _client_for_actor_with_fake_ocr(member) as client:
        recognized = client.post(
            "/api/v1/capture-drafts/screenshot-ocr",
            data={"capturedAt": "2026-05-17T14:00:00+00:00"},
            files=_png_file(),
        )

    assert mapped.status_code == 200, mapped.text
    assert recognized.status_code == 200, recognized.text
    assert recognized.json()["data"]["items"][0]["suggestedCategoryId"] is None


def test_screenshot_ocr_ignores_mapping_to_archived_category(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    category_id = transaction_graph["categories"]["cat_a_food"]

    with _client_for_actor_with_fake_ocr(owner) as client:
        mapped = client.put(
            "/api/v1/capture-drafts/category-mappings",
            json={"externalLabel": "Супермаркеты", "categoryId": category_id},
        )

    engine = sync_engine_for_url(get_settings().database_url)
    with Session(engine) as session:
        updated = session.execute(
            update(Category)
            .where(Category.id == UUID(category_id))
            .values(record_status="archived", updated_at=datetime.now(UTC))
        )
        assert updated.rowcount == 1
        session.commit()

    with _client_for_actor_with_fake_ocr(owner) as client:
        recognized = client.post(
            "/api/v1/capture-drafts/screenshot-ocr",
            data={"capturedAt": "2026-05-17T14:00:00+00:00"},
            files=_png_file(),
        )

    assert mapped.status_code == 200, mapped.text
    assert recognized.status_code == 200, recognized.text
    assert recognized.json()["data"]["items"][0]["suggestedCategoryId"] is None


def test_screenshot_ocr_rate_limit_returns_error_envelope(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]

    with _client_for_actor_with_fake_ocr(owner) as client:
        client.app.state.auth_rate_limiter = InMemoryRateLimiter(
            RateLimitConfig.default().with_overrides(
                {
                    RateLimitKey.SCREENSHOT_OCR_ACTOR_MINUTE: 1,
                    RateLimitKey.SCREENSHOT_OCR_IP_MINUTE: 100,
                }
            )
        )
        first = client.post(
            "/api/v1/capture-drafts/screenshot-ocr",
            data={"capturedAt": "2026-05-17T14:00:00+00:00"},
            files=_png_file("first.png"),
        )
        second = client.post(
            "/api/v1/capture-drafts/screenshot-ocr",
            data={"capturedAt": "2026-05-17T14:00:00+00:00"},
            files=_png_file("second.png"),
        )

    assert first.status_code == 200, first.text
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert "Retry-After" in second.headers
