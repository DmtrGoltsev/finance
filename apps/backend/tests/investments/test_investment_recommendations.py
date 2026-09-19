from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import yaml
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.authz import Actor
from app.db.base import Base
from app.db.models import OutboxEvent, User
from app.investments.allocation import AllocationPolicy, RiskBucket, cash_first_rebalance
from app.investments.hmac_auth import HmacVerificationError, sign_callback, verify_callback
from app.investments.repository import InvestmentRepository
from app.investments.schemas import (
    PortfolioImportConfirmRequest,
    PortfolioImportCreateRequest,
    PortfolioPositionInput,
    RecommendationCallbackRequest,
    RecommendationJobCreateRequest,
    RecommendationSourceInput,
)
from app.investments.service import (
    IdempotencyConflict,
    InvalidObservedAt,
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

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as value:
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
    assert scripts.get_heads() == ["20260919_0021"]
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
                    "currentPercent": "5",
                    "targetPercent": "10",
                    "amount": "10000",
                    "priority": 1,
                    "rationale": "Снижает отклонение консервативной доли.",
                    "risks": "Стоимость пая может меняться.",
                }
            ],
            sources=[
                {
                    "title": "Данные инструмента",
                    "url": "https://www.moex.com/ru/issue.aspx?board=TQTF&code=LQDT",
                    "publisher": "Московская биржа",
                    "fetchedAt": NOW,
                }
            ],
        ),
    )
    assert job.status == "ready"
    report = service.report(owner, job.id)
    assert report.valid_until == NOW + timedelta(days=7)
    assert report.valid_until.tzinfo is UTC
    assert len(service.repo.report_actions(report.id)) == 1
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
        "actions": [],
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

    static_components = static_schema["components"]["schemas"]
    runtime_components = runtime_schema["components"]["schemas"]
    for schema_name in (
        "PortfolioPositionInput",
        "RecommendationActionInput",
        "RecommendationSourceInput",
        "RecommendationCallbackRequest",
    ):
        assert set(static_components[schema_name].get("required", [])) == set(
            runtime_components[schema_name].get("required", [])
        )
        assert set(static_components[schema_name]["properties"]) == set(
            runtime_components[schema_name]["properties"]
        )
    assert (
        static_components["PortfolioPositionInput"]["anyOf"]
        == runtime_components["PortfolioPositionInput"]["anyOf"]
    )
    assert (
        static_components["RecommendationActionInput"]["anyOf"]
        == runtime_components["RecommendationActionInput"]["anyOf"]
    )
