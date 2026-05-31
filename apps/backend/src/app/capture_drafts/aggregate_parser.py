from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from hashlib import sha256

PARSE_VERSION = "category-aggregate-v1"
CAPTURE_SOURCE = "screenshot"

_AMOUNT_AFTER_RE = re.compile(
    r"(?i)(\d[\d\s.,]*\d|\d)(?:\s*)(₽|руб\.?|rub|rur|usd|\$|eur|€|в‚Ѕ)"
)
_AMOUNT_BEFORE_RE = re.compile(
    r"(?i)(₽|руб\.?|rub|rur|usd|\$|eur|€|в‚Ѕ)(?:\s*)(\d[\d\s.,]*\d|\d)"
)
_OPERATION_COUNT_RE = re.compile(r"(?i)(\d{1,4})\s+(?:операци\w*|operations?)")
_SUMMARY_RE = re.compile(r"(?i)^(?:еще|ещё|more)\s+\d{1,4}\s+(?:категори\w*|categories)\s+")
_NON_LABEL_CHARS_RE = re.compile(r"[^\w]+", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")

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
) -> list[CategoryAggregateCandidate]:
    lines = [
        _WHITESPACE_RE.sub(" ", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]
    if not lines:
        return []

    effective_captured_at = _utc(captured_at)
    time_bucket = str(int(effective_captured_at.timestamp()) // 60)
    candidates: list[CategoryAggregateCandidate] = []
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

        evidence_hash = _evidence_hash(
            label=label,
            amount=amount_match.amount.amount,
            currency=amount_match.amount.currency,
            operation_count=next_line_operation_count,
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
                _idempotency_amount_key(amount_match.amount.amount),
                amount_match.amount.currency,
                label_key,
                evidence_hash[:16],
            )
        )
        candidates.append(
            CategoryAggregateCandidate(
                external_label=label,
                amount=amount_match.amount.amount,
                currency=amount_match.amount.currency,
                operation_count=next_line_operation_count,
                captured_at=effective_captured_at,
                occurred_at=effective_captured_at,
                idempotency_key=idempotency_key,
                confidence=Decimal("0.82"),
                evidence_hash=evidence_hash,
            )
        )

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
    if _is_summary_line(text):
        return False
    return any(character.isalpha() for character in text)


def _clean_label(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip(" .,;:-"))[:80]


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
