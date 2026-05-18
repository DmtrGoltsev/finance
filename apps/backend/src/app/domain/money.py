"""Decimal-safe money helpers for domain code.

Money enters and leaves the API as decimal strings. Domain code should keep
amounts as ``Decimal`` values and reject floats to avoid binary rounding.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Final


MAX_MONEY_SCALE: Final[int] = 6
DECIMAL_STRING_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^-?[0-9]+(\.[0-9]{{1,{MAX_MONEY_SCALE}}})?$"
)
CURRENCY_CODE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Z]{3}$")


def parse_money_decimal(value: Decimal | int | str) -> Decimal:
    """Parse a decimal-safe money value, rejecting floats and bad wire strings."""

    if isinstance(value, bool):
        raise TypeError("money amount must not be boolean")
    if isinstance(value, float):
        raise TypeError("money amount must not be float")
    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, int):
        decimal_value = Decimal(value)
    elif isinstance(value, str):
        if not DECIMAL_STRING_PATTERN.fullmatch(value):
            raise ValueError("money amount must match DecimalString")
        try:
            decimal_value = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("money amount is not a valid decimal") from exc
    else:
        raise TypeError("money amount must be Decimal, int, or decimal string")

    if not decimal_value.is_finite():
        raise ValueError("money amount must be finite")
    if _fractional_scale(decimal_value) > MAX_MONEY_SCALE:
        raise ValueError(f"money amount supports at most {MAX_MONEY_SCALE} decimals")
    return decimal_value


def decimal_to_wire(value: Decimal | int | str) -> str:
    """Format a money value as the OpenAPI DecimalString wire shape."""

    decimal_value = parse_money_decimal(value)
    return format(decimal_value, "f")


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    @classmethod
    def from_wire(cls, amount: Decimal | int | str, currency: str) -> "Money":
        if not CURRENCY_CODE_PATTERN.fullmatch(currency):
            raise ValueError("currency must be an ISO 4217-style uppercase code")
        return cls(amount=parse_money_decimal(amount), currency=currency)

    def amount_wire(self) -> str:
        return decimal_to_wire(self.amount)


def _fractional_scale(value: Decimal) -> int:
    exponent = value.as_tuple().exponent
    return abs(exponent) if exponent < 0 else 0
