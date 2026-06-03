from __future__ import annotations

from datetime import UTC, datetime

from app.capture_drafts.aggregate_parser import (
    external_label_hash,
    normalize_aggregate_label,
    parse_category_aggregate_screenshot_ocr,
)
from app.capture_drafts.ocr_engine import ScreenshotOcrWord

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


def test_category_aggregate_parser_extracts_dense_bank_layout_fixture() -> None:
    candidates = parse_category_aggregate_screenshot_ocr(
        "layout fixture intentionally omits parseable aggregate text",
        captured_at=FIXED_TIME,
        ocr_words=_dense_bank_layout_words(),
    )

    assert [
        (candidate.external_label, str(candidate.amount), candidate.operation_count)
        for candidate in candidates
    ] == [
        ("Переводы людям", "685674.00", 28),
        ("Супермаркеты", "224584.00", 34),
        ("Кафе, рестораны, фастфуд", "222129.00", 80),
        ("Погашение кредитов", "104621.00", 1),
        ("Медицинские услуги", "100636.00", 1),
        ("Ювелирные изделия", "74976.00", 3),
        ("Такси и каршеринг", "59866.00", 64),
        ("Табачные магазины", "27756.00", 6),
    ]
    assert all(candidate.currency == "RUB" for candidate in candidates)


def test_category_aggregate_parser_recovers_noisy_production_layout_patterns() -> None:
    candidates = parse_category_aggregate_screenshot_ocr(
        "layout fixture intentionally omits parseable aggregate text",
        captured_at=FIXED_TIME,
        ocr_words=_noisy_production_layout_words(),
    )

    assert [
        (candidate.external_label, str(candidate.amount), candidate.operation_count)
        for candidate in candidates
    ] == [
        ("Переводы людям", "685674.00", 28),
        ("Супермаркеты", "224584.00", 34),
        ("Кафе, рестораны, фастфуд", "222129.00", 80),
        ("Погашение кредитов", "104621.00", 1),
        ("Медицинские услуги", "100636.00", 1),
        ("Ювелирные изделия", "74976.00", 3),
        ("Такси и каршеринг", "59866.00", 64),
        ("Табачные магазины", "27756.00", 6),
    ]


def test_category_aggregate_parser_recovers_prod_final_mismatch_mechanics() -> None:
    candidates = parse_category_aggregate_screenshot_ocr(
        "layout fixture intentionally omits parseable aggregate text",
        captured_at=FIXED_TIME,
        ocr_words=_prod_final_mismatch_layout_words(),
    )

    assert [
        (candidate.external_label, str(candidate.amount), candidate.operation_count)
        for candidate in candidates
    ] == [
        ("Переводы людям", "685674.00", 28),
        ("Супермаркеты", "224584.00", 34),
        ("Кафе, рестораны, фастфуд", "222129.00", 80),
        ("Погашение кредитов", "104621.00", 1),
        ("Медицинские услуги", "100636.00", 1),
        ("Ювелирные изделия", "74976.00", 3),
        ("Такси и каршеринг", "59866.00", 64),
        ("Табачные магазины", "27756.00", 6),
    ]


def test_category_aggregate_parser_recovers_split_count_before_right_only_amount() -> None:
    candidates = parse_category_aggregate_screenshot_ocr(
        "layout fixture intentionally omits parseable aggregate text",
        captured_at=FIXED_TIME,
        ocr_words=_split_count_before_amount_layout_words(),
    )

    assert [
        (candidate.external_label, str(candidate.amount), candidate.operation_count)
        for candidate in candidates
    ] == [
        ("Кафе, рестораны, фастфуд", "222129.00", 80),
    ]


def test_category_aggregate_parser_recovers_operation_word_on_amount_line() -> None:
    candidates = parse_category_aggregate_screenshot_ocr(
        "layout fixture intentionally omits parseable aggregate text",
        captured_at=FIXED_TIME,
        ocr_words=_operation_word_on_amount_line_layout_words(),
    )

    assert [
        (candidate.external_label, str(candidate.amount), candidate.operation_count)
        for candidate in candidates
    ] == [
        ("Кафе, рестораны, фастфуд", "222129.00", 80),
    ]


def test_category_mapping_hash_normalization_is_stable_and_hash_only() -> None:
    assert normalize_aggregate_label("  Кафе, рестораны,\nфастфуд  ") == (
        "кафе рестораны фастфуд"
    )
    assert external_label_hash("Супермаркеты") == external_label_hash("супермаркеты")
    assert external_label_hash("Супермаркеты") != "Супермаркеты"


def _dense_bank_layout_words() -> tuple[ScreenshotOcrWord, ...]:
    words: list[ScreenshotOcrWord] = []

    def add_text_line(parts: list[str], *, left: int, top: int) -> None:
        x = left
        for part in parts:
            width = max(24, len(part) * 17)
            words.append(_word(part, x, top, width))
            x += width + 14

    def add_amount(amount: str, *, top: int) -> None:
        x = 700
        for part in [*amount.split(), "₽"]:
            width = 50 if part != "₽" else 24
            words.append(_word(part, x, top, width))
            x += width + 13

    def add_row(
        label_lines: list[list[str]],
        *,
        amount: str,
        count: int,
        count_word: str,
        top: int,
    ) -> None:
        add_text_line(label_lines[0], left=180, top=top)
        add_amount(amount, top=top)
        for offset, label_line in enumerate(label_lines[1:], start=1):
            add_text_line(label_line, left=180, top=top + (offset * 46))
        add_text_line([str(count), count_word], left=180, top=top + (len(label_lines) * 46))

    add_text_line(["Анализ", "финансов"], left=185, top=145)
    add_text_line(["Расходы"], left=215, top=270)
    add_row(
        [["Переводы", "людям"]],
        amount="685 674",
        count=28,
        count_word="операций",
        top=420,
    )
    add_row(
        [["Супермаркеты"]],
        amount="224 584",
        count=34,
        count_word="операции",
        top=600,
    )
    add_row(
        [["Кафе,", "рестораны,"], ["фастфуд"]],
        amount="222 129",
        count=80,
        count_word="операций",
        top=780,
    )
    add_row(
        [["Погашение", "кредитов"]],
        amount="104 621",
        count=1,
        count_word="операция",
        top=1010,
    )
    add_row(
        [["Медицинские", "услуги"]],
        amount="100 636",
        count=1,
        count_word="операция",
        top=1190,
    )
    add_row(
        [["Ювелирные", "изделия"]],
        amount="74 976",
        count=3,
        count_word="операции",
        top=1370,
    )
    add_row(
        [["Такси", "и", "каршеринг"]],
        amount="59 866",
        count=64,
        count_word="операции",
        top=1550,
    )
    add_row(
        [["Табачные", "магазины"]],
        amount="27 756",
        count=6,
        count_word="операций",
        top=1730,
    )
    return tuple(words)


def _noisy_production_layout_words() -> tuple[ScreenshotOcrWord, ...]:
    words: list[ScreenshotOcrWord] = []

    def add_text_line(parts: list[str], *, left: int, top: int) -> None:
        x = left
        for part in parts:
            width = max(24, len(part) * 17)
            words.append(_word(part, x, top, width))
            x += width + 14

    def add_amount_parts(parts: list[str], *, top: int) -> None:
        x = 700
        for part in parts:
            width = 50 if part != "₽" else 24
            words.append(_word(part, x, top, width))
            x += width + 13

    def add_row(
        label_parts: list[str],
        *,
        amount_parts: list[str],
        count: int,
        count_word: str,
        top: int,
    ) -> None:
        add_text_line(label_parts, left=180, top=top)
        add_amount_parts([*amount_parts, "₽"], top=top)
        add_text_line([str(count), count_word], left=180, top=top + 46)

    add_text_line(["Анализ", "финансов"], left=185, top=145)
    add_text_line(["Расходы"], left=215, top=270)
    add_row(
        ["ee", "Переводы", "людям", "Г)"],
        amount_parts=["685", "674"],
        count=28,
        count_word="операций",
        top=420,
    )
    add_row(
        ["Супермаркеты"],
        amount_parts=["224", "584"],
        count=34,
        count_word="операции",
        top=600,
    )
    add_text_line(["Кафе,", "рестораны,"], left=180, top=780)
    add_text_line(["фастфуд"], left=180, top=826)
    add_amount_parts(["222", "129", "₽"], top=826)
    add_text_line(["80", "операций"], left=180, top=872)
    add_row(
        ["a", "Погашение", "кредитов"],
        amount_parts=["104", "621"],
        count=1,
        count_word="операция",
        top=1010,
    )
    add_row(
        ["+", "Медицинские", "услуги"],
        amount_parts=["100", "636"],
        count=1,
        count_word="операция",
        top=1190,
    )
    add_row(
        ["`....", "Ювелирные", "изделия"],
        amount_parts=["74", "976", "2"],
        count=3,
        count_word="операции",
        top=1370,
    )
    add_row(
        ["Такси", "и", "каршеринг"],
        amount_parts=["59", "866"],
        count=64,
        count_word="операции",
        top=1550,
    )
    add_row(
        ["Табачные", "магазины"],
        amount_parts=["27", "756"],
        count=6,
        count_word="операций",
        top=1730,
    )
    return tuple(words)


def _prod_final_mismatch_layout_words() -> tuple[ScreenshotOcrWord, ...]:
    words: list[ScreenshotOcrWord] = []

    def add_text_line(parts: list[str], *, left: int, top: int) -> None:
        x = left
        for part in parts:
            width = max(24, len(part) * 17)
            words.append(_word(part, x, top, width))
            x += width + 14

    def add_amount_parts(parts: list[str], *, top: int) -> None:
        x = 700
        for part in parts:
            width = 50 if part != "₽" else 24
            words.append(_word(part, x, top, width))
            x += width + 13

    def add_row(
        label_parts: list[str],
        *,
        amount_parts: list[str],
        count: int,
        count_word: str,
        top: int,
        append_currency: bool = True,
    ) -> None:
        add_text_line(label_parts, left=180, top=top)
        parts = [*amount_parts, "₽"] if append_currency else amount_parts
        add_amount_parts(parts, top=top)
        add_text_line([str(count), count_word], left=180, top=top + 46)

    add_text_line(["Анализ", "финансов"], left=185, top=145)
    add_text_line(["Расходы"], left=215, top=270)
    add_row(
        ["ee", "Переводы", "людям", "Г)"],
        amount_parts=["685", "674"],
        count=28,
        count_word="операций",
        top=420,
    )
    add_row(
        ["Супермаркеты"],
        amount_parts=["224", "584"],
        count=34,
        count_word="операции",
        top=600,
    )
    add_text_line(["Кафе,", "рестораны,"], left=180, top=780)
    add_text_line(["фастфуд"], left=180, top=826)
    add_text_line(["80", "операций"], left=180, top=872)
    add_amount_parts(["222", "129"], top=918)
    add_row(
        ["a", "Погашение", "кредитов"],
        amount_parts=["104", "621"],
        count=1,
        count_word="операция",
        top=1010,
    )
    add_row(
        ["+", "Медицинские", "услуги"],
        amount_parts=["100", "636"],
        count=1,
        count_word="операция",
        top=1190,
    )
    add_row(
        ["`....", "Ювелирные", "изделия"],
        amount_parts=["74", "976", "2"],
        count=3,
        count_word="операции",
        top=1370,
        append_currency=False,
    )
    add_row(
        ["Такси", "и", "каршеринг"],
        amount_parts=["59", "866"],
        count=64,
        count_word="операции",
        top=1550,
    )
    add_row(
        ["Табачные", "магазины"],
        amount_parts=["27", "756"],
        count=6,
        count_word="операций",
        top=1730,
    )
    return tuple(words)


def _split_count_before_amount_layout_words() -> tuple[ScreenshotOcrWord, ...]:
    return (
        _word("Кафе,", 180, 780, 80),
        _word("рестораны,", 274, 780, 175),
        _word("фастфуд", 180, 826, 119),
        _word("80", 180, 872, 40),
        _word("операций", 236, 918, 128),
        _word("222", 700, 964, 50),
        _word("129", 763, 964, 50),
    )


def _operation_word_on_amount_line_layout_words() -> tuple[ScreenshotOcrWord, ...]:
    return (
        _word("Кафе,", 180, 780, 80),
        _word("рестораны,", 274, 780, 175),
        _word("фастфуд", 180, 826, 119),
        _word("80", 180, 872, 40),
        _word("операций", 180, 918, 128),
        _word("222", 700, 918, 50),
        _word("129", 763, 918, 50),
    )


def _word(text: str, left: int, top: int, width: int) -> ScreenshotOcrWord:
    return ScreenshotOcrWord(
        text=text,
        left=left,
        top=top,
        width=width,
        height=34,
        confidence=96.0,
    )
