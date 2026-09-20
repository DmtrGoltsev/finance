from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MoexInstrumentModel

SECID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,31}$")
ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


@dataclass(frozen=True, slots=True)
class ResolvedInstrument:
    secid: str
    isin: str


CATALOG_TTL = timedelta(hours=24)


class MoexInstrumentResolver:
    """Read verified, fresh identifiers without network access on the request path."""

    def __init__(self, session: Session, *, now: datetime | None = None) -> None:
        self.session = session
        self._now = now

    def resolve(self, *, secid: str | None, isin: str | None) -> ResolvedInstrument | None:
        normalized_secid = secid.upper() if secid else None
        normalized_isin = isin.upper() if isin else None
        if normalized_secid and not is_valid_secid(normalized_secid):
            return None
        if normalized_isin and not is_valid_isin(normalized_isin):
            return None
        if not normalized_secid and not normalized_isin:
            return None
        query = select(MoexInstrumentModel)
        if normalized_secid:
            query = query.where(MoexInstrumentModel.secid == normalized_secid)
        if normalized_isin:
            query = query.where(MoexInstrumentModel.isin == normalized_isin)
        rows = self.session.scalars(query.limit(2)).all()
        if len(rows) != 1:
            return None
        row = rows[0]
        fetched_at = (
            row.fetched_at.replace(tzinfo=UTC)
            if row.fetched_at.tzinfo is None else row.fetched_at
        )
        age = (self._now or datetime.now(UTC)) - fetched_at
        if not timedelta(0) <= age < CATALOG_TTL:
            return None
        if not is_valid_secid(row.secid) or not is_valid_isin(row.isin):
            return None
        return ResolvedInstrument(secid=row.secid, isin=row.isin)


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
