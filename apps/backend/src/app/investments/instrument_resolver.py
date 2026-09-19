from __future__ import annotations

import re
from dataclasses import dataclass

SECID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,31}$")
ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


@dataclass(frozen=True, slots=True)
class ResolvedInstrument:
    secid: str
    isin: str


LOCAL_MOEX_INSTRUMENTS = (
    ResolvedInstrument(secid="SU26238RMFS4", isin="RU000A1038V6"),
    ResolvedInstrument(secid="SBMX", isin="RU000A0ZZH92"),
    ResolvedInstrument(secid="SBER", isin="RU0009029540"),
    ResolvedInstrument(secid="LQDT", isin="RU000A1013V9"),
)


class LocalMoexInstrumentResolver:
    """Resolve only instruments present in the server-managed local MOEX catalog."""

    def __init__(
        self, instruments: tuple[ResolvedInstrument, ...] = LOCAL_MOEX_INSTRUMENTS
    ) -> None:
        self._by_secid = {item.secid: item for item in instruments}
        self._by_isin = {item.isin: item for item in instruments}

    def resolve(self, *, secid: str | None, isin: str | None) -> ResolvedInstrument | None:
        normalized_secid = secid.upper() if secid else None
        normalized_isin = isin.upper() if isin else None
        if normalized_secid and not is_valid_secid(normalized_secid):
            return None
        if normalized_isin and not is_valid_isin(normalized_isin):
            return None
        by_secid = self._by_secid.get(normalized_secid) if normalized_secid else None
        by_isin = self._by_isin.get(normalized_isin) if normalized_isin else None
        if normalized_secid and by_secid is None:
            return None
        if normalized_isin and by_isin is None:
            return None
        if by_secid and by_isin and by_secid != by_isin:
            return None
        return by_secid or by_isin


def is_valid_secid(value: str) -> bool:
    return SECID_PATTERN.fullmatch(value) is not None


def is_valid_isin(value: str) -> bool:
    if ISIN_PATTERN.fullmatch(value) is None:
        return False
    digits = "".join(str(int(character, 36)) for character in value)
    checksum = 0
    for index, character in enumerate(reversed(digits)):
        digit = int(character)
        if index % 2 == 1:
            digit *= 2
        checksum += digit // 10 + digit % 10
    return checksum % 10 == 0
