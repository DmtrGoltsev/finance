from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import ssl
from collections.abc import Iterable
from datetime import UTC, datetime
from urllib.parse import quote

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .instrument_resolver import ResolvedInstrument, is_valid_isin, is_valid_secid
from .models import MoexInstrumentModel

MOEX_HOST = "iss.moex.com"
REQUEST_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 1024 * 1024


class CatalogRefreshError(Exception):
    """An unverified response must never refresh catalog freshness."""


class _PinnedMoexConnection(http.client.HTTPSConnection):
    def __init__(self, address: str) -> None:
        super().__init__(MOEX_HOST, timeout=REQUEST_TIMEOUT_SECONDS)
        self._address = address

    def connect(self) -> None:
        # Pin the validated DNS result while retaining TLS hostname verification.
        raw_socket = socket.create_connection(
            (self._address, 443), timeout=REQUEST_TIMEOUT_SECONDS
        )
        try:
            self.sock = ssl.create_default_context().wrap_socket(
                raw_socket, server_hostname=MOEX_HOST
            )
        except Exception:
            raw_socket.close()
            raise


class MoexIssAdapter:
    def fetch(self, secid: str) -> ResolvedInstrument:
        if not is_valid_secid(secid):
            raise CatalogRefreshError("Invalid SECID")
        path = (
            f"/iss/securities/{quote(secid, safe='')}.json"
            "?iss.only=description&iss.meta=off"
        )
        try:
            addresses = {
                item[4][0]
                for item in socket.getaddrinfo(MOEX_HOST, 443, type=socket.SOCK_STREAM)
            }
            if not addresses or any(
                not ipaddress.ip_address(address).is_global for address in addresses
            ):
                raise CatalogRefreshError("MOEX DNS must resolve to public addresses")
            connection = _PinnedMoexConnection(sorted(addresses)[0])
            try:
                connection.request("GET", path, headers={"Accept": "application/json"})
                response = connection.getresponse()
                if response.status != 200:
                    # http.client never follows redirects or environment proxies.
                    raise CatalogRefreshError("MOEX response must be HTTP 200")
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise CatalogRefreshError("MOEX response exceeds size limit")
            finally:
                connection.close()
            description = json.loads(body)["description"]
            columns = description["columns"]
            if (
                not isinstance(columns, list)
                or columns.count("name") != 1
                or columns.count("value") != 1
                or not isinstance(description["data"], list)
            ):
                raise CatalogRefreshError("Invalid MOEX description table")
            name_index, value_index = columns.index("name"), columns.index("value")
            values = {}
            for row in description["data"]:
                if not isinstance(row, list) or len(row) != len(columns):
                    raise CatalogRefreshError("Invalid MOEX description row")
                name = row[name_index]
                if name in ("SECID", "ISIN"):
                    if name in values:
                        raise CatalogRefreshError("Ambiguous MOEX identifiers")
                    values[name] = row[value_index]
            isin = values.get("ISIN")
            if values.get("SECID") != secid or not isinstance(isin, str) or not is_valid_isin(isin):
                raise CatalogRefreshError("MOEX identifier mismatch or missing ISIN")
            return ResolvedInstrument(secid=secid, isin=isin)
        except CatalogRefreshError:
            raise
        except (OSError, http.client.HTTPException, ValueError, KeyError, TypeError, IndexError):
            raise CatalogRefreshError("Unable to validate MOEX response") from None


def refresh_catalog(
    session: Session,
    secids: Iterable[str],
    *,
    adapter: MoexIssAdapter | None = None,
    now: datetime | None = None,
) -> int:
    identifiers = sorted(set(secids))
    if not 1 <= len(identifiers) <= 500 or any(not is_valid_secid(s) for s in identifiers):
        raise CatalogRefreshError("Expected 1 to 500 valid SECIDs")
    adapter = adapter or MoexIssAdapter()
    fetched_at = now or datetime.now(UTC)
    if fetched_at.tzinfo is None:
        raise CatalogRefreshError("Catalog timestamp must be timezone-aware")
    # Validate the complete batch before any write. The caller owns the transaction.
    instruments = [adapter.fetch(secid) for secid in identifiers]
    for secid, instrument in zip(identifiers, instruments, strict=True):
        if instrument.secid != secid or not is_valid_isin(instrument.isin):
            raise CatalogRefreshError("Unverified catalog entry")
    dialect = session.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise CatalogRefreshError("Unsupported catalog database")
    insert = pg_insert if dialect == "postgresql" else sqlite_insert
    for instrument in instruments:
        statement = insert(MoexInstrumentModel).values(
            secid=instrument.secid, isin=instrument.isin, fetched_at=fetched_at
        )
        session.execute(statement.on_conflict_do_update(
            index_elements=[MoexInstrumentModel.secid],
            set_={"isin": statement.excluded.isin, "fetched_at": statement.excluded.fetched_at},
            where=MoexInstrumentModel.fetched_at <= statement.excluded.fetched_at,
        ))
    session.flush()
    session.expire_all()
    return len(instruments)
