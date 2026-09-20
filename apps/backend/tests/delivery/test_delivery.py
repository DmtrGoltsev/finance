import importlib.util
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.orm import sessionmaker

from app.api.auth_context import require_authenticated_actor
from app.auth.db_stores import SqlAlchemySessionTokenStore
from app.authz import Actor
from app.config import Settings
from app.db.base import Base
from app.db.models import OutboxEvent, User
from app.db.models import Session as AuthSession
from app.delivery.models import PushDelivery, PushDevice
from app.delivery.router import PushDeviceRequest, register_device, revoke_device
from app.delivery.transports import DeliveryError, FcmTransport, InvalidToken, N8nTransport
from app.delivery.worker import READY, REQUESTED, Dispatcher, claim, refresh_due_catalog
from app.investments.hmac_auth import sign_callback
from app.investments.models import MoexInstrumentModel, RecommendationJobModel
from app.investments.repository import InvestmentRepository
from app.investments.router import investment_service_for_request
from app.investments.schemas import RecommendationJobCreateRequest
from app.investments.service import DeliveryRetryRequired, InvestmentService
from app.main import create_app


@pytest.fixture
def factory(tmp_path):
    url = os.environ.get("FINANCE_DELIVERY_TEST_POSTGRES_URL")
    if url:
        schema = "delivery_test_" + uuid4().hex
        admin = create_engine(url)
        with admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine(
            f"sqlite:///{tmp_path / 'test.db'}",
            connect_args={"check_same_thread": False, "timeout": 15},
        )
    Base.metadata.create_all(engine)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()
    if url:
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def identity(factory):
    now, owner, sid = datetime.now(UTC), uuid4(), uuid4()
    with factory.begin() as s:
        s.add(
            User(
                id=owner,
                email_normalized=f"{owner}@example.test",
                password_hash="test",
                auth_status="active",
                record_status="active",
                session_version=1,
                created_at=now,
                updated_at=now,
                version=1,
            )
        )
        s.flush()
        s.add(
            AuthSession(
                id=sid,
                user_id=owner,
                session_token_hash=uuid4().hex,
                transport="android_bearer",
                session_version=1,
                status="active",
                expires_at=now + timedelta(days=1),
                created_at=now,
                updated_at=now,
                version=1,
            )
        )
    return Actor(user_id=str(owner), session_id=str(sid))


def event(factory, owner=None, kind=REQUESTED):
    now = datetime.now(UTC)
    with factory.begin() as s:
        item = OutboxEvent(
            id=uuid4(),
            event_type=kind,
            aggregate_type="recommendation_job",
            aggregate_id=uuid4(),
            owner_user_id=owner,
            status="pending",
            payload_safe={"jobId": str(uuid4())} if kind == READY else {},
            created_at=now,
            available_at=now,
            attempt_count=0,
            delivery_attempts=0,
            deduplication_key=uuid4().hex,
        )
        s.add(item)
    return item


def device(factory, actor, token=None):
    did = uuid4()
    with factory.begin() as s:
        register_device(did, PushDeviceRequest(token=token or uuid4().hex), actor, s)
    return did


def dispatcher(factory, **settings):
    return Dispatcher(factory, Settings(**settings), Mock(), Mock())


def test_atomic_claim_race_and_lease_recovery(factory):
    item = event(factory)
    barrier = threading.Barrier(2)

    def race():
        barrier.wait()
        return claim(factory)

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: race(), range(2)))
    assert sum(r is not None for r in results) == 1
    original = next(r for r in results if r is not None)
    assert claim(factory) is None
    with factory.begin() as s:
        s.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == item.id)
            .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
        )
    recovered = claim(factory)
    assert recovered.id == item.id and recovered.lease_token != original.lease_token
    assert recovered.delivery_attempts == 2
    worker = dispatcher(factory)
    worker.finish(original, True)
    with factory() as s:
        assert s.get(OutboxEvent, item.id).status == "processing"
    worker.finish(recovered, True)
    assert claim(factory) is None


def test_retry_backoff_and_no_duplicate_after_ack(factory):
    item = event(factory)
    worker = dispatcher(factory)
    worker.n8n.send.side_effect = OSError("must not be logged")
    assert worker.tick()
    with factory.begin() as s:
        saved = s.get(OutboxEvent, item.id)
        assert saved.status == "failed"
        assert saved.delivery_attempts == 1
        assert saved.available_at > saved.created_at
        saved.available_at = datetime.now(UTC) - timedelta(seconds=1)
    worker.n8n.send.side_effect = None
    assert worker.tick()
    assert not worker.tick()
    assert worker.n8n.send.call_count == 2
    with factory() as s:
        assert s.get(OutboxEvent, item.id).status == "processed"


def test_exhausted_transport_is_dead_not_delivered(factory):
    item = event(factory)
    worker = dispatcher(factory, delivery_max_attempts=1)
    worker.n8n.send.side_effect = ValueError()
    worker.tick()
    with factory() as s:
        assert s.get(OutboxEvent, item.id).status == "dead"


def linked_job(factory, actor, status="queued"):
    item = event(factory, UUID(actor.user_id))
    with factory.begin() as s:
        job = RecommendationJobModel(
            id=item.aggregate_id,
            owner_user_id=UUID(actor.user_id),
            idempotency_key=uuid4().hex,
            request_hash="original-hash",
            status=status,
            attempt_count=1,
            version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        s.add(job)
    return item, job


def exhaust(factory):
    worker = dispatcher(factory, delivery_max_attempts=1)
    worker.n8n.send.side_effect = OSError("offline")
    assert worker.tick()
    return worker


def test_exhaustion_and_authenticated_retry_keep_identity(factory):
    actor, outsider = identity(factory), identity(factory)
    item, job = linked_job(factory, actor)
    exhaust(factory)
    with factory() as s:
        saved = s.get(RecommendationJobModel, job.id)
        assert (saved.status, saved.last_error_code) == ("failed", "delivery_failed")
        assert saved.completed_at is not None
        assert saved.version == 2
        with pytest.raises(DeliveryRetryRequired):
            InvestmentService(InvestmentRepository(s)).create_job(
                actor,
                RecommendationJobCreateRequest(idempotencyKey=uuid4().hex, snapshotIds=[uuid4()]),
            )

    app = create_app(Settings())

    def service():
        with factory.begin() as s:
            yield InvestmentService(InvestmentRepository(s))

    app.dependency_overrides[investment_service_for_request] = service
    path = f"/api/v1/investments/recommendation-jobs/{job.id}/retry-delivery"
    with TestClient(app) as client:
        assert client.post(path).status_code == 401
        app.dependency_overrides[require_authenticated_actor] = lambda: outsider
        assert client.post(path).status_code == 404
        app.dependency_overrides[require_authenticated_actor] = lambda: actor
        response = client.post(path)
        assert response.status_code == 202, response.text
        assert response.json()["data"]["status"] == "queued"
        assert response.json()["data"]["lastErrorCode"] is None
        leased = claim(factory)
        assert client.post(path).status_code == 202
        with factory() as s:
            saved_event, saved_job = (
                s.get(OutboxEvent, item.id),
                s.get(RecommendationJobModel, job.id),
            )
            assert saved_event.status == "processing"
            assert saved_event.lease_token == leased.lease_token
            assert saved_event.delivery_attempts == 1
            assert saved_event.deduplication_key == item.deduplication_key
            assert saved_event.payload_safe == item.payload_safe
            assert saved_job.idempotency_key == job.idempotency_key
            assert saved_job.request_hash == job.request_hash
            assert saved_job.attempt_count == 1 and saved_job.version == 3
            assert len(list(s.scalars(select(RecommendationJobModel)))) == 1
            assert len(list(s.scalars(select(OutboxEvent)))) == 1


@pytest.mark.parametrize("status", ["collecting", "analyzing", "ready", "failed"])
def test_transport_exhaustion_does_not_overwrite_progress(factory, status):
    actor = identity(factory)
    item, job = linked_job(factory, actor, status)
    exhaust(factory)
    with factory() as s:
        assert s.get(OutboxEvent, item.id).status == "dead"
        saved = s.get(RecommendationJobModel, job.id)
        assert saved.status == status and saved.last_error_code is None and saved.version == 1


def test_concurrent_delivery_retry_only_resets_once(factory):
    actor = identity(factory)
    item, job = linked_job(factory, actor)
    exhaust(factory)
    barrier = threading.Barrier(2)

    def retry(_):
        barrier.wait()
        with factory.begin() as s:
            return InvestmentService(InvestmentRepository(s)).retry_delivery(actor, job.id).id

    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(retry, range(2))) == [job.id, job.id]
    with factory() as s:
        assert s.get(RecommendationJobModel, job.id).version == 3
        assert s.get(OutboxEvent, item.id).status == "pending"
    assert claim(factory).id == item.id
    assert claim(factory) is None


def test_lost_acceptance_retries_same_gateway_generation(factory):
    actor = identity(factory)
    item, job = linked_job(factory, actor)
    accepted, bodies = set(), []

    def respond(request):
        data = json.loads(request.content)
        bodies.append(request.content)
        accepted.add((data["eventId"], data["jobId"], data["attempt"]))
        if len(bodies) == 1:
            raise httpx.ReadTimeout("lost ACK")
        return httpx.Response(202, json={"accepted": True, "eventId": data["eventId"]})

    worker = dispatcher(factory, delivery_max_attempts=1)
    worker.n8n = N8nTransport(
        Settings(delivery_ingress_secret="test-" * 8),
        httpx.Client(transport=httpx.MockTransport(respond)),
    )
    assert worker.tick()
    with factory.begin() as s:
        InvestmentService(InvestmentRepository(s)).retry_delivery(actor, job.id)
    assert worker.tick()
    assert not worker.tick()
    assert len(accepted) == 1 and bodies[0] == bodies[1]
    with factory() as s:
        assert s.get(OutboxEvent, item.id).status == "processed"


def test_0024_downgrade_upgrade_reclaims_processing_identity(factory):
    item = event(factory)
    claimed = claim(factory)
    root = Path(__file__).resolve().parents[4]
    path = root / "db/migrations/versions/20260920_0024_delivery.py"
    spec = importlib.util.spec_from_file_location("delivery_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with factory.kw["bind"].begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            row = connection.execute(
                text("SELECT status, deduplication_key FROM outbox_events")
            ).one()
            assert row.status == "pending" and row.deduplication_key == item.deduplication_key
            migration.upgrade()
    recovered = claim(factory)
    assert recovered.id == claimed.id
    assert recovered.aggregate_id == claimed.aggregate_id
    assert recovered.deduplication_key == claimed.deduplication_key
    assert recovered.payload_safe == claimed.payload_safe
    assert recovered.attempt_count == claimed.attempt_count
    assert recovered.lease_token != claimed.lease_token
    assert claim(factory) is None


def test_worker_docker_context_is_allowlisted():
    root = Path(__file__).resolve().parents[4]
    dockerfile = (root / "ops/finance-delivery/Dockerfile").read_text()
    copies = [line for line in dockerfile.splitlines() if line.startswith("COPY ")]
    assert copies == [
        "COPY apps/backend/pyproject.toml apps/backend/README.md ./apps/backend/",
        "COPY apps/backend/src ./apps/backend/src",
    ]
    rules = [
        line
        for line in (root / "ops/finance-delivery/Dockerfile.dockerignore").read_text().splitlines()
        if line and not line.startswith("#")
    ]
    assert rules[0] == "**"
    assert [line for line in rules if line.startswith("!")] == [
        "!apps/",
        "!apps/backend/",
        "!apps/backend/pyproject.toml",
        "!apps/backend/README.md",
        "!apps/backend/src/",
        "!apps/backend/src/**/",
        "!apps/backend/src/**/*.py",
    ]
    for denied in [
        "**/.env",
        "**/.env.*",
        "**/*credential*",
        "**/*service-account*",
        "**/*service_account*",
        "**/.venv/**",
        "**/venv/**",
        "**/.git/**",
        "**/__pycache__/**",
        "**/.pytest_cache/**",
        "**/.ruff_cache/**",
        "**/google-services.json",
        "**/*.pem",
        "**/*.key",
    ]:
        assert denied in rules and rules.index(denied) > rules.index("!apps/backend/src/**/*.py")


@pytest.mark.parametrize(
    "status,ack,accepted",
    [
        (202, "valid", True),
        (200, "valid", False),
        (202, "wrong", False),
        (202, "false", False),
        (503, "valid", False),
        (302, "valid", False),
    ],
)
def test_n8n_signed_acceptance(factory, status, ack, accepted):
    item = event(factory)
    secret = "test-key-" * 5
    bodies = []

    def respond(request):
        bodies.append(request.content)
        expected = sign_callback(
            secret=secret,
            method="POST",
            canonical_path=request.url.path,
            timestamp=int(request.headers["x-finance-timestamp"]),
            nonce=request.headers["x-finance-nonce"],
            body=request.content,
        )
        assert expected == request.headers["x-finance-signature"]
        payload = json.loads(request.content)
        assert payload["attempt"] == 1 and payload["eventId"] == str(item.id)
        return httpx.Response(
            status,
            json={
                "accepted": ack != "false",
                "eventId": "wrong" if ack == "wrong" else str(item.id),
            },
        )

    transport = N8nTransport(
        Settings(delivery_ingress_secret=secret),
        httpx.Client(transport=httpx.MockTransport(respond)),
    )
    if accepted:
        transport.send(item)
        transport.send(item)
        assert bodies[0] == bodies[1]  # Stable idempotency payload, fresh nonce per retry.
    else:
        with pytest.raises(DeliveryError):
            transport.send(item)


def test_device_ownership_update_revoke_and_logout(factory):
    actor, outsider = identity(factory), identity(factory)
    did = device(factory, actor)
    with factory.begin() as s:
        with pytest.raises(HTTPException) as exc:
            register_device(did, PushDeviceRequest(token=uuid4().hex), outsider, s)
        assert exc.value.status_code == 404
        revoke_device(did, outsider, s)
        assert s.get(PushDevice, did).token is not None
        register_device(did, PushDeviceRequest(token="changed-" + uuid4().hex), actor, s)
    SqlAlchemySessionTokenStore(factory).revoke_session(
        session_id=actor.session_id, revoked_at=datetime.now(UTC)
    )
    with factory.begin() as s:
        assert s.get(PushDevice, did).token is None
        with pytest.raises(HTTPException):
            register_device(did, PushDeviceRequest(token=uuid4().hex), actor, s)


def test_invalid_token_cleanup_and_no_repeat_push(factory):
    actor = identity(factory)
    first, second = device(factory, actor), device(factory, actor)
    item = event(factory, UUID(actor.user_id), READY)
    worker = dispatcher(factory)
    worker.fcm.send.side_effect = [InvalidToken("FCM_UNREGISTERED"), None]
    assert worker.tick()
    assert not worker.tick()
    with factory() as s:
        assert s.get(OutboxEvent, item.id).status == "processed"
        assert sorted(s.scalars(select(PushDelivery.status))) == ["invalid", "sent"]
        assert sum(s.get(PushDevice, did).token is None for did in (first, second)) == 1


def test_partial_push_retry_does_not_resend_successful_devices(factory):
    actor = identity(factory)
    device(factory, actor)
    device(factory, actor)
    item = event(factory, UUID(actor.user_id), READY)
    worker = dispatcher(factory)
    worker.fcm.send.side_effect = [None, DeliveryError("RETRY"), None]
    worker.tick()
    with factory.begin() as s:
        s.get(OutboxEvent, item.id).available_at = datetime.now(UTC) - timedelta(seconds=1)
    worker.tick()
    assert worker.fcm.send.call_count == 3
    with factory() as s:
        assert list(s.scalars(select(PushDelivery.status))) == ["sent", "sent"]


def test_revoked_and_stale_devices_never_sent(factory):
    actor = identity(factory)
    did = device(factory, actor)
    with factory.begin() as s:
        s.get(PushDevice, did).updated_at = datetime.now(UTC) - timedelta(days=271)
    event(factory, UUID(actor.user_id), READY)
    worker = dispatcher(factory)
    worker.tick()
    worker.fcm.send.assert_not_called()


@pytest.mark.parametrize("error,invalid", [("UNREGISTERED", True), ("INVALID_ARGUMENT", False)])
def test_fcm_ack_and_error_classification(factory, error, invalid):
    item = event(factory, kind=READY)

    def respond(request):
        body = json.loads(request.content)["message"]
        assert "notification" not in body  # Data-only for foreground/background deduplication.
        assert body["data"]["body"] == "Анализ портфеля готов"
        assert set(body["data"]) == {"eventId", "jobId", "sessionId", "body", "deepLink", "type"}
        assert "Bearer test" == request.headers["authorization"]
        return httpx.Response(
            400,
            json={
                "error": {
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
                            "errorCode": error,
                        }
                    ]
                }
            },
        )

    transport = FcmTransport(
        Settings(fcm_enabled=True, fcm_project_id="finance-test"),
        httpx.Client(transport=httpx.MockTransport(respond)),
        SimpleNamespace(valid=True, token="test"),
    )
    with pytest.raises(DeliveryError) as exc:
        transport.send("token", item, uuid4())
    assert isinstance(exc.value, InvalidToken) is invalid


def test_catalog_singleton_and_twelve_hour_refresh(factory):
    count = []

    def refresh(session, secids):
        count.extend(secids)
        row = session.get(MoexInstrumentModel, secids[0])
        if row is None:
            session.add(
                MoexInstrumentModel(
                    secid=secids[0], isin="RU0009029540", fetched_at=datetime.now(UTC)
                )
            )
        else:
            row.fetched_at = datetime.now(UTC)

    barrier = threading.Barrier(2)

    def run():
        barrier.wait()
        return refresh_due_catalog(factory, seeds=["SBER"], refresh=refresh)

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda _: run(), range(2)))
    assert count == ["SBER"]
    with factory.begin() as s:
        s.get(MoexInstrumentModel, "SBER").fetched_at = datetime.now(UTC) - timedelta(hours=13)
    assert refresh_due_catalog(factory, refresh=refresh) == 1


def test_fcm_only_confirmed_message_name_is_success(factory):
    item = event(factory, kind=READY)
    answers = iter([{"name": "projects/finance-test/messages/accepted"}, {"ok": True}])
    transport = FcmTransport(
        Settings(fcm_enabled=True, fcm_project_id="finance-test"),
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=next(answers)))
        ),
        SimpleNamespace(valid=True, token="test"),
    )
    transport.send("token", item, uuid4())
    with pytest.raises(DeliveryError, match="FCM_INVALID_ACK"):
        transport.send("token", item, uuid4())


def test_shutdown_does_not_send_remaining_devices(factory):
    actor = identity(factory)
    device(factory, actor)
    event(factory, UUID(actor.user_id), READY)
    worker = dispatcher(factory)
    worker.stop.set()
    worker.tick()
    worker.fcm.send.assert_not_called()


def test_missing_config_and_arbitrary_destination_fail_closed():
    with pytest.raises(DeliveryError, match="FCM_CREDENTIALS_REQUIRED"):
        FcmTransport(Settings(fcm_enabled=True, fcm_project_id="finance-test"))
    with pytest.raises(DeliveryError, match="INVALID_INTERNAL_URL"):
        N8nTransport(
            Settings(
                delivery_ingress_secret="a" * 32,
                delivery_n8n_url="https://untrusted.example/accept",
            )
        )


def test_bad_catalog_entry_does_not_starve_other_instruments(factory):
    from app.investments.moex_catalog import CatalogRefreshError

    seen = []

    def refresh(session, secids):
        seen.append(secids[0])
        if secids[0] == "BAD":
            raise CatalogRefreshError("not listed")

    assert refresh_due_catalog(factory, seeds=["BAD", "SBER"], refresh=refresh) == 1
    assert seen == ["BAD", "SBER"]


def test_device_routes_require_authentication_and_contract_matches():
    from pathlib import Path

    import yaml
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        for method in ("put", "delete"):
            kwargs = {"json": {"token": "test-" * 8}} if method == "put" else {}
            response = getattr(client, method)(f"/api/v1/push/devices/{uuid4()}", **kwargs)
            assert response.status_code == 401
    contract = yaml.safe_load(
        (Path(__file__).resolve().parents[4] / "api/openapi/openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    runtime = app.openapi()["components"]["schemas"]["PushDeviceRequest"]
    static = contract["components"]["schemas"]["PushDeviceRequest"]
    assert runtime["required"] == static["required"]
    assert runtime["properties"]["token"]["pattern"] == static["properties"]["token"]["pattern"]
