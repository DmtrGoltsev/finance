"""Run with python -m app.delivery.worker; no web-server side effects."""

import json
import signal
import threading
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

from sqlalchemy import and_, exists, or_, select, text, update

from app.config import get_settings
from app.db.models import OutboxEvent
from app.db.models import Session as AuthSession
from app.db.session import sync_session_factory_for_settings
from app.delivery.models import PushDelivery, PushDevice
from app.delivery.transports import FcmTransport, InvalidToken, N8nTransport
from app.investments.instrument_resolver import is_valid_secid
from app.investments.models import (
    MoexInstrumentModel,
    PortfolioPositionModel,
    RecommendationJobModel,
)
from app.investments.moex_catalog import CatalogRefreshError, refresh_catalog

REQUESTED = "investment.recommendation.requested.v1"
READY = "investment.recommendation.ready.v1"


def claim(factory, *, lease_seconds=120, now=None):
    now = now or datetime.now(UTC)
    eligible = and_(
        OutboxEvent.event_type.in_((REQUESTED, READY)),
        or_(
            and_(OutboxEvent.status.in_(("pending", "failed")), OutboxEvent.available_at <= now),
            and_(OutboxEvent.status == "processing", OutboxEvent.lease_until <= now),
        ),
    )
    token = uuid4()
    with factory.begin() as session:
        candidate = (
            select(OutboxEvent.id)
            .where(eligible)
            .order_by(OutboxEvent.available_at, OutboxEvent.created_at, OutboxEvent.id)
            .limit(1)
        )
        if session.bind.dialect.name == "postgresql":
            candidate = candidate.with_for_update(skip_locked=True)
        # One conditional UPDATE is atomic also on SQLite (SELECT/INSERT is not).
        return session.scalar(
            update(OutboxEvent)
            .where(
                OutboxEvent.id == candidate.scalar_subquery(),
                eligible,
            )
            .values(
                status="processing",
                lease_token=token,
                lease_until=now + timedelta(seconds=lease_seconds),
                delivery_attempts=OutboxEvent.delivery_attempts + 1,
            )
            .returning(OutboxEvent)
        )


class Dispatcher:
    def __init__(self, factory, settings, n8n, fcm, stop=None):
        self.factory, self.settings, self.n8n, self.fcm = factory, settings, n8n, fcm
        self.metrics = Counter()
        self.last_tick = 0.0
        self.stop = stop or threading.Event()
        self.last_prune = 0.0

    def fence(self, session, event):
        now = datetime.now(UTC)
        return session.execute(
            update(OutboxEvent)
            .where(
                OutboxEvent.id == event.id,
                OutboxEvent.lease_token == event.lease_token,
                OutboxEvent.status == "processing",
                OutboxEvent.lease_until > now,
            )
            .values(lease_until=now + timedelta(seconds=self.settings.delivery_lease_seconds))
        ).rowcount

    def finish(self, event, success):
        now = datetime.now(UTC)
        with self.factory.begin() as session:
            if not self.fence(session, event):
                return
            status = (
                "processed"
                if success
                else (
                    "dead"
                    if event.delivery_attempts >= self.settings.delivery_max_attempts
                    else "failed"
                )
            )
            session.execute(
                update(OutboxEvent)
                .where(OutboxEvent.id == event.id)
                .values(
                    status=status,
                    lease_token=None,
                    lease_until=None,
                    processed_at=now if success else None,
                    available_at=now
                    + timedelta(seconds=min(3600, 5 * 2 ** min(event.delivery_attempts, 10))),
                )
            )
            if status == "dead" and event.event_type == REQUESTED:
                session.execute(
                    update(RecommendationJobModel)
                    .where(
                        RecommendationJobModel.id == event.aggregate_id,
                        RecommendationJobModel.owner_user_id == event.owner_user_id,
                        RecommendationJobModel.status == "queued",
                        RecommendationJobModel.attempt_count == event.attempt_count + 1,
                    )
                    .values(
                        status="failed",
                        last_error_code="delivery_failed",
                        completed_at=now,
                        updated_at=now,
                        version=RecommendationJobModel.version + 1,
                    )
                )
            self.metrics[status] += 1

    def push(self, event):
        now = datetime.now(UTC)
        with self.factory.begin() as session:
            if not self.fence(session, event):
                return False
            devices = session.scalars(
                select(PushDevice)
                .join(AuthSession, AuthSession.id == PushDevice.session_id)
                .where(
                    PushDevice.owner_user_id == event.owner_user_id,
                    PushDevice.revoked_at.is_(None),
                    PushDevice.token.is_not(None),
                    PushDevice.updated_at > now - timedelta(days=270),
                    AuthSession.status == "active",
                    AuthSession.expires_at > now,
                )
            ).all()
            for device in devices:
                if (
                    session.scalar(
                        select(PushDelivery.id).where(
                            PushDelivery.event_id == event.id,
                            PushDelivery.device_id == device.id,
                        )
                    )
                    is None
                ):
                    session.add(
                        PushDelivery(
                            event_id=event.id,
                            device_id=device.id,
                            session_id=device.session_id,
                            status="pending",
                        )
                    )
        with self.factory() as session:
            ids = list(
                session.scalars(
                    select(PushDelivery.id).where(
                        PushDelivery.event_id == event.id, PushDelivery.status == "pending"
                    )
                )
            )
        for delivery_id in ids:
            if self.stop.is_set():
                return False
            self.last_tick = time.monotonic()
            with self.factory.begin() as session:
                if not self.fence(session, event):
                    return False
                delivery = session.get(PushDelivery, delivery_id)
                # Lock registration across send so logout/token refresh cannot repurpose it.
                device = session.scalar(
                    select(PushDevice).where(PushDevice.id == delivery.device_id).with_for_update()
                )
                auth = session.get(AuthSession, delivery.session_id)
                current = datetime.now(UTC)

                def aware(value):
                    return value.replace(tzinfo=UTC) if value.tzinfo is None else value

                if (
                    device is None
                    or not device.token
                    or device.revoked_at
                    or device.owner_user_id != event.owner_user_id
                    or device.session_id != delivery.session_id
                    or auth is None
                    or auth.status != "active"
                    or aware(auth.expires_at) <= current
                    or aware(device.updated_at) <= current - timedelta(days=270)
                ):
                    delivery.status = "skipped"
                    continue
                try:
                    self.fcm.send(device.token, event, delivery.session_id)
                    delivery.status = "sent"
                except InvalidToken:
                    device.token, device.revoked_at = None, current
                    delivery.status = "invalid"
                    self.metrics["invalid_tokens"] += 1
        return True

    def tick(self):
        if time.monotonic() - self.last_prune > 300:
            now = datetime.now(UTC)
            with self.factory.begin() as session:
                active = exists(
                    select(AuthSession.id).where(
                        AuthSession.id == PushDevice.session_id,
                        AuthSession.user_id == PushDevice.owner_user_id,
                        AuthSession.status == "active",
                        AuthSession.expires_at > now,
                    )
                )
                count = session.execute(
                    update(PushDevice)
                    .where(
                        PushDevice.token.is_not(None),
                        or_(PushDevice.updated_at <= now - timedelta(days=270), ~active),
                    )
                    .values(token=None, revoked_at=now)
                ).rowcount
                self.metrics["expired_tokens"] += count
            self.last_prune = time.monotonic()
        event = claim(self.factory, lease_seconds=self.settings.delivery_lease_seconds)
        self.last_tick = time.monotonic()
        if event is None:
            return False
        self.metrics["claimed"] += 1
        try:
            if event.event_type == REQUESTED:
                self.n8n.send(event)
                success = True
            else:
                success = self.push(event)
        except Exception:
            # Never log transport exceptions: URLs, credentials and payloads can be embedded.
            self.metrics["delivery_errors"] += 1
            success = False
        self.finish(event, success)
        self.last_tick = time.monotonic()
        return True


def refresh_due_catalog(factory, *, seeds=(), stop=None, refresh=refresh_catalog, metrics=None):
    """PostgreSQL transaction advisory lock, one instrument per short transaction."""
    stop = stop or threading.Event()
    with factory() as session:
        identifiers = set(session.scalars(select(MoexInstrumentModel.secid)))
        identifiers.update(session.scalars(select(PortfolioPositionModel.ticker).distinct()))
    identifiers.update(seeds)
    count = 0
    for secid in sorted(s for s in identifiers if s and is_valid_secid(s)):
        if stop.is_set():
            break
        with factory.begin() as session:
            if session.bind.dialect.name == "postgresql":
                if not session.scalar(text("SELECT pg_try_advisory_xact_lock(624120924)")):
                    continue
            elif session.bind.dialect.name == "sqlite":
                session.execute(text("BEGIN IMMEDIATE"))
            existing = session.get(MoexInstrumentModel, secid)
            cutoff = datetime.now(UTC) - timedelta(hours=12)
            if existing:
                fetched = existing.fetched_at
                if (fetched.replace(tzinfo=UTC) if fetched.tzinfo is None else fetched) > cutoff:
                    continue
            try:
                refresh(session, [secid])
                count += 1
            except CatalogRefreshError:
                session.rollback()
                if metrics is not None:
                    metrics["catalog_errors"] += 1
    return count


def main():
    settings = get_settings()
    factory = sync_session_factory_for_settings(settings)
    stop = threading.Event()
    dispatcher = Dispatcher(factory, settings, N8nTransport(settings), FcmTransport(settings), stop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    class Health(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/healthz", "/metrics"):
                self.send_error(404)
                return
            healthy = time.monotonic() - dispatcher.last_tick < 90 and not stop.is_set()
            if self.path == "/metrics":
                data = "".join(
                    f"finance_delivery_{k} {v}\n" for k, v in dispatcher.metrics.copy().items()
                ).encode()
            else:
                data = json.dumps({"status": "ok" if healthy else "unavailable"}).encode()
            self.send_response(200 if healthy else 503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(
        (settings.delivery_health_host, settings.delivery_health_port), Health
    )
    http_thread = threading.Thread(target=server.serve_forever, daemon=True)
    http_thread.start()

    def catalog_loop():
        while not stop.is_set():
            try:
                count = refresh_due_catalog(
                    factory,
                    seeds=settings.moex_refresh_secids,
                    stop=stop,
                    metrics=dispatcher.metrics,
                )
                dispatcher.metrics["catalog_refreshed"] += count
            except Exception:
                dispatcher.metrics["catalog_errors"] += 1
            stop.wait(300)

    catalog_thread = threading.Thread(target=catalog_loop)
    catalog_thread.start()
    try:
        while not stop.is_set():
            try:
                worked = dispatcher.tick()
            except Exception:
                dispatcher.metrics["database_errors"] += 1
                worked = False
            if not worked:
                stop.wait(settings.delivery_poll_seconds)
    finally:
        stop.set()
        catalog_thread.join()
        server.shutdown()
        server.server_close()
        dispatcher.n8n.client.close()
        dispatcher.fcm.client.close()


if __name__ == "__main__":
    main()
