from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from hashlib import sha256
from statistics import median
from typing import Protocol

PARSE_VERSION = "category-aggregate-v1"
CAPTURE_SOURCE = "screenshot"

_CURRENCY_RE_PART = r"(₽|руб\.?|р\.?|rub|rur|usd|\$|eur|€|в‚Ѕ|p)"
_AMOUNT_AFTER_RE = re.compile(rf"(?i)(\d[\d\s.,]*\d|\d)(?:\s*){_CURRENCY_RE_PART}")
_AMOUNT_BEFORE_RE = re.compile(
    rf"(?i){_CURRENCY_RE_PART}(?:\s*)(\d[\d\s.,]*\d|\d)"
)
_LAYOUT_AMOUNT_RE = re.compile(rf"(?i)(\d[\d\s.,]*\d|\d)(?:\s*)({_CURRENCY_RE_PART})?")
_OPERATION_COUNT_RE = re.compile(r"(?i)(\d{1,4})\s+(?:операци\w*|operations?)")
_OPERATION_WORD_RE = re.compile(r"(?i)^(?:операци\w*|operations?)\b")
_OPERATION_WORD_ONLY_RE = re.compile(r"(?i)^(?:операци\w*|operations?)$")
_SUMMARY_RE = re.compile(r"(?i)^(?:еще|ещё|more)\s+\d{1,4}\s+(?:категори\w*|categories)\s+")
_NON_LABEL_CHARS_RE = re.compile(r"[^\w]+", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")
_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")

_AGGREGATE_HEADER_LINES = {
    "анализ финансов",
    "расходы",
    "доходы",
    "категории",
    "операции",
    "за месяц",
    "за период",
    "finance analysis",
    "expenses",
    "income",
    "categories",
}


@dataclass(frozen=True, slots=True)
class ParsedAmount:
    amount: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class ParsedAmountMatch:
    amount: ParsedAmount
    start: int
    end: int


class OcrWordLike(Protocol):
    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float | None


@dataclass(frozen=True, slots=True)
class _LayoutLine:
    text: str
    words: tuple[OcrWordLike, ...]
    left: int
    top: int
    right: int
    bottom: int

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass(frozen=True, slots=True)
class _OperationCountLine:
    index: int
    count: int


@dataclass(frozen=True, slots=True)
class CategoryAggregateCandidate:
    external_label: str
    amount: Decimal
    currency: str
    operation_count: int
    captured_at: datetime
    occurred_at: datetime
    idempotency_key: str
    confidence: Decimal
    evidence_hash: str

    @property
    def description(self) -> str:
        return f"Скрин: агрегированные расходы, {self.operation_count} операций"


def parse_category_aggregate_screenshot_ocr(
    text: str,
    *,
    captured_at: datetime,
    ocr_words: Sequence[OcrWordLike] = (),
) -> list[CategoryAggregateCandidate]:
    effective_captured_at = _utc(captured_at)
    time_bucket = str(int(effective_captured_at.timestamp()) // 60)
    candidates = _parse_category_aggregate_layout_ocr(
        ocr_words,
        captured_at=effective_captured_at,
        time_bucket=time_bucket,
    )

    lines = [
        _WHITESPACE_RE.sub(" ", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]
    if not lines:
        return _dedupe_candidates(candidates)

    label_buffer: list[str] = []
    skip_line_index: int | None = None

    for index, line in enumerate(lines):
        if skip_line_index == index:
            skip_line_index = None
            continue
        if _is_summary_line(line):
            label_buffer.clear()
            continue

        amount_match = _amount_match_in(line)
        if amount_match is None:
            if _is_label_line(line):
                label_buffer.append(line)
            continue

        trailing_text = line[amount_match.end :].strip()
        same_line_operation_count = _operation_count(trailing_text)
        next_line_operation_count = same_line_operation_count
        next_line = lines[index + 1] if index + 1 < len(lines) else None
        if next_line_operation_count is None and next_line is not None:
            next_match = _OPERATION_COUNT_RE.search(next_line)
            if next_match is not None and next_match.start() <= 2:
                next_line_operation_count = int(next_match.group(1))
                skip_line_index = index + 1

        label_before_amount = line[: amount_match.start].strip()
        label = _clean_label(
            " ".join(
                item
                for item in [*label_buffer, label_before_amount]
                if _is_label_line(item)
            ).strip()
        )
        label_buffer.clear()

        if not label or next_line_operation_count is None:
            continue

        candidates.append(
            _candidate(
                label=label,
                amount=amount_match.amount.amount,
                currency=amount_match.amount.currency,
                operation_count=next_line_operation_count,
                captured_at=effective_captured_at,
                time_bucket=time_bucket,
                confidence=Decimal("0.82"),
            )
        )

    return _dedupe_candidates(candidates)


def _dedupe_candidates(
    candidates: list[CategoryAggregateCandidate],
) -> list[CategoryAggregateCandidate]:
    seen: set[tuple[str, str, int]] = set()
    deduped: list[CategoryAggregateCandidate] = []
    for candidate in candidates:
        key = (
            normalize_aggregate_label(candidate.external_label),
            _decimal_string(candidate.amount),
            candidate.operation_count,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _parse_category_aggregate_layout_ocr(
    words: Sequence[OcrWordLike],
    *,
    captured_at: datetime,
    time_bucket: str,
) -> list[CategoryAggregateCandidate]:
    lines = _layout_lines(words)
    if not lines:
        return []

    right_column_left = _right_column_left(lines)
    amount_line_indexes = {
        index
        for index, line in enumerate(lines)
        if _layout_amount_match(line, right_column_left) is not None
    }
    candidates: list[CategoryAggregateCandidate] = []

    for index, line in enumerate(lines):
        amount_match = _layout_amount_match(line, right_column_left)
        if amount_match is None:
            continue

        count_line = _next_operation_count_line(lines, index, amount_line_indexes)
        label_anchor_index = index
        use_same_line_label = True
        if count_line is None and not _is_label_line(
            _layout_left_text(line, right_column_left)
        ):
            count_line = _previous_operation_count_line(
                lines,
                index,
                amount_line_indexes,
            )
            label_anchor_index = count_line.index if count_line is not None else index
            use_same_line_label = False
        if count_line is None:
            continue
        operation_count = count_line.count

        label_parts: list[str] = []
        label_parts.extend(
            _previous_layout_label_parts(lines, label_anchor_index, right_column_left)
        )
        same_line_label = _layout_left_text(line, right_column_left)
        if use_same_line_label and _is_label_line(same_line_label):
            label_parts.append(same_line_label)

        if use_same_line_label:
            for continuation in lines[index + 1 : count_line.index]:
                if continuation.left >= right_column_left:
                    continue
                if _is_label_line(continuation.text):
                    label_parts.append(continuation.text)

        label = _clean_label(" ".join(label_parts))
        if not label:
            continue

        candidates.append(
            _candidate(
                label=label,
                amount=amount_match.amount.amount,
                currency=amount_match.amount.currency,
                operation_count=operation_count,
                captured_at=captured_at,
                time_bucket=time_bucket,
                confidence=Decimal("0.9"),
            )
        )

    return candidates


def _candidate(
    *,
    label: str,
    amount: Decimal,
    currency: str,
    operation_count: int,
    captured_at: datetime,
    time_bucket: str,
    confidence: Decimal,
) -> CategoryAggregateCandidate:
    evidence_hash = _evidence_hash(
        label=label,
        amount=amount,
        currency=currency,
        operation_count=operation_count,
        time_bucket=time_bucket,
    )
    normalized_label = normalize_aggregate_label(label)
    label_key = _sha256_hex(normalized_label)[:16]
    idempotency_key = ":".join(
        (
            "capture-v1",
            CAPTURE_SOURCE,
            "category-aggregate",
            time_bucket,
            _idempotency_amount_key(amount),
            currency,
            label_key,
            evidence_hash[:16],
        )
    )
    return CategoryAggregateCandidate(
        external_label=label,
        amount=amount,
        currency=currency,
        operation_count=operation_count,
        captured_at=captured_at,
        occurred_at=captured_at,
        idempotency_key=idempotency_key,
        confidence=confidence,
        evidence_hash=evidence_hash,
    )


def external_label_hash(external_label: str) -> str:
    normalized_label = normalize_aggregate_label(external_label)
    return _sha256_hex(normalized_label)


def normalize_aggregate_label(value: str) -> str:
    normalized = value.casefold().replace("ё", "е")
    normalized = _NON_LABEL_CHARS_RE.sub(" ", normalized)
    return _WHITESPACE_RE.sub(" ", normalized).strip()[:120]


def _amount_match_in(text: str) -> ParsedAmountMatch | None:
    matches: list[ParsedAmountMatch] = []
    after_match = _AMOUNT_AFTER_RE.search(text)
    if after_match is not None:
        amount = _normalize_amount(after_match.group(1), after_match.group(2))
        if amount is not None:
            matches.append(ParsedAmountMatch(amount, after_match.start(), after_match.end()))
    before_match = _AMOUNT_BEFORE_RE.search(text)
    if before_match is not None:
        amount = _normalize_amount(before_match.group(2), before_match.group(1))
        if amount is not None:
            matches.append(ParsedAmountMatch(amount, before_match.start(), before_match.end()))
    return min(matches, key=lambda match: match.start) if matches else None


def _layout_amount_match(line: _LayoutLine, right_column_left: float) -> ParsedAmountMatch | None:
    if _operation_count(line.text) is not None:
        return None
    right_text = _layout_right_text(line, right_column_left)
    match = _layout_amount_match_in(right_text)
    if match is not None:
        return match
    return _layout_amount_match_in(line.text)


def _layout_amount_match_in(text: str) -> ParsedAmountMatch | None:
    matches: list[ParsedAmountMatch] = []
    for match in _LAYOUT_AMOUNT_RE.finditer(text):
        raw_amount = _clean_layout_amount(match.group(1))
        amount = _normalize_amount(raw_amount, match.group(2) or "RUB")
        if amount is None:
            continue
        has_currency = bool(match.group(2))
        if not has_currency and amount.amount < Decimal("1000"):
            continue
        matches.append(ParsedAmountMatch(amount, match.start(), match.end()))
    if not matches:
        return None
    return max(matches, key=lambda item: (item.amount.amount, item.start))


def _layout_lines(words: Sequence[OcrWordLike]) -> list[_LayoutLine]:
    clean_words = [
        word
        for word in words
        if (
            word.text.strip()
            and word.width > 0
            and word.height > 0
            and (
                word.confidence is None
                or word.confidence >= 15
                or _contains_digit(word.text)
            )
        )
    ]
    if not clean_words:
        return []

    sorted_words = sorted(clean_words, key=lambda word: (_word_center_y(word), word.left))
    median_height = median(word.height for word in sorted_words)
    y_tolerance = max(8.0, float(median_height) * 0.75)
    grouped: list[list[OcrWordLike]] = []

    for word in sorted_words:
        if not grouped:
            grouped.append([word])
            continue
        current = grouped[-1]
        current_center = sum(_word_center_y(item) for item in current) / len(current)
        if abs(_word_center_y(word) - current_center) <= y_tolerance:
            current.append(word)
        else:
            grouped.append([word])

    lines: list[_LayoutLine] = []
    for group in grouped:
        line_words = tuple(sorted(group, key=lambda word: word.left))
        text = " ".join(word.text.strip() for word in line_words if word.text.strip())
        if not text:
            continue
        left = min(word.left for word in line_words)
        top = min(word.top for word in line_words)
        right = max(word.left + word.width for word in line_words)
        bottom = max(word.top + word.height for word in line_words)
        lines.append(
            _LayoutLine(
                text=text,
                words=line_words,
                left=left,
                top=top,
                right=right,
                bottom=bottom,
            )
        )
    return lines


def _right_column_left(lines: Sequence[_LayoutLine]) -> float:
    min_left = min(line.left for line in lines)
    max_right = max(line.right for line in lines)
    return min_left + ((max_right - min_left) * 0.58)


def _layout_left_text(line: _LayoutLine, right_column_left: float) -> str:
    words = [word.text for word in line.words if _word_center_x(word) < right_column_left]
    return _WHITESPACE_RE.sub(" ", " ".join(words)).strip()


def _layout_right_text(line: _LayoutLine, right_column_left: float) -> str:
    words = [word.text for word in line.words if _word_center_x(word) >= right_column_left]
    return _WHITESPACE_RE.sub(" ", " ".join(words)).strip()


def _next_operation_count_line(
    lines: Sequence[_LayoutLine],
    amount_line_index: int,
    amount_line_indexes: set[int],
) -> _OperationCountLine | None:
    max_lookahead = min(len(lines), amount_line_index + 4)
    for index in range(amount_line_index + 1, max_lookahead):
        if index in amount_line_indexes:
            return None
        operation_count = _layout_operation_count_at(lines, index)
        if operation_count is not None:
            return _OperationCountLine(index=index, count=operation_count)
    return None


def _previous_operation_count_line(
    lines: Sequence[_LayoutLine],
    amount_line_index: int,
    amount_line_indexes: set[int],
) -> _OperationCountLine | None:
    min_lookbehind = max(-1, amount_line_index - 4)
    amount_line_top = lines[amount_line_index].top
    for index in range(amount_line_index - 1, min_lookbehind, -1):
        if index in amount_line_indexes:
            return None
        line = lines[index]
        if amount_line_top - line.bottom > 120:
            break
        operation_count = _layout_operation_count_at(lines, index)
        if operation_count is not None:
            return _OperationCountLine(index=index, count=operation_count)
    return None


def _layout_operation_count_at(
    lines: Sequence[_LayoutLine],
    index: int,
) -> int | None:
    direct_count = _operation_count(lines[index].text)
    if direct_count is not None:
        return direct_count
    if index + 1 >= len(lines):
        return None
    return _split_operation_count(lines[index].text, lines[index + 1].text)


def _split_operation_count(count_text: str, operation_text: str) -> int | None:
    normalized_count = normalize_aggregate_label(count_text)
    if re.fullmatch(r"\d{1,4}", normalized_count) is None:
        return None
    normalized_operation = normalize_aggregate_label(operation_text)
    if _OPERATION_WORD_RE.search(normalized_operation) is None:
        return None
    return int(normalized_count)


def _previous_layout_label_parts(
    lines: Sequence[_LayoutLine],
    amount_line_index: int,
    right_column_left: float,
) -> list[str]:
    parts: list[str] = []
    previous_bottom = lines[amount_line_index].top
    for index in range(amount_line_index - 1, -1, -1):
        line = lines[index]
        if previous_bottom - line.bottom > 72:
            break
        if line.left >= right_column_left:
            break
        if _layout_amount_match(line, right_column_left) is not None:
            break
        if _operation_count(line.text) is not None:
            break
        if not _is_label_line(line.text):
            break
        parts.insert(0, line.text)
        previous_bottom = line.top
    return parts


def _word_center_x(word: OcrWordLike) -> float:
    return word.left + (word.width / 2)


def _word_center_y(word: OcrWordLike) -> float:
    return word.top + (word.height / 2)


def _contains_digit(text: str) -> bool:
    return any(character.isdigit() for character in text)


def _normalize_amount(raw_amount: str, raw_currency: str) -> ParsedAmount | None:
    decimal_text = raw_amount.replace(" ", "")
    decimal_text = re.sub(r"(?<=\d)[,.](?=\d{3}(\D|$))", "", decimal_text)
    decimal_text = decimal_text.replace(",", ".")
    try:
        amount = Decimal(decimal_text)
    except InvalidOperation:
        return None
    if amount <= 0:
        return None
    return ParsedAmount(
        amount=amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        currency=_normalize_currency(raw_currency),
    )


def _clean_layout_amount(raw_amount: str) -> str:
    if re.search(r"[,.]", raw_amount):
        return raw_amount
    groups = raw_amount.split()
    if len(groups) < 2:
        return raw_amount
    if not all(group.isdigit() for group in groups):
        return raw_amount
    if len(groups[-1]) != 1:
        return raw_amount
    prefix_groups = groups[:-1]
    if not (1 <= len(prefix_groups[0]) <= 3):
        return raw_amount
    if not all(len(group) == 3 for group in prefix_groups[1:]):
        return raw_amount
    prefix_value = Decimal("".join(prefix_groups))
    if prefix_value < Decimal("1000"):
        return raw_amount
    return " ".join(prefix_groups)


def _normalize_currency(raw: str) -> str:
    lowered = raw.casefold()
    if raw == "$" or lowered == "usd":
        return "USD"
    if raw == "€" or lowered == "eur":
        return "EUR"
    return "RUB"


def _operation_count(text: str) -> int | None:
    match = _OPERATION_COUNT_RE.search(normalize_aggregate_label(text))
    return int(match.group(1)) if match is not None else None


def _is_summary_line(text: str) -> bool:
    return _SUMMARY_RE.search(normalize_aggregate_label(text)) is not None


def _is_label_line(text: str) -> bool:
    normalized = normalize_aggregate_label(text)
    if not normalized or normalized in _AGGREGATE_HEADER_LINES:
        return False
    if _AMOUNT_AFTER_RE.search(text) is not None or _AMOUNT_BEFORE_RE.search(text) is not None:
        return False
    if _OPERATION_COUNT_RE.search(normalized) is not None:
        return False
    if _OPERATION_WORD_ONLY_RE.search(normalized) is not None:
        return False
    if _is_summary_line(text):
        return False
    return any(character.isalpha() for character in text)


def _clean_label(value: str) -> str:
    label = _WHITESPACE_RE.sub(" ", value.strip(" .,;:-`+")).strip()
    tokens = label.split()
    while len(tokens) > 1 and _is_edge_label_noise(tokens[0], neighbor=tokens[1]):
        tokens.pop(0)
    while len(tokens) > 1 and _is_edge_label_noise(tokens[-1], neighbor=tokens[-2]):
        tokens.pop()
    return _WHITESPACE_RE.sub(" ", " ".join(tokens).strip(" .,;:-`+"))[:80]


def _is_edge_label_noise(token: str, *, neighbor: str) -> bool:
    normalized = normalize_aggregate_label(token)
    if not normalized:
        return True
    if not _CYRILLIC_RE.search(neighbor):
        return False
    if not _CYRILLIC_RE.search(token):
        return len(normalized) <= 4
    return len(normalized) <= 1


def _evidence_hash(
    *,
    label: str,
    amount: Decimal,
    currency: str,
    operation_count: int,
    time_bucket: str,
) -> str:
    evidence_input = "|".join(
        (
            CAPTURE_SOURCE,
            PARSE_VERSION,
            normalize_aggregate_label(label),
            _decimal_string(amount),
            currency,
            str(operation_count),
            time_bucket,
        )
    )
    return _sha256_hex(evidence_input)


def _sha256_hex(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _decimal_string(value: Decimal) -> str:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP).to_eng_string()


def _idempotency_amount_key(value: Decimal) -> str:
    return _decimal_string(value).replace(".", "_")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
