from __future__ import annotations

from datetime import UTC, datetime

from app.capture_drafts.aggregate_parser import (
    external_label_hash,
    normalize_aggregate_label,
    parse_category_aggregate_screenshot_ocr,
)

FIXED_TIME = datetime(2026, 5, 17, 14, 0, tzinfo=UTC)


def test_category_aggregate_parser_extracts_rows_and_ignores_summary() -> None:
    candidates = parse_category_aggregate_screenshot_ocr(
        """
        Анализ финансов
        Расходы
        Супермаркеты
        224 584 ₽
        34 операции
        Кафе, рестораны, фастфуд
        222 129 ₽
        80 операций
        Погашение кредитов
        104 621 ₽
        1 операция
        Ещё 17 категорий на 338 156 ₽
        """,
        captured_at=FIXED_TIME,
    )

    assert len(candidates) == 3
    assert candidates[0].external_label == "Супермаркеты"
    assert str(candidates[0].amount) == "224584.00"
    assert candidates[0].currency == "RUB"
    assert candidates[0].operation_count == 34
    assert candidates[1].external_label == "Кафе, рестораны, фастфуд"
    assert str(candidates[1].amount) == "222129.00"
    assert candidates[1].operation_count == 80
    assert candidates[2].external_label == "Погашение кредитов"
    assert str(candidates[2].amount) == "104621.00"
    assert candidates[2].operation_count == 1
    assert all("Ещё" not in candidate.external_label for candidate in candidates)
    assert all("Супермаркеты" not in candidate.description for candidate in candidates)
    assert all("Products" not in candidate.description for candidate in candidates)


def test_category_aggregate_parser_supports_multiline_labels_and_inline_count() -> None:
    candidates = parse_category_aggregate_screenshot_ocr(
        """
        Кафе, рестораны,
        фастфуд
        1 234,56 ₽ 12 операций
        """,
        captured_at=FIXED_TIME,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.external_label == "Кафе, рестораны, фастфуд"
    assert str(candidate.amount) == "1234.56"
    assert candidate.operation_count == 12
    assert candidate.description == "Скрин: агрегированные расходы, 12 операций"
    assert "Кафе" not in candidate.description
    assert "Products" not in candidate.description
    assert candidate.idempotency_key.startswith("capture-v1:screenshot:category-aggregate:")
    assert len(candidate.evidence_hash) == 64


def test_category_mapping_hash_normalization_is_stable_and_hash_only() -> None:
    assert normalize_aggregate_label("  Кафе, рестораны,\nфастфуд  ") == (
        "кафе рестораны фастфуд"
    )
    assert external_label_hash("Супермаркеты") == external_label_hash("супермаркеты")
    assert external_label_hash("Супермаркеты") != "Супермаркеты"
