from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.investments import moex_catalog
from app.investments.instrument_resolver import (
    CATALOG_TTL,
    MoexInstrumentResolver,
    ResolvedInstrument,
)
from app.investments.models import MoexInstrumentModel
from app.investments.moex_catalog import CatalogRefreshError, MoexIssAdapter, refresh_catalog

NOW = datetime(2026, 9, 20, tzinfo=UTC)
GAZP = ResolvedInstrument("GAZP", "RU0007661625")
PINNED_CONNECTION = moex_catalog._PinnedMoexConnection


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture(autouse=True)
def network(monkeypatch):
    dns = Mock(return_value=[(2, 1, 6, "", ("8.8.8.8", 443))])
    monkeypatch.setattr(moex_catalog.socket, "getaddrinfo", dns)
    connection = Mock()
    response = connection.getresponse.return_value
    response.status = 200
    response.read.return_value = (
        b'{"description":{"columns":["name","value"],"data":'
        b'[["SECID","GAZP"],["ISIN","RU0007661625"]]}}'
    )
    factory = Mock(return_value=connection)
    monkeypatch.setattr(moex_catalog, "_PinnedMoexConnection", factory)
    return dns, factory, connection, response


def test_official_adapter_refreshes_gazp_and_upserts(session, network):
    dns, factory, connection, _ = network
    assert refresh_catalog(session, ["GAZP"], now=NOW) == 1
    resolver = MoexInstrumentResolver(session, now=NOW)
    assert resolver.resolve(secid="GAZP", isin="RU0007661625") == GAZP
    assert resolver.resolve(secid=None, isin=GAZP.isin) == GAZP
    assert resolver.resolve(secid="GAZP", isin="RU0009029540") is None
    assert refresh_catalog(session, ["GAZP", "GAZP"], now=NOW + timedelta(hours=1)) == 1
    assert session.scalar(select(func.count()).select_from(MoexInstrumentModel)) == 1
    assert session.get(MoexInstrumentModel, "GAZP").fetched_at.replace(tzinfo=UTC) == (
        NOW + timedelta(hours=1)
    )
    dns.assert_called_with("iss.moex.com", 443, type=moex_catalog.socket.SOCK_STREAM)
    factory.assert_called_with("8.8.8.8")
    connection.request.assert_called_with(
        "GET", "/iss/securities/GAZP.json?iss.only=description&iss.meta=off",
        headers={"Accept": "application/json"},
    )
    assert connection.close.call_count == 2


@pytest.mark.parametrize("age", [CATALOG_TTL, CATALOG_TTL * 2, -timedelta(seconds=1)])
def test_catalog_stale_or_future_fails_closed(session, age):
    refresh_catalog(session, ["GAZP"], now=NOW - age)
    assert MoexInstrumentResolver(session, now=NOW).resolve(secid="GAZP", isin=GAZP.isin) is None


def test_missing_catalog_and_ambiguous_isin_fail_closed(session):
    resolver = MoexInstrumentResolver(session, now=NOW)
    assert resolver.resolve(secid="GAZP", isin=GAZP.isin) is None
    refresh_catalog(session, ["GAZP"], now=NOW)
    session.add(MoexInstrumentModel(secid="ALIAS", isin=GAZP.isin, fetched_at=NOW))
    session.flush()
    assert resolver.resolve(secid=None, isin=GAZP.isin) is None
    assert resolver.resolve(secid="GAZP", isin=GAZP.isin) == GAZP


@pytest.mark.parametrize("text", ["ACCOUNT 123 PERSON", "https://127.0.0.1", "../GAZP", "GAZP?x=1"])
def test_malicious_identifier_never_reaches_network(session, network, text):
    with pytest.raises(CatalogRefreshError):
        refresh_catalog(session, [text], now=NOW)
    with pytest.raises(CatalogRefreshError):
        MoexIssAdapter().fetch(text)
    assert MoexInstrumentResolver(session, now=NOW).resolve(secid=text, isin=None) is None
    network[0].assert_not_called()


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1"])
def test_private_dns_is_rejected(network, ip):
    network[0].return_value.append((2, 1, 6, "", (ip, 443)))
    with pytest.raises(CatalogRefreshError, match="public"):
        MoexIssAdapter().fetch("GAZP")
    network[1].assert_not_called()


@pytest.mark.parametrize("status", [301, 302, 307, 404, 500])
def test_redirect_or_failure_does_not_refresh_catalog(session, network, status):
    refresh_catalog(session, ["GAZP"], now=NOW)
    network[3].status = status
    with pytest.raises(CatalogRefreshError):
        refresh_catalog(session, ["GAZP"], now=NOW + CATALOG_TTL)
    assert MoexInstrumentResolver(session, now=NOW + CATALOG_TTL).resolve(
        secid="GAZP", isin=None
    ) is None


@pytest.mark.parametrize("body", [
    b'{}', b'not json', b'x' * (moex_catalog.MAX_RESPONSE_BYTES + 1),
    b'{"description":{"columns":["name","value"],"data":[["SECID","SBER"]]}}',
    b'{"description":{"columns":["name","value"],"data":'
    b'[["SECID","GAZP"],["ISIN","ACCOUNT 123 PERSON"]]}}',
    b'{"description":{"columns":["name","value"],"data":'
    b'[["SECID","GAZP"],["ISIN","RU0007661625"],["ISIN","RU0009029540"]]}}',
    b'{"description":{"columns":{},"data":[]}}',
    b'{"description":{"columns":["name","value"],"data":["not-a-row"]}}',
], ids=[
    "missing", "not-json", "oversized", "mismatch", "malicious", "ambiguous",
    "invalid-columns", "invalid-row",
])
def test_invalid_response_cannot_populate_catalog(session, network, body):
    network[3].read.return_value = body
    with pytest.raises(CatalogRefreshError):
        refresh_catalog(session, ["GAZP"], now=NOW)
    assert session.get(MoexInstrumentModel, "GAZP") is None


def test_timeout_fails_closed_and_closes_connection(session, network):
    network[2].getresponse.side_effect = TimeoutError()
    with pytest.raises(CatalogRefreshError):
        refresh_catalog(session, ["GAZP"], now=NOW)
    network[2].close.assert_called_once()


def test_batch_failure_is_atomic_and_older_refresh_cannot_overwrite(session):
    adapter = Mock()
    adapter.fetch.side_effect = [GAZP, CatalogRefreshError("unavailable")]
    with pytest.raises(CatalogRefreshError):
        refresh_catalog(session, ["GAZP", "SBER"], now=NOW, adapter=adapter)
    assert session.get(MoexInstrumentModel, "GAZP") is None
    refresh_catalog(session, ["GAZP"], now=NOW)
    refresh_catalog(session, ["GAZP"], now=NOW - timedelta(hours=1))
    assert session.get(MoexInstrumentModel, "GAZP").fetched_at.replace(tzinfo=UTC) == NOW


def test_connection_pins_checked_address_and_verifies_moex_tls(monkeypatch):
    socket_factory = Mock()
    context = Mock()
    context_factory = Mock(return_value=context)
    monkeypatch.setattr(moex_catalog.socket, "create_connection", socket_factory)
    monkeypatch.setattr(moex_catalog.ssl, "create_default_context", context_factory)
    connection = PINNED_CONNECTION("8.8.8.8")
    connection.connect()
    socket_factory.assert_called_once_with(("8.8.8.8", 443), timeout=10)
    context.wrap_socket.assert_called_once_with(
        socket_factory.return_value, server_hostname="iss.moex.com"
    )
    assert connection.sock is context.wrap_socket.return_value
    connection.close()


def test_tls_failure_closes_raw_socket(monkeypatch):
    socket_factory = Mock()
    context = Mock()
    context.wrap_socket.side_effect = moex_catalog.ssl.SSLError()
    monkeypatch.setattr(moex_catalog.socket, "create_connection", socket_factory)
    monkeypatch.setattr(moex_catalog.ssl, "create_default_context", Mock(return_value=context))
    with pytest.raises(moex_catalog.ssl.SSLError):
        PINNED_CONNECTION("8.8.8.8").connect()
    socket_factory.return_value.close.assert_called_once()
