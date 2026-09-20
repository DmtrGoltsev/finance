from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
import yaml
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.api.auth_context import require_authenticated_actor
from app.authz import Actor
from app.config import Settings
from app.db.base import Base
from app.db.models import OutboxEvent, User
from app.investments.allocation import AllocationPolicy, RiskBucket, cash_first_rebalance
from app.investments.hmac_auth import HmacVerificationError, sign_callback, verify_callback
from app.investments.instrument_resolver import ResolvedInstrument
from app.investments.models import MoexInstrumentModel, RecommendationReportModel
from app.investments.moex_catalog import refresh_catalog
from app.investments.repository import InvestmentRepository
from app.investments.router import investment_service_for_request
from app.investments.schemas import (
    InvestmentPolicyPutRequest,
    PortfolioPositionInput,
    RecommendationCallbackRequest,
    RecommendationJobCreateRequest,
    RecommendationSourceInput,
)
from app.investments.schemas import (
    PortfolioImportConfirmRequest as PortfolioImportConfirmRequestModel,
)
from app.investments.schemas import (
    PortfolioImportCreateRequest as PortfolioImportCreateRequestModel,
)
from app.investments.service import (
    AccountProfileConflict,
    ConfirmedImportNotDiscardable,
    IdempotencyConflict,
    InvalidObservedAt,
    InvalidPagination,
    InvalidRecommendationPayload,
    InvalidTransition,
    InvestmentService,
    ReplayDetected,
    ResourceNotFoundOrInaccessible,
    StaleMarketData,
    StalePortfolio,
)
from app.investments.source_validation import (
    UntrustedRecommendationSource,
    validate_recommendation_sources,
)
from app.main import create_app

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
PROFILE_IDS = {
    "sinara": UUID("10000000-0000-4000-8000-000000000001"),
    "sber_investments": UUID("10000000-0000-4000-8000-000000000002"),
    "finam": UUID("10000000-0000-4000-8000-000000000003"),
}


def PortfolioImportCreateRequest(**values):
    brokerage = values.get("brokerage", values.get("brokerage", "finam"))
    values.setdefault("accountProfileId", PROFILE_IDS[str(brokerage)])
    values.setdefault("userLabel", "Основной счет")
    values.setdefault("accountType", "brokerage")
    return PortfolioImportCreateRequestModel(**values)


def PortfolioImportConfirmRequest(**values):
    values.setdefault("accountProfileId", PROFILE_IDS["finam"])
    return PortfolioImportConfirmRequestModel(**values)


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as value:
        value.add_all([
            MoexInstrumentModel(secid=secid, isin=isin, fetched_at=NOW)
            for secid, isin in (
                ("SU26238RMFS4", "RU000A1038V6"),
                ("SBMX", "RU000A0ZZH92"),
                ("SBER", "RU0009029540"),
                ("LQDT", "RU000A1013V9"),
            )
        ])
        value.flush()
        yield value


def actor(session: Session) -> Actor:
    user_id = uuid4()
    session.add(
        User(
            id=user_id,
            email_normalized=f"{user_id}@example.test",
            password_hash="test-only",
            display_name=None,
            auth_status="active",
            record_status="active",
            session_version=1,
            created_at=NOW,
            updated_at=NOW,
            version=1,
        )
    )
    session.flush()
    return Actor(user_id=str(user_id), request_id="req-test")


def position(*, bucket: str = "conservative", value: str = "40000") -> PortfolioPositionInput:
    identifiers = {
        "conservative": ("SU26238RMFS4", "RU000A1038V6"),
        "moderate": ("SBMX", "RU000A0ZZH92"),
        "aggressive": ("SBER", "RU0009029540"),
    }
    ticker, isin = identifiers[bucket]
    return PortfolioPositionInput(
        instrumentName="ОФЗ 26238",
        ticker=ticker,
        isin=isin,
        instrumentType="bond",
        riskBucket=bucket,
        quantity="40",
        marketPrice="1000",
        marketValue=value,
        averagePrice="990",
        nominal="1000",
        accruedInterest="12.34",
        couponRate="7.10",
        maturityDate="2041-05-15",
        taxAccountType="iis_iii",
        holdingStartedAt="2026-01-10",
        estimatedFeeRate="0.30",
    )


def confirmed_snapshot(
    service: InvestmentService,
    owner: Actor,
    *,
    observed_at: datetime = NOW,
) -> UUID:
    imported = service.create_import(
        owner,
        PortfolioImportCreateRequest(
            idempotencyKey=f"import-{uuid4()}",
            brokerage="finam",
            screenshotCount=2,
            observedAt=observed_at,
        ),
    )
    snapshot = service.confirm_import(
        owner,
        imported.id,
        PortfolioImportConfirmRequest(
            freeCash="10000",
            monthlyContribution="10000",
            positions=[
                position(bucket="conservative", value="40000"),
                position(bucket="moderate", value="20000"),
                position(bucket="aggressive", value="20000"),
            ],
        ),
    )
    return snapshot.id


def test_migrations_have_one_head_and_two_sequential_revisions() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(backend_root.parents[1] / "db" / "migrations"),
    )
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["20260920_0024"]
    assert scripts.get_revision("20260920_0024").down_revision == "20260920_0023"
    assert scripts.get_revision("20260920_0023").down_revision == "20260920_0022"
    assert scripts.get_revision("20260920_0022").down_revision == "20260919_0021"
    assert scripts.get_revision("20260919_0021").down_revision == "20260919_0020"
    assert scripts.get_revision("20260919_0020").down_revision == "20260822_0019"


def test_policy_boundaries_and_cash_first_use_new_money_before_reductions() -> None:
    policy = AllocationPolicy()
    exact = cash_first_rebalance(
        current_values={
            RiskBucket.CONSERVATIVE: Decimal("40"),
            RiskBucket.MODERATE: Decimal("30"),
            RiskBucket.AGGRESSIVE: Decimal("30"),
        },
        free_cash=Decimal("0"),
        monthly_contribution=Decimal("0"),
        policy=policy,
    )
    assert all(item.within_tolerance for item in exact)
    assert all(item.add_amount == 0 and item.reduce_amount == 0 for item in exact)

    cash_first = cash_first_rebalance(
        current_values={
            RiskBucket.CONSERVATIVE: Decimal("40"),
            RiskBucket.MODERATE: Decimal("20"),
            RiskBucket.AGGRESSIVE: Decimal("20"),
        },
        free_cash=Decimal("10"),
        monthly_contribution=Decimal("10"),
        policy=policy,
    )
    by_bucket = {item.bucket: item for item in cash_first}
    assert by_bucket[RiskBucket.MODERATE].add_amount == Decimal("10.0000")
    assert by_bucket[RiskBucket.AGGRESSIVE].add_amount == Decimal("10.0000")
    assert all(item.reduce_amount == 0 for item in cash_first)

    at_lower_boundary = cash_first_rebalance(
        current_values={
            RiskBucket.CONSERVATIVE: Decimal("45"),
            RiskBucket.MODERATE: Decimal("25"),
            RiskBucket.AGGRESSIVE: Decimal("30"),
        },
        free_cash=Decimal("0"),
        monthly_contribution=Decimal("0"),
        policy=policy,
    )
    assert all(item.within_tolerance for item in at_lower_boundary)


def test_owner_isolation_and_idempotency(session: Session) -> None:
    owner = actor(session)
    other = actor(session)
    service = InvestmentService(InvestmentRepository(session), now=NOW)
    request = PortfolioImportCreateRequest(
        idempotencyKey="same-import-key",
        brokerage="sinara",
        screenshotCount=3,
        observedAt=NOW,
    )
    first = service.create_import(owner, request)
    assert service.create_import(owner, request).id == first.id
    with pytest.raises(IdempotencyConflict):
        service.create_import(
            owner,
            PortfolioImportCreateRequest(
                idempotencyKey="same-import-key",
                brokerage="finam",
                screenshotCount=3,
                observedAt=NOW,
            ),
        )

    snapshot_id = confirmed_snapshot(service, owner)
    with pytest.raises(ResourceNotFoundOrInaccessible):
        service.snapshot(other, snapshot_id)
    with pytest.raises(ResourceNotFoundOrInaccessible):
        service.create_job(
            other,
            RecommendationJobCreateRequest(
                idempotencyKey="other-users-job",
                snapshotIds=[snapshot_id],
            ),
        )


def test_concurrent_first_policy_and_snapshot_confirmation_reread_winner(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = actor(session)
    repository = InvestmentRepository(session)
    service = InvestmentService(repository, now=NOW)
    policy = service.policy(owner)
    original_policy_lookup = repository.get_policy
    policy_calls = 0

    def miss_policy_twice(owner_user_id: UUID):
        nonlocal policy_calls
        policy_calls += 1
        if policy_calls <= 2:
            return None
        return original_policy_lookup(owner_user_id)

    monkeypatch.setattr(repository, "get_policy", miss_policy_twice)
    assert service.policy(owner).id == policy.id
    monkeypatch.setattr(repository, "get_policy", original_policy_lookup)

    imported = service.create_import(
        owner,
        PortfolioImportCreateRequest(
            idempotencyKey="snapshot-race-import",
            brokerage="finam",
            screenshotCount=1,
            observedAt=NOW,
        ),
    )
    confirm_request = PortfolioImportConfirmRequest(
        freeCash="0",
        monthlyContribution="0",
        positions=[position()],
    )
    snapshot = service.confirm_import(owner, imported.id, confirm_request)
    original_snapshot_lookup = repository.get_snapshot_by_import
    snapshot_calls = 0

    def miss_snapshot_once(import_id: UUID):
        nonlocal snapshot_calls
        snapshot_calls += 1
        if snapshot_calls == 1:
            return None
        return original_snapshot_lookup(import_id)

    monkeypatch.setattr(repository, "get_snapshot_by_import", miss_snapshot_once)
    assert service.confirm_import(owner, imported.id, confirm_request).id == snapshot.id


def test_idempotency_insert_race_returns_existing_or_conflict(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = actor(session)
    repository = InvestmentRepository(session)
    service = InvestmentService(repository, now=NOW)
    original_lookup = repository.find_import_by_idempotency
    first = service.create_import(
        owner,
        PortfolioImportCreateRequest(
            idempotencyKey="racing-import-key",
            brokerage="sinara",
            screenshotCount=1,
            observedAt=NOW,
        ),
    )

    calls = 0

    def miss_then_read(owner_user_id: UUID, idempotency_key: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return original_lookup(owner_user_id, idempotency_key)

    monkeypatch.setattr(repository, "find_import_by_idempotency", miss_then_read)
    replay = service.create_import(
        owner,
        PortfolioImportCreateRequest(
            idempotencyKey="racing-import-key",
            brokerage="sinara",
            screenshotCount=1,
            observedAt=NOW,
        ),
    )
    assert replay.id == first.id

    calls = 0
    with pytest.raises(IdempotencyConflict):
        service.create_import(
            owner,
            PortfolioImportCreateRequest(
                idempotencyKey="racing-import-key",
                brokerage="finam",
                screenshotCount=1,
                observedAt=NOW,
            ),
        )


def test_position_requires_canonical_secid_or_isin() -> None:
    with pytest.raises(ValueError, match="SECID or ISIN"):
        PortfolioPositionInput(
            instrumentName="Произвольный текст OCR",
            instrumentType="stock",
            riskBucket="aggressive",
            quantity="1",
            marketValue="100",
        )

    with pytest.raises(ValueError, match="pattern"):
        PortfolioPositionInput(
            instrumentName="Утечка OCR",
            ticker="ACCOUNT 123 PERSON",
            instrumentType="stock",
            riskBucket="aggressive",
            quantity="1",
            marketValue="100",
        )

    with pytest.raises(ValueError, match="invalid ISIN"):
        PortfolioPositionInput(
            instrumentName="Неверный ISIN",
            isin="RU000A1038V7",
            instrumentType="bond",
            riskBucket="conservative",
            quantity="1",
            marketValue="100",
        )


def test_unresolved_instrument_never_creates_external_payload(session: Session) -> None:
    owner = actor(session)
    service = InvestmentService(InvestmentRepository(session), now=NOW)
    imported = service.create_import(
        owner,
        PortfolioImportCreateRequest(
            idempotencyKey="unresolved-import",
            brokerage="finam",
            screenshotCount=1,
            observedAt=NOW,
        ),
    )
    snapshot = service.confirm_import(
        owner,
        imported.id,
        PortfolioImportConfirmRequest(
            positions=[
                PortfolioPositionInput(
                    instrumentName="Произвольный тикер",
                    ticker="ACCOUNT",
                    instrumentType="stock",
                    riskBucket="aggressive",
                    quantity="1",
                    marketValue="100",
                )
            ]
        ),
    )
    with pytest.raises(InvalidRecommendationPayload):
        service.create_job(
            owner,
            RecommendationJobCreateRequest(
                idempotencyKey="unresolved-job",
                snapshotIds=[snapshot.id],
            ),
        )
    assert list(session.scalars(select(OutboxEvent))) == []


@pytest.mark.parametrize("catalog_state", ["fresh", "missing", "stale", "mismatch"])
def test_gazp_external_package_requires_verified_fresh_catalog(session, catalog_state):
    service = InvestmentService(InvestmentRepository(session), now=NOW)
    owner = actor(session)
    imported = service.create_import(owner, PortfolioImportCreateRequest(
        idempotencyKey="gazp-import", brokerage="sinara", screenshotCount=1, observedAt=NOW,
    ))
    snapshot = service.confirm_import(owner, imported.id, PortfolioImportConfirmRequest(
        accountProfileId=PROFILE_IDS["sinara"],
        positions=[PortfolioPositionInput(
            instrumentName="Private user label", ticker="GAZP", isin="RU0007661625",
            instrumentType="stock", riskBucket="aggressive", quantity="10", marketValue="1500",
        )],
    ))
    adapter = Mock()
    adapter.fetch.return_value = ResolvedInstrument(
        "GAZP", "RU0009029540" if catalog_state == "mismatch" else "RU0007661625",
    )
    if catalog_state != "missing":
        refresh_catalog(
            session, ["GAZP"], adapter=adapter,
            now=NOW - timedelta(days=2) if catalog_state == "stale" else NOW,
        )
    request = RecommendationJobCreateRequest(idempotencyKey="gazp-job", snapshotIds=[snapshot.id])
    if catalog_state == "fresh":
        service.create_job(owner, request)
        event = session.scalar(select(OutboxEvent))
        assert "GAZP" in str(event.payload_safe)
        assert "RU0007661625" in str(event.payload_safe)
        assert "Private user label" not in str(event.payload_safe)
        allowed_sources = event.payload_safe["constraints"]["allowedSources"]
        assert "nalog.gov.ru" not in allowed_sources
        assert "www.nalog.gov.ru" not in allowed_sources
    else:
        with pytest.raises(InvalidRecommendationPayload):
            service.create_job(owner, request)
        assert list(session.scalars(select(OutboxEvent))) == []


def test_multiple_accounts_same_broker_are_distinct_and_owner_scoped(session: Session) -> None:
    owner = actor(session)
    other = actor(session)
    service = InvestmentService(InvestmentRepository(session), now=NOW)
    first_id, second_id = uuid4(), uuid4()
    first = service.create_import(owner, PortfolioImportCreateRequest(
        idempotencyKey="same-broker-first", accountProfileId=first_id,
        brokerage="finam", userLabel="Основной счет", accountType="brokerage",
        screenshotCount=1, observedAt=NOW,
    ))
    second = service.create_import(owner, PortfolioImportCreateRequest(
        idempotencyKey="same-broker-second", accountProfileId=second_id,
        brokerage="finam", userLabel="ИИС долгий", accountType="iis_iii",
        screenshotCount=1, observedAt=NOW,
    ))
    assert first.account_profile_id == first_id
    assert second.account_profile_id == second_id
    assert first.brokerage == second.brokerage == "finam"

    snapshot = service.confirm_import(owner, second.id, PortfolioImportConfirmRequest(
        accountProfileId=second_id, positions=[position()],
    ))
    assert snapshot.account_profile_id == second_id
    with pytest.raises(AccountProfileConflict):
        service.confirm_import(
            owner,
            first.id,
            PortfolioImportConfirmRequest(
                accountProfileId=second_id, positions=[position()]
            ),
        )

    with pytest.raises(ResourceNotFoundOrInaccessible):
        service.create_import(other, PortfolioImportCreateRequest(
            idempotencyKey="profile-idor", accountProfileId=first_id,
            brokerage="finam", userLabel="Основной счет", accountType="brokerage",
            screenshotCount=1, observedAt=NOW,
        ))
    with pytest.raises(AccountProfileConflict):
        service.create_import(owner, PortfolioImportCreateRequest(
            idempotencyKey="duplicate-profile-label", accountProfileId=uuid4(),
            brokerage="finam", userLabel="  ОСНОВНОЙ   СЧЕТ  ", accountType="brokerage",
            screenshotCount=1, observedAt=NOW,
        ))
    with pytest.raises(ValueError):
        PortfolioImportCreateRequest(
            idempotencyKey="unsafe-profile-label", accountProfileId=uuid4(),
            brokerage="finam", userLabel="Счет 123@example.com", accountType="brokerage",
            screenshotCount=1, observedAt=NOW,
        )


def test_discard_import_is_owner_only_idempotent_and_rejects_confirmed(session: Session) -> None:
    owner = actor(session)
    other = actor(session)
    service = InvestmentService(InvestmentRepository(session), now=NOW)
    pending = service.create_import(owner, PortfolioImportCreateRequest(
        idempotencyKey="discard-pending", brokerage="sinara", screenshotCount=1, observedAt=NOW,
    ))
    service.discard_import(other, pending.id)
    assert service.repo.get_import(pending.id) is not None
    service.discard_import(owner, pending.id)
    service.discard_import(owner, pending.id)
    assert service.repo.get_import(pending.id) is None

    confirmed = service.create_import(owner, PortfolioImportCreateRequest(
        idempotencyKey="discard-confirmed", brokerage="finam", screenshotCount=1, observedAt=NOW,
    ))
    service.confirm_import(
        owner, confirmed.id, PortfolioImportConfirmRequest(positions=[position()])
    )
    with pytest.raises(ConfirmedImportNotDiscardable):
        service.discard_import(owner, confirmed.id)
    assert service.repo.get_import(confirmed.id) is not None

    route_pending = service.create_import(owner, PortfolioImportCreateRequest(
        idempotencyKey="discard-route", brokerage="sinara", screenshotCount=1, observedAt=NOW,
    ))
    application = create_app()
    application.dependency_overrides[investment_service_for_request] = lambda: service
    application.dependency_overrides[require_authenticated_actor] = lambda: owner
    with TestClient(application) as test_client:
        path = f"/api/v1/investments/portfolio-imports/{route_pending.id}"
        assert test_client.delete(path).status_code == 204
        assert test_client.delete(path).status_code == 204
        confirmed_path = f"/api/v1/investments/portfolio-imports/{confirmed.id}"
        response = test_client.delete(confirmed_path)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFIRMED_IMPORT_NOT_DISCARDABLE"


def test_recommendation_history_is_owner_only_paginated_and_newest_first(session: Session) -> None:
    owner = actor(session)
    other = actor(session)
    service = InvestmentService(InvestmentRepository(session), now=NOW)
    snapshot_id = confirmed_snapshot(service, owner)
    jobs = [
        service.create_job(owner, RecommendationJobCreateRequest(
            idempotencyKey=f"history-job-{index}", snapshotIds=[snapshot_id],
        ))
        for index in range(3)
    ]
    for index, job in enumerate(jobs):
        job.created_at = NOW + timedelta(minutes=index)
        job.updated_at = job.created_at
    session.add(RecommendationReportModel(
        owner_user_id=UUID(owner.user_id), job_id=jobs[2].id,
        summary="Свежая рекомендация", assumptions={}, generated_at=NOW,
        valid_until=NOW + timedelta(days=7), disclaimer="Ручное исполнение",
    ))
    session.flush()

    first_page, cursor, has_more = service.jobs(owner, limit=2, cursor=None)
    assert [item.id for item in first_page] == [jobs[2].id, jobs[1].id]
    assert cursor == "2" and has_more is True
    second_page, cursor, has_more = service.jobs(owner, limit=2, cursor=cursor)
    assert [item.id for item in second_page] == [jobs[0].id]
    assert cursor is None and has_more is False
    assert service.jobs(other, limit=20, cursor=None)[0] == []
    with pytest.raises(InvalidPagination):
        service.jobs(owner, limit=20, cursor="not-a-cursor")

    application = create_app()
    application.dependency_overrides[investment_service_for_request] = lambda: service
    application.dependency_overrides[require_authenticated_actor] = lambda: owner
    with TestClient(application) as test_client:
        response = test_client.get("/api/v1/investments/recommendation-jobs?limit=2")
    assert response.status_code == 200
    payload = response.json()
    assert [item["job"]["id"] for item in payload["items"]] == [
        str(jobs[2].id), str(jobs[1].id)
    ]
    assert payload["items"][0]["reportSummary"] == "Свежая рекомендация"
    assert payload["items"][0]["reportPath"].endswith(f"/{jobs[2].id}/report")
    assert payload["items"][0]["accountProfiles"][0]["userLabel"] == "Основной счет"
    assert payload["page"] == {"limit": 2, "nextCursor": "2", "hasMore": True}

    unauthenticated = create_app()
    unauthenticated.dependency_overrides[investment_service_for_request] = lambda: service
    with TestClient(unauthenticated) as test_client:
        response = test_client.get("/api/v1/investments/recommendation-jobs")
    assert response.status_code == 401


def test_future_portfolio_observation_is_rejected(session: Session) -> None:
    owner = actor(session)
    service = InvestmentService(InvestmentRepository(session), now=NOW)
    with pytest.raises(InvalidObservedAt):
        service.create_import(
            owner,
            PortfolioImportCreateRequest(
                idempotencyKey="future-import-key",
                brokerage="finam",
                screenshotCount=1,
                observedAt=NOW + timedelta(minutes=5, seconds=1),
            ),
        )


def test_source_allowlist_rejects_evil_and_private_hosts_and_derives_trust() -> None:
    valid = RecommendationSourceInput(
        title="MOEX ISS",
        url="https://iss.moex.com/iss/securities.json",
        publisher="Московская биржа",
        fetchedAt=NOW,
    )
    assert validate_recommendation_sources([valid], issuer_hosts=[])[0].trust_tier == "official"

    for host in ("nalog.gov.ru", "www.nalog.gov.ru"):
        tax_source = RecommendationSourceInput(
            title="ФНС России",
            url=f"https://{host}/rn77/taxation/investment_deduction/",
            publisher="ФНС России",
            fetchedAt=NOW,
        )
        with pytest.raises(UntrustedRecommendationSource):
            validate_recommendation_sources([tax_source], issuer_hosts=[])
        assert (
            validate_recommendation_sources(
                [tax_source], issuer_hosts=[], allow_tax_sources=True
            )[0].trust_tier
            == "official"
        )

    for url in ("https://evil.example/data", "https://127.0.0.1/data"):
        with pytest.raises(UntrustedRecommendationSource):
            validate_recommendation_sources(
                [
                    RecommendationSourceInput(
                        title="Недоверенный источник",
                        url=url,
                        publisher="Неизвестно",
                        fetchedAt=NOW,
                    )
                ],
                issuer_hosts=[],
            )


def test_stale_snapshot_and_stale_market_data_are_rejected(session: Session) -> None:
    owner = actor(session)
    service = InvestmentService(InvestmentRepository(session), now=NOW)
    stale_snapshot_id = confirmed_snapshot(
        service,
        owner,
        observed_at=NOW - timedelta(hours=24, seconds=1),
    )
    with pytest.raises(StalePortfolio):
        service.create_job(
            owner,
            RecommendationJobCreateRequest(
                idempotencyKey="stale-portfolio-job",
                snapshotIds=[stale_snapshot_id],
            ),
        )

    fresh_snapshot_id = confirmed_snapshot(service, owner)
    job = service.create_job(
        owner,
        RecommendationJobCreateRequest(
            idempotencyKey="fresh-portfolio-job",
            snapshotIds=[fresh_snapshot_id],
        ),
    )
    with pytest.raises(StaleMarketData):
        service.apply_callback(
            job_id=job.id,
            nonce="nonce-stale-market-0001",
            request=RecommendationCallbackRequest(
                status="analyzing",
                marketDataAsOf=NOW - timedelta(hours=25),
            ),
        )


def test_transitions_three_attempts_ready_report_and_replay(session: Session) -> None:
    owner = actor(session)
    service = InvestmentService(InvestmentRepository(session), now=NOW)
    snapshot_id = confirmed_snapshot(service, owner)
    job = service.create_job(
        owner,
        RecommendationJobCreateRequest(
            idempotencyKey="transition-job-key",
            snapshotIds=[snapshot_id],
        ),
    )
    dispatch = session.scalars(select(OutboxEvent)).first()
    assert dispatch is not None
    serialized_dispatch = str(dispatch.payload_safe)
    assert owner.user_id not in serialized_dispatch
    assert "secid" in serialized_dispatch
    for forbidden in (
        "instrumentName",
        "accountNumber",
        "personName",
        "rawScreenshot",
        "rawOcrText",
    ):
        assert forbidden not in serialized_dispatch
    allowed_sources = dispatch.payload_safe["constraints"]["allowedSources"]
    assert "nalog.gov.ru" in allowed_sources
    assert "www.nalog.gov.ru" in allowed_sources

    for expected_attempt in (2, 3):
        job = service.apply_callback(
            job_id=job.id,
            nonce=f"retry-nonce-{expected_attempt:02d}-unique",
            request=RecommendationCallbackRequest(
                status="failed",
                retryable=True,
                errorCode="TEMPORARY_SOURCE_ERROR",
            ),
        )
        assert job.status == "queued"
        assert job.attempt_count == expected_attempt

    job = service.apply_callback(
        job_id=job.id,
        nonce="collecting-nonce-unique-01",
        request=RecommendationCallbackRequest(status="collecting"),
    )
    assert job.status == "collecting"
    job = service.apply_callback(
        job_id=job.id,
        nonce="analyzing-nonce-unique-01",
        request=RecommendationCallbackRequest(
            status="analyzing",
            marketDataAsOf=NOW - timedelta(hours=1),
        ),
    )
    assert job.status == "analyzing"
    job = service.apply_callback(
        job_id=job.id,
        nonce="ready-nonce-unique-0001",
        request=RecommendationCallbackRequest(
            status="ready",
            marketDataAsOf=NOW - timedelta(hours=1),
            summary="Сначала направить свободные деньги в недовзвешенные доли.",
            assumptions={"cashFirst": True},
            aggregates=[
                {
                    "riskBucket": "conservative",
                    "currentPercent": "50",
                    "proposedPercent": "40",
                },
                {
                    "riskBucket": "moderate",
                    "currentPercent": "25",
                    "proposedPercent": "30",
                },
                {
                    "riskBucket": "aggressive",
                    "currentPercent": "25",
                    "proposedPercent": "30",
                },
            ],
            actions=[
                {
                    "instrumentName": "Фонд денежного рынка",
                    "ticker": "LQDT",
                    "riskBucket": "moderate",
                    "action": "add",
                    "currentPercent": "25",
                    "targetPercent": "30",
                    "amount": "10000",
                    "priority": 1,
                    "rationale": "Снижает отклонение консервативной доли.",
                    "risks": "Стоимость пая может меняться.",
                },
                {
                    "instrumentName": "Сбербанк",
                    "ticker": "SBER",
                    "riskBucket": "aggressive",
                    "action": "increase",
                    "currentPercent": "25",
                    "targetPercent": "30",
                    "amount": "10000",
                    "priority": 2,
                    "rationale": "Закрывает рассчитанный дефицит доли.",
                    "risks": "Цена акции может меняться.",
                },
            ],
            sources=[
                {
                    "title": "Индивидуальный инвестиционный счет",
                    "url": "https://www.nalog.gov.ru/rn77/taxation/investment_deduction/",
                    "publisher": "ФНС России",
                    "fetchedAt": NOW,
                }
            ],
        ),
    )
    assert job.status == "ready"
    report = service.report(owner, job.id)
    assert report.valid_until == NOW + timedelta(days=7)
    assert report.valid_until.tzinfo is UTC
    assert len(service.repo.report_actions(report.id)) == 2
    sources = service.repo.report_sources(report.id)
    assert len(sources) == 1
    assert sources[0].trust_tier == "official"

    with pytest.raises(ReplayDetected):
        service.apply_callback(
            job_id=job.id,
            nonce="ready-nonce-unique-0001",
            request=RecommendationCallbackRequest(status="collecting"),
        )
    with pytest.raises(InvalidTransition):
        service.apply_callback(
            job_id=job.id,
            nonce="post-ready-nonce-unique",
            request=RecommendationCallbackRequest(status="collecting"),
        )


def test_ready_callback_rejects_arbitrary_sales_and_invalid_aggregates(
    session: Session,
) -> None:
    owner = actor(session)
    service = InvestmentService(InvestmentRepository(session), now=NOW)
    snapshot_id = confirmed_snapshot(service, owner)

    def queued_job(key: str):
        job = service.create_job(
            owner,
            RecommendationJobCreateRequest(
                idempotencyKey=key,
                snapshotIds=[snapshot_id],
            ),
        )
        return service.apply_callback(
            job_id=job.id,
            nonce=f"collecting-{key}",
            request=RecommendationCallbackRequest(status="collecting"),
        )

    valid_payload = {
        "status": "ready",
        "marketDataAsOf": NOW - timedelta(hours=1),
        "summary": "Результат детерминированной проверки.",
        "assumptions": {"cashFirst": True},
        "aggregates": [
            {
                "riskBucket": "conservative",
                "currentPercent": "50",
                "proposedPercent": "40",
            },
            {
                "riskBucket": "moderate",
                "currentPercent": "25",
                "proposedPercent": "30",
            },
            {
                "riskBucket": "aggressive",
                "currentPercent": "25",
                "proposedPercent": "30",
            },
        ],
        "actions": [
            {
                "instrumentName": "Фонд денежного рынка",
                "ticker": "LQDT",
                "riskBucket": "moderate",
                "action": "add",
                "currentPercent": "25",
                "targetPercent": "30",
                "amount": "10000",
                "priority": 1,
                "rationale": "Закрывает рассчитанный дефицит доли.",
                "risks": "Стоимость пая может меняться.",
            },
            {
                "instrumentName": "Сбербанк",
                "ticker": "SBER",
                "riskBucket": "aggressive",
                "action": "increase",
                "currentPercent": "25",
                "targetPercent": "30",
                "amount": "10000",
                "priority": 2,
                "rationale": "Закрывает рассчитанный дефицит доли.",
                "risks": "Цена акции может меняться.",
            },
        ],
        "sources": [
            {
                "title": "MOEX ISS",
                "url": "https://iss.moex.com/iss/securities.json",
                "publisher": "Московская биржа",
                "fetchedAt": NOW,
            }
        ],
    }

    sale_payload = {**valid_payload}
    sale_payload["actions"] = [
        {
            "instrumentName": "ОФЗ 26238",
            "ticker": "SU26238RMFS4",
            "riskBucket": "conservative",
            "action": "reduce",
            "currentPercent": "50",
            "targetPercent": "40",
            "amount": "1",
            "priority": 1,
            "rationale": "Произвольная продажа.",
            "risks": "Не разрешена расчётным ядром.",
        }
    ]
    sale_job = queued_job("reject-sale-job")
    with pytest.raises(InvalidRecommendationPayload):
        service.apply_callback(
            job_id=sale_job.id,
            nonce="reject-sale-ready",
            request=RecommendationCallbackRequest.model_validate(sale_payload),
        )

    aggregate_payload = {**valid_payload}
    aggregate_payload["aggregates"] = [*valid_payload["aggregates"]]
    aggregate_payload["aggregates"][2] = {
        "riskBucket": "aggressive",
        "currentPercent": "25",
        "proposedPercent": "35.01",
    }
    aggregate_job = queued_job("reject-aggregate-job")
    with pytest.raises(InvalidRecommendationPayload):
        service.apply_callback(
            job_id=aggregate_job.id,
            nonce="reject-aggregate-ready",
            request=RecommendationCallbackRequest.model_validate(aggregate_payload),
        )

    for suffix, actions in (
        ("empty", []),
        ("partial", valid_payload["actions"][:1]),
    ):
        incomplete_job = queued_job(f"reject-{suffix}-actions")
        incomplete_payload = {**valid_payload, "actions": actions}
        with pytest.raises(InvalidRecommendationPayload):
            service.apply_callback(
                job_id=incomplete_job.id,
                nonce=f"reject-{suffix}-ready",
                request=RecommendationCallbackRequest.model_validate(incomplete_payload),
            )


def test_custom_policy_tolerance_is_enforced(session: Session) -> None:
    owner = actor(session)
    service = InvestmentService(InvestmentRepository(session), now=NOW)
    service.put_policy(
        owner,
        InvestmentPolicyPutRequest(
            conservativePercent="40",
            moderatePercent="30",
            aggressivePercent="30",
            tolerancePercent="1",
        ),
    )
    imported = service.create_import(
        owner,
        PortfolioImportCreateRequest(
            idempotencyKey="custom-tolerance-import",
            brokerage="finam",
            screenshotCount=1,
            observedAt=NOW,
        ),
    )
    snapshot = service.confirm_import(
        owner,
        imported.id,
        PortfolioImportConfirmRequest(
            positions=[
                position(bucket="conservative", value="0"),
                position(bucket="moderate", value="31"),
                position(bucket="aggressive", value="69"),
            ]
        ),
    )
    job = service.create_job(
        owner,
        RecommendationJobCreateRequest(
            idempotencyKey="custom-tolerance-job",
            snapshotIds=[snapshot.id],
        ),
    )
    job = service.apply_callback(
        job_id=job.id,
        nonce="custom-tolerance-collecting",
        request=RecommendationCallbackRequest(status="collecting"),
    )
    with pytest.raises(InvalidRecommendationPayload):
        service.apply_callback(
            job_id=job.id,
            nonce="custom-tolerance-ready",
            request=RecommendationCallbackRequest(
                status="ready",
                marketDataAsOf=NOW,
                summary="Недопустимое отклонение при tolerance=1.",
                aggregates=[
                    {
                        "riskBucket": "conservative",
                        "currentPercent": "0",
                        "proposedPercent": "38",
                    },
                    {
                        "riskBucket": "moderate",
                        "currentPercent": "31",
                        "proposedPercent": "31",
                    },
                    {
                        "riskBucket": "aggressive",
                        "currentPercent": "69",
                        "proposedPercent": "31",
                    },
                ],
                actions=[
                    {
                        "instrumentName": "ОФЗ 26238",
                        "ticker": "SU26238RMFS4",
                        "riskBucket": "conservative",
                        "action": "increase",
                        "currentPercent": "0",
                        "targetPercent": "38",
                        "amount": "38",
                        "priority": 1,
                        "rationale": "Расчётное пополнение.",
                        "risks": "Рыночный риск.",
                    },
                    {
                        "instrumentName": "Сбербанк",
                        "ticker": "SBER",
                        "riskBucket": "aggressive",
                        "action": "reduce",
                        "currentPercent": "69",
                        "targetPercent": "31",
                        "amount": "38",
                        "priority": 2,
                        "rationale": "Расчётное сокращение.",
                        "risks": "Рыночный риск.",
                    },
                ],
                sources=[
                    {
                        "title": "MOEX ISS",
                        "url": "https://iss.moex.com/iss/securities.json",
                        "publisher": "Московская биржа",
                        "fetchedAt": NOW,
                    }
                ],
            ),
        )


def test_concurrent_retry_cas_emits_one_outbox_event_per_attempt(session: Session) -> None:
    owner = actor(session)
    repository = InvestmentRepository(session)
    service = InvestmentService(repository, now=NOW)
    job = service.create_job(
        owner,
        RecommendationJobCreateRequest(
            idempotencyKey="concurrent-retry-job",
            snapshotIds=[confirmed_snapshot(service, owner)],
        ),
    )
    stale_version = job.version
    values = {
        "attempt_count": 2,
        "status": "queued",
        "last_error_code": "TEMPORARY_SOURCE_ERROR",
        "updated_at": NOW,
        "market_data_as_of": None,
    }
    winner = repository.conditional_update_job(
        job_id=job.id,
        expected_version=stale_version,
        values=values,
    )
    assert winner is not None
    repository.enqueue_job(winner, {"schemaVersion": 1, "jobId": str(job.id), "retry": True})
    loser = repository.conditional_update_job(
        job_id=job.id,
        expected_version=stale_version,
        values=values,
    )
    assert loser is None
    session.flush()
    deduplication_key = f"investment-recommendation:{job.id}:attempt:2"
    assert (
        len(
            list(
                session.scalars(
                    select(OutboxEvent).where(OutboxEvent.deduplication_key == deduplication_key)
                )
            )
        )
        == 1
    )


def test_hmac_signature_timestamp_and_replay_inputs() -> None:
    body = b'{"status":"collecting"}'
    nonce = "0123456789abcdef"
    timestamp = 1_789_812_000
    path = (
        "/api/v1/investments/internal/recommendation-jobs/"
        "11111111-1111-1111-1111-111111111111/callback"
    )
    signature = sign_callback(
        secret="test-secret",
        method="POST",
        canonical_path=path,
        timestamp=timestamp,
        nonce=nonce,
        body=body,
    )
    verified = verify_callback(
        secret="test-secret",
        method="POST",
        canonical_path=path,
        timestamp_text=str(timestamp),
        nonce=nonce,
        signature=signature,
        body=body,
        now_epoch=timestamp,
    )
    assert verified.nonce == nonce
    with pytest.raises(HmacVerificationError):
        verify_callback(
            secret="test-secret",
            method="POST",
            canonical_path=path,
            timestamp_text=str(timestamp),
            nonce=nonce,
            signature=signature,
            body=b"tampered",
            now_epoch=timestamp,
        )
    with pytest.raises(HmacVerificationError):
        verify_callback(
            secret="test-secret",
            method="POST",
            canonical_path=path,
            timestamp_text=str(timestamp - 301),
            nonce=nonce,
            signature=signature,
            body=body,
            now_epoch=timestamp,
        )

    other_path = (
        "/api/v1/investments/internal/recommendation-jobs/"
        "22222222-2222-2222-2222-222222222222/callback"
    )
    with pytest.raises(HmacVerificationError):
        verify_callback(
            secret="test-secret",
            method="POST",
            canonical_path=other_path,
            timestamp_text=str(timestamp),
            nonce=nonce,
            signature=signature,
            body=body,
            now_epoch=timestamp,
        )


def test_api_v2_callback_verifies_hmac_before_parsing_body(session: Session) -> None:
    owner = actor(session)
    service = InvestmentService(InvestmentRepository(session), now=NOW)
    job = service.create_job(
        owner,
        RecommendationJobCreateRequest(
            idempotencyKey="api-v2-callback-job",
            snapshotIds=[confirmed_snapshot(service, owner)],
        ),
    )
    settings = Settings(
        api_v1_prefix="/api/v2",
        investment_callback_hmac_secret="test-secret",
    )
    application = create_app(settings)
    application.dependency_overrides[investment_service_for_request] = lambda: service
    path = f"/api/v2/investments/internal/recommendation-jobs/{job.id}/callback"
    timestamp = int(time.time())

    malformed_body = b"{not-json"
    unauthenticated_headers = {
        "X-Finance-Timestamp": str(timestamp),
        "X-Finance-Nonce": "malformed-unauth-0001",
        "X-Finance-Signature": "0" * 64,
        "Content-Type": "application/json",
    }
    with TestClient(application) as test_client:
        rejected = test_client.post(
            path,
            content=malformed_body,
            headers=unauthenticated_headers,
        )
        assert rejected.status_code == 401
        assert rejected.json()["error"]["code"] == "INVALID_SERVICE_CALLBACK"

        body = b'{"status":"collecting"}'
        nonce = "api-v2-valid-000001"
        signature = sign_callback(
            secret="test-secret",
            method="POST",
            canonical_path=path,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
        )
        accepted = test_client.post(
            path,
            content=body,
            headers={
                "X-Finance-Timestamp": str(timestamp),
                "X-Finance-Nonce": nonce,
                "X-Finance-Signature": signature,
                "Content-Type": "application/json",
            },
        )
        assert accepted.status_code == 200
        assert accepted.json()["data"]["status"] == "collecting"


def test_static_and_runtime_openapi_callback_contract_match(client) -> None:
    static_path = Path(__file__).resolve().parents[4] / "api" / "openapi" / "openapi.yaml"
    static_schema = yaml.safe_load(static_path.read_text(encoding="utf-8"))
    runtime_schema = client.get("/openapi.json").json()

    static_operation = static_schema["paths"][
        "/investments/internal/recommendation-jobs/{jobId}/callback"
    ]["post"]
    runtime_operation = runtime_schema["paths"][
        "/api/v1/investments/internal/recommendation-jobs/{jobId}/callback"
    ]["post"]
    assert static_operation["operationId"] == runtime_operation["operationId"]
    assert static_operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RecommendationCallbackRequest"
    }
    assert runtime_operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RecommendationCallbackRequest"
    }
    assert static_operation["requestBody"]["required"] is True
    assert runtime_operation["requestBody"]["required"] is True

    def header_contract(operation: dict) -> dict[str, tuple[bool, dict]]:
        return {
            item["name"]: (item["required"], item["schema"])
            for item in operation["parameters"]
            if item["in"] == "header" and item["name"].startswith("X-Finance-")
        }

    assert header_contract(static_operation) == header_contract(runtime_operation)

    static_components = static_schema["components"]["schemas"]
    runtime_components = runtime_schema["components"]["schemas"]

    def allows_null(schema: dict) -> bool:
        schema_type = schema.get("type")
        if schema_type == "null" or (isinstance(schema_type, list) and "null" in schema_type):
            return True
        return any(
            allows_null(candidate)
            for keyword in ("anyOf", "oneOf")
            for candidate in schema.get(keyword, [])
        )

    for schema_name in (
        "PortfolioPositionInput",
        "RecommendationActionInput",
        "RecommendationAggregateInput",
        "RecommendationSourceInput",
        "RecommendationCallbackRequest",
    ):
        assert set(static_components[schema_name].get("required", [])) == set(
            runtime_components[schema_name].get("required", [])
        )
        assert set(static_components[schema_name]["properties"]) == set(
            runtime_components[schema_name]["properties"]
        )
        for property_name in static_components[schema_name]["properties"]:
            assert allows_null(
                static_components[schema_name]["properties"][property_name]
            ) == allows_null(runtime_components[schema_name]["properties"][property_name])
    assert (
        static_components["PortfolioPositionInput"]["anyOf"]
        == runtime_components["PortfolioPositionInput"]["anyOf"]
    )
    assert (
        static_components["RecommendationActionInput"]["anyOf"]
        == runtime_components["RecommendationActionInput"]["anyOf"]
    )
